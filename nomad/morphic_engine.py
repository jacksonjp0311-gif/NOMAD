from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .morphic import MORPHIC_FAMILIES, MorphicLearner, Observation, effect_signature
from .morphic_adapters import ADAPTERS
from .morphic_benchmarks import MorphicTask


@dataclass(frozen=True)
class MorphicResult:
    solved: bool
    challenge_correct: bool
    attempts: int
    chosen_family: str | None
    signature: int


def _same(a: tuple[float, ...], b: tuple[float, ...], tol: float = 1e-9) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


class MorphicEngine:
    def __init__(
        self,
        learner: MorphicLearner | None = None,
        *,
        fixed_order: Iterable[str] | None = None,
        learn: bool = False,
    ) -> None:
        self.learner = learner or MorphicLearner()
        self.fixed_order = tuple(fixed_order) if fixed_order is not None else None
        self.learn = learn

    def solve(self, task: MorphicTask) -> MorphicResult:
        adapter = ADAPTERS[task.domain]
        current = adapter.observe(task.artifact, task.public_inputs)
        target = adapter.observe(task.target_artifact, task.public_inputs)
        sig = effect_signature(Observation(current, target)).key
        ranking = list(self.fixed_order) if self.fixed_order is not None else self.learner.rank(sig)

        for attempt, family in enumerate(ranking, start=1):
            candidate = adapter.transform(task.artifact, family)
            predicted = adapter.observe(candidate, task.public_inputs)
            success = _same(predicted, target)
            if self.learn:
                self.learner.update(sig, family, success)
            if not success:
                continue
            challenge_pred = adapter.observe(candidate, task.challenge_inputs)
            challenge_target = adapter.observe(task.target_artifact, task.challenge_inputs)
            return MorphicResult(True, _same(challenge_pred, challenge_target), attempt, family, sig)
        return MorphicResult(False, False, len(ranking), None, sig)
