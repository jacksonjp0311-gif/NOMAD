"""Interlink feedback loop.

Observations from Interlink can be written as suggestions. The body reads
them. It does not apply them. A suggestion is not a mutation. The host
remains the authority. The feedback is the connective tissue that lets an
external observer improve the system by making the host aware of what it sees.
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
    return data_root() / "interlink_feedback.jsonl"


def suggest(kind: str, detail: dict[str, Any]) -> None:
    """Write a suggestion. The body may read it. It does not apply it."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "kind": kind, "detail": detail, "applied": False}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def recent(limit: int = 10) -> list[dict[str, Any]]:
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


def unapplied() -> list[dict[str, Any]]:
    return [r for r in recent(50) if not r.get("applied")]
