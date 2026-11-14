"""One file boundary shared by the builder and read-only verifier."""
from pathlib import Path
import hashlib
import os
import stat

# Keep the first engineering seal as historical evidence. Qualification fixes
# remain v0.18.0 and receive a distinct, immutable internal snapshot seal.
MANIFEST = 'results/RELEASE_MANIFEST_QUALIFICATION_V018.json'
GATES = 'results/GATES_QUALIFICATION_V018.json'
EXCLUDED = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache',
            'node_modules', 'runs', 'work', 'outputs', 'build', 'dist'}
ROOT_FILES = {'README.md', 'LICENSE', 'pyproject.toml', 'NOMAD.ps1', 'NOMAD.cmd', 'platform.example.json',
              'RELEASE.md', 'CHANGELOG.md', 'DESKTOP_SOURCE_NOTICE.txt', 'CODEX_HANDOFF.md'}
RUNTIME_SCRIPTS = {'release_files_v18.py', 'verify_package_v18.py', 'qualify_isolation_v18.py',
                   'windows_entry_v18.py', 'verify_lineage_v18.py',
                   'experiment_qualification_v18.py', 'qualify_recovery_v18.py'}


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1 << 20), b''):
            value.update(data)
    return value.hexdigest()


def files(root: Path, mode: str = 'source') -> list[tuple[str, Path]]:
    if mode not in ('source', 'runtime'):
        raise ValueError('unknown package mode')
    selected = []
    def walk(directory):
        for path in sorted(directory.iterdir()):
            if path.name.casefold() in EXCLUDED or path.name.casefold().endswith('.egg-info'):
                continue
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_reparse_tag', 0):
                raise ValueError('release link/reparse point refused: ' + str(path.relative_to(root)))
            if stat.S_ISDIR(metadata.st_mode):
                yield from walk(path)
            elif not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError('release special file/hardlink refused: ' + str(path.relative_to(root)))
            else:
                yield path
    for path in walk(root):
        relative = path.relative_to(root)
        if any(part.casefold() in EXCLUDED or part.casefold().endswith('.egg-info') for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError('release symlink refused: ' + str(relative))
        if not path.is_file():
            continue
        name = relative.as_posix()
        if name.casefold() == MANIFEST.casefold() or name.casefold() == 'platform.local.json' or path.suffix.casefold() in ('.pyc', '.pyo') or name.casefold().startswith('results/ci_'):
            continue
        if (path.name.casefold() in {'.env', '.npmrc', '.netrc', '.pypirc', 'credentials.json',
                                    'token.json', 'id_rsa', 'id_ed25519'}
                or path.name.casefold().startswith('.env.') or path.suffix.casefold() in {'.pem', '.key', '.pfx', '.p12'}
                or any(part.casefold() in {'.ssh', '.aws', '.azure', '.gnupg'} for part in relative.parts)):
            raise ValueError('credential-like release path refused: ' + name)
        if mode == 'runtime' and not (
            relative.parts[0] in {'nomad', 'vendor', 'docs', 'assets', 'baseline',
                                 'results', 'experiments', 'external_sources'} or name in ROOT_FILES or
            name.startswith('scripts/') and path.name in RUNTIME_SCRIPTS
        ):
            continue
        selected.append((name, path))
    return sorted(selected)
