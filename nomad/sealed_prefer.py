"""Sealed measurement with a prior that prefers faster operators.

Compares cold (default order) against a prior built to prefer operators
that reach the goal fastest on the training examples. Measures whether
that reduces evaluations on absdiff, median, and clamp.

Does not modify the continuous loop.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .prefer_ops import compare, prefer
from .abstract_targets import TARGETS
from .genesis import GrammarPrior

def sealed() -> dict[str, Any]:
    cold = GrammarPrior()
    from .extended_enum import attempt_with_prior
    cold_results = [attempt_with_prior(name, cold) for name in TARGETS]
    prefer_results = compare()
    return {
        "cold": cold_results,
        "prefer": prefer_results,
        "note": "Prefer prior built to favor operators that reach the goal fastest. Causal if prefer evaluations are lower than cold.",
    }

def main() -> int:
    result = sealed()
    Path("data").mkdir(exist_ok=True)
    Path("data/sealed_prefer.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
