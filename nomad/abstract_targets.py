"""Abstraction discovery targets.

Phase C of PLAN_V2. Attempts to synthesize absdiff, median, and clamp
from examples only. The solutions are not supplied. The synthesizer sees
public examples and must produce a candidate that matches.

This module is not wired into the continuous loop. It is a measurement
tool. Run it against the current synthesizer and record whether the
targets are reachable without being given the solutions.
"""
from __future__ import annotations

from .genesis import IOExample, SynthesisTask, synthesize, GrammarPrior

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

def make_task(name: str) -> SynthesisTask:
    examples = TARGETS[name]
    return SynthesisTask(
        task_id=f"abstract-{name}",
        source="def solve(x, y):\n    return 0\n",
        public=examples[:3],
        challenge=examples[3:4],
        final=examples[4:],
        hidden_family=name,
    )

def attempt(name: str, *, prior: GrammarPrior | None = None) -> dict:
    """Try to synthesize the target. Returns whether a candidate was produced."""
    task = make_task(name)
    result = synthesize(task, prior=prior, max_nodes=9, max_eval=20000)
    return {
        "target": name,
        "candidate": result.candidate,
        "public_correct": result.public_correct,
        "evaluations": result.candidates_evaluated,
        "abstained": result.abstained,
    }

def attempt_all() -> list[dict]:
    return [attempt(name) for name in TARGETS]
