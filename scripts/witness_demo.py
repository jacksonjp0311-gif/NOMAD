from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nomad.witness import Witness


def run_demo() -> dict:
    w = Witness("nomad-witness-v0.6-demo")
    common = dict(
        task_id="demo-task",
        world_epoch=3,
        current_public=(0.0, 1.0, 2.0, 3.0),
        target_public=(1.0, 2.0, 3.0, 4.0),
        current_challenge=(4.0, 5.0, 6.0),
        target_challenge=(5.0, 6.0, 7.0),
    )
    contradicted = w.attest(
        **common,
        transmission_id="tx-overfit",
        candidate_public=(1.0, 2.0, 3.0, 4.0),
        candidate_challenge=(5.2, 5.7, 7.4),
    )
    supported = w.attest(
        **common,
        transmission_id="tx-supported",
        candidate_public=(1.0, 2.0, 3.0, 4.0),
        candidate_challenge=(5.0, 6.0, 7.0),
    )
    tampered = replace(supported, task_id="demo-task-mutated")
    return {
        "schema": "nomad.v0.6.witness-demo.v1",
        "contradicted_receipt": contradicted.payload_without_hash() | {"receipt_hash": contradicted.receipt_hash},
        "supported_receipt": supported.payload_without_hash() | {"receipt_hash": supported.receipt_hash},
        "checks": {
            "supported_authorizes_exact_context": w.authorize(supported, task_id="demo-task", transmission_id="tx-supported", world_epoch=3),
            "supported_rejected_when_stale": not w.authorize(supported, task_id="demo-task", transmission_id="tx-supported", world_epoch=4),
            "contradicted_not_authorized": not w.authorize(contradicted, task_id="demo-task", transmission_id="tx-overfit", world_epoch=3),
            "field_mutation_detected": not tampered.verify_checksum(),
        },
        "boundary": "receipt hashes detect accidental/unsynchronized mutation; they are not digital signatures against an actor able to recompute hashes",
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
