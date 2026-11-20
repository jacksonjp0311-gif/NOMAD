"""Staleness policy for versioned field packets.

Idea credited to NVIDIA Molt (Apache-2.0): bounded asynchrony between
rollout and training (``async_queue_size`` slots in
``molt/trainer/rl_trainer.py``) and per-unit off-policy gating
(``is_correction_mode`` mask/clip/trunc in ``molt/models/loss.py`` and
``importance_weights`` in ``molt/models/score_centering.py``). This is an
independent pure-Python re-implementation; no Molt code is copied.

NOMAD has no probability ratio between a sampler and a learner. The only
off-policy quantity is *lag*: how many field versions the learner has
advanced since an awake attempt read the field. The weight below is a
staleness discount, not a true importance-sampling correction. GrammarPrior
counts are integers, so in this version the weight only gates (apply or
reject); it does not scale counts.
"""
from __future__ import annotations

from dataclasses import dataclass

MODES = ("mask", "decay", "trunc", "clip")


def importance_weight(ratio: float, mode: str = "none", low: float | None = None,
                      high: float | None = None) -> float:
    """Scalar ``f(ratio)``: none -> 1, trunc -> min(r, high), clip -> clamp, mask -> r or 0."""
    if mode == "none":
        return 1.0
    if mode == "trunc":
        return min(ratio, high if high is not None else ratio)
    if mode == "clip":
        lo = low if low is not None else ratio
        hi = high if high is not None else ratio
        return max(lo, min(hi, ratio))
    if mode == "mask":
        lo = low if low is not None else float("-inf")
        hi = high if high is not None else float("inf")
        return ratio if lo <= ratio <= hi else 0.0
    raise ValueError(f"unknown importance weight mode {mode!r}")


@dataclass(frozen=True)
class StalenessPolicy:
    """How the single learner treats a packet produced under an older field.

    max_lag:    packets older than this many versions are rejected (bounded staleness).
    mode:       mask  -> weight 1 inside the bound, 0 outside
                decay -> weight decay**lag inside the bound
                trunc -> like decay but never below min_weight inside the bound
                clip  -> decay clamped into [min_weight, 1]
    decay:      per-version discount for decay/trunc/clip.
    min_weight: a packet is applied only when its weight >= min_weight.
    """
    max_lag: int = 2
    mode: str = "mask"
    decay: float = 0.5
    min_weight: float = 0.25

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if self.max_lag < 0:
            raise ValueError("max_lag must be >= 0")
        if not 0.0 < self.decay <= 1.0:
            raise ValueError("decay must be in (0, 1]")

    def weight(self, lag: int) -> float:
        if lag < 0:
            # A packet from a future version means the version file was rolled
            # back or edited. Refuse it rather than guess.
            return 0.0
        if lag > self.max_lag:
            return 0.0
        if self.mode == "mask":
            return 1.0
        raw = self.decay ** lag
        if self.mode == "decay":
            return raw
        if self.mode == "trunc":
            return max(raw, self.min_weight)
        return importance_weight(raw, "clip", self.min_weight, 1.0)

    def decide(self, lag: int) -> tuple[bool, float, str | None]:
        """Return (apply, weight, drop_reason)."""
        if lag < 0:
            return False, 0.0, "future_version"
        w = self.weight(lag)
        if lag > self.max_lag:
            return False, 0.0, "stale"
        if w < self.min_weight:
            return False, w, "stale_discounted"
        return True, w, None
