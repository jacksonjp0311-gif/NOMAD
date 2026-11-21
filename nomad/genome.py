"""NOMAD genome: the bounded parameters the organism may evolve on its own.

Only these genes can change through self-evolution. Code never rewrites
itself; a gene change is a data commit that tests and the twin scoreboard
must accept, and that sleep reverts if live twin results regress.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import data_root

DEFAULTS: dict[str, Any] = {"decay": 0.97, "library_k": 6, "patience": 4, "max_lag": 2,
                            # invention genes (docs/SELFEDIT.md); read only while NOMAD_SELFEDIT is on,
                            # and the defaults reproduce INVENT round 2 exactly
                            "inv_max_constants": 2, "inv_const_depth": 1, "inv_rounds": 2, "inv_floor_fit": 0}
BOUNDS: dict[str, tuple[float, float]] = {"decay": (0.85, 1.0), "library_k": (2, 10),
                                          "patience": (2, 8), "max_lag": (0, 4),
                                          "inv_max_constants": (0, 8),   # derived learned constants promoted
                                          "inv_const_depth": (1, 2),     # product-closure rounds over learned scales
                                          "inv_rounds": (1, 3),          # invention rounds (composition depth)
                                          "inv_floor_fit": (0, 1)}       # floor-division fit by learned constants
INVENT_GENES = ("inv_max_constants", "inv_const_depth", "inv_rounds", "inv_floor_fit")

# In-process override (the self-edit sandbox evaluates a candidate genome without writing genome.json).
OVERRIDE: dict[str, Any] = {}
_CACHE: dict[str, Any] = {}


def path() -> Path:
    """data/genome.json; NOMAD_GENOME points at another file (measurement of a frozen genome)."""
    o = os.environ.get("NOMAD_GENOME")
    return Path(o) if o else data_root() / "genome.json"


def clamp(name: str, v: Any) -> Any:
    lo, hi = BOUNDS[name]
    return type(DEFAULTS[name])(min(hi, max(lo, v)))


def load() -> dict[str, Any]:
    g = dict(_load_file())
    for k, v in OVERRIDE.items():
        if k in BOUNDS:
            g[k] = clamp(k, v)
    return g


def _load_file() -> dict[str, Any]:
    p = path()
    try:
        key = (str(p), p.stat().st_mtime_ns, p.stat().st_size)
    except OSError:
        key = (str(p), None, None)
    if _CACHE.get("key") == key:
        return _CACHE["genes"]
    g = dict(DEFAULTS)
    if p.exists():
        try:
            raw = json.loads(p.read_text())
            for k, v in (raw.get("genes") or {}).items():
                if k in BOUNDS:
                    lo, hi = BOUNDS[k]
                    g[k] = type(DEFAULTS[k])(min(hi, max(lo, v)))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    _CACHE.update(key=key, genes=g)
    return g


class override:
    """``with genome.override(genes): ...`` -- evaluate a candidate genome in-process (sandbox)."""

    def __init__(self, genes: dict[str, Any]):
        self.genes = dict(genes)

    def __enter__(self):
        self.saved = dict(OVERRIDE)
        OVERRIDE.clear()
        OVERRIDE.update(self.genes)
        return self

    def __exit__(self, *exc):
        OVERRIDE.clear()
        OVERRIDE.update(self.saved)
        return False


def save(genes: dict[str, Any], note: str = "") -> None:
    path().parent.mkdir(parents=True, exist_ok=True)
    _CACHE.clear()
    path().write_text(json.dumps({"schema": "nomad.genome.v1", "genes": genes, "note": note}, indent=2))


def get(name: str) -> Any:
    return load()[name]
