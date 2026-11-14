"""NOMAD v0.17: fail-closed container execution for unfamiliar repositories.

A Docker daemon with a trusted digest-pinned image and effective kernel isolation
is REQUIRED. A host Python subprocess is NEVER a fallback for untrusted code.

The container sees ONLY a read-only, filtered, disposable source snapshot.
Mission journals, WITNESS holdouts, credentials, host project roots and Docker
socket are never mounted. Passing tests is not independent acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Sequence
import json
import os
import re
import shutil
import stat
import tempfile
import uuid

from .supervised import minimal_env, run_supervised

IMAGE_RE = re.compile(r'^[A-Za-z0-9_./:-]+@sha256:[0-9a-f]{64}$')
VALID_BINARIES = frozenset(('python', 'python3', 'node', 'cargo', 'pytest', 'npm'))
DENIED_SEGMENTS = frozenset(('.git', '.ssh', '.aws', '.gnupg', '.venv', 'node_modules',
                             '__pycache__', '.pytest_cache'))
DENIED_FILES = frozenset(('.env', '.npmrc', '.pypirc', 'id_rsa', 'id_ed25519',
                           'credentials.json', 'token.json', '.netrc'))


class IsolationUnavailable(RuntimeError):
    pass


class UnsafeWorkspace(ValueError):
    pass


@dataclass(frozen=True)
class SandboxPolicy:
    image: str
    timeout_s: float = 20.0
    memory_mib: int = 256
    cpus: float = 1.0
    pids_limit: int = 48
    max_files: int = 3000
    max_total_bytes: int = 30_000_000

    def validate(self) -> None:
        if not isinstance(self.image, str) or not IMAGE_RE.fullmatch(self.image):
            raise ValueError('sandbox image must be a trusted, digest-pinned reference')
        if not (1 <= self.timeout_s <= 120 and 64 <= self.memory_mib <= 4096
                and 0.1 <= self.cpus <= 4 and 8 <= self.pids_limit <= 256
                and 1 <= self.max_files <= 20000
                and 1024 <= self.max_total_bytes <= 200_000_000):
            raise ValueError('sandbox resource budget invalid')


@dataclass(frozen=True)
class Snapshot:
    root: Path
    digest: str
    files: int
    bytes: int


def _input_paths(source: Path, *, policy: SandboxPolicy):
    if source.is_symlink() or not source.is_dir():
        raise UnsafeWorkspace('source must be an actual directory, never a symlink')
    files: list[tuple[Path, Path, os.stat_result]] = []
    total = 0
    for path in sorted(source.rglob('*')):
        rel = path.relative_to(source)
        if len(rel.parts) > 32 or any(part in DENIED_SEGMENTS for part in rel.parts):
            raise UnsafeWorkspace('unsafe or overly deep source path: '+str(rel))
        if path.name in DENIED_FILES or path.suffix in ('.pem', '.key'):
            raise UnsafeWorkspace('credential-like file refused: '+str(rel))
        m = path.lstat()
        if stat.S_ISLNK(m.st_mode):
            raise UnsafeWorkspace('symlink refused: '+str(rel))
        if stat.S_ISDIR(m.st_mode):
            continue
        if not stat.S_ISREG(m.st_mode) or m.st_nlink != 1:
            raise UnsafeWorkspace('nonregular or multiply linked file refused: '+str(rel))
        total += m.st_size
        files.append((path, rel, m))
        if len(files) > policy.max_files or total > policy.max_total_bytes:
            raise UnsafeWorkspace('source exceeds bounded snapshot budget')
    if not files:
        raise UnsafeWorkspace('empty repository')
    return files


def snapshot_source(source: Path, destination: Path, policy: SandboxPolicy) -> Snapshot:
    """Snapshot without following symlinks; reject dangerous entries rather than skip silently.

    The caller owns the disposable destination. This prevents the container from
    ever mounting the original source or NOMAD's evidence directories.
    """
    policy.validate()
    source = Path(source)
    destination = Path(destination)
    if destination.exists():
        raise UnsafeWorkspace('snapshot destination already exists')
    paths = _input_paths(source, policy=policy)
    destination.mkdir(parents=True, exist_ok=False)
    entries = []
    for path, rel, old in paths:
        dest = destination / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(path, flags), 'rb') as f:
            now = os.fstat(f.fileno())
            if not stat.S_ISREG(now.st_mode) or (now.st_ino, now.st_dev, now.st_size,
                                                now.st_mtime_ns) != (
                    old.st_ino, old.st_dev, old.st_size, old.st_mtime_ns):
                raise UnsafeWorkspace('source changed while taking snapshot')
            h = sha256()
            with dest.open('xb') as out:
                while block := f.read(65536):
                    h.update(block)
                    out.write(block)
            os.chmod(dest, 0o444)
        entries.append([rel.as_posix(), h.hexdigest(), old.st_size])
    return Snapshot(destination, sha256(json.dumps(entries, separators=(',', ':'),
                                  ensure_ascii=True).encode()).hexdigest(),
                    len(entries), sum(e[2] for e in entries))


def docker_arguments(*, engine: str, snapshot: Path, image: str, name: str,
                     command: Sequence[str], policy: SandboxPolicy) -> list[str]:
    policy.validate()
    if not command or command[0] not in VALID_BINARIES:
        raise ValueError('unsupported container entrypoint')
    if any(not isinstance(p, str) or not p or '\x00' in p for p in command):
        raise ValueError('invalid container argument')
    if not re.fullmatch(r'nomad-[a-f0-9]{24}', name):
        raise ValueError('invalid disposable container name')
    if not snapshot.is_dir():
        raise ValueError('disposable snapshot missing')
    # The only bind is the disposable source copy, read-only. No host root,
    # credentials, repository journal, Docker socket or WITNESS holdout is mounted.
    return [engine, 'run', '--rm', '--pull=never', '--name', name,
            '--network=none', '--ipc=none', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges=true', '--user=65534:65534',
            '--pids-limit', str(policy.pids_limit),
            '--memory', str(policy.memory_mib)+'m', '--memory-swap', str(policy.memory_mib)+'m',
            '--cpus', str(policy.cpus), '--ulimit', 'nofile=64:64',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m,mode=1777',
            '--mount', f'type=bind,src={snapshot},dst=/work,readonly',
            '--workdir', '/work', '-e', 'PYTHONDONTWRITEBYTECODE=1',
            '-e', 'PYTHONPATH=/work', '-e', 'HOME=/tmp',
            image, *command]


def sandbox_available(engine: str = 'docker') -> bool:
    """Binary presence, not a guarantee that daemon or containment works."""
    return shutil.which(engine) is not None


def _cleanup_container(engine: str, name: str, *, cwd: Path) -> bool:
    """Never claim cleanup solely because the Docker client exited."""
    # `--rm` may already have deleted the container; inspect distinguishes it
    # from a still-running instance. Any daemon error beyond missing-object HOLDs.
    check = run_supervised([engine, 'container', 'inspect', name], cwd=cwd,
                           timeout_s=5, env=minimal_env(), max_output_bytes=2048)
    if check.returncode == 0:
        run_supervised([engine, 'rm', '-f', '--volumes', name], cwd=cwd,
                       timeout_s=5, env=minimal_env(), max_output_bytes=2048)
        check = run_supervised([engine, 'container', 'inspect', name], cwd=cwd,
                               timeout_s=5, env=minimal_env(), max_output_bytes=2048)
    # Docker English diagnostic is intentionally narrow. If a daemon cannot
    # confirm the object disappeared, do not accept a passing test outcome.
    out = check.output.decode('utf-8', errors='replace').lower()
    return check.returncode != 0 and ('no such object' in out or 'no such container' in out)


def run_isolated(source: Path, *, command: Sequence[str], policy: SandboxPolicy,
                 engine: str = 'docker') -> dict:
    policy.validate()
    if engine != 'docker':
        raise IsolationUnavailable('unsupported isolation backend; no host fallback')
    if not sandbox_available(engine):
        raise IsolationUnavailable('Docker binary unavailable; untrusted execution DENIED')
    with tempfile.TemporaryDirectory(prefix='nomad-isolated-source-') as td:
        snapshot = snapshot_source(Path(source), Path(td)/'source', policy)
        name = 'nomad-'+uuid.uuid4().hex[:24]
        argv = docker_arguments(engine=engine, snapshot=snapshot.root, image=policy.image,
                                name=name, command=command, policy=policy)
        result = None
        cleanup_confirmed = False
        try:
            result = run_supervised(argv, cwd=Path(td), timeout_s=policy.timeout_s,
                                    env=minimal_env(), max_output_bytes=8192)
        finally:
            cleanup_confirmed = _cleanup_container(engine, name, cwd=Path(td))
        if not cleanup_confirmed or 'unconfirmed' in result.cleanup:
            raise IsolationUnavailable('container cleanup unconfirmed; HOLD outcome')
        return {
            'schema': 'nomad.isolated-test.v1',
            'snapshot_sha256': snapshot.digest, 'source_files':snapshot.files,
            'source_bytes':snapshot.bytes, 'image_digest':policy.image.split('@sha256:')[-1],
            'command': list(command), 'returncode': result.returncode,
            'tests_passed': result.returncode == 0 and not result.timed_out,
            'timed_out': result.timed_out, 'elapsed_ms': result.elapsed_ms,
            'output_sha256': result.output_sha256,
            'output_truncated': result.truncated,
            'container_cleanup_confirmed': cleanup_confirmed,
            'authority': 'test execution only; independent WITNESS still required',
        }
