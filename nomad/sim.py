"""Self-Improvement Memory.

Structured receipts for every field update.
Records the prediction, the measured outcome, and the context.
Later cycles check recent entries before reinforcing.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SIM_LOG = ROOT / "data" / "sim.jsonl"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    SIM_LOG.parent.mkdir(parents=True, exist_ok=True)

def record(
    edit: str,
    predicted: str,
    measured: str,
    context: dict[str, Any] | None = None,
) -> None:
    """Append a SIM entry."""
    _ensure()
    row = {
        "ts": _now(),
        "edit": edit,
        "predicted": predicted,
        "measured": measured,
        "context": context or {},
    }
    with SIM_LOG.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")

def recent(n: int = 16) -> list[dict[str, Any]]:
    """Last n SIM entries for the next cycle."""
    if not SIM_LOG.exists():
        return []
    lines = SIM_LOG.read_text().strip().splitlines()
    out = []
    for line in lines[-n:]:
        if line:
            out.append(json.loads(line))
    return out

def should_reinforce(predicted: str) -> bool:
    """Skip if the same prediction recently failed."""
    history = recent(32)
    failures = sum(
        1 for row in history
        if row.get("predicted") == predicted and row.get("measured") != "public_correct"
    )
    successes = sum(
        1 for row in history
        if row.get("predicted") == predicted and row.get("measured") == "public_correct"
    )
    if failures > successes and failures >= 2:
        return False
    return True
