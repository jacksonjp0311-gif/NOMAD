"""Sensory and telemetry tools for the swarm.

Roles can observe local state, record measurements, and post them to the bus.
No external network. No cloud. Local only.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .society import post
from .paths import data_root


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    (data_root()).mkdir(parents=True, exist_ok=True)

def sense() -> dict[str, Any]:
    """Local sensory snapshot."""
    return {
        "ts": _now(),
        "uptime": time.time(),
        "packets": _count_packets(),
        "fitness": _load_fitness(),
    }

def _count_packets() -> int:
    path = data_root() / "weights" / "packets.jsonl"
    if not path.exists():
        return 0
    with path.open() as f:
        return sum(1 for _ in f)

def _load_fitness() -> dict[str, Any]:
    path = data_root() / "society" / "fitness.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())

def record(measurement: dict[str, Any]) -> None:
    """Append a telemetry row and post it to the bus."""
    _ensure()
    row = {"ts": _now(), "measurement": measurement}
    with (data_root() / "telemetry.jsonl").open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    post("keeper", row)

def telemetry() -> dict[str, Any]:
    """Sense and record."""
    snap = sense()
    record(snap)
    return snap
