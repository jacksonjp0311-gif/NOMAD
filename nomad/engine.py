from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .bitstate import encode_failure
from .learner import ContextualOperatorLearner
from .ledger import EvidenceLedger
from .model import Candidate, CodeTask
from .operators import FAMILIES, generate_candidates
from .safe_eval import evaluate


@dataclass(frozen=True)
class SolveResult:
    solved: bool
    source: str
    attempts: int
    operator_family: str | None
    signature: int


def passes(task: CodeTask, source: str) -> bool:
    try:
        return all(evaluate(source, ex.inputs) == ex.expected for ex in task.examples)
    except Exception:
        return False


class NomadEngine:
    def __init__(
        self,
        learner: ContextualOperatorLearner | None = None,
        fixed_order: Iterable[str] | None = None,
        learn: bool = True,
        ledger: EvidenceLedger | None = None,
    ) -> None:
        self.learner = learner or ContextualOperatorLearner(contextual=True)
        self.fixed_order = tuple(fixed_order) if fixed_order is not None else None
        self.learn = learn
        self.ledger = ledger

    def solve(self, task: CodeTask, max_attempts: int = 64) -> SolveResult:
        state = encode_failure(task)
        if passes(task, task.source):
            return SolveResult(True, task.source, 0, None, state.key)

        grouped = generate_candidates(task.source)
        families = list(self.fixed_order) if self.fixed_order is not None else self.learner.rank(state.key)
        attempts = 0
        for family in families:
            family_solved = False
            for candidate in grouped.get(family, []):
                if attempts >= max_attempts:
                    return SolveResult(False, task.source, attempts, None, state.key)
                attempts += 1
                ok = passes(task, candidate.source)
                if ok:
                    family_solved = True
                    if self.learn:
                        self.learner.update(state.key, family, True)
                        if self.ledger is not None:
                            self.ledger.append({"signature": state.key, "family": family, "success": True, "attempts": attempts})
                    return SolveResult(True, candidate.source, attempts, family, state.key)
            if self.learn and grouped.get(family):
                self.learner.update(state.key, family, False)
                if self.ledger is not None:
                    self.ledger.append({"signature": state.key, "family": family, "success": False, "attempts": attempts})
        return SolveResult(False, task.source, attempts, None, state.key)
