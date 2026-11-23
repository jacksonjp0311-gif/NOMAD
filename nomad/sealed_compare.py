"""Sealed comparison for Abs, Min, FloorDiv.

PLAN_V4. Measures whether the field certifies absdiff, median, and clamp
with fewer evaluations than cold when extended operators are available.
Does not modify the continuous loop.

Set NOMAD_EXTENDED=on to enable. Default OFF.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .extended_genesis import compare_arms, enabled
from .genesis import GrammarPrior, load_prior_file

def _prior_path() -> Path:
    return Path("data/continuous/prior.json")

def sealed() -> dict[str, Any]:
    """Run cold and field on the three targets with extended operators."""
    if not enabled():
        return {"status": "skipped", "reason": "NOMAD_EXTENDED is off"}
    cold = GrammarPrior()
    field = None
    path = _prior_path()
    if path.exists():
        field = load_prior_file(path)
    return {
        "cold": compare_arms(cold),
        "field": compare_arms(field),
        "extended": True,
        "note": "Operators available. Prior is recorded. Causal order change requires operators inside enumerator.",
    }

def main() -> int:
    os.environ.setdefault("NOMAD_EXTENDED", "on")
    result = sealed()
    Path("data").mkdir(exist_ok=True)
    Path("data/sealed_compare.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
