"""Task proposer.

Generates the next task from the weight field and recent SIM entries.
Keeps the scope bounded. Earns its place by whether the twin control improves.
"""
from __future__ import annotations

from typing import Any

from .sim import recent
from .weights import load_packets

def propose(current: str = "cycle") -> dict[str, Any]:
    """Propose the next task."""
    packets = load_packets()
    history = recent(16)
    # Prefer a variation of a successful packet if one exists
    successes = [row for row in history if row.get("measured") == "public_correct"]
    if successes:
        last = successes[-1]
        label = last.get("edit", current)
        return {
            "task": f"{label}-variant",
            "reason": "reinforce recent success",
            "source": "sim",
        }
    if packets:
        return {
            "task": packets[-1].label or current,
            "reason": "continue from field",
            "source": "field",
        }
    return {
        "task": current,
        "reason": "default",
        "source": "none",
    }
