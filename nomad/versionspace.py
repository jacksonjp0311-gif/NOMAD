"""Version space.

When multiple domain packets return conflicting operators for the same query,
the learner abstains. Certification requires agreement among surviving hypotheses.
Derived from the Theory of Language (v0.2.0, Section 4.1 and 4.3).
"""
from __future__ import annotations

from typing import Any

def conflicts(context: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the conflict if domain packets disagree on operator."""
    domain = [
        c for c in context
        if c.get("label", "").startswith("domain:")
        and c.get("receipt", {}).get("measured") == "seeded"
    ]
    operators = set()
    for c in domain:
        op = c.get("receipt", {}).get("context", {}).get("operator")
        if op:
            operators.add(op)
    if len(operators) > 1:
        return {
            "abstain": True,
            "reason": "conflicting operators",
            "operators": sorted(operators),
            "count": len(domain),
        }
    return None

def decide(context: list[dict[str, Any]]) -> dict[str, Any]:
    """Return abstain or the agreed operator."""
    conflict = conflicts(context)
    if conflict:
        return conflict
    domain = [
        c for c in context
        if c.get("label", "").startswith("domain:")
        and c.get("receipt", {}).get("measured") == "seeded"
    ]
    if not domain:
        return {"abstain": False, "operator": None, "reason": "no domain"}
    chosen = max(domain, key=lambda c: c.get("overlap", 0) * c.get("count", 1))
    op = chosen.get("receipt", {}).get("context", {}).get("operator")
    return {"abstain": False, "operator": op, "reason": "agreed"}
