"""Minimal continuous cycle.

Does not import GENESIS. Produces observation data so the field can be watched.
Use this while the full continuous runner is blocked.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .sensors import telemetry
from .observe import write_snapshot
from .sim import record as sim_record
from .weights import accumulate

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "continuous"
LOG = DATA / "log.jsonl"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    DATA.mkdir(parents=True, exist_ok=True)

def run(mode: str = "awake") -> dict:
    _ensure()
    snap = telemetry()
    row = {
        "mode": mode,
        "ts": _now(),
        "telemetry": snap,
        "status": "minimal",
    }
    with LOG.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    if mode == "awake":
        sim_record(
            edit="minimal-cycle",
            predicted="public success",
            measured="minimal",
            context={"mode": mode},
        )
        accumulate(set(range(8)), True, label="minimal")
    write_snapshot()
    return row

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("awake", "sleep"), default="awake")
    args = parser.parse_args()
    print(json.dumps(run(args.mode), indent=2))
