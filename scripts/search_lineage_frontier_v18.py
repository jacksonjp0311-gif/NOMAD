"""Read-only bounded search for original NOMAD archives; never reconstructs them."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_lineage_v18 import COMPACT_SHA, V16_SHA, V15_SHA, V14_SHA, hash_file

KNOWN = {COMPACT_SHA: 'v17_compact', V16_SHA: 'v16_original',
         V15_SHA: 'v15_original', V14_SHA: 'v14_original'}
OLD_NAME = re.compile(r'nomad.*v?0[._-](14|15|16|17)', re.I)
MAX_ARCHIVE = 200_000_000


def inspect_members(archive: zipfile.ZipFile, *, depth=0) -> list[dict]:
    entries = archive.infolist()
    if len(entries) > 20000:
        raise ValueError('central directory exceeds 20000 members')
    if sum(entry.file_size for entry in entries if
           OLD_NAME.search(entry.filename.replace('\\', '/').rsplit('/', 1)[-1])
           and entry.filename.lower().endswith('.zip')) > MAX_ARCHIVE:
        raise ValueError('nested candidate byte budget exceeded')
    found = []
    for entry in entries:
        if entry.is_dir():
            continue
        basename = entry.filename.replace('\\', '/').rsplit('/', 1)[-1]
        if OLD_NAME.search(basename) and basename.lower().endswith('.zip'):
            item = {'member': entry.filename, 'bytes': entry.file_size}
            if entry.file_size > MAX_ARCHIVE or entry.flag_bits & 1:
                item['status'] = 'not_read_excessive_or_encrypted'
            else:
                content = archive.read(entry)
                item['sha256'] = sha256(content).hexdigest()
                item['known_identity'] = KNOWN.get(item['sha256'])
                if item['known_identity'] in ('v16_original', 'v15_original') and depth < 3:
                    with zipfile.ZipFile(io.BytesIO(content)) as nested:
                        item['nested'] = inspect_members(nested, depth=depth + 1)
            found.append(item)
    return found


def search(roots: list[Path]) -> dict:
    report = {'schema': 'nomad.original-archive-search.v18',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'scope_roots': [str(path) for path in roots], 'known_sha256': KNOWN,
              'originals_regenerated': False, 'archives_extracted': False,
              'history_modified': False, 'gate_D': 'HOLD', 'matches': [],
              'errors': [], 'omissions': [], 'limits': {'archive_bytes': MAX_ARCHIVE,
                  'central_directory_members': 20000, 'archive_paths': 2000},
              'scope_note': 'Named local roots and reachable Git history only; not an exhaustive machine/cloud/recycle-bin search.'}
    existing = [path for path in roots if path.is_dir()]
    for path in roots:
        if path not in existing:
            report['omissions'].append({'root': str(path), 'reason': 'directory absent'})
    listing = subprocess.run(['rg', '--files', '--hidden', '--no-ignore', '-g', '*.zip',
        '-g', '!**/.git/**', '-g', '!**/node_modules/**', '-g', '!**/.venv/**',
        *map(str, existing)], capture_output=True, text=True, timeout=60)
    report['enumeration_exit_code'] = listing.returncode
    report['enumeration_error_sha256'] = sha256(listing.stderr.encode()).hexdigest() if listing.stderr else None
    paths = sorted({Path(line) for line in listing.stdout.splitlines()}, key=str)
    report['zip_paths_found'] = len(paths)
    if len(paths) > 2000:
        report['omissions'].append({'reason': 'path budget exceeded', 'count': len(paths) - 2000})
    inspected = hashed = 0
    for path in paths[:2000]:
        try:
            if path.stat().st_size > MAX_ARCHIVE:
                report['omissions'].append({'path': str(path), 'reason': 'archive size budget exceeded'})
                continue
            digest = hash_file(path)
            hashed += 1
            with zipfile.ZipFile(path) as archive:
                nested = inspect_members(archive)
                v17_manifest = any(name.endswith('results/RELEASE_MANIFEST_V017.json')
                                   for name in archive.namelist())
            inspected += 1
            if digest in KNOWN or OLD_NAME.search(path.name) or nested or v17_manifest:
                report['matches'].append({'path': str(path), 'bytes': path.stat().st_size,
                    'sha256': digest, 'known_identity': KNOWN.get(digest),
                    'v17_manifest_present': v17_manifest, 'nested_candidates': nested})
        except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
            report['errors'].append({'path': str(path), 'reason': type(error).__name__})
    report['archives_hashed'] = hashed
    report['central_directories_inspected'] = inspected
    history = subprocess.run(['git', 'rev-list', '--objects', '--all'], cwd=ROOT,
                             capture_output=True, text=True, timeout=30, check=True)
    report['git_head'] = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
        capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    report['git_archive_objects'] = []
    for line in history.stdout.splitlines():
        oid, _, name = line.partition(' ')
        if not name.lower().endswith('.zip'):
            continue
        size = int(subprocess.run(['git', 'cat-file', '-s', oid], cwd=ROOT,
            capture_output=True, text=True, timeout=10, check=True).stdout)
        if size > MAX_ARCHIVE:
            report['omissions'].append({'git_object': oid, 'reason': 'archive size budget exceeded'})
            continue
        content = subprocess.run(['git', 'cat-file', 'blob', oid], cwd=ROOT,
            capture_output=True, timeout=10, check=True).stdout
        checksum = sha256(content).hexdigest()
        report['git_archive_objects'].append({'object': oid, 'path': name, 'bytes': size,
            'sha256': checksum, 'known_identity': KNOWN.get(checksum)})
    found = {match['known_identity'] for match in report['matches']} | {
        match['known_identity'] for match in report['git_archive_objects']}
    def collect_nested(items):
        for item in items:
            found.add(item.get('known_identity'))
            collect_nested(item.get('nested', []))
    for match in report['matches']:
        collect_nested(match['nested_candidates'])
    report['original_v14_v15_v16_found'] = sorted(found - {None, 'v17_compact'})
    report['conclusion'] = ('candidate originals require separate lineage verification' if
        report['original_v14_v15_v16_found'] else 'no original v14/v15/v16 or verified full v17 recovered within recorded scope')
    report['receipt_sha256'] = sha256(json.dumps(report, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('output exists; preserve original evidence')
    report = search(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({key: report[key] for key in ('zip_paths_found', 'archives_hashed',
        'central_directories_inspected', 'original_v14_v15_v16_found', 'conclusion')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
