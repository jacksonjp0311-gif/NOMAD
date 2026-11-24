"""Compression measurement.

Invariant from CALM (docs/INVARIANT_CALM.md): if a structure recurs,
compress it. Measure whether the field's own inventions reduce evaluations
on absdiff, median, and clamp.

This is a measurement tool. It does not modify the continuous loop.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .abstract_targets import attempt_extended, TARGETS
from .genesis import GrammarPrior, load_prior_file

def _prior_path() -> Path:
    return Path("data/continuous/prior.json")

def measure() -> dict[str, Any]:
    """Compare cold and field on abstract targets.

    The extended grammar is available to both. The field prior is recorded.
    A causal gain requires the inventions inside the enumerator.
    """
    cold = GrammarPrior()
    field = None
    path = _prior_path()
    if path.exists():
        field = load_prior_file(path)
    cold_results = [attempt_extended(name) for name in TARGETS]
    field_results = [attempt_extended(name) for name in TARGETS]
    for r in cold_results:
        r["prior_witnessed"] = 0
    for r in field_results:
        r["prior_witnessed"] = field.witnessed if field else 0
    return {
        "cold": cold_results,
        "field": field_results,
        "note": "Extended grammar available to both. Prior recorded. Causal order change requires inventions inside enumerator.",
    }

def main() -> int:
    result = measure()
    Path("data").mkdir(exist_ok=True)
    Path("data/compress_measure.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
