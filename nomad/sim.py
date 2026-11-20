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

from .paths import data_root


def _sim_log() -> Path:
    return data_root() / "sim.jsonl"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    _sim_log().parent.mkdir(parents=True, exist_ok=True)

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
    with _sim_log().open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")

def recent(n: int = 16) -> list[dict[str, Any]]:
    """Last n SIM entries for the next cycle."""
    if not _sim_log().exists():
        return []
    lines = _sim_log().read_text().strip().splitlines()
    out = []
    for line in lines[-n:]:
        if line:
            out.append(json.loads(line))
    return out

CERTIFIED = {"witness_and_final", "public_correct"}


def should_reinforce(predicted: str) -> bool:
    """Skip if the same prediction recently failed certification.

    `public_correct` remains accepted as a legacy SIM label. New cycles
    record `witness_and_final` for certified success.
    """
    history = recent(32)
    failures = sum(
        1 for row in history
        if row.get("predicted") == predicted and row.get("measured") not in CERTIFIED
    )
    successes = sum(
        1 for row in history
        if row.get("predicted") == predicted and row.get("measured") in CERTIFIED
    )
    if failures > successes and failures >= 2:
        return False
    return True
