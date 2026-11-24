"""Probe-failure receipt: records which library primitives were tried on none probes.

Written when a held-out probe returns kind none. Lists tried primitives from
the field library. Descriptive only. Not a learning claim. Does not mutate.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def receipt_path() -> Path:
    return data_root() / "probe_failures.jsonl"


def write_failure(probe: str, kind: str, library: list[str], tried: list[str]) -> dict[str, Any]:
    """Append one receipt for a none probe."""
    row = {
        "ts": _now(),
        "probe": probe,
        "kind": kind,
        "library_size": len(library),
        "tried": tried,
        "untried": [p for p in library if p not in tried],
        "note": "Descriptive only. Lists primitives available when the probe returned none.",
    }
    path = receipt_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    return row


def recent(n: int = 8) -> list[dict]:
    path = receipt_path()
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
