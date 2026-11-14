from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple

from .python_operators import PY_FAMILIES


@dataclass
class SenseCounts:
    success: int = 0
    failure: int = 0

    @property
    def mean(self) -> float:
        return (self.success + 1.0) / (self.success + self.failure + 2.0)


@dataclass
class SensoryOperatorLearner:
    contextual: bool = True
    families: tuple[str, ...] = PY_FAMILIES
    global_counts: Dict[str, SenseCounts] = field(default_factory=dict)
    context_counts: Dict[Tuple[int, str], SenseCounts] = field(default_factory=dict)

    def _g(self, family: str) -> SenseCounts:
        return self.global_counts.setdefault(family, SenseCounts())

    def _c(self, signature: int, family: str) -> SenseCounts:
        return self.context_counts.setdefault((signature, family), SenseCounts())

    def update(self, signature: int, family: str, success: bool) -> None:
        for counts in (self._g(family), self._c(signature, family)):
            if success:
                counts.success += 1
            else:
                counts.failure += 1

    def score(self, signature: int, family: str) -> float:
        g = self._g(family).mean
        if not self.contextual:
            return g
        c = self._c(signature, family)
        n = c.success + c.failure
        weight = n / (n + 3.0)
        return weight * c.mean + (1.0 - weight) * g

    def rank(self, signature: int) -> list[str]:
        order = {name: i for i, name in enumerate(self.families)}
        return sorted(self.families, key=lambda f: (-self.score(signature, f), order[f]))

    def snapshot(self) -> dict:
        return {
            "contextual": self.contextual,
            "families": list(self.families),
            "global": {k: vars(v) for k, v in sorted(self.global_counts.items())},
            "contexts": {f"{sig}:{fam}": vars(v) for (sig, fam), v in sorted(self.context_counts.items())},
        }
