"""Bounded, fail-closed extraction for untrusted ZIP-based source distributions."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import os
import stat
import zipfile

from .isolation import UnsafeWorkspace, validate_source_name


def extract_checked(archive: Path, destination: Path, *, max_files: int = 3000,
                    max_total_bytes: int = 30_000_000,
                    max_expansion_ratio: int = 200) -> dict:
    archive=Path(archive)
    destination=Path(destination)
    if destination.exists() or destination.is_symlink():
        raise UnsafeWorkspace('destination must not exist')
    entries=[]
    total=0
    paths=set()
    spellings={}
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name=item.filename
            path=PurePosixPath(name)
            if (not name or '\\' in name or '\x00' in name or path.as_posix()!=name.rstrip('/') or path.is_absolute()
                or '..' in path.parts or any(x in ('', '.') for x in path.parts)
                or ':' in name or len(path.parts)>32):
                raise UnsafeWorkspace('unsafe ZIP member path')
            for part in path.parts:
                validate_source_name(part)
            for depth in range(1, len(path.parts)+1):
                prefix='/'.join(path.parts[:depth])
                key=prefix.casefold()
                if key in spellings and spellings[key]!=prefix:
                    raise UnsafeWorkspace('case-colliding ZIP parent/member')
                spellings[key]=prefix
            normalized = name.rstrip('/').casefold()
            if normalized in paths:
                raise UnsafeWorkspace('duplicate ZIP member')
            paths.add(normalized)
            unix_type=stat.S_IFMT(item.external_attr>>16)
            if unix_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise UnsafeWorkspace('nonregular ZIP member (including symlink) refused')
            if item.is_dir():
                continue
            if item.file_size<0 or item.file_size>max_total_bytes:
                raise UnsafeWorkspace('oversized ZIP member')
            total+=item.file_size
            if len(entries)+1>max_files or total>max_total_bytes:
                raise UnsafeWorkspace('archive exceeds extraction quota')
            if item.file_size>10_000 and item.file_size>max(1,item.compress_size)*max_expansion_ratio:
                raise UnsafeWorkspace('suspicious ZIP expansion ratio')
            entries.append(item)
        destination.mkdir(parents=True,exist_ok=False)
        try:
            for item in entries:
                target=destination.joinpath(*PurePosixPath(item.filename).parts)
                target.parent.mkdir(parents=True,exist_ok=True)
                # ZipFile.open performs CRC checking. The loop enforces the
                # predeclared per-member bound even on malformed metadata.
                used=0
                with z.open(item) as src, target.open('xb') as out:
                    while chunk:=src.read(65536):
                        used+=len(chunk)
                        if used>item.file_size:
                            raise UnsafeWorkspace('expanded beyond registered member size')
                        out.write(chunk)
                if used!=item.file_size:
                    raise UnsafeWorkspace('mismatched ZIP member size')
                if os.name != 'nt':
                    os.chmod(target,0o444)
        except Exception:
            import shutil
            shutil.rmtree(destination)
            raise
    return {'files':len(entries),'bytes':total, 'authority':'source extracted; never executed'}
