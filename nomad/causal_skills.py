from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Iterable

from .witness import Witness, WitnessReceipt


@dataclass(frozen=True)
class CausalObservation:
    task_id: str
    family: str
    context: frozenset[str]
    supported: bool
    receipt_hash: str


@dataclass(frozen=True)
class CausalSkill:
    family: str
    preconditions: tuple[str, ...]
    positives: int
    negatives: int
    matched_positives: int
    matched_negatives: int
    precision: float
    coverage: float
    status: str
    positive_tasks: tuple[str, ...]
    counterexample_tasks: tuple[str, ...]

    def applies(self, context: Iterable[str]) -> bool:
        values = set(context)
        return all(p in values for p in self.preconditions)

    @property
    def expected_effect(self) -> str:
        return "witnessed target match"


class CausalSkillRegistry:
    """Learn conservative preconditions for witnessed transformation families.

    The learner searches conjunctions of *observed* predicates.  A rule is
    promoted only when it has enough positive support and no observed negative
    example matching the same conjunction.  This is intentionally conservative:
    absence of a counterexample is not treated as proof of universal causality.
    """

    def __init__(self, *, min_support: int = 4, max_terms: int = 3) -> None:
        self.min_support = int(min_support)
        self.max_terms = int(max_terms)
        self.observations: list[CausalObservation] = []
        self.skills: dict[str, CausalSkill] = {}

    def ingest(
        self,
        *,
        witness: Witness,
        receipt: WitnessReceipt,
        context: Iterable[str],
        family: str,
        task_id: str,
        transmission_id: str,
        world_epoch: int,
    ) -> bool:
        if not witness.valid_for_context(
            receipt,
            task_id=task_id,
            transmission_id=transmission_id,
            world_epoch=world_epoch,
        ):
            return False
        self.observations.append(
            CausalObservation(
                task_id=task_id,
                family=str(family),
                context=frozenset(context),
                supported=bool(receipt.supported),
                receipt_hash=receipt.receipt_hash,
            )
        )
        self._rebuild_family(str(family))
        return True

    def _rebuild_family(self, family: str) -> None:
        rows = [r for r in self.observations if r.family == family]
        positives = [r for r in rows if r.supported]
        negatives = [r for r in rows if not r.supported]
        if not positives:
            self.skills.pop(family, None)
            return

        predicate_pool = sorted(set().union(*(r.context for r in positives)))
        candidates: list[tuple[tuple[float, float, int, int, tuple[str, ...]], tuple[str, ...], list[CausalObservation], list[CausalObservation]]] = []
        max_terms = min(self.max_terms, len(predicate_pool))
        for width in range(1, max_terms + 1):
            for terms in combinations(predicate_pool, width):
                p_match = [r for r in positives if all(t in r.context for t in terms)]
                if not p_match:
                    continue
                n_match = [r for r in negatives if all(t in r.context for t in terms)]
                precision = len(p_match) / (len(p_match) + len(n_match))
                coverage = len(p_match) / len(positives)
                # Prefer perfect precision, then coverage/support, then simpler rules.
                score = (precision, coverage, len(p_match), -width, terms)
                candidates.append((score, terms, p_match, n_match))

        if not candidates:
            self.skills.pop(family, None)
            return
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, terms, p_match, n_match = candidates[0]
        precision = len(p_match) / (len(p_match) + len(n_match))
        coverage = len(p_match) / len(positives)
        promoted = len(p_match) >= self.min_support and len(n_match) == 0
        status = "promoted" if promoted else "provisional"
        self.skills[family] = CausalSkill(
            family=family,
            preconditions=tuple(terms),
            positives=len(positives),
            negatives=len(negatives),
            matched_positives=len(p_match),
            matched_negatives=len(n_match),
            precision=precision,
            coverage=coverage,
            status=status,
            positive_tasks=tuple(sorted({r.task_id for r in p_match})),
            counterexample_tasks=tuple(sorted({r.task_id for r in n_match})),
        )

    def promoted(self) -> list[CausalSkill]:
        return sorted((s for s in self.skills.values() if s.status == "promoted"), key=lambda s: s.family)

    def applicable(self, context: Iterable[str], available_families: Iterable[str] | None = None) -> list[CausalSkill]:
        available = None if available_families is None else set(available_families)
        skills = [
            s for s in self.promoted()
            if s.applies(context) and (available is None or s.family in available)
        ]
        skills.sort(key=lambda s: (s.precision, s.coverage, s.matched_positives, -len(s.preconditions)), reverse=True)
        return skills

    def rank_families(self, context: Iterable[str], available_families: Iterable[str]) -> list[str]:
        available = list(dict.fromkeys(available_families))
        preferred = [s.family for s in self.applicable(context, available)]
        return preferred + [f for f in available if f not in preferred]

    def snapshot(self) -> dict[str, object]:
        return {
            "schema": "nomad.v0.7.causal-skills.v1",
            "min_support": self.min_support,
            "max_terms": self.max_terms,
            "observation_count": len(self.observations),
            "skills": [asdict(s) for s in sorted(self.skills.values(), key=lambda s: s.family)],
        }
