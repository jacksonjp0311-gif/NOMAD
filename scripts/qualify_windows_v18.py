"""Record read-only native environment checks and trusted Windows qualification.

Never installs software, enables Windows features, elevates, reboots, downloads
images, or runs unfamiliar repository code. All output paths are create-only.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def execute(argv: list[str], timeout: float = 15) -> dict:
    started = time.monotonic()
    try:
        observed = subprocess.run(argv, capture_output=True, timeout=timeout,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        raw = observed.stdout + observed.stderr
        encoding = 'utf-16-le' if b'\x00' in raw[:100] else 'utf-8'
        return {'command': argv[:1] + argv[1:3], 'returncode': observed.returncode,
                'elapsed_s': time.monotonic()-started,
                'output': raw.decode(encoding, errors='replace')}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'command': argv[:1] + argv[1:3], 'error': type(error).__name__,
                'elapsed_s': time.monotonic()-started}


def environment() -> dict:
    names = ('docker', 'wsl', 'podman', 'nerdctl', 'containerd', 'VBoxManage',
             'vmrun', 'qemu-system-x86_64', 'WindowsSandbox')
    report = {'platform': sys.platform, 'tools': {name: shutil.which(name) is not None for name in names}}
    if os.name != 'nt':
        report['windows_probe_status'] = 'HOLD: this qualification requires native Windows'
        return report
    command = r'''
$report=[ordered]@{}
$report.os=Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture
$report.machine=Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,HypervisorPresent,TotalPhysicalMemory
$report.cpu=Get-CimInstance Win32_Processor | Select-Object Name,VirtualizationFirmwareEnabled,SecondLevelAddressTranslationExtensions,VMMonitorModeExtensions
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
$report.elevated_administrator=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$report.optional_features=@(Get-CimInstance Win32_OptionalFeature | Where-Object {$_.Name -match 'VirtualMachinePlatform|Microsoft-Windows-Subsystem-Linux|Hyper-V|HypervisorPlatform|Containers-DisposableClientVM'} | Select-Object Name,InstallState)
$report.services=@(Get-Service -Name '*docker*','*vmcompute*','*Lxss*','*Wsl*' -ErrorAction SilentlyContinue | Select-Object Name,@{N='Status';E={$_.Status.ToString()}},@{N='StartType';E={$_.StartType.ToString()}})
$report.standard_install_files=@(@('C:\Program Files\Docker\Docker\resources\bin\docker.exe','C:\Program Files\Docker\Docker\Docker Desktop.exe','C:\Windows\System32\WindowsSandbox.exe',(Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),(Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe')) | ForEach-Object {[pscustomobject]@{Path=$_;Exists=(Test-Path -LiteralPath $_)}})
$report.registered_backends=@(Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object DisplayName -match 'Docker|Rancher|Podman|VirtualBox|VMware|Windows Subsystem for Linux' | Select-Object DisplayName,DisplayVersion,InstallLocation)
$report | ConvertTo-Json -Depth 6 -Compress
'''
    cim = execute(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command])
    try:
        report['native_cim'] = json.loads(cim['output']) if cim.get('returncode') == 0 else cim
    except (ValueError, KeyError):
        report['native_cim'] = cim
    report['wsl_status'] = execute(['wsl', '--status'])
    report['wsl_distributions'] = execute(['wsl', '--list', '--verbose'])
    report['privileges'] = execute(['whoami', '/priv'])
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    api.WaitNamedPipeW.restype = wintypes.BOOL
    pipes = []
    for name in ('dockerDesktopLinuxEngine', 'docker_engine'):
        available = bool(api.WaitNamedPipeW('\\\\.\\pipe\\' + name, 0))
        pipes.append({'name': name, 'available': available,
                      'winerror': 0 if available else ctypes.get_last_error()})
    report['docker_named_pipes'] = pipes
    return report


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)

    def addSuccess(self, test):
        self.cases.append({'test': test.id(), 'status': 'PASS', 'elapsed_s': time.monotonic()-self.started})
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.cases.append({'test': test.id(), 'status': 'FAIL', 'elapsed_s': time.monotonic()-self.started})
        super().addFailure(test, err)

    def addError(self, test, err):
        self.cases.append({'test': test.id(), 'status': 'ERROR', 'elapsed_s': time.monotonic()-self.started})
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.cases.append({'test': test.id(), 'status': 'HOLD', 'reason': reason})
        super().addSkip(test, reason)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.cases.append({'test': subtest.id(),
                               'status': 'FAIL' if issubclass(err[0], test.failureException) else 'ERROR',
                               'elapsed_s': time.monotonic()-self.started})
        super().addSubTest(test, subtest, err)


def source_identity() -> dict:
    names = ('nomad/windows_job.py', 'nomad/supervised.py', 'nomad/isolation.py',
             'nomad/archive_guard.py', 'tests/test_native_qualification_v18.py',
             'tests/test_platform_isolation_v18.py', 'scripts/qualify_windows_v18.py',
             'scripts/qualify_isolation_v18.py')
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.log.exists() or args.output.resolve() == args.log.resolve():
        parser.error('use distinct new output and log paths; existing evidence is never replaced')
    before = source_identity()
    report = {'schema': 'nomad.windows-native-qualification.v18',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'environment': environment(), 'source_sha256_before': before,
              'native_containment_gate': 'HOLD', 'strict_peak_counter_gate': 'HOLD',
              'scope': 'controlled trusted Windows supervision; no Docker or VM qualification',
              'cloud_model_calls': 0}
    from tests import test_native_qualification_v18 as native
    from tests.test_platform_isolation_v18 import NativeWindowsSupervisionTests
    native.OBSERVATIONS.clear()
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(NativeWindowsSupervisionTests),
        unittest.defaultTestLoader.loadTestsFromModule(native)])
    stream = io.StringIO()
    started = time.monotonic()
    results = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordingResult).run(suite)
    report.update({'elapsed_s': time.monotonic()-started, 'tests_run': results.testsRun,
                   'failures': len(results.failures), 'errors': len(results.errors),
                   'skipped': len(results.skipped), 'cases': results.cases,
                   'observations': native.OBSERVATIONS, 'source_sha256_after': source_identity()})
    report['source_stable'] = before == report['source_sha256_after']
    report['trusted_windows_supervision_gate'] = ('PASS' if results.wasSuccessful()
                and not results.skipped and report['source_stable'] else 'HOLD' if results.wasSuccessful() else 'FAIL')
    report['limitations'] = [
        'Windows Job supervision is not a hostile-code filesystem/network boundary.',
        'No Docker/VM case ran in this Windows-only script.',
        'Native peak counters exceeded the configured limit in retained initial experiments; counter semantics remain HOLD.',
        'Direct allocation refusal and before/after private-commit measurements do not establish an atomic historical job-wide peak.',
        'Process-death tests do not establish hard-power-loss durability.']
    for path in (args.output, args.log):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write('\n')
    with args.log.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(stream.getvalue())
    print(json.dumps({key: report[key] for key in ('trusted_windows_supervision_gate',
          'native_containment_gate', 'strict_peak_counter_gate', 'tests_run', 'failures',
          'errors', 'skipped', 'elapsed_s', 'source_stable')}, indent=2))
    return 0 if report['trusted_windows_supervision_gate'] == 'PASS' else 3


if __name__ == '__main__':
    raise SystemExit(main())
