"""Read-only integrity verification. Never seals/regenerates its own expected hashes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release_files_v18 import MANIFEST, GATES, files, sha
from scripts.verify_lineage_v18 import verify as verify_lineage

BGR_SHA = '93177c5cc628ac0c6426d8c612c0d769b86ed53cbd7b2a3f872d2706c601a8c2'
PARENT_SHA = '9f206af8f285a97f77d97642f183ba9f120e9b4cf2f6de914ab6446d5dcfb3b6'


def verify_qualification_evidence(root: Path, gates: dict, inventory: dict) -> None:
    """A summary cannot override a missing, changed or unresolved receipt.

    These are consistency checks under an externally trusted package anchor,
    not authentication of a hostile author's all-new evidence set.
    """
    required = {
        'gate_A': ('nomad.native-isolation-qualification.v18', 'native_containment_gate'),
        'gate_B': ('nomad.real-repository-qualification.v18', 'gate_B'),
        'gate_C': ('nomad.pipeline-qualification.v18', 'gate_C'),
        'gate_D': ('nomad.lineage-qualification.v18', 'gate_D'),
        'isolated_mission_recovery': ('nomad.platform-recovery-qualification.v18',
                                     'isolated_mission_recovery'),
    }
    bindings = gates.get('qualification_evidence', {})
    receipts = {}
    for gate, (schema, field) in required.items():
        binding = bindings.get(gate, {})
        path, expected = binding.get('path'), binding.get('sha256')
        if (not isinstance(path, str) or not path.startswith('results/')
                or path not in inventory or inventory[path] != expected):
            raise ValueError('publication gate HOLD: missing/unbound evidence for ' + gate)
        record = json.loads((root / path).read_bytes())
        if (record.get('schema') != schema or record.get(field) != 'PASS'
                or record.get('status') in ('FAIL', 'HOLD', 'NOT_RUN')):
            raise ValueError('publication gate HOLD: unresolved receipt for ' + gate)
        receipts[gate] = record
        if gate == 'gate_A':
            from scripts.qualify_isolation_v18 import CONTROLLED_CASES, canonical_digest
            payload = {key: value for key, value in record.items() if key != 'receipt_sha256'}
            code = record.get('source_sha256_after', {})
            observed = {case.get('case') for case in record.get('cases', []) if case.get('status') == 'PASS'}
            required_cases = set(CONTROLLED_CASES) | {'supervisor_hard_death_cleanup'}
            required_sources = {'nomad/isolation.py', 'nomad/supervised.py',
                                'nomad/windows_job.py', 'scripts/qualify_isolation_v18.py'}
            if (record.get('receipt_sha256') != canonical_digest(payload)
                    or record.get('source_stable') is not True or not code
                    or code != record.get('source_sha256_before')
                    or not required_sources <= set(code)
                    or any(inventory.get(name) != digest for name, digest in code.items())
                    or observed != required_cases
                    or len(record['cases']) != len(required_cases)
                    or record.get('protected_host_sentinel_unchanged') is not True
                    or record.get('backend') != 'docker' or record.get('status') != 'PASS'):
                raise ValueError('publication gate HOLD: native receipt is incomplete or stale')
        if gate == 'isolated_mission_recovery':
            from scripts.qualify_isolation_v18 import canonical_digest
            from scripts.qualify_recovery_v18 import required_cases
            payload = {key: value for key, value in record.items() if key != 'receipt_sha256'}
            code = record.get('source_sha256_after', {})
            native = receipts['gate_A']
            expected_cases = set(required_cases())
            cases = record.get('cases', [])
            needed_sources = {name for name in inventory if name.startswith('nomad/') and name.endswith('.py')}
            needed_sources |= {'scripts/qualify_recovery_v18.py', 'scripts/qualify_isolation_v18.py'}
            if (record.get('receipt_sha256') != canonical_digest(payload)
                    or record.get('source_stable') is not True
                    or code != record.get('source_sha256_before')
                    or not needed_sources <= set(code)
                    or any(inventory.get(name) != checksum for name, checksum in code.items())
                    or len(cases) != len(expected_cases)
                    or {case.get('case') for case in cases} != expected_cases
                    or any(case.get('status') != 'PASS' for case in cases)
                    or record.get('protected_host_sentinel_unchanged') is not True
                    or record.get('original_source_unchanged') is not True
                    or not record.get('evidence_files_sha256')
                    or record.get('backend') != 'docker'
                    or record.get('isolation_receipt_sha256') != bindings['gate_A']['sha256']
                    or any(record.get(key) != native.get(key) for key in
                           ('image', 'policy_sha256', 'host_identity_sha256'))):
                raise ValueError('publication gate HOLD: recovery receipt is incomplete or stale')


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
    lineage = verify_lineage(root)['gate_D']
    gates = json.loads((root / GATES).read_text(encoding='utf-8'))
    report = {'schema': 'nomad.v0.18.verification.v1', 'source_integrity': 'PASS',
              'package_kind': record['package_kind'], 'files_verified': len(actual),
              'bgr_archive': 'PASS', 'historical_lineage': lineage,
              'recorded_gates': gates, 'production_ready': False,
              'note': 'Checksums detect changed bytes; they do not authenticate an adversarially replaced manifest.'}
    if require_release and (gates.get('publication') != 'PASS' or lineage != 'PASS'
                            or gates.get('native_containment') != 'PASS'
                            or gates.get('isolated_mission_recovery') != 'PASS'
                            or any(gates.get(name) != 'PASS' for name in (
                                'gate_A', 'gate_B', 'gate_C', 'gate_D'))):
        raise ValueError('publication gate HOLD: native platform qualification incomplete')
    if require_release:
        verify_qualification_evidence(root, gates, expected)
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
