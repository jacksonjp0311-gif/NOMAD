from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable
import math

from .morphic import MORPHIC_FAMILIES


@dataclass(frozen=True)
class EchoRecord:
    current: tuple[float, ...]
    target: tuple[float, ...]
    verified_family: str


@dataclass(frozen=True)
class EchoPoint:
    coordinates: tuple[float, ...]
    bit_key: int


def _avg(values: Iterable[float]) -> float:
    vals = tuple(values)
    return sum(vals) / len(vals) if vals else 0.0


def _spread(values: Iterable[float]) -> float:
    vals = tuple(values)
    return max(vals) - min(vals) if vals else 0.0


def _rms(values: Iterable[float]) -> float:
    vals = tuple(values)
    return math.sqrt(sum(v * v for v in vals) / len(vals)) if vals else 0.0


def relation_bank(current: tuple[float, ...], target: tuple[float, ...]) -> dict[str, float]:
    """Generate a generic relation bank from paired observations.

    No transformation names or domain identifiers enter this function.  The
    supplied grammar is intentionally generic: pairwise difference, sum,
    absolute difference, ratio and product, plus raw current/target channels;
    each is reduced by mean/spread/RMS.  v0.5 learns which coordinates matter.
    """
    if len(current) != len(target) or not current:
        raise ValueError("current and target must have equal non-zero length")
    eps = 1e-12
    difference = tuple(t - c for c, t in zip(current, target))
    summed = tuple(t + c for c, t in zip(current, target))
    absolute = tuple(abs(t - c) for c, t in zip(current, target))
    ratio = tuple(t / c for c, t in zip(current, target) if abs(c) > eps)
    product = tuple(t * c for c, t in zip(current, target))
    channels = {
        "difference": difference,
        "sum": summed,
        "absolute": absolute,
        "ratio": ratio,
        "product": product,
        "current": current,
        "target": target,
    }
    out: dict[str, float] = {}
    for channel, values in channels.items():
        out[f"{channel}.mean"] = _avg(values)
        out[f"{channel}.spread"] = _spread(values)
        out[f"{channel}.rms"] = _rms(values)
    return out


@dataclass
class EchoMapEncoder:
    """A small learned cross-substrate representation.

    Feature choice is learned from verified transformation outcomes using a
    Fisher-style between/within-family separation score.  Thresholds are not
    hand-coded.  The learned selected relations are standardized and converted
    to both continuous coordinates (for distance ranking) and a compact sign
    bit-key (for Bitwork-style identity/caching experiments).
    """

    dimensions: int = 4
    selected: tuple[str, ...] = ()
    center: dict[str, float] | None = None
    scale: dict[str, float] | None = None
    prototypes: dict[str, tuple[float, ...]] | None = None
    feature_scores: dict[str, float] | None = None

    def fit(self, records: Iterable[EchoRecord]) -> "EchoMapEncoder":
        rows = list(records)
        if not rows:
            raise ValueError("at least one verified record is required")
        families = {r.verified_family for r in rows}
        missing = set(MORPHIC_FAMILIES) - families
        if missing:
            raise ValueError(f"training evidence missing families: {sorted(missing)}")

        vectors = [(relation_bank(r.current, r.target), r.verified_family) for r in rows]
        names = tuple(vectors[0][0])
        scores: dict[str, float] = {}
        for name in names:
            values = [v[name] for v, _ in vectors]
            grand = mean(values)
            between = 0.0
            within = 0.0
            for family in MORPHIC_FAMILIES:
                local = [v[name] for v, label in vectors if label == family]
                local_mean = mean(local)
                between += len(local) * (local_mean - grand) ** 2
                within += sum((x - local_mean) ** 2 for x in local)
            scores[name] = between / (within + 1e-9)

        self.selected = tuple(sorted(names, key=lambda n: (-scores[n], n))[: self.dimensions])
        self.feature_scores = scores
        self.center = {name: mean([v[name] for v, _ in vectors]) for name in self.selected}
        self.scale = {}
        for name in self.selected:
            mu = self.center[name]
            sd = math.sqrt(mean([(v[name] - mu) ** 2 for v, _ in vectors]))
            self.scale[name] = sd if sd > 1e-12 else 1.0

        prototypes: dict[str, tuple[float, ...]] = {}
        for family in MORPHIC_FAMILIES:
            local = [v for v, label in vectors if label == family]
            prototypes[family] = tuple(
                mean([(v[name] - self.center[name]) / self.scale[name] for v in local])
                for name in self.selected
            )
        self.prototypes = prototypes
        return self

    def _require_fit(self) -> None:
        if not self.selected or self.center is None or self.scale is None or self.prototypes is None:
            raise RuntimeError("EchoMapEncoder must be fit before use")

    def encode(self, current: tuple[float, ...], target: tuple[float, ...]) -> EchoPoint:
        self._require_fit()
        values = relation_bank(current, target)
        coords = tuple((values[name] - self.center[name]) / self.scale[name] for name in self.selected)
        bit_key = 0
        for i, value in enumerate(coords):
            bit_key |= int(value >= 0.0) << i
        return EchoPoint(coords, bit_key)

    def rank(self, current: tuple[float, ...], target: tuple[float, ...]) -> list[str]:
        point = self.encode(current, target)
        order = {name: i for i, name in enumerate(MORPHIC_FAMILIES)}
        return sorted(
            MORPHIC_FAMILIES,
            key=lambda family: (
                sum((a - b) ** 2 for a, b in zip(point.coordinates, self.prototypes[family])),
                order[family],
            ),
        )

    def snapshot(self) -> dict:
        self._require_fit()
        return {
            "schema": "nomad.v0.5.echo-map.v1",
            "dimensions": self.dimensions,
            "selected": list(self.selected),
            "center": self.center,
            "scale": self.scale,
            "prototypes": {k: list(v) for k, v in self.prototypes.items()},
            "selected_feature_scores": {name: self.feature_scores[name] for name in self.selected},
            "bit_encoding": "sign of standardized learned coordinates; ranking uses continuous prototype distance",
        }
