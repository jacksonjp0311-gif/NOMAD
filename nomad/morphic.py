from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Protocol, Tuple

MORPHIC_FAMILIES = ("shift_up", "shift_down", "amplify", "dampen", "invert")


@dataclass(frozen=True)
class EffectSignature:
    """Substrate-independent description of how present behavior misses a target.

    The signature deliberately describes effect geometry, not source tokens or
    domain names. This lets evidence collected in one adapter be reused by
    another adapter without sharing syntax.
    """

    residual_sign: int
    residual_constant: int
    ratio_class: int
    inversion: int
    zero_agreement: int

    @property
    def key(self) -> int:
        # 2 bits residual sign, then four small categorical fields.
        return (
            (self.residual_sign & 0b11)
            | ((self.residual_constant & 0b1) << 2)
            | ((self.ratio_class & 0b11) << 3)
            | ((self.inversion & 0b1) << 5)
            | ((self.zero_agreement & 0b1) << 6)
        )


@dataclass(frozen=True)
class Observation:
    current: tuple[float, ...]
    target: tuple[float, ...]


def effect_signature(observation: Observation, *, tol: float = 1e-9) -> EffectSignature:
    current = observation.current
    target = observation.target
    if len(current) != len(target) or not current:
        raise ValueError("current and target must have equal non-zero length")

    residuals = [t - c for c, t in zip(current, target)]
    pos = sum(r > tol for r in residuals)
    neg = sum(r < -tol for r in residuals)
    if pos and not neg:
        residual_sign = 1
    elif neg and not pos:
        residual_sign = 2
    elif not pos and not neg:
        residual_sign = 0
    else:
        residual_sign = 3

    residual_constant = int(max(residuals) - min(residuals) <= tol)

    nonzero = [(c, t) for c, t in zip(current, target) if abs(c) > tol]
    ratio_class = 0
    if nonzero:
        ratios = [t / c for c, t in nonzero]
        if max(abs(r - 2.0) for r in ratios) <= tol:
            ratio_class = 1
        elif max(abs(r - 0.5) for r in ratios) <= tol:
            ratio_class = 2
        elif max(abs(r + 1.0) for r in ratios) <= tol:
            ratio_class = 3

    inversion = int(all(abs(t + c) <= tol for c, t in zip(current, target)))
    zero_agreement = int(all((abs(c) <= tol) == (abs(t) <= tol) for c, t in zip(current, target)))
    return EffectSignature(residual_sign, residual_constant, ratio_class, inversion, zero_agreement)


@dataclass
class Counts:
    success: int = 0
    failure: int = 0

    @property
    def n(self) -> int:
        return self.success + self.failure

    @property
    def mean(self) -> float:
        return (self.success + 1.0) / (self.success + self.failure + 2.0)


@dataclass
class MorphicLearner:
    """Learns reusable transformation priors from effect signatures.

    `contextual=False` is the global-frequency control. The contextual model
    shrinks sparse signature evidence toward the global estimate so transfer can
    help without granting one observation absolute authority.
    """

    families: tuple[str, ...] = MORPHIC_FAMILIES
    contextual: bool = True
    global_counts: Dict[str, Counts] = field(default_factory=dict)
    signature_counts: Dict[Tuple[int, str], Counts] = field(default_factory=dict)

    def _global(self, family: str) -> Counts:
        return self.global_counts.setdefault(family, Counts())

    def _local(self, signature: int, family: str) -> Counts:
        return self.signature_counts.setdefault((signature, family), Counts())

    def update(self, signature: int, family: str, success: bool) -> None:
        for c in (self._global(family), self._local(signature, family)):
            if success:
                c.success += 1
            else:
                c.failure += 1

    def score(self, signature: int, family: str) -> float:
        base = self._global(family).mean
        if not self.contextual:
            return base
        local = self._local(signature, family)
        weight = local.n / (local.n + 2.0)
        return weight * local.mean + (1.0 - weight) * base

    def rank(self, signature: int) -> list[str]:
        order = {name: i for i, name in enumerate(self.families)}
        return sorted(self.families, key=lambda f: (-self.score(signature, f), order[f]))

    def snapshot(self) -> dict:
        return {
            "schema": "nomad.v0.4.morphic-learner.v1",
            "contextual": self.contextual,
            "families": list(self.families),
            "global": {f: vars(c) for f, c in sorted(self.global_counts.items())},
            "signature": {
                f"{sig}:{fam}": vars(c)
                for (sig, fam), c in sorted(self.signature_counts.items())
            },
        }


class Adapter(Protocol):
    name: str

    def observe(self, artifact: object, inputs: tuple[float, ...]) -> tuple[float, ...]: ...
    def transform(self, artifact: object, family: str) -> object: ...
    def describe(self, artifact: object) -> str: ...
