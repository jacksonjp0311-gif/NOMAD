"""Sealed comparison for Abs, Min, FloorDiv.

PLAN_V3. Measures whether the field certifies absdiff, median, and clamp
on held-out families where cold cannot. Does not modify the continuous loop.

Arms: cold (no prior), empty (empty prior), field (loaded prior if present).
Operators: Abs, Min, FloorDiv are available to all arms in this measurement.
The difference is the prior, not the grammar.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .abstract_targets import attempt_extended, TARGETS
from .genesis import GrammarPrior, load_prior_file

def _prior_path() -> Path:
    return Path("data/continuous/prior.json")

def run_arm(name: str, prior: GrammarPrior | None) -> dict[str, Any]:
    """Run one target with a given prior. Prior is unused by attempt_extended;
    the measurement records whether the target fits under the extended grammar.
    A real prior-sensitive comparison requires the operators inside genesis.
    This records reachability and cost for the sealed suite."""
    result = attempt_extended(name)
    return {
        "target": name,
        "fit": result.get("fit"),
        "candidate": result.get("candidate"),
        "evaluations": result.get("evaluations"),
        "prior_witnessed": prior.witnessed if prior else 0,
    }

def sealed() -> dict[str, Any]:
    """Run cold, empty, field on the three targets."""
    cold = GrammarPrior()
    empty = GrammarPrior()
    field = None
    path = _prior_path()
    if path.exists():
        field = load_prior_file(path)
    arms = {
        "cold": cold,
        "empty": empty,
        "field": field,
    }
    out = {}
    for arm_name, prior in arms.items():
        out[arm_name] = [run_arm(t, prior) for t in TARGETS]
    return {"arms": out, "note": "Operators available to all arms. Prior difference is recorded but not yet causal."}

def main() -> int:
    result = sealed()
    Path("data").mkdir(exist_ok=True)
    Path("data/sealed_compare.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
