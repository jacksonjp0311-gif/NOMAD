"""NOMAD Interlink receipts.

Append-only redacted export. No raw prompts. No credentials. No field
mutation. A receipt records what was asked and what was allowed.
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
    return data_root() / "interlink_receipts.jsonl"


def write(kind: str, payload: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "kind": kind, "payload": payload}
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
