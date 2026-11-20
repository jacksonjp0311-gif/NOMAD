"""Tool selection.

Agents select a tool based on domain bias. The choice is logged.
Tools can load external examples from a file when present.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .external import load_examples
from .domain_tasks import examples_for
from .genesis import IOExample

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

EXTERNAL = Path(__file__).resolve().parent.parent / "data" / "external"

def select(bias: dict[str, Any]) -> dict[str, Any]:
    """Select a tool from the bias reason and load examples."""
    reason = bias.get("reason", "")
    domain = reason.split(":", 1)[1] if reason.startswith("domain:") else "meta"
    tool = TOOLS.get(domain, "measure_overlap")
    external_path = EXTERNAL / f"{domain}.txt"
    external = load_examples(external_path) if external_path.exists() else ()
    base = examples_for(domain) if domain in TOOLS else ()
    examples = external or base
    return {
        "domain": domain,
        "tool": tool,
        "reason": reason,
        "examples": len(examples),
        "source": "external" if external else "domain",
    }
