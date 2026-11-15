"""Read-only lineage qualification. Missing originals are HOLD, never regenerated."""
from __future__ import annotations
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMPACT_SHA = '57ca9835540d0ff23c0f03d0dae9c00ac906677f7eedbe780f98b6c5b7c0dafc'
V16_SHA = '9f206af8f285a97f77d97642f183ba9f120e9b4cf2f6de914ab6446d5dcfb3b6'
V15_SHA = '088203e8af0b0c9886417c20a7eec2e75176b05b8313a527356def3b96a76544'
V14_SHA = '22c218597f5fa1cfc4003fc7694daac420ac42d0603feaeb8130ade6ef2619ea'
BGR_SHA = '93177c5cc628ac0c6426d8c612c0d769b86ed53cbd7b2a3f872d2706c601a8c2'
ENGINEERING_SEAL_SHA = '577c0182ed917742ffa49b286638026657a165f2ee0a49e4f2130b124fdb8335'
QUALIFICATION_SEAL_SHA = 'a51bf062d96db7a144450f37fb09f39377584e9642f36fbf3fd9606023afcfec'
FRONTIER_SEAL_SHA = 'e2c2fd63a811b7ccc2aaa3470cbb07e490fc2b6782d153db4e26d6d147f664e1'
ADAPTIVE_SEAL_SHA = 'ce2740ce18c6e3ad1b8474e43dbf4a0e7d776bf11a42e9156eb47b2660afae31'
ADAPTIVE_STUDY_CODE = frozenset({
    'nomad/adaptive.py', 'scripts/experiment_adaptive_v18.py',
    'scripts/audit_adaptive_metrics_v18.py', 'scripts/verify_adaptive_replay_v18.py',
    'scripts/summarize_adaptive_v18.py', 'scripts/diagnose_adaptive_v18.py'})


