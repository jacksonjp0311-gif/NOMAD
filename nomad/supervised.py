"""Bounded process supervision for *trusted* fixtures and sandbox CLI invocations.

Not a sandbox: Python subprocesses retain their OS authority. Unfamiliar repository
code must go through nomad.isolation, never this module directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import math
import signal
import subprocess
import threading
import time
from typing import Mapping, Sequence

_ALLOWED_ENV = (
    'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR',
    'HOME', 'USERPROFILE', 'LANG', 'LC_ALL', 'LC_CTYPE',
)


def minimal_env(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """Do not propagate host credentials, access tokens or Python injection hooks."""
    result = {key: os.environ[key] for key in _ALLOWED_ENV if key in os.environ}
    result['PYTHONDONTWRITEBYTECODE'] = '1'
    result['PYTHONNOUSERSITE'] = '1'
    for key, value in (overrides or {}).items():
        if key not in {'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE', 'HOME', 'TMPDIR'}:
            raise ValueError('unapproved child environment override: ' + key)
        if not isinstance(value, str) or '\x00' in value:
            raise ValueError('invalid child environment value')
        result[key] = value
    return result


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    output: bytes
    output_sha256: str
    timed_out: bool
    truncated: bool
    total_output_bytes: int
    elapsed_ms: int
    cleanup: str
    metrics: dict | None = None


def _terminate_tree(process: subprocess.Popen) -> str:
    """Best-effort host process-tree termination; only an isolation engine is a security boundary."""
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return 'posix-process-group-killed'
        except ProcessLookupError:
            return 'posix-process-group-exited'
        except PermissionError:
            return 'posix-process-group-kill-denied'
    # Windows callers must own a Job; there is no taskkill/parent-only fallback.
    return 'windows-job-missing-cleanup-unconfirmed'


def run_supervised(argv: Sequence[str], *, cwd: Path, timeout_s: float,
                   env: Mapping[str, str] | None = None, max_output_bytes: int = 1_048_576,
                   discard_output: bool = False, windows_memory_mib: int = 1024,
                   windows_max_processes: int = 64) -> ProcessResult:
    if isinstance(argv, (str, bytes)) or not argv or not all(isinstance(v, str) and v and '\x00' not in v for v in argv):
        raise ValueError('command must be a nonempty argument vector')
    if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
            or not 0 < timeout_s <= 120 or type(max_output_bytes) is not int
            or not 0 <= max_output_bytes <= 4_194_304):
        raise ValueError('execution limits outside bounded range')
    if os.name != 'nt' and (windows_memory_mib != 1024 or windows_max_processes != 64):
        raise ValueError('Windows Job budgets cannot be enforced on this platform')
    if not cwd.is_dir():
        raise ValueError('execution cwd must exist')
    started = time.monotonic()
    job = None
    child_env = minimal_env() if env is None else dict(env)
    if os.name == 'nt':
        from .windows_job import launch_in_job
        process, job = launch_in_job(argv, cwd=cwd, env=child_env,
                                     memory_mib=windows_memory_mib, max_processes=windows_max_processes)
    else:
        process = subprocess.Popen(list(argv), cwd=str(cwd), env=child_env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, shell=False,
                                   start_new_session=True)
    assert process.stdout is not None
    digest = sha256()
    saved = bytearray()
    total = [0]
    truncated = [False]

    def drain() -> None:
        while True:
            data = process.stdout.read(65536)
            if not data:
                break
            digest.update(data)
            total[0] += len(data)
            n = max_output_bytes - len(saved) if not discard_output else 0
            if n > 0:
                saved.extend(data[:n])
            if total[0] > max_output_bytes or discard_output:
                truncated[0] = True

    collector = threading.Thread(target=drain, daemon=True, name='nomad-output-collector')
    collector.start()
    timed_out = False
    cleanup = 'not-required'
    metrics = None
    try:
        try:
            process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        # Always kill orphaned descendants in the original process group, even if
        # the original process exits quickly and leaves a child behind.
        cleanup = job.terminate() if job is not None else _terminate_tree(process)
        if job is not None:
            metrics = job.metrics()
            job.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        collector.join(timeout=4)
        if collector.is_alive():
            # BufferedReader.close can block forever while another thread reads.
            # Never turn an unconfirmed cleanup into an unbounded supervisor wait.
            cleanup += ';output-drain-unconfirmed'
        else:
            try:
                process.stdout.close()
            except OSError:
                pass
    return ProcessResult(124 if timed_out else int(process.returncode), bytes(saved),
                         digest.hexdigest(), timed_out, truncated[0], total[0],
                         int((time.monotonic()-started)*1000), cleanup, metrics)
