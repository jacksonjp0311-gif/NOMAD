"""Twin scoreboard.

Records actual treatment-minus-control *certified* success.

Certified means WITNESS-supported and final-correct. Public-only
correctness is not a learning signal. Each arm writes its own result.
Delta is computed only when both arms for the same task identity are
present. No hard-coded control failure. An unpaired treatment result
is pending, not learning.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root


def _board() -> Path:
    return data_root() / "scoreboard.jsonl"


def _pending() -> Path:
    return data_root() / "scoreboard_pending.json"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    data_root().mkdir(parents=True, exist_ok=True)

def _load_pending() -> dict[str, Any]:
    if not _pending().exists():
        return {}
    return json.loads(_pending().read_text())

def _save_pending(data: dict[str, Any]) -> None:
    _ensure()
    _pending().write_text(json.dumps(data, indent=2))

def record_arm(task_id: str, arm: str, success: bool, *, kind: str = "certified") -> dict[str, Any] | None:
    """Record one arm. Return the paired delta if both arms are now present.

    `success` must be the certified (WITNESS + final) outcome, not public-only.
    """
    _ensure()
    pending = _load_pending()
    entry = pending.get(task_id, {})
    entry[arm] = success
    entry["ts"] = _now()
    pending[task_id] = entry
    _save_pending(pending)
    if "treatment" in entry and "control" in entry:
        delta = int(entry["treatment"]) - int(entry["control"])
        row = {
            "ts": _now(),
            "task": task_id,
            "treatment": entry["treatment"],
            "control": entry["control"],
            "delta": delta,
            "kind": kind,
        }
        with _board().open("a") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
        del pending[task_id]
        _save_pending(pending)
        return row
    return None

def recent(n: int = 32) -> list[dict]:
    if not _board().exists():
        return []
    lines = _board().read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-n:] if line]
