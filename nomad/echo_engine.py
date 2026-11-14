from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .echo_map import EchoMapEncoder
from .morphic import MORPHIC_FAMILIES
from .morphic_adapters import ADAPTERS
from .morphic_benchmarks import MorphicTask


def _same(a: tuple[float, ...], b: tuple[float, ...], tol: float = 1e-9) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


@dataclass(frozen=True)
class EchoResult:
    solved: bool
    challenge_correct: bool
    attempts: int
    chosen_family: str | None
    echo_bit_key: int


class EchoMapEngine:
    def __init__(self, encoder: EchoMapEncoder, *, fixed_order: Iterable[str] | None = None) -> None:
        self.encoder = encoder
        self.fixed_order = tuple(fixed_order) if fixed_order is not None else None

    def solve(self, task: MorphicTask) -> EchoResult:
        adapter = ADAPTERS[task.domain]
        current = adapter.observe(task.artifact, task.public_inputs)
        target = adapter.observe(task.target_artifact, task.public_inputs)
        point = self.encoder.encode(current, target)
        ranking = list(self.fixed_order) if self.fixed_order is not None else self.encoder.rank(current, target)
        for attempt, family in enumerate(ranking, start=1):
            candidate = adapter.transform(task.artifact, family)
            public_pred = adapter.observe(candidate, task.public_inputs)
            if not _same(public_pred, target):
                continue
            challenge_pred = adapter.observe(candidate, task.challenge_inputs)
            challenge_target = adapter.observe(task.target_artifact, task.challenge_inputs)
            return EchoResult(True, _same(challenge_pred, challenge_target), attempt, family, point.bit_key)
        return EchoResult(False, False, len(MORPHIC_FAMILIES), None, point.bit_key)
