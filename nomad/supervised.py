"""Bounded process supervision for *trusted* fixtures and sandbox CLI invocations.

Not a sandbox: Python subprocesses retain their OS authority. Unfamiliar repository
code must go through nomad.isolation, never this module directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
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
    # CREATE_NEW_PROCESS_GROUP alone cannot guarantee descendant termination on Windows.
    # taskkill is a defense in depth for *trusted* fixtures, not a job-object sandbox.
    try:
        done = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                              capture_output=True, timeout=4, check=False)
        return 'windows-taskkill-'+str(done.returncode)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            return 'windows-parent-killed-only'
        except OSError:
            return 'windows-cleanup-unconfirmed'


def run_supervised(argv: Sequence[str], *, cwd: Path, timeout_s: float,
                   env: Mapping[str, str] | None = None, max_output_bytes: int = 1_048_576,
                   discard_output: bool = False) -> ProcessResult:
    if not argv or not all(isinstance(v, str) and v and '\x00' not in v for v in argv):
        raise ValueError('command must be a nonempty argument vector')
    if timeout_s <= 0 or timeout_s > 120 or not (0 <= max_output_bytes <= 4_194_304):
        raise ValueError('execution limits outside bounded range')
    if not cwd.is_dir():
        raise ValueError('execution cwd must exist')
    started = time.monotonic()
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    process = subprocess.Popen(list(argv), cwd=str(cwd), env=dict(env or minimal_env()),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, shell=False,
                               creationflags=flags, start_new_session=os.name == 'posix')
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
    try:
        try:
            process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        # Always kill orphaned descendants in the original process group, even if
        # the original process exits quickly and leaves a child behind.
        cleanup = _terminate_tree(process)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        collector.join(timeout=4)
        if collector.is_alive():
            try:
                process.stdout.close()
            except OSError:
                pass
            collector.join(timeout=1)
            cleanup += ';output-drain-unconfirmed'
        try:
            process.stdout.close()
        except OSError:
            pass
    return ProcessResult(124 if timed_out else int(process.returncode), bytes(saved),
                         digest.hexdigest(), timed_out, truncated[0], total[0],
                         int((time.monotonic()-started)*1000), cleanup)
