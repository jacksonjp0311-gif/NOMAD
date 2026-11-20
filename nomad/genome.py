"""NOMAD genome: the bounded parameters the organism may evolve on its own.

Only these genes can change through self-evolution. Code never rewrites
itself; a gene change is a data commit that tests and the twin scoreboard
must accept, and that sleep reverts if live twin results regress.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import data_root

DEFAULTS: dict[str, Any] = {"decay": 0.97, "library_k": 6, "patience": 4, "max_lag": 2}
BOUNDS: dict[str, tuple[float, float]] = {"decay": (0.85, 1.0), "library_k": (2, 10),
                                          "patience": (2, 8), "max_lag": (0, 4)}


def path() -> Path:
    return data_root() / "genome.json"


def load() -> dict[str, Any]:
    g = dict(DEFAULTS)
    p = path()
    if p.exists():
        try:
            raw = json.loads(p.read_text())
            for k, v in (raw.get("genes") or {}).items():
                if k in BOUNDS:
                    lo, hi = BOUNDS[k]
                    g[k] = type(DEFAULTS[k])(min(hi, max(lo, v)))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return g


def save(genes: dict[str, Any], note: str = "") -> None:
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text(json.dumps({"schema": "nomad.genome.v1", "genes": genes, "note": note}, indent=2))


def get(name: str) -> Any:
    return load()[name]
