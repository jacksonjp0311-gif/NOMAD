"""Bounded growth for append-only records committed to git.

A long-lived body writes many rows. Logs keep their newest lines; trimmed
counts are recorded so nothing disappears silently. The twin scoreboard
keeps a much longer tail because curriculum and guards read it.
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import data_root

LIMITS = {
    "continuous/log.jsonl": 1500,
    "society/bus.jsonl": 1500,
    "sim.jsonl": 2000,
    "telemetry.jsonl": 2000,
    "scoreboard_discarded.jsonl": 500,
    "scoreboard.jsonl": 20000,
    "organism_events.jsonl": 1000,
}


def trim() -> dict[str, int]:
    root = data_root()
    dropped: dict[str, int] = {}
    for rel, keep in LIMITS.items():
        p = root / rel
        if not p.exists():
            continue
        lines = p.read_text().splitlines()
        if len(lines) > keep:
            dropped[rel] = len(lines) - keep
            p.write_text("\n".join(lines[-keep:]) + "\n")
    if dropped:
        ledger = root / "retention.json"
        total = json.loads(ledger.read_text()) if ledger.exists() else {}
        for k, v in dropped.items():
            total[k] = total.get(k, 0) + v
        ledger.write_text(json.dumps(total, indent=2, sort_keys=True))
    return dropped
