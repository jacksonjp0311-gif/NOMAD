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
from .paths import data_root


def snapshot() -> dict[str, Any]:
    """Current state of the field."""
    return {
        "sense": sense(),
        "fitness": load_fitness(),
        "recent_bus": _tail_bus(8),
        "recent_sim": _tail_sim(4),
    }

def _tail_bus(n: int) -> list[dict[str, Any]]:
    path = data_root() / "society" / "bus.jsonl"
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-n:] if line]

def _tail_sim(n: int) -> list[dict[str, Any]]:
    path = data_root() / "sim.jsonl"
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-n:] if line]

def _snapshot_path() -> Path:
    return data_root() / "observe.json"


def write_snapshot() -> None:
    path = _snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot(), indent=2))

if __name__ == "__main__":
    write_snapshot()
    print(_snapshot_path().read_text())
