"""Sealed comparison with inventions inside the enumerator.

PLAN_V5. Measures whether the field certifies absdiff, median, and clamp
with fewer evaluations than cold when the prior changes search order.
Does not modify the continuous loop.

Set NOMAD_INVENT_ENUM=on. Default OFF.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .extended_enum import compare, enabled
from .genesis import GrammarPrior, load_prior_file

def _prior_path() -> Path:
    return Path("data/continuous/prior.json")

def sealed() -> dict[str, Any]:
    if not enabled():
        return {"status": "skipped", "reason": "NOMAD_INVENT_ENUM is off"}
    cold = GrammarPrior()
    field = None
    path = _prior_path()
    if path.exists():
        field = load_prior_file(path)
    return {
        "cold": compare(cold),
        "field": compare(field),
        "inventions": True,
        "note": "Extended enumerator. Prior changes operator order. Causal if field evaluations differ from cold.",
    }

def main() -> int:
    os.environ.setdefault("NOMAD_INVENT_ENUM", "on")
    result = sealed()
    Path("data").mkdir(exist_ok=True)
    Path("data/sealed_invent.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
