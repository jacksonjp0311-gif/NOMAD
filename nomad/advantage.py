"""Group baselines and informative-group filtering for twin outcomes.

Ideas credited to NVIDIA Molt (Apache-2.0): the advantage-estimator
registry in ``molt/trainer/algorithm/advantage.py`` (GRPO, Dr.GRPO, RLOO,
FlashREINFORCE baselines) and the DAPO-style dynamic filter with pre-filter
pass/fail statistics in ``molt/trainer/rollout/samples_generator.py``.
Independent pure-Python re-implementation over plain floats; no tensors.

In NOMAD a "group" is all attempts on one task identity (for a twin pair:
control and treatment). A group where every attempt passed or every attempt
failed carries no contrast. It is not evidence for or against the field.
These numbers describe the twin record; they do not certify anything.
"""
from __future__ import annotations

from math import sqrt
from typing import Callable, Iterable, Sequence

Estimator = Callable[[Sequence[float]], list[float]]
_REGISTRY: dict[str, Estimator] = {}


def register(name: str) -> Callable[[Estimator], Estimator]:
    def deco(fn: Estimator) -> Estimator:
        _REGISTRY[name] = fn
        return fn
    return deco


def estimator(name: str) -> Estimator:
    if name not in _REGISTRY:
        raise KeyError(f"unknown estimator {name!r}; have {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


@register("dr_grpo")
def dr_grpo(rewards: Sequence[float]) -> list[float]:
    """Group-mean baseline, no std scaling."""
    m = _mean(rewards)
    return [r - m for r in rewards]


@register("grpo")
def grpo(rewards: Sequence[float]) -> list[float]:
    """(r - mean) / (sample std + eps); a singleton group has std 0."""
    m = _mean(rewards)
    n = len(rewards)
    std = sqrt(sum((r - m) ** 2 for r in rewards) / (n - 1)) if n > 1 else 0.0
    return [(r - m) / (std + 1e-9) for r in rewards]


@register("rloo")
def rloo(rewards: Sequence[float]) -> list[float]:
    """Leave-one-out baseline; a singleton keeps its raw reward."""
    n = len(rewards)
    if n <= 1:
        return list(rewards)
    s = sum(rewards)
    return [r - (s - r) / (n - 1) for r in rewards]


@register("flash_reinforce")
def flash_reinforce(rewards: Sequence[float]) -> list[float]:
    """Whole-batch mean baseline (use on a flat batch, not per group)."""
    return dr_grpo(rewards)


def informative(rewards: Sequence[float], low: float = 0.0, high: float = 1.0) -> bool:
    """False when the group is uniform at the floor or ceiling (all fail / all pass)."""
    if not rewards:
        return False
    m = _mean(rewards)
    return low < m < high


def group_stats(groups: Iterable[Sequence[float]], low: float = 0.0, high: float = 1.0) -> dict[str, float]:
    """Pre-filter statistics: true pass rate over all attempts, plus all-pass/all-fail/mixed rates."""
    n_groups = 0
    all_pass = all_fail = mixed = 0
    total = 0.0
    count = 0
    for g in groups:
        g = list(g)
        if not g:
            continue
        n_groups += 1
        total += sum(g)
        count += len(g)
        m = _mean(g)
        if m >= high:
            all_pass += 1
        elif m <= low:
            all_fail += 1
        else:
            mixed += 1
    if n_groups == 0:
        return {"groups": 0, "pass_rate": 0.0, "all_pass_rate": 0.0, "all_fail_rate": 0.0, "informative_rate": 0.0}
    return {
        "groups": n_groups,
        "pass_rate": total / count,
        "all_pass_rate": all_pass / n_groups,
        "all_fail_rate": all_fail / n_groups,
        "informative_rate": mixed / n_groups,
    }


def twin_summary(rows: Iterable[dict], name: str = "rloo") -> dict[str, object]:
    """Summarise scoreboard rows (each a control/treatment pair).

    Returns pre-filter stats, the count of informative pairs, and the mean
    treatment advantage over informative pairs under the chosen estimator.
    For a two-arm pair, rloo/dr_grpo give the treatment advantage
    (t - c) and (t - c) / 2; the sign is what matters.
    """
    est = estimator(name)
    groups = []
    adv = []
    for row in rows:
        if "treatment" not in row or "control" not in row:
            continue
        g = [float(bool(row["control"])), float(bool(row["treatment"]))]
        groups.append(g)
        if informative(g):
            adv.append(est(g)[1])
    stats = group_stats(groups)
    return {
        "estimator": name,
        **stats,
        "informative_pairs": len(adv),
        "mean_treatment_advantage": (sum(adv) / len(adv)) if adv else None,
        "note": "Descriptive only. Uniform pairs carry no contrast and are excluded from the advantage.",
    }
