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
import math
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
        if not (math.isfinite(self.timeout_s) and math.isfinite(self.cpus)
                and 1 <= self.timeout_s <= 120 and 64 <= self.memory_mib <= 4096
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


def validate_source_name(name: str) -> None:
    """Use portable Windows-safe names, including on POSIX before packaging."""
    folded = name.casefold()
    stem = folded.split('.')[0]
    reserved = {'con', 'prn', 'aux', 'nul', 'clock$'} | {
        prefix + n for prefix in ('com', 'lpt') for n in '123456789\u00b9\u00b2\u00b3'}
    if (not name or name in ('.', '..') or name[-1] in ' .'
            or any(ord(c) < 32 or c in '<>:"\\|?*' for c in name)
            or stem in reserved):
        raise UnsafeWorkspace('unsafe portable source name: ' + name)


def _reparse(metadata: os.stat_result) -> bool:
    return bool(getattr(metadata, 'st_file_attributes', 0) & 0x400)


def _input_paths(source: Path, *, policy: SandboxPolicy):
    root_stat = source.lstat()
    if stat.S_ISLNK(root_stat.st_mode) or _reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
        raise UnsafeWorkspace('source must be an actual directory, never a link/reparse point')
    files: list[tuple[Path, Path, os.stat_result]] = []
    total = 0
    paths = []
    pending = [(source, root_stat)]
    # Bounded scandir avoids following junctions or first expanding an unbounded rglob.
    while pending:
        directory, expected = pending.pop()
        current = directory.lstat()
        if (_reparse(current) or not stat.S_ISDIR(current.st_mode)
                or (current.st_ino, current.st_dev) != (expected.st_ino, expected.st_dev)):
            raise UnsafeWorkspace('source directory changed before traversal')
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                rel = path.relative_to(source)
                if len(paths) >= policy.max_files * 2 or len(rel.parts) > 32:
                    raise UnsafeWorkspace('source directory traversal exceeds budget')
                validate_source_name(path.name)
                # DirEntry.stat on Windows caches directory-enumeration metadata
                # whose inode/link count can be zero; lstat obtains file identity.
                metadata = path.lstat()
                if stat.S_ISLNK(metadata.st_mode) or _reparse(metadata):
                    raise UnsafeWorkspace('link/reparse point refused: ' + str(rel))
                paths.append((path, metadata))
                if stat.S_ISDIR(metadata.st_mode):
                    pending.append((path, metadata))
        after_scan = directory.lstat()
        if (_reparse(after_scan) or (after_scan.st_ino, after_scan.st_dev) !=
                (expected.st_ino, expected.st_dev)):
            raise UnsafeWorkspace('source directory changed during traversal')
    seen = set()
    for path, m in sorted(paths, key=lambda row: row[0].as_posix()):
        rel = path.relative_to(source)
        identity = rel.as_posix().casefold()
        if identity in seen:
            raise UnsafeWorkspace('case-colliding source path: ' + str(rel))
        seen.add(identity)
        if any(part.casefold() in DENIED_SEGMENTS for part in rel.parts):
            raise UnsafeWorkspace('unsafe or overly deep source path: '+str(rel))
        if (path.name.casefold() in DENIED_FILES or path.name.casefold().startswith('.env.')
                or path.suffix.casefold() in ('.pem', '.key')):
            raise UnsafeWorkspace('credential-like file refused: '+str(rel))
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
    if source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents:
        raise UnsafeWorkspace('snapshot destination must be outside source')
    paths = _input_paths(source, policy=policy)
    destination.mkdir(parents=True, exist_ok=False)
    entries = []
    for path, rel, old in paths:
        for parent in (path.parent, *path.parent.parents):
            if parent == source.parent:
                break
            metadata = parent.lstat()
            if _reparse(metadata) or not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                raise UnsafeWorkspace('source parent changed to link/reparse point')
        dest = destination / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(path, flags), 'rb') as f:
            now = os.fstat(f.fileno())
            if not stat.S_ISREG(now.st_mode) or now.st_nlink != 1 or (now.st_ino, now.st_dev, now.st_size,
                                                now.st_mtime_ns) != (
                    old.st_ino, old.st_dev, old.st_size, old.st_mtime_ns):
                raise UnsafeWorkspace('source changed while taking snapshot')
            h = sha256()
            copied = 0
            with dest.open('xb') as out:
                while block := f.read(65536):
                    copied += len(block)
                    if copied > old.st_size:
                        raise UnsafeWorkspace('source grew while taking snapshot')
                    h.update(block)
                    out.write(block)
            after = os.fstat(f.fileno())
            if copied != old.st_size or (after.st_size, after.st_mtime_ns, after.st_ctime_ns,
                                        after.st_nlink) != (now.st_size, now.st_mtime_ns,
                                                          now.st_ctime_ns, now.st_nlink):
                raise UnsafeWorkspace('source changed during snapshot read')
            # Docker enforces readonly. NTFS readonly attributes obstruct safe cleanup.
            if os.name != 'nt':
                os.chmod(dest, 0o444)
        entries.append([rel.as_posix(), h.hexdigest(), old.st_size])
    return Snapshot(destination, sha256(json.dumps(entries, separators=(',', ':'),
                                  ensure_ascii=True).encode()).hexdigest(),
                    len(entries), sum(e[2] for e in entries))


