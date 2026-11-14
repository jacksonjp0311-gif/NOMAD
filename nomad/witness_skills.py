from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .skills import SkillEvidence, SkillRegistry
from .witness import Witness, WitnessReceipt


@dataclass(frozen=True)
class IngestResult:
    accepted_provenance: bool
    evidence_supported: bool | None
    skill: SkillEvidence | None
    reason: str


class WitnessedSkillRegistry:
    """Durable skill memory that accepts consequence evidence only via WITNESS.

    This wrapper removes the caller-controlled `challenge_passed` boolean from
    the promotion boundary.  Callers may still choose goals and candidate
    transformations; they cannot promote a skill merely by asserting success.
    """

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or SkillRegistry()

    def ingest(
        self,
        *,
        witness: Witness,
        receipt: WitnessReceipt,
        signature: int,
        sequence: Iterable[str],
        task_id: str,
        transmission_id: str,
        world_epoch: int,
    ) -> IngestResult:
        if not witness.valid_for_context(
            receipt,
            task_id=task_id,
            transmission_id=transmission_id,
            world_epoch=world_epoch,
        ):
            return IngestResult(False, None, None, "receipt integrity/provenance mismatch")
        record = self.registry.record_challenge(
            signature=int(signature),
            sequence=tuple(sequence),
            task_id=task_id,
            challenge_passed=receipt.supported,
            evaluator=receipt.witness_id,
        )
        return IngestResult(True, receipt.supported, record, "supported" if receipt.supported else "contradicted")

    def promoted(self) -> list[SkillEvidence]:
        return self.registry.promoted()

    def snapshot(self) -> dict:
        payload = self.registry.snapshot()
        payload["schema"] = "nomad.v0.6.witnessed-skill-registry.v1"
        payload["promotion_authority"] = "WITNESS receipts only"
        return payload
