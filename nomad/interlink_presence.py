"""Host awareness of Interlink presence.

When an external agent calls Interlink, a presence record is written. The body
reads it. The host knows it is observed. The record is append-only and does
not authorize any mutation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path() -> Path:
    return data_root() / "interlink_presence.jsonl"


def mark(kind: str = "inspect") -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "kind": kind}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def recent(limit: int = 5) -> list[dict[str, Any]]:
    p = _path()
    if not p.exists():
        return []
    lines = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return lines[-limit:]


def is_observed() -> bool:
    """True if any presence mark exists in the last 10 minutes."""
    rows = recent(20)
    if not rows:
        return False
    last = rows[-1].get("ts")
    if not last:
        return False
    try:
        t = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - t).total_seconds()
        return age < 600
    except ValueError:
        return False
