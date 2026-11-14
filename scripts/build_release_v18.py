"""Deterministic local engineering packages; no publication or qualification inference."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release_files_v18 import MANIFEST, EXCLUDED, files, sha


def manifest(mode: str) -> dict:
    return {'schema': 'nomad.v0.18.manifest.v1', 'version': '0.18.0', 'package_kind': mode,
            'status': 'engineering snapshot; publication HOLD',
            'sha256_by_path': {name: sha(path) for name, path in files(ROOT, mode)}}


def canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')


def build(output: Path, mode: str, *, seal_source: bool = False) -> dict:
    output = output.resolve()
    if output.exists():
        raise FileExistsError('refusing to overwrite an existing archive')
    if output.is_relative_to(ROOT.resolve()):
        relative = output.relative_to(ROOT.resolve())
        if relative.parts[0] not in EXCLUDED:
            raise ValueError('archive output must be outside included source paths')
    if seal_source and mode != 'source':
        raise ValueError('only source can seal the repository')
    seal = ROOT / MANIFEST
    if seal_source and seal.exists():
        raise FileExistsError('source already sealed; refusing to replace integrity evidence')
    payloads = [(name, path.read_bytes()) for name, path in files(ROOT, mode)]
    record = {'schema': 'nomad.v0.18.manifest.v1', 'version': '0.18.0', 'package_kind': mode,
              'status': 'engineering snapshot; publication HOLD',
              'sha256_by_path': {name: hashlib.sha256(data).hexdigest() for name, data in payloads}}
    if seal.exists():
        existing = json.loads(seal.read_bytes())
        current_source = record if mode == 'source' else manifest('source')
        if existing != current_source:
            raise ValueError('source differs from existing seal; retain evidence and investigate')
    payloads.append((MANIFEST, canonical(record)))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payloads):
            entry = zipfile.ZipInfo('NOMAD-v0.18.0/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    if seal_source:
        with seal.open('xb') as stream:
            stream.write(canonical(record))
    return {'path': output.name, 'sha256': sha(output), 'bytes': output.stat().st_size,
            'package_kind': mode, 'files': len(payloads)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('source', 'runtime'), default='source')
    parser.add_argument('--seal-source', action='store_true', help='first-time explicit post-development source seal')
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.mode, seal_source=args.seal_source), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
