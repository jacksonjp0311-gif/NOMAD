"""Independent *process* observer for trusted NOMAD v0.16 fixture missions.

It reads withheld examples that the mission search process is never passed.
This is an evidence separation contract, NOT an OS-level adversarial sandbox.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import sys
from pathlib import Path

from .codeworld import CodeWorldExample, _evidence_vector, _expected_vector
from .witness import Witness


def canonical(o: object) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(o: bytes) -> str:
    return hashlib.sha256(o).hexdigest()


def examples(rows: list[dict]) -> tuple[CodeWorldExample, ...]:
    if not isinstance(rows, list) or not rows:
        raise ValueError('empty or missing evaluation rows')
    return tuple(CodeWorldExample(dict(x['inputs']), x['expected']) for x in rows)


def inspect(root: Path, stage: str, *, task_id: str, transmission_id: str,
            expected_candidate_sha256: str) -> dict:
    root = root.resolve(strict=True)
    goal_path = root / 'goal.json'
    private_path = root / 'sealed' / 'withheld.json'
    goal = json.loads(goal_path.read_text(encoding='utf-8'))
    if goal.get('schema') != 'nomad.mission.goal.v1' or goal['task_id'] != task_id:
        raise ValueError('mission identity mismatch')
    if sha(private_path.read_bytes()) != goal['sealed_sha256']:
        raise ValueError('withheld evidence changed')
    sealed = json.loads(private_path.read_text(encoding='utf-8'))
    if sealed.get('schema') != 'nomad.mission.sealed.v1' or sealed['task_id'] != task_id:
        raise ValueError('withheld context mismatch')
    source_path = root / 'workspace' / 'solution.py'
    current = source_path.read_text(encoding='utf-8')
    if sha(current.encode()) != expected_candidate_sha256:
        raise ValueError('candidate source mismatched witness claim')
    original = (root / 'original.py').read_text(encoding='utf-8')
    if sha(original.encode()) != goal['original_sha256']:
        raise ValueError('mission source baseline changed')
    public = examples(goal['public'])
    if stage == 'witness':
        challenge = examples(sealed['challenge'])
        receipt = Witness(witness_id='nomad-v016-independent-process').attest(
            task_id=task_id,
            transmission_id=transmission_id,
            world_epoch=0,
            current_public=_evidence_vector(original, public),
            target_public=_expected_vector(public),
            candidate_public=_evidence_vector(current, public),
            current_challenge=_evidence_vector(original, challenge),
            target_challenge=_expected_vector(challenge),
            candidate_challenge=_evidence_vector(current, challenge),
        )
        if not receipt.verify_checksum():
            raise ValueError('witness receipt checksum invalid')
        result = {
            'schema': 'nomad.mission.observation.v1',
            'stage': 'witness', 'task_id': task_id,
            'transmission_id': transmission_id,
            'candidate_sha256': expected_candidate_sha256,
            'supported': receipt.supported,
            'receipt': asdict(receipt),
        }
    elif stage == 'final':
        final = examples(sealed['final'])
        prediction = _evidence_vector(current, final)
        expected = _expected_vector(final)
        supported = prediction == expected
        result = {
            'schema': 'nomad.mission.observation.v1',
            'stage': 'final', 'task_id': task_id,
            'transmission_id': transmission_id,
            'candidate_sha256': expected_candidate_sha256,
            'supported': supported,
            'observations': len(final),
            'observed_sha256': sha(canonical(list(prediction))),
            'expected_sha256': sha(canonical(list(expected))),
        }
    else:
        raise ValueError('unsupported witness stage')
    result['observation_sha256'] = sha(canonical(result))
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='NOMAD independent fixture observer')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--stage', choices=['witness', 'final'], required=True)
    p.add_argument('--task-id', required=True)
    p.add_argument('--transmission-id', required=True)
    p.add_argument('--candidate-sha256', required=True)
    p.add_argument('--trusted-fixture', action='store_true', required=True)
    a = p.parse_args(argv)
    r = inspect(a.root, a.stage, task_id=a.task_id, transmission_id=a.transmission_id,
                expected_candidate_sha256=a.candidate_sha256)
    print(json.dumps(r, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