def docker_arguments(*, engine: str, snapshot: Path, image: str, name: str,
                     command: Sequence[str], policy: SandboxPolicy) -> list[str]:
    policy.validate()
    if image != policy.image:
        raise ValueError('image must match the validated policy')
    if not command or command[0] not in VALID_BINARIES:
        raise ValueError('unsupported container entrypoint')
    if any(not isinstance(p, str) or not p or '\x00' in p for p in command):
        raise ValueError('invalid container argument')
    if not re.fullmatch(r'nomad-[a-f0-9]{24}', name):
        raise ValueError('invalid disposable container name')
    if not snapshot.is_dir():
        raise ValueError('disposable snapshot missing')
    if any(c in str(snapshot) for c in ',"\r\n'):
        raise ValueError('snapshot path cannot be represented safely as a Docker mount')
    # The only bind is the disposable source copy, read-only. No host root,
    # credentials, repository journal, Docker socket or WITNESS holdout is mounted.
    return [engine, 'run', '--rm', '--pull=never', '--name', name,
            '--label', 'nomad.managed=v0.18', '--label', 'nomad.execution=' + name,
            '--network=none', '--ipc=none', '--read-only', '--cap-drop=ALL',
            '--cgroupns=private', '--no-healthcheck', '--restart=no',
            '--security-opt=no-new-privileges=true', '--user=65534:65534',
            '--pids-limit', str(policy.pids_limit),
            '--memory', str(policy.memory_mib)+'m', '--memory-swap', str(policy.memory_mib)+'m',
            '--cpus', str(policy.cpus), '--ulimit', 'nofile=64:64',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m,mode=1777',
            '--mount', f'type=bind,src={snapshot},dst=/work,readonly',
            '--workdir', '/work', '-e', 'PYTHONDONTWRITEBYTECODE=1',
            '-e', 'PYTHONPATH=/work', '-e', 'HOME=/tmp',
            '--entrypoint', command[0], image, *command[1:]]


def sandbox_available(engine: str = 'docker') -> bool:
    """Binary presence, not a guarantee that daemon or containment works."""
    return shutil.which(engine) is not None


def _docker_prefix(engine: str, cwd: Path) -> list[str]:
    # A fresh config prevents user contexts, credential helpers and CLI plugins
    # from selecting a remote daemon or inheriting registry credentials.
    config = cwd / 'docker-config'
    config.mkdir(exist_ok=True)
    endpoint = ('npipe:////./pipe/dockerDesktopLinuxEngine' if os.name == 'nt'
                else 'unix:///var/run/docker.sock')
    return [engine, '--config', str(config), '--host', endpoint]


def _cleanup_container(engine: str, name: str, *, cwd: Path) -> bool:
    """Never claim cleanup solely because the Docker client exited."""
    # `--rm` may already have deleted the container; inspect distinguishes it
    # from a still-running instance. Any daemon error beyond missing-object HOLDs.
    prefix = _docker_prefix(engine, cwd)
    check = run_supervised([*prefix, 'container', 'inspect', name], cwd=cwd,
                           timeout_s=5, env=minimal_env(), max_output_bytes=262144)
    if check.returncode == 0:
        # A name collision must not authorize deleting somebody else's container.
        try:
            metadata = json.loads(check.output)
            labels = metadata[0]['Config']['Labels']
            container_id = metadata[0]['Id']
            if (check.timed_out or check.truncated or 'unconfirmed' in check.cleanup
                    or len(metadata) != 1 or labels.get('nomad.managed') != 'v0.18'
                    or labels.get('nomad.execution') != name
                    or not isinstance(container_id, str) or not re.fullmatch(r'[a-f0-9]{64}', container_id)):
                return False
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            return False
        run_supervised([*prefix, 'rm', '-f', '--volumes', container_id], cwd=cwd,
                       timeout_s=5, env=minimal_env(), max_output_bytes=2048)
        check = run_supervised([*prefix, 'container', 'inspect', name], cwd=cwd,
                               timeout_s=5, env=minimal_env(), max_output_bytes=2048)
    # Docker English diagnostic is intentionally narrow. If a daemon cannot
    # confirm the object disappeared, do not accept a passing test outcome.
    out = check.output.decode('utf-8', errors='replace').lower()
    return (check.returncode != 0 and not check.timed_out and 'unconfirmed' not in check.cleanup
            and ('no such object' in out or 'no such container' in out))


