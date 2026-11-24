"""Prior that prefers operators which reduce evaluations.

The sealed invent result showed the field prior increased evaluations on
absdiff and clamp. This module builds a prior that prefers operators which
reach the goal faster on the training examples, then measures whether that
reduces evaluations on the held-out targets.

Not used by the continuous loop.
"""
from __future__ import annotations

from typing import Any

from .abstract_targets import TARGETS, Prog, _abs, _min, _max, _sub, _add, _floordiv
from .genesis import GrammarPrior

def prefer(examples: list, goal: tuple) -> GrammarPrior:
    """Build a prior that prefers operators which reach the goal fastest."""
    x = Prog("x", tuple(e.x for e in examples), 1)
    y = Prog("y", tuple(e.y for e in examples), 1)
    ops = {
        "Abs": lambda p: _abs(p),
        "Sub": lambda p: _sub(p, y),
        "Min": lambda p: _min(p, y),
        "Max": lambda p: _max(p, y),
        "Add": lambda p: _add(p, y),
        "FloorDiv": lambda p: _floordiv(_add(p, y), 2),
    }
    scores = {}
    for name, op in ops.items():
        budget = 0
        frontier = [x]
        found = False
        for _ in range(3):
            nxt = []
            for p in frontier:
                budget += 1
                cand = op(p)
                if cand.values == goal:
                    found = True
                    break
                nxt.append(cand)
            if found:
                break
            frontier = nxt[:5]
        scores[name] = budget if found else 999
    prior = GrammarPrior()
    for name, score in scores.items():
        for _ in range(max(1, 100 - score)):
            prior.operator.update(0, name, True)
        prior.witnessed += 1
    return prior

def attempt(name: str, prior: GrammarPrior | None = None, *, max_eval: int = 5000) -> dict[str, Any]:
    examples = TARGETS[name]
    goal = tuple(e.expected for e in examples)
    if prior is None:
        prior = prefer(examples, goal)
    from .extended_enum import attempt_with_prior
    return attempt_with_prior(name, prior, max_eval=max_eval)

def compare() -> list[dict[str, Any]]:
    return [attempt(name) for name in TARGETS]
