from __future__ import annotations

from dataclasses import replace
import unittest

from nomad.witness import ConsequenceClaim, Witness
from nomad.witness_skills import WitnessedSkillRegistry
from nomad.simulation_v6 import _public_overfit_outputs


class WitnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.witness = Witness("test-witness")
        self.common = dict(
            task_id="task-1",
            transmission_id="tx-1",
            world_epoch=7,
            current_public=(0.0, 1.0),
            target_public=(1.0, 2.0),
            current_challenge=(2.0, 3.0),
            target_challenge=(3.0, 4.0),
        )

    def test_supported_receipt_authorizes_exact_context(self) -> None:
        receipt = self.witness.attest(
            **self.common,
            candidate_public=(1.0, 2.0),
            candidate_challenge=(3.0, 4.0),
        )
        self.assertTrue(receipt.supported)
        self.assertTrue(receipt.verify_checksum())
        self.assertTrue(self.witness.authorize(receipt, task_id="task-1", transmission_id="tx-1", world_epoch=7))

    def test_contradicted_challenge_cannot_authorize(self) -> None:
        receipt = self.witness.attest(
            **self.common,
            candidate_public=(1.0, 2.0),
            candidate_challenge=(3.0, 4.25),
        )
        self.assertFalse(receipt.supported)
        self.assertEqual(receipt.verdict, "contradicted")
        self.assertFalse(self.witness.authorize(receipt, task_id="task-1", transmission_id="tx-1", world_epoch=7))

    def test_stale_epoch_is_rejected(self) -> None:
        receipt = self.witness.attest(
            **self.common,
            candidate_public=(1.0, 2.0),
            candidate_challenge=(3.0, 4.0),
        )
        self.assertFalse(self.witness.authorize(receipt, task_id="task-1", transmission_id="tx-1", world_epoch=8))

    def test_mutated_field_breaks_checksum(self) -> None:
        receipt = self.witness.attest(
            **self.common,
            candidate_public=(1.0, 2.0),
            candidate_challenge=(3.0, 4.0),
        )
        changed = replace(receipt, task_id="other")
        self.assertFalse(changed.verify_checksum())

    def test_skill_registry_cannot_take_caller_success_boolean(self) -> None:
        receipt = self.witness.attest(
            **self.common,
            candidate_public=(1.0, 2.0),
            candidate_challenge=(3.0, 4.0),
        )
        registry = WitnessedSkillRegistry()
        result = registry.ingest(
            witness=self.witness,
            receipt=receipt,
            signature=5,
            sequence=("shift_up",),
            task_id="task-1",
            transmission_id="tx-1",
            world_epoch=7,
        )
        self.assertTrue(result.accepted_provenance)
        self.assertTrue(result.evidence_supported)
        self.assertIsNotNone(result.skill)

    def test_stale_receipt_does_not_mutate_skill_registry(self) -> None:
        receipt = self.witness.attest(
            **self.common,
            candidate_public=(1.0, 2.0),
            candidate_challenge=(3.0, 4.0),
        )
        registry = WitnessedSkillRegistry()
        result = registry.ingest(
            witness=self.witness,
            receipt=receipt,
            signature=5,
            sequence=("shift_up",),
            task_id="task-1",
            transmission_id="tx-1",
            world_epoch=8,
        )
        self.assertFalse(result.accepted_provenance)
        self.assertEqual(registry.registry.records, {})

    def test_public_overfit_is_exact_only_on_public_points(self) -> None:
        xs = (-2.0, -1.0, 1.0, 3.0)
        ys = tuple(2.0 * x + 1.0 for x in xs)
        public_pred = _public_overfit_outputs(xs, ys, xs)
        self.assertEqual(public_pred, ys)
        held = (0.0, 2.0)
        held_target = tuple(2.0 * x + 1.0 for x in held)
        held_pred = _public_overfit_outputs(xs, ys, held)
        self.assertNotEqual(held_pred, held_target)

    def test_contradicted_receipt_contests_skill(self) -> None:
        receipt = self.witness.attest(
            **self.common,
            candidate_public=(1.0, 2.0),
            candidate_challenge=(3.0, 9.0),
        )
        registry = WitnessedSkillRegistry()
        result = registry.ingest(
            witness=self.witness,
            receipt=receipt,
            signature=5,
            sequence=("public_overfit",),
            task_id="task-1",
            transmission_id="tx-1",
            world_epoch=7,
        )
        self.assertTrue(result.accepted_provenance)
        self.assertFalse(result.evidence_supported)
        self.assertEqual(result.skill.status, "contested")


if __name__ == "__main__":
    unittest.main()
