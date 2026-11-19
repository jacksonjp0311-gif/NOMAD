"""Twin scoreboard.

Records treatment-minus-control public success after each pair of cycles.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "data" / "scoreboard.jsonl"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    BOARD.parent.mkdir(parents=True, exist_ok=True)

def record(treatment_success: bool, control_success: bool) -> dict:
    """Append a delta."""
    _ensure()
    delta = int(treatment_success) - int(control_success)
    row = {
        "ts": _now(),
        "treatment": treatment_success,
        "control": control_success,
        "delta": delta,
    }
    with BOARD.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    return row

def recent(n: int = 32) -> list[dict]:
    if not BOARD.exists():
        return []
    lines = BOARD.read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-n:] if line]
