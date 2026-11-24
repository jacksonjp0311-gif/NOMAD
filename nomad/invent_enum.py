"""Inventions inside the enumerator.

PLAN_V5. When NOMAD_INVENT_ENUM=on, the extended grammar includes
abstractions extracted from the field. Default OFF. Not used by the
continuous loop.

The prior can change search order for these operators. The sealed
comparison measures whether that reduces evaluations on a held-out family.
"""
from __future__ import annotations

import os
from typing import Any

from .abstract_targets import attempt_extended, TARGETS
from .genesis import GrammarPrior

def enabled() -> bool:
    return os.environ.get("NOMAD_INVENT_ENUM", "off").lower() == "on"

def synthesize_with_inventions(
    name: str,
    *,
    prior: GrammarPrior | None = None,
) -> dict[str, Any]:
    """Synthesize one target with inventions available.

    Prior is recorded. When inventions are inside the enumerator,
    prior.order changes search order. Until then, the prior is logged.
    """
    result = attempt_extended(name)
    result["prior_witnessed"] = prior.witnessed if prior else 0
    result["inventions"] = True
    return result

def compare(prior: GrammarPrior | None = None) -> list[dict[str, Any]]:
    return [synthesize_with_inventions(name, prior=prior) for name in TARGETS]
