from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from .python_operators import PY_FAMILIES
from .resonance import AST_MASK, PARSER_MASK, RUNTIME_MASK, ResonanceState


@dataclass
class ResonanceCounts:
    success: int = 0
    failure: int = 0

    @property
    def n(self) -> int:
        return self.success + self.failure

    @property
    def mean(self) -> float:
        return (self.success + 1.0) / (self.success + self.failure + 2.0)


@dataclass
class ResonanceOperatorLearner:
    """Hierarchical multi-sense learner.

    Detailed telemetry is allowed to refine a broad test-conditioned estimate,
    but sparse high-dimensional contexts fall back instead of erasing reusable
    lower-dimensional experience. This is the v0.3 answer to sensor-fragmentation.
    """

    families: tuple[str, ...] = PY_FAMILIES
    global_counts: Dict[str, ResonanceCounts] = field(default_factory=dict)
    test_counts: Dict[Tuple[int, str], ResonanceCounts] = field(default_factory=dict)
    error_counts: Dict[Tuple[int, str], ResonanceCounts] = field(default_factory=dict)
    full_counts: Dict[Tuple[int, str], ResonanceCounts] = field(default_factory=dict)

    def _get(self, table, key):
        return table.setdefault(key, ResonanceCounts())

    @staticmethod
    def _blend(local: ResonanceCounts, base: float, strength: float) -> float:
        weight = local.n / (local.n + strength)
        return weight * local.mean + (1.0 - weight) * base

    @staticmethod
    def _error_view(state: ResonanceState) -> int:
        sig = state.fusion_signature
        return sig & (PARSER_MASK | RUNTIME_MASK | AST_MASK)

    def update_state(self, state: ResonanceState, family: str, success: bool) -> None:
        keys = [
            (self.global_counts, family),
            (self.test_counts, (state.test_signature, family)),
            (self.full_counts, (state.fusion_signature, family)),
        ]
        if state.parser_bits or state.runtime_bits:
            keys.append((self.error_counts, (self._error_view(state), family)))
        for table, key in keys:
            c = self._get(table, key)
            if success:
                c.success += 1
            else:
                c.failure += 1

    def score_state(self, state: ResonanceState, family: str) -> float:
        g = self._get(self.global_counts, family).mean
        t = self._get(self.test_counts, (state.test_signature, family))
        score = self._blend(t, g, 3.0)

        if state.parser_bits or state.runtime_bits:
            e = self._get(self.error_counts, (self._error_view(state), family))
            score = self._blend(e, score, 3.0)

        # Full-state evidence gets a deliberately conservative influence. It can
        # sharpen a repeated sensory pattern but cannot dominate from one sample.
        f = self._get(self.full_counts, (state.fusion_signature, family))
        score = self._blend(f, score, 8.0)
        return score

    def rank_state(self, state: ResonanceState) -> list[str]:
        order = {name: i for i, name in enumerate(self.families)}
        return sorted(self.families, key=lambda f: (-self.score_state(state, f), order[f]))

    def snapshot(self) -> dict:
        def rows(table):
            out = {}
            for key, counts in sorted(table.items(), key=lambda kv: str(kv[0])):
                out[str(key)] = vars(counts)
            return out
        return {
            "schema": "nomad.v0.3.hierarchical-resonance-learner.v1",
            "families": list(self.families),
            "global": rows(self.global_counts),
            "test": rows(self.test_counts),
            "error_view": rows(self.error_counts),
            "full": rows(self.full_counts),
        }
