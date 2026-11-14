"""Read-only integrity verification. Never seals/regenerates its own expected hashes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release_files_v18 import MANIFEST, files, sha

BGR_SHA = '93177c5cc628ac0c6426d8c612c0d769b86ed53cbd7b2a3f872d2706c601a8c2'
PARENT_SHA = '9f206af8f285a97f77d97642f183ba9f120e9b4cf2f6de914ab6446d5dcfb3b6'


def verify(root: Path = ROOT, *, require_release: bool = False) -> dict:
    record = json.loads((root / MANIFEST).read_text(encoding='utf-8'))
    if record.get('schema') != 'nomad.v0.18.manifest.v1' or record.get('version') != '0.18.0':
        raise ValueError('invalid v0.18 manifest')
    expected = record['sha256_by_path']
    # Scan every deliverable file, even for runtime packages: an injected file is an error.
    actual = {relative: sha(path) for relative, path in files(root)}
    if set(actual) != set(expected):
        raise ValueError('inventory mismatch: extra=' + repr(sorted(set(actual) - set(expected))[:8]) +
                         ' missing=' + repr(sorted(set(expected) - set(actual))[:8]))
    changed = [name for name in actual if actual[name] != expected[name]]
    if changed:
        raise ValueError('changed release bytes: ' + repr(changed[:8]))
    if sha(root / 'vendor/BGR-v1.4.0-runtime.zip') != BGR_SHA:
        raise ValueError('original BGR archive changed')
    parent = root / 'baseline/NOMAD-v0.16.0.zip'
    lineage = 'HOLD'
    if parent.exists():
        if sha(parent) != PARENT_SHA:
            raise ValueError('historical predecessor differs')
        lineage = 'PASS'
    gates = json.loads((root / 'results/GATES_V018.json').read_text(encoding='utf-8'))
    report = {'schema': 'nomad.v0.18.verification.v1', 'source_integrity': 'PASS',
              'package_kind': record['package_kind'], 'files_verified': len(actual),
              'bgr_archive': 'PASS', 'historical_lineage': lineage,
              'recorded_gates': gates, 'production_ready': False,
              'note': 'Checksums detect changed bytes; they do not authenticate an adversarially replaced manifest.'}
    if require_release and (gates.get('publication') != 'PASS' or lineage != 'PASS'
                            or gates.get('native_containment') != 'PASS'
                            or gates.get('isolated_mission_recovery') != 'PASS'):
        raise ValueError('publication gate HOLD: native platform qualification incomplete')
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-release', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(require_release=args.require_release), indent=2, sort_keys=True))
        return 0
    except (ValueError, KeyError, OSError) as error:
        print('NOMAD integrity/release HOLD: ' + str(error), file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
