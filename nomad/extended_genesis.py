"""Extended operators for genesis.

PLAN_V4. Abs, Min, FloorDiv available when NOMAD_EXTENDED=on.
Default OFF. Not used by the continuous loop.

This is the measurement path for whether a prior can change search cost
for operators the system was not given. The sealed comparison uses this.
"""
from __future__ import annotations

import os
from typing import Any

from .abstract_targets import attempt_extended, TARGETS
from .genesis import GrammarPrior

def enabled() -> bool:
    return os.environ.get("NOMAD_EXTENDED", "off").lower() == "on"

def synthesize_extended(
    name: str,
    *,
    prior: GrammarPrior | None = None,
) -> dict[str, Any]:
    """Synthesize one target with extended operators.

    Prior is recorded. When the operators are inside the enumerator,
    prior.order will change search order. Until then, the prior is
    logged but not causal.
    """
    result = attempt_extended(name)
    result["prior_witnessed"] = prior.witnessed if prior else 0
    result["extended"] = True
    return result

def compare_arms(prior: GrammarPrior | None = None) -> list[dict[str, Any]]:
    """Run all targets. Used by sealed comparison."""
    return [synthesize_extended(name, prior=prior) for name in TARGETS]
