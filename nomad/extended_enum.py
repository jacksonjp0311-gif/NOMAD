"""Extended enumerator with prior-ordered search.

When NOMAD_INVENT_ENUM=on, Abs, Min, and FloorDiv are available and the
prior changes their search order. Default OFF. Not used by the continuous
loop.

This is the measurement path for whether a prior can reduce evaluations on
absdiff, median, and clamp.
"""
from __future__ import annotations

import os
from typing import Any

from .abstract_targets import TARGETS, Prog, _abs, _min, _max, _sub, _add, _floordiv
from .genesis import GrammarPrior

def enabled() -> bool:
    return os.environ.get("NOMAD_INVENT_ENUM", "off").lower() == "on"

def attempt_with_prior(name: str, prior: GrammarPrior | None = None, *, max_eval: int = 5000) -> dict[str, Any]:
    """Search with Abs, Min, Max, Sub, Add, FloorDiv. Prior changes operator order."""
    examples = TARGETS[name]
    goal = tuple(e.expected for e in examples)
    x = Prog("x", tuple(e.x for e in examples), 1)
    y = Prog("y", tuple(e.y for e in examples), 1)
    atoms = [x, y]
    budget = 0
    for a in atoms:
        budget += 1
        if a.values == goal:
            return {"target": name, "candidate": a.text, "evaluations": budget, "fit": True,
                    "prior_witnessed": prior.witnessed if prior else 0}
    base_ops = ["Abs", "Sub", "Min", "Max", "Add", "FloorDiv"]
    if prior and prior.witnessed > 0:
        order = list(prior.order(0))
        ordered = [op for op in order if op in base_ops] + [op for op in base_ops if op not in order]
    else:
        ordered = base_ops
    ops = []
    for op in ordered:
        if op == "Abs":
            ops.append(lambda p: _abs(p))
        elif op == "Sub":
            ops.append(lambda p: _sub(p, y))
        elif op == "Min":
            ops.append(lambda p: _min(p, y))
        elif op == "Max":
            ops.append(lambda p: _max(p, y))
        elif op == "Add":
            ops.append(lambda p: _add(p, y))
        elif op == "FloorDiv":
            ops.append(lambda p: _floordiv(_add(p, y), 2))
    frontier = list(atoms)
    for _ in range(4):
        nxt = []
        for p in frontier:
            for op in ops:
                if budget >= max_eval:
                    return {"target": name, "candidate": None, "evaluations": budget, "fit": False,
                            "prior_witnessed": prior.witnessed if prior else 0, "reason": "budget"}
                cand = op(p)
                budget += 1
                if cand.values == goal:
                    return {"target": name, "candidate": cand.text, "evaluations": budget, "fit": True,
                            "prior_witnessed": prior.witnessed if prior else 0}
                nxt.append(cand)
        frontier = nxt[:20]
    return {"target": name, "candidate": None, "evaluations": budget, "fit": False,
            "prior_witnessed": prior.witnessed if prior else 0, "reason": "frontier"}

def compare(prior: GrammarPrior | None = None) -> list[dict[str, Any]]:
    return [attempt_with_prior(name, prior) for name in TARGETS]
