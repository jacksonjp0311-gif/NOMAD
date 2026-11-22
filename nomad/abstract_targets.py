"""Abstraction discovery targets.

Phase C of PLAN_V2. Attempts to synthesize absdiff, median, and clamp
from examples only. The solutions are not supplied.

The extended grammar adds Abs, Min, Max. These are not in the continuous
loop. This is a measurement tool. Run attempt_all() and record whether
the targets are reachable with the extended operators.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .genesis import IOExample, SynthesisTask

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

def attempt_extended(name: str, *, max_eval: int = 5000) -> dict[str, Any]:
    """Search with Abs, Min, Max, Sub. Returns first fit or abstain."""
    examples = TARGETS[name]
    goal = tuple(e.expected for e in examples)
    atoms = [
        Prog("x", tuple(e.x for e in examples), 1),
        Prog("y", tuple(e.y for e in examples), 1),
    ]
    budget = 0
    pool = list(atoms)
    for a in atoms:
        budget += 1
        if a.values == goal:
            return {"target": name, "candidate": a.text, "evaluations": budget, "fit": True}
        if budget >= max_eval:
            break
    ops = [
        lambda p: _abs(p),
        lambda p: _sub(p, Prog("y", tuple(e.y for e in examples), 1)),
        lambda p: _sub(Prog("x", tuple(e.x for e in examples), 1), p),
        lambda p: _min(p, Prog("y", tuple(e.y for e in examples), 1)),
        lambda p: _max(p, Prog("y", tuple(e.y for e in examples), 1)),
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
