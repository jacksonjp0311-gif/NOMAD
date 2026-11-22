"""Generation-first synthesis.

Drafts candidates from the public examples alone, before consulting memory.
Scores drafts against the examples. Falls back to the existing synthesizer
only if no draft fits. Default OFF. Enable with NOMAD_GENFIRST=on.

This is Phase B of PLAN_V2. It does not invent new operators. It enumerates
the existing grammar from the problem statement first, then recalls.
"""
from __future__ import annotations

import os
from typing import Any

from .genesis import (
    GrammarPrior,
    SynthesisTask,
    synthesize,
    SynthesisRun,
    _enumerate,
    _OPERATOR,
)

def enabled() -> bool:
    return os.environ.get("NOMAD_GENFIRST", "off").lower() == "on"

def generate_first(
    task: SynthesisTask,
    *,
    max_nodes: int = 7,
    max_eval: int = 65000,
) -> SynthesisRun | None:
    """Draft from public examples only. Return a fit or None."""
    if not task.public:
        return None
    root_order = ("Add", "Sub", "Mult")
    program, used, classes = _enumerate(
        task.public,
        root_order=root_order,
        max_nodes=max_nodes,
        max_eval=max_eval,
    )
    if program is None:
        return None
    return SynthesisRun(
        candidate=program.text,
        candidates_evaluated=used,
        observational_classes=classes,
        counterexamples=0,
        public_correct=True,
        abstained=None,
        source_context=0,
    )

def synthesize_first(
    task: SynthesisTask,
    *,
    prior: GrammarPrior | None = None,
    max_nodes: int = 7,
    max_eval: int = 65000,
    family: str | None = None,
) -> SynthesisRun:
    """Generation first. Recall only if generation returns nothing."""
    if enabled():
        draft = generate_first(task, max_nodes=max_nodes, max_eval=max_eval)
        if draft is not None and draft.public_correct:
            return draft
    return synthesize(
        task,
        prior=prior,
        max_nodes=max_nodes,
        max_eval=max_eval,
        family=family,
    )