def cleanup_isolated(container_name: str, *, engine: str = 'docker') -> bool:
    """Reconcile only the caller's recorded NOMAD container, never bulk-prune."""
    if not re.fullmatch(r'nomad-[a-f0-9]{24}', container_name) or engine != 'docker':
        raise ValueError('invalid recorded container identity')
    if not sandbox_available(engine):
        raise IsolationUnavailable('Docker unavailable; recorded container cleanup HOLD')
    with tempfile.TemporaryDirectory(prefix='nomad-container-recovery-') as td:
        return _cleanup_container(engine, container_name, cwd=Path(td))


def docker_preflight(policy: SandboxPolicy, *, engine: str = 'docker') -> dict:
    """Read daemon/image metadata only; readiness is NOT containment qualification."""
    policy.validate()
    report = {'schema': 'nomad.docker-preflight.v1', 'ready': False,
              'native_containment_qualified': False, 'reasons': []}
    if engine != 'docker' or not sandbox_available(engine):
        report['reasons'].append('Docker binary unavailable or unsupported backend')
        return report
    with tempfile.TemporaryDirectory(prefix='nomad-docker-preflight-') as td:
        cwd = Path(td)
        prefix = _docker_prefix(engine, cwd)
        for kind, arguments in (('daemon', ['info', '--format', '{{json .}}']),
                                ('image', ['image', 'inspect', policy.image])):
            result = run_supervised([*prefix, *arguments], cwd=cwd, timeout_s=5,
                                    env=minimal_env(), max_output_bytes=262144)
            if result.returncode != 0 or result.timed_out or result.truncated or 'unconfirmed' in result.cleanup:
                report['reasons'].append(kind + ' metadata unavailable or cleanup unconfirmed')
                return report
            try:
                metadata = json.loads(result.output)
                if kind == 'daemon':
                    if metadata.get('OSType') != 'linux':
                        raise ValueError('Linux containers required')
                    if not any('seccomp' in str(x) for x in metadata.get('SecurityOptions', [])):
                        raise ValueError('daemon seccomp support required')
                    report['server_version'] = metadata.get('ServerVersion')
                else:
                    if len(metadata) != 1 or policy.image not in metadata[0].get('RepoDigests', []):
                        raise ValueError('local image does not attest requested repository digest')
                    if metadata[0].get('Os') != 'linux':
                        raise ValueError('Linux image required')
                    if metadata[0].get('Config', {}).get('Volumes'):
                        raise ValueError('image-declared volumes are outside the source-only policy')
                    report['image_id'] = metadata[0].get('Id')
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                report['reasons'].append(str(error))
                return report
    report['ready'] = True
    return report


def run_isolated(source: Path, *, command: Sequence[str], policy: SandboxPolicy,
                 engine: str = 'docker', container_name: str | None = None) -> dict:
    policy.validate()
    if engine != 'docker':
        raise IsolationUnavailable('unsupported isolation backend; no host fallback')
    if not sandbox_available(engine):
        raise IsolationUnavailable('Docker binary unavailable; untrusted execution DENIED')
    preflight = docker_preflight(policy, engine=engine)
    if not preflight['ready']:
        raise IsolationUnavailable('Docker preflight HOLD: ' + '; '.join(preflight['reasons']))
    with tempfile.TemporaryDirectory(prefix='nomad-isolated-source-') as td:
        snapshot = snapshot_source(Path(source), Path(td)/'source', policy)
        name = container_name or ('nomad-'+uuid.uuid4().hex[:24])
        argv = docker_arguments(engine=engine, snapshot=snapshot.root, image=policy.image,
                                name=name, command=command, policy=policy)
        argv = [*_docker_prefix(engine, Path(td)), *argv[1:]]
        result = None
        cleanup_confirmed = False
        try:
            result = run_supervised(argv, cwd=Path(td), timeout_s=policy.timeout_s,
                                    env=minimal_env(), max_output_bytes=8192)
        finally:
            cleanup_confirmed = _cleanup_container(engine, name, cwd=Path(td))
        if result is None or not cleanup_confirmed or 'unconfirmed' in result.cleanup:
            raise IsolationUnavailable('container cleanup unconfirmed; HOLD outcome')
        if result.returncode in (125, 126, 127) and not result.timed_out:
            raise IsolationUnavailable('container engine or requested interpreter did not start; HOLD outcome')
        return {
            'schema': 'nomad.isolated-test.v1',
            'container_name': name,
            'preflight': preflight,
            'snapshot_sha256': snapshot.digest, 'source_files':snapshot.files,
            'source_bytes':snapshot.bytes, 'image_digest':policy.image.split('@sha256:')[-1],
            'command': list(command), 'returncode': result.returncode,
            'tests_passed': result.returncode == 0 and not result.timed_out,
            'timed_out': result.timed_out, 'elapsed_ms': result.elapsed_ms,
            'supervisor_metrics': result.metrics,
            'output_sha256': result.output_sha256,
            'output_truncated': result.truncated,
            'container_cleanup_confirmed': cleanup_confirmed,
            'authority': 'test execution only; independent WITNESS still required',
        }
