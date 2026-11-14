from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .ledger import EvidenceLedger


@dataclass
class SkillEvidence:
    signature: int
    sequence: tuple[str, ...]
    challenge_successes: int = 0
    challenge_failures: int = 0
    task_ids: set[str] = field(default_factory=set)
    evaluators: set[str] = field(default_factory=set)
    status: str = "candidate"

    def reconsider(self, min_challenges: int = 3, min_tasks: int = 3) -> None:
        if self.challenge_failures:
            self.status = "contested"
        elif self.challenge_successes >= min_challenges and len(self.task_ids) >= min_tasks:
            self.status = "promoted"
        elif self.challenge_successes:
            self.status = "provisional"
        else:
            self.status = "candidate"

    def payload(self) -> dict:
        return {
            "signature": self.signature,
            "sequence": list(self.sequence),
            "challenge_successes": self.challenge_successes,
            "challenge_failures": self.challenge_failures,
            "task_ids": sorted(self.task_ids),
            "evaluators": sorted(self.evaluators),
            "status": self.status,
        }


class SkillRegistry:
    """Externally attested sequence memory.

    NOMAD search is not allowed to certify its own skills. A sequence can only be
    promoted after a caller records outcomes from evidence that was withheld from
    repair-time search (for example, hidden challenge tests or an independent CI
    job). A later counterexample immediately marks a promoted skill contested.
    """

    def __init__(self, ledger: EvidenceLedger | None = None) -> None:
        self.records: dict[tuple[int, tuple[str, ...]], SkillEvidence] = {}
        self.ledger = ledger

    def record_challenge(
        self,
        *,
        signature: int,
        sequence: Iterable[str],
        task_id: str,
        challenge_passed: bool,
        evaluator: str,
    ) -> SkillEvidence:
        seq = tuple(sequence)
        key = (int(signature), seq)
        record = self.records.setdefault(key, SkillEvidence(signature=int(signature), sequence=seq))
        record.task_ids.add(task_id)
        record.evaluators.add(evaluator)
        if challenge_passed:
            record.challenge_successes += 1
        else:
            record.challenge_failures += 1
        old_status = record.status
        record.reconsider()
        if self.ledger is not None:
            self.ledger.append({
                "kind": "external_challenge",
                "task_id": task_id,
                "signature": int(signature),
                "sequence": list(seq),
                "challenge_passed": bool(challenge_passed),
                "evaluator": evaluator,
                "status_before": old_status,
                "status_after": record.status,
            })
        return record

    def promoted(self) -> list[SkillEvidence]:
        return [r for r in self.records.values() if r.status == "promoted"]

    def snapshot(self) -> dict:
        rows = [r.payload() for r in self.records.values()]
        rows.sort(key=lambda r: (r["signature"], r["sequence"]))
        return {"schema": "nomad.v0.2.skill-registry.v1", "records": rows}

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.snapshot(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, ledger: EvidenceLedger | None = None) -> "SkillRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        registry = cls(ledger=ledger)
        for raw in payload.get("records", []):
            record = SkillEvidence(
                signature=int(raw["signature"]),
                sequence=tuple(raw["sequence"]),
                challenge_successes=int(raw.get("challenge_successes", 0)),
                challenge_failures=int(raw.get("challenge_failures", 0)),
                task_ids=set(raw.get("task_ids", [])),
                evaluators=set(raw.get("evaluators", [])),
                status=str(raw.get("status", "candidate")),
            )
            record.reconsider()
            registry.records[(record.signature, record.sequence)] = record
        return registry
