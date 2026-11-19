"""Agent observation surface.

Aggregates the latest telemetry, fitness, packet count, and recent bus messages
into a single snapshot that any external agent can read.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .sensors import sense
from .society import load_fitness

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "observe.json"

def snapshot() -> dict[str, Any]:
    """Current state of the field."""
    return {
        "sense": sense(),
        "fitness": load_fitness(),
        "recent_bus": _tail_bus(8),
        "recent_sim": _tail_sim(4),
    }

def _tail_bus(n: int) -> list[dict[str, Any]]:
    path = ROOT / "data" / "society" / "bus.jsonl"
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-n:] if line]

def _tail_sim(n: int) -> list[dict[str, Any]]:
    path = ROOT / "data" / "sim.jsonl"
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-n:] if line]

def write_snapshot() -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snapshot(), indent=2))

if __name__ == "__main__":
    write_snapshot()
    print(SNAPSHOT.read_text())
