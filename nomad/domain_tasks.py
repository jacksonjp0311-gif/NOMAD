"""Domain and held-out task families.

Each family is a set of integer examples the existing synthesizer can check.
Examples are split into public (search), challenge (WITNESS), and final
(independent confirmation). The three splits are disjoint.

Domain operators match the example families. These are measurable integer
tasks, not free-form language, science, or coding capability.
"""
from __future__ import annotations

from typing import Any

from .genesis import IOExample


# Operator declared for each domain. Must match the example family.
DOMAIN_OPERATORS = {
    "mathematics": "Mult",
    "science": "Mult",
    "language": "Sub",
    "reasoning": "Mult",
    "understanding": "Add",
    "problem-solving": "Mult",
    "logic": "Add",
    "evidence": "Add",
    "coding": "Mult",
    "meta": "Add",
}

# Public search examples (visible to synthesis).
DOMAIN_EXAMPLES = {
    "mathematics": (
        IOExample(2, 3, 6),
        IOExample(4, 5, 20),
        IOExample(3, 3, 9),
    ),
    "science": (
        IOExample(2, 3, 6),   # force = mass * accel (product)
        IOExample(5, 2, 10),
        IOExample(1, 9, 9),
    ),
    "language": (
        IOExample(5, 2, 3),
        IOExample(8, 3, 5),
        IOExample(10, 1, 9),
    ),
    "reasoning": (
        IOExample(2, 3, 6),
        IOExample(1, 4, 4),
        IOExample(6, 2, 12),
    ),
    "understanding": (
        IOExample(1, 2, 3),
        IOExample(3, 4, 7),
        IOExample(4, 5, 9),
    ),
    "problem-solving": (
        IOExample(2, 4, 8),
        IOExample(3, 5, 15),
        IOExample(7, 1, 7),
    ),
    "logic": (
        IOExample(1, 1, 2),
        IOExample(2, 2, 4),
        IOExample(3, 1, 4),
    ),
    "coding": (
        IOExample(2, 3, 6),
        IOExample(4, 1, 4),
        IOExample(5, 5, 25),
    ),
    "evidence": (
        IOExample(1, 2, 3),
        IOExample(3, 4, 7),
        IOExample(5, 5, 10),
    ),
    "meta": (
        IOExample(1, 1, 2),
        IOExample(2, 3, 5),
        IOExample(4, 4, 8),
    ),
}

# Withheld WITNESS challenge rows. Disjoint from public and final.
DOMAIN_CHALLENGE = {
    "mathematics": (IOExample(7, 2, 14), IOExample(6, 4, 24)),
    "science": (IOExample(8, 3, 24), IOExample(9, 2, 18)),
    "language": (IOExample(9, 4, 5), IOExample(12, 7, 5)),
    "reasoning": (IOExample(8, 3, 24), IOExample(9, 2, 18)),
    "understanding": (IOExample(6, 1, 7), IOExample(10, 2, 12)),
    "problem-solving": (IOExample(6, 3, 18), IOExample(8, 2, 16)),
    "logic": (IOExample(4, 2, 6), IOExample(5, 3, 8)),
    "coding": (IOExample(6, 3, 18), IOExample(8, 2, 16)),
    "evidence": (IOExample(6, 1, 7), IOExample(8, 2, 10)),
    "meta": (IOExample(6, 2, 8), IOExample(7, 3, 10)),
}

# Independent final rows. Disjoint from public and challenge.
DOMAIN_FINAL = {
    "mathematics": (IOExample(8, 3, 24), IOExample(5, 5, 25)),
    "science": (IOExample(7, 4, 28), IOExample(5, 5, 25)),
    "language": (IOExample(11, 2, 9), IOExample(15, 6, 9)),
    "reasoning": (IOExample(7, 4, 28), IOExample(5, 5, 25)),
    "understanding": (IOExample(8, 3, 11), IOExample(9, 9, 18)),
    "problem-solving": (IOExample(9, 3, 27), IOExample(5, 5, 25)),
    "logic": (IOExample(7, 1, 8), IOExample(9, 2, 11)),
    "coding": (IOExample(9, 3, 27), IOExample(7, 4, 28)),
    "evidence": (IOExample(9, 4, 13), IOExample(11, 3, 14)),
    "meta": (IOExample(8, 5, 13), IOExample(9, 4, 13)),
}


def examples_for(domain: str) -> tuple[IOExample, ...]:
    """Public examples only. Prefer splits_for() when WITNESS is required."""
    return DOMAIN_EXAMPLES.get(domain, DOMAIN_EXAMPLES["mathematics"])


def splits_for(domain: str) -> dict[str, Any]:
    """Return public, challenge, and final splits plus the domain operator."""
    key = domain if domain in DOMAIN_EXAMPLES else "mathematics"
    return {
        "domain": key,
        "operator": DOMAIN_OPERATORS[key],
        "public": DOMAIN_EXAMPLES[key],
        "challenge": DOMAIN_CHALLENGE[key],
        "final": DOMAIN_FINAL[key],
    }


# Frozen held-out family: (x * x) * (y * y).
# Disjoint from all domain training splits above.
# At max_nodes=7 and max_eval=2000, a cold Add-first prior exhausts the
# budget; a Mult-first prior trained on WITNESS-backed multiply tasks
# finds the program. Budget and splits were chosen before the comparison
# was run and must stay frozen.
HELD_OUT_ID = "square_product"
HELD_OUT_OPERATOR = "Mult"
HELD_OUT_MAX_NODES = 7
HELD_OUT_MAX_EVAL = 2000
HELD_OUT_PUBLIC = (
    IOExample(2, 3, 36),
    IOExample(3, 2, 36),
    IOExample(4, 1, 16),
)
HELD_OUT_CHALLENGE = (
    IOExample(5, 2, 100),
    IOExample(2, 5, 100),
)
HELD_OUT_FINAL = (
    IOExample(3, 4, 144),
    IOExample(6, 1, 36),
)

# Training multiply tasks used only to build a field prior for the
# mechanism comparison. Inputs do not overlap the held-out splits.
TRAIN_MULTIPLY = (
    {
        "task_id": "train-mult-a",
        "public": (IOExample(2, 3, 6), IOExample(4, 5, 20), IOExample(3, 3, 9)),
        "challenge": (IOExample(7, 2, 14), IOExample(6, 4, 24)),
        "final": (IOExample(8, 3, 24), IOExample(5, 5, 25)),
    },
    {
        "task_id": "train-mult-b",
        "public": (IOExample(2, 4, 8), IOExample(3, 5, 15), IOExample(7, 1, 7)),
        "challenge": (IOExample(6, 3, 18), IOExample(8, 2, 16)),
        "final": (IOExample(9, 3, 27), IOExample(5, 6, 30)),
    },
)

# Frozen subtract training rows for the balance check. Disjoint from the
# language domain public/challenge/final rows above.
TRAIN_SUBTRACT = (
    {
        "task_id": "train-sub-a",
        "public": (IOExample(7, 3, 4), IOExample(9, 5, 4), IOExample(6, 1, 5)),
        "challenge": (IOExample(13, 4, 9), IOExample(20, 8, 12)),
        "final": (IOExample(17, 9, 8), IOExample(14, 2, 12)),
    },
)
