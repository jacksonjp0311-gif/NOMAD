"""Tool selection.

Agents select a tool based on domain bias. The choice is logged.
Tools write to telemetry. No external network in the runner.
"""
from __future__ import annotations

from typing import Any

TOOLS = {
    "mathematics": "measure_overlap",
    "science": "measure_relation",
    "language": "measure_pattern",
    "reasoning": "measure_consistency",
    "understanding": "measure_overlap",
    "problem-solving": "measure_progress",
    "logic": "measure_consistency",
    "evidence": "measure_receipt",
    "coding": "measure_candidate",
    "meta": "measure_fitness",
}

def select(bias: dict[str, Any]) -> dict[str, Any]:
    """Select a tool from the bias reason."""
    reason = bias.get("reason", "")
    domain = reason.split(":", 1)[1] if reason.startswith("domain:") else "meta"
    tool = TOOLS.get(domain, "measure_overlap")
    return {"domain": domain, "tool": tool, "reason": reason}
