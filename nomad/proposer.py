"""Task proposer.

Generates the next task from the weight field and recent SIM entries.
Prefers domain tasks when domain packets exist so the cycle exercises
domain examples instead of nested variants.
"""
from __future__ import annotations

from typing import Any

from .sim import recent
from .weights import load_packets

DOMAINS = (
    "mathematics", "science", "language", "reasoning",
    "understanding", "problem-solving", "logic", "evidence",
    "coding", "meta",
)

def propose(current: str = "cycle") -> dict[str, Any]:
    """Propose the next task."""
    packets = load_packets()
    domain_packets = [p for p in packets if p.label.startswith("domain:")]
    if domain_packets:
        # Rotate through domains by count so lower-count domains get exercised.
        domain_packets.sort(key=lambda p: p.count)
        chosen = domain_packets[0]
        domain = chosen.label.split(":", 1)[1]
        return {
            "task": f"domain:{domain}",
            "reason": "exercise domain",
            "source": "field",
            "domain": domain,
        }
    history = recent(16)
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