def hash_file(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def members(archive: zipfile.ZipFile, prefix: str) -> dict:
    result = {}
    aliases = set()
    entries = archive.infolist()
    if len(entries) > 20000 or sum(info.file_size for info in entries) > 500_000_000:
        raise ValueError('excessive archive inventory')
    for info in entries:
        # ZipInfo normalizes Windows separators and truncates NULs in filename.
        # Inspect the original decoded central-directory spelling as well.
        name = info.orig_filename
        parts = name.rstrip('/').split('/')
        reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{kind}{n}' for kind in ('COM', 'LPT') for n in range(1, 10)}
        if (name != info.filename or not name.startswith(prefix) or name.startswith('/') or '\\' in name
                or any(not part or part in ('.', '..') or part[-1:] in ('.', ' ')
                       or any(ord(c) < 32 or c in ':<>"|?*' for c in part)
                       or part.split('.')[0].upper() in reserved for part in parts)):
            raise ValueError('unsafe archive member path')
        alias = name.rstrip('/').casefold()
        if alias in aliases:
            raise ValueError('unexpected or duplicate archive member')
        aliases.add(alias)
        kind = stat.S_IFMT(info.external_attr >> 16)
        if (kind not in (0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG)
                or info.external_attr & 0x400 or info.flag_bits & 1):
            raise ValueError('archive link, special, reparse or encrypted member refused')
        if info.file_size > 150_000_000:
            raise ValueError('unsafe or excessive archive member')
        if info.is_dir():
            if info.file_size != 0:
                raise ValueError('nonempty directory archive member')
            continue
        relative = name[len(prefix):]
        if not relative:
            raise ValueError('archive file has no relative name')
        if relative in result:
            raise ValueError('duplicate relative archive member')
        result[relative] = info
    return result


def verify(root: Path = ROOT, *, compact: Path | None = None, predecessor: Path | None = None,
           full_v17: Path | None = None) -> dict:
    compact = compact or root / 'baseline/NOMAD-v0.17.0-Desktop-Source.zip'
    predecessor = predecessor or root / 'baseline/NOMAD-v0.16.0.zip'
    if full_v17 is None and (root / 'baseline/NOMAD-v0.17.0.zip').is_file():
        full_v17 = root / 'baseline/NOMAD-v0.17.0.zip'
    if not compact.is_file():
        return {'schema': 'nomad.lineage-qualification.v18', 'gate_D': 'HOLD',
                'missing': ['original v0.17 compact archive'], 'historical_results_regenerated': False}
    if hash_file(compact) != COMPACT_SHA:
        raise ValueError('original compact v0.17 archive differs from recorded digest')
    with zipfile.ZipFile(compact) as archive:
        inventory = members(archive, 'NOMAD-v0.17.0/')
        manifest = json.loads(archive.read(inventory['results/RELEASE_MANIFEST_V017.json']))
        if manifest['schema'] != 'nomad.v0.17.manifest.v1':
            raise ValueError('unexpected original manifest')
        expected = manifest['sha256_by_path']
        missing = sorted(set(expected) - set(inventory))
        if missing != ['baseline/NOMAD-v0.16.0.zip']:
            raise ValueError('compact omission does not match documented predecessor absence')
        bad = [name for name in expected if name in inventory and
               sha256(archive.read(inventory[name])).hexdigest() != expected[name]]
        if bad:
            raise ValueError('original compact members disagree with original manifest: ' + repr(bad))
        preserved = {name: expected[name] for name in expected if name.startswith(
                     ('results/', 'experiments/', 'vendor/', 'external_sources/'))}
        changed = [name for name, digest in preserved.items()
                   if not (root / name).is_file() or hash_file(root / name) != digest]
        if changed:
            raise ValueError('protected historical evidence differs: ' + repr(changed))
    if hash_file(root / 'vendor/BGR-v1.4.0-runtime.zip') != BGR_SHA:
        raise ValueError('original native BGR archive differs')
    engineering_seal = root / 'results/RELEASE_MANIFEST_V018.json'
    if hash_file(engineering_seal) != ENGINEERING_SEAL_SHA:
        raise ValueError('original v0.18 engineering seal differs')
    engineering = json.loads(engineering_seal.read_bytes())['sha256_by_path']
    frozen = {name: digest for name, digest in engineering.items() if name.startswith(
              ('results/', 'experiments/', 'vendor/', 'external_sources/'))}
    changed = [name for name, digest in frozen.items()
               if not (root / name).is_file() or hash_file(root / name) != digest]
    if changed:
        raise ValueError('frozen v0.18 engineering evidence differs: ' + repr(changed))
    qualification_seal = root / 'results/RELEASE_MANIFEST_QUALIFICATION_V018.json'
    if hash_file(qualification_seal) != QUALIFICATION_SEAL_SHA:
        raise ValueError('original ddb5c32 qualification seal differs')
    qualification = json.loads(qualification_seal.read_bytes())['sha256_by_path']
    protected = {name: checksum for name, checksum in qualification.items() if name.startswith(
                  ('results/', 'experiments/', 'vendor/', 'external_sources/', 'baseline/'))}
    changed = [name for name, checksum in protected.items()
               if not (root / name).is_file() or hash_file(root / name) != checksum]
    if changed:
        raise ValueError('frozen ddb5c32 qualification evidence differs: ' + repr(changed))
    frontier_seal = root / 'results/RELEASE_MANIFEST_FRONTIER_RECOVERY_V018.json'
    if hash_file(frontier_seal) != FRONTIER_SEAL_SHA:
        raise ValueError('original 993395f FRONTIER seal differs')
    frontier = json.loads(frontier_seal.read_bytes())['sha256_by_path']
    frozen_study_code = {'scripts/frontier_bitwork_v18.py',
                         'scripts/verify_frontier_bitwork_replay_v18.py',
                         'scripts/audit_frontier_metrics_v18.py'}
    frontier_protected = {name: checksum for name, checksum in frontier.items()
                          if name.startswith(('results/', 'experiments/', 'vendor/',
                                              'external_sources/', 'baseline/'))
                          or name in frozen_study_code}
    changed = [name for name, checksum in frontier_protected.items()
               if not (root / name).is_file() or hash_file(root / name) != checksum]
    if changed:
        raise ValueError('frozen 993395f FRONTIER evidence differs: ' + repr(changed))
    adaptive_seal = root / 'results/RELEASE_MANIFEST_ADAPTIVE_V018.json'
    if hash_file(adaptive_seal) != ADAPTIVE_SEAL_SHA:
        raise ValueError('original 3ffd467 ADAPTIVE seal differs')
    adaptive = json.loads(adaptive_seal.read_bytes())['sha256_by_path']
    adaptive_protected = {name: checksum for name, checksum in adaptive.items()
                          if name.startswith(('results/', 'experiments/', 'vendor/',
                                              'external_sources/', 'baseline/', 'docs/ADAPTIVE'))
                          or name in ADAPTIVE_STUDY_CODE}
    changed = [name for name, checksum in adaptive_protected.items()
               if not (root / name).is_file() or hash_file(root / name) != checksum]
    if changed:
        raise ValueError('frozen 3ffd467 ADAPTIVE evidence differs: ' + repr(changed))
    report = {'schema': 'nomad.lineage-qualification.v18', 'gate_D': 'HOLD',
              'compact_v17': {'status': 'PASS', 'sha256': COMPACT_SHA,
                              'original_manifest_members_verified': len(expected) - len(missing)},
              'historical_evidence': {'status': 'PASS', 'unchanged_files': len(preserved)},
              'engineering_5851566_evidence': {'status': 'PASS', 'unchanged_files': len(frozen),
                                              'original_seal_sha256': ENGINEERING_SEAL_SHA},
              'qualification_ddb5c32_evidence': {'status': 'PASS', 'unchanged_files': len(protected),
                                                'original_seal_sha256': QUALIFICATION_SEAL_SHA},
              'frontier_993395f_evidence': {'status': 'PASS', 'unchanged_files': len(frontier_protected),
                                           'original_seal_sha256': FRONTIER_SEAL_SHA,
                                           'includes_original_mechanism_code': True},
              'adaptive_3ffd467_evidence': {'status': 'PASS', 'unchanged_files': len(adaptive_protected),
                                           'original_seal_sha256': ADAPTIVE_SEAL_SHA,
                                           'includes_original_controller_study_audits_and_reports': True},
              'original_bgr_archive': {'status': 'PASS', 'sha256': BGR_SHA},
              'historical_results_regenerated': False,
              'missing': [{'path': missing[0], 'expected_sha256': V16_SHA,
                           'consequence': 'nested v0.15/v0.14 bytes and complete predecessor lineage unavailable'}],
              'full_v17_archive': {'status': 'HOLD', 'reason': 'full original ZIP not available'}}
    parent_bytes = None
    if full_v17 is not None:
        with zipfile.ZipFile(full_v17) as archive:
            full = members(archive, 'NOMAD-v0.17.0/')
            allowed = set(expected) | {'results/RELEASE_MANIFEST_V017.json'}
            if set(full) != allowed:
                raise ValueError('full original v0.17 inventory differs')
            for name, digest in expected.items():
                if sha256(archive.read(full[name])).hexdigest() != digest:
                    raise ValueError('full original member differs: ' + name)
            if json.loads(archive.read(full['results/RELEASE_MANIFEST_V017.json'])) != manifest:
                raise ValueError('full archive manifest differs from pinned compact manifest')
            parent_bytes = archive.read(full['baseline/NOMAD-v0.16.0.zip'])
        report['full_v17_archive'] = {'status': 'PASS', 'sha256': hash_file(full_v17),
                                     'identity': 'all original member hashes verified; ZIP hash recorded now'}
    elif predecessor.is_file():
        if hash_file(predecessor) != V16_SHA:
            raise ValueError('v0.16 predecessor digest mismatch')
        parent_bytes = predecessor.read_bytes()
    if parent_bytes is not None:
        if sha256(parent_bytes).hexdigest() != V16_SHA:
            raise ValueError('v0.16 predecessor digest mismatch')
        with zipfile.ZipFile(io.BytesIO(parent_bytes)) as archive:
            v15 = archive.read('NOMAD-v0.16.0/baseline/NOMAD-v0.15.0.zip')
        if sha256(v15).hexdigest() != V15_SHA:
            raise ValueError('nested v0.15 differs')
        with zipfile.ZipFile(io.BytesIO(v15)) as archive:
            v14 = archive.read('NOMAD-v0.15.0/baseline/NOMAD-v0.14.0.zip')
        if sha256(v14).hexdigest() != V14_SHA:
            raise ValueError('nested v0.14 differs')
        report['predecessors'] = {'status': 'PASS', 'v16_sha256': V16_SHA,
                                  'v15_sha256': V15_SHA, 'v14_sha256': V14_SHA}
        report['missing'] = []
        report['gate_D'] = 'PASS' if full_v17 is not None else 'HOLD'
        if full_v17 is None:
            report['missing'] = [{'path': 'NOMAD-v0.17.0.zip',
                                  'consequence': 'complete original distribution archive has not been verified'}]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compact', type=Path)
    parser.add_argument('--predecessor', type=Path)
    parser.add_argument('--full-v17', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error('refusing to overwrite a lineage receipt')
    try:
        report = verify(compact=args.compact, predecessor=args.predecessor, full_v17=args.full_v17)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        report = {'schema': 'nomad.lineage-qualification.v18', 'gate_D': 'FAIL', 'reason': str(error)}
    text = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
    print(text)
    return 0 if report['gate_D'] == 'PASS' else 3


if __name__ == '__main__':
    raise SystemExit(main())
