"""Local platform diagnostics. Tool presence is never containment qualification."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform as host_platform
import shutil
import sys
import tempfile

from .isolation import SandboxPolicy, docker_preflight
from .supervised import minimal_env, run_supervised

CONFIG_SCHEMA = 'nomad.platform.config.v1'


def load_policy(path: Path | None = None, image: str | None = None) -> SandboxPolicy | None:
    settings = {}
    if path is not None:
        if path.stat().st_size > 16384:
            raise ValueError('configuration exceeds size budget')
        data = json.loads(path.read_text(encoding='utf-8'))
        allowed = {'schema', 'image', 'timeout_s', 'memory_mib', 'cpus', 'pids_limit',
                   'max_files', 'max_total_bytes'}
        if not isinstance(data, dict) or set(data) - allowed or data.get('schema') != CONFIG_SCHEMA:
            raise ValueError('unrecognized platform configuration')
        settings = {k: v for k, v in data.items() if k != 'schema'}
    if image is not None:
        settings['image'] = image
    if settings.get('image') is None:
        if set(settings) - {'image'}:
            raise ValueError('resource configuration requires a digest-pinned image')
        return None
    policy = SandboxPolicy(**settings)
    policy.validate()
    return policy


def _text(raw: bytes) -> str:
    # WSL emits UTF-16LE even when its stdout is a redirected pipe.
    encoding = 'utf-16-le' if b'\x00' in raw[:100] else 'utf-8'
    return raw.decode(encoding, errors='replace').strip()


def probe(argv: list[str], cwd: Path) -> dict:
    binary = shutil.which(argv[0])
    if binary is None:
        return {'available': False, 'status': 'HOLD', 'reason': 'binary absent'}
    try:
        result = run_supervised([binary, *argv[1:]], cwd=cwd, timeout_s=15,
                                env=minimal_env(), max_output_bytes=16384)
        return {'available': True, 'returncode': result.returncode,
                'status': 'PASS' if result.returncode == 0 and not result.timed_out else 'HOLD',
                'output': _text(result.output), 'elapsed_ms': result.elapsed_ms,
                'timed_out': result.timed_out, 'cleanup': result.cleanup}
    except (OSError, RuntimeError) as error:
        return {'available': True, 'status': 'HOLD', 'reason': str(error)}


def doctor(policy: SandboxPolicy | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix='nomad-doctor-') as directory:
        cwd = Path(directory)
        versions = {name: probe(args, cwd) for name, args in {
            'python': [sys.executable, '--version'], 'node': ['node', '--version'],
            'rustc': ['rustc', '--version'], 'cargo': ['cargo', '--version'],
            'git': ['git', '--version'], 'docker': ['docker', 'version', '--format', '{{json .Server}}'],
        }.items()}
        windows = {}
        if os.name == 'nt':
            windows['wsl'] = probe(['wsl', '--status'], cwd)
            windows['hardware'] = probe(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                "$c=Get-CimInstance Win32_ComputerSystem; $p=Get-CimInstance Win32_Processor; "
                "$o=Get-CimInstance Win32_OperatingSystem; "
                "[pscustomobject]@{manufacturer=$c.Manufacturer;model=$c.Model;"
                "memory_bytes=$c.TotalPhysicalMemory;hypervisor_present=$c.HypervisorPresent;"
                "cpu=$p.Name;virtualization_firmware=$p.VirtualizationFirmwareEnabled;"
                "os=$o.Caption;build=$o.BuildNumber}|ConvertTo-Json -Compress"], cwd)
            windows['features'] = probe(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                "$ErrorActionPreference='Stop'; try { @('VirtualMachinePlatform',"
                "'Microsoft-Windows-Subsystem-Linux','Microsoft-Hyper-V-All',"
                "'Containers-DisposableClientVM') | ForEach-Object { "
                "Get-WindowsOptionalFeature -Online -FeatureName $_ | "
                "Select-Object FeatureName,State } | ConvertTo-Json -Compress } "
                "catch { Write-Output $_.Exception.Message; exit 3 }"], cwd)
        image = None
        if policy is not None:
            image = docker_preflight(policy)
    return {'schema': 'nomad.platform.doctor.v1', 'version': '0.18.0',
            'observed_at_utc': datetime.now(timezone.utc).isoformat(),
            'platform': host_platform.platform(), 'tools': versions, 'windows': windows,
            'policy': asdict(policy) if policy else None, 'local_image': image,
            'untrusted_host_fallback': False, 'native_containment': 'HOLD',
            'ready_for_untrusted_code': False,
            'reason': 'Run the native qualification suite with a reviewed local image; diagnostics grant no execution authority.'}


def runtime_smoke() -> dict:
    """Only generated, reviewed programs execute on host. Never accepts user source."""
    from .genesis import IOExample
    from .transcend import run_native
    import time
    results = {}
    rows = tuple(IOExample(x, y, x * x + y) for x, y in ((2, 3), (-4, 7), (0, -1)))
    for language in ('python', 'javascript', 'rust'):
        started = time.perf_counter()
        try:
            result = run_native(language, 'x*x+y', rows, timeout=30)
            results[language] = {**asdict(result),
                'status': 'PASS' if result.status == 'passed' else 'HOLD',
                'native_status': result.status, 'elapsed_s': time.perf_counter() - started,
                'expected': [row.expected for row in rows]}
        except (ValueError, ImportError, OSError) as error:
            results[language] = {'status': 'HOLD', 'reason': str(error)}
    return {'schema': 'nomad.platform.runtime-smoke.v1', 'languages': results,
            'scope': 'generated trusted arithmetic programs; not hostile-code containment'}
