"""Abstraction discovery targets.

Phase C of PLAN_V2. Attempts to synthesize absdiff, median, and clamp
from examples only. The solutions are not supplied.

Extended grammar: Abs, Min, Max, Sub, FloorDiv. FloorDiv is for the
median remeasure (PLAN_V3). Not in the continuous loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .genesis import IOExample

TARGETS = {
    "absdiff": (
        IOExample(5, 2, 3),
        IOExample(2, 5, 3),
        IOExample(7, 7, 0),
        IOExample(0, 4, 4),
        IOExample(9, 3, 6),
    ),
    "median": (
        IOExample(1, 5, 3),
        IOExample(4, 2, 3),
        IOExample(7, 1, 4),
        IOExample(3, 9, 6),
        IOExample(2, 8, 5),
    ),
    "clamp": (
        IOExample(0, 5, 0),
        IOExample(3, 5, 3),
        IOExample(7, 5, 5),
        IOExample(1, 4, 1),
        IOExample(9, 2, 2),
    ),
}

@dataclass(frozen=True)
class Prog:
    text: str
    values: tuple[int, ...]
    cost: int

def _abs(a: Prog) -> Prog:
    return Prog(f"abs({a.text})", tuple(abs(v) for v in a.values), a.cost + 1)

def _min(a: Prog, b: Prog) -> Prog:
    return Prog(f"min({a.text},{b.text})", tuple(min(x, y) for x, y in zip(a.values, b.values)), a.cost + b.cost + 1)

def _max(a: Prog, b: Prog) -> Prog:
    return Prog(f"max({a.text},{b.text})", tuple(max(x, y) for x, y in zip(a.values, b.values)), a.cost + b.cost + 1)

def _sub(a: Prog, b: Prog) -> Prog:
    return Prog(f"({a.text}-{b.text})", tuple(x - y for x, y in zip(a.values, b.values)), a.cost + b.cost + 1)

def _add(a: Prog, b: Prog) -> Prog:
    return Prog(f"({a.text}+{b.text})", tuple(x + y for x, y in zip(a.values, b.values)), a.cost + b.cost + 1)

def _floordiv(a: Prog, k: int) -> Prog:
    return Prog(f"({a.text}//{k})", tuple(x // k for x in a.values), a.cost + 1)

def attempt_extended(name: str, *, max_eval: int = 5000) -> dict[str, Any]:
    examples = TARGETS[name]
    goal = tuple(e.expected for e in examples)
    x = Prog("x", tuple(e.x for e in examples), 1)
    y = Prog("y", tuple(e.y for e in examples), 1)
    atoms = [x, y]
    budget = 0
    for a in atoms:
        budget += 1
        if a.values == goal:
            return {"target": name, "candidate": a.text, "evaluations": budget, "fit": True}
    ops = [
        lambda p: _abs(p),
        lambda p: _sub(p, y),
        lambda p: _sub(x, p),
        lambda p: _min(p, y),
        lambda p: _max(p, y),
        lambda p: _add(p, y),
        lambda p: _floordiv(_add(p, y), 2),
    ]
    frontier = list(atoms)
    for _ in range(4):
        nxt = []
        for p in frontier:
            for op in ops:
                if budget >= max_eval:
                    return {"target": name, "candidate": None, "evaluations": budget, "fit": False, "reason": "budget"}
                cand = op(p)
                budget += 1
                if cand.values == goal:
                    return {"target": name, "candidate": cand.text, "evaluations": budget, "fit": True}
                nxt.append(cand)
        frontier = nxt[:20]
    return {"target": name, "candidate": None, "evaluations": budget, "fit": False, "reason": "frontier"}

def attempt_all() -> list[dict[str, Any]]:
    return [attempt_extended(name) for name in TARGETS]
