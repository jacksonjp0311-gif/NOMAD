"""Domain task families.

Each family is a set of integer examples that the existing synthesizer
can check. Success under a domain bias reinforces that domain packet.
These are measurable, not free-form.
"""
from __future__ import annotations

from .genesis import IOExample

DOMAIN_EXAMPLES = {
    "mathematics": (
        IOExample(2, 3, 6),
        IOExample(4, 5, 20),
        IOExample(3, 3, 9),
    ),
    "science": (
        IOExample(2, 3, 6),   # force = mass * accel
        IOExample(5, 2, 10),
        IOExample(1, 9, 9),
    ),
    "language": (
        IOExample(5, 2, 3),   # difference as simple transform
        IOExample(8, 3, 5),
        IOExample(10, 1, 9),
    ),
    "reasoning": (
        IOExample(2, 3, 6),
        IOExample(1, 4, 4),
        IOExample(6, 2, 12),
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

def examples_for(domain: str) -> tuple[IOExample, ...]:
    return DOMAIN_EXAMPLES.get(domain, DOMAIN_EXAMPLES["mathematics"])
