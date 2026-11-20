"""Organism-level health: one view of sense -> think -> act -> verify -> remember -> evolve.

Writes ``data/organism.json``. Reads every organ's own records; it computes
nothing new and certifies nothing. Heartbeat gaps found by the watch
workflow are appended to ``data/organism_events.jsonl``.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except json.JSONDecodeError:
        return None


def _jsonl_tail(path: Path, n: int) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def events_path() -> Path:
    return data_root() / "organism_events.jsonl"


def log_event(kind: str, **fields: Any) -> dict:
    row = {"ts": _now(), "kind": kind, **fields}
    events_path().parent.mkdir(parents=True, exist_ok=True)
    with events_path().open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    return row


def status(write: bool = True) -> dict[str, Any]:
    from . import field_queue
    from .advantage import twin_summary
    from .curriculum import family_records, open_levels
    from .scoreboard import recent

    root = data_root()
    cont = root / "continuous"
    board = recent(256)
    genesis_rows = [r for r in board if not str(r.get("task", "")).startswith("world:")]
    world_rows = [r for r in board if str(r.get("task", "")).startswith("world:")]
    log = _jsonl_tail(cont / "log.jsonl", 400)
    last = {}
    for row in log:
        mode = row.get("mode")
        if mode in ("pair", "sleep", "world_pair", "awake"):
            last[mode] = row.get("ts")
    heldout = _json(cont / "heldout.json") or {}
    world_heldout = _json(cont / "world_heldout.json") or {}
    evolve = _jsonl_tail(root / "evolution.jsonl", 5)
    events = _jsonl_tail(events_path(), 10)
    probes = (world_heldout.get("probes") or {})
    report = {
        "schema": "nomad.organism.v1",
        "ts": _now(),
        "sense": {"last_pair": last.get("pair"), "last_world_pair": last.get("world_pair"),
                  "last_sleep": last.get("sleep")},
        "think": {"curriculum_open_levels": open_levels(family_records(world_rows))},
        "act_verify": {
            "genesis_twin": twin_summary(genesis_rows),
            "world_twin": twin_summary(world_rows),
        },
        "remember": {**field_queue.stats(),
                     "genesis_heldout": {"field_certified": (heldout.get("field") or {}).get("certified"),
                                         "cold_certified": (heldout.get("cold") or {}).get("certified")},
                     "world_heldout": {k: v.get("kind") for k, v in probes.items()},
                     "world_library_size": world_heldout.get("library_size")},
        "evolve": {"recent": evolve},
        "heartbeat": {"recent_events": events},
        "boundaries": "No transformers. WITNESS certifies; search and memory never do. Bounded programs only.",
    }
    if write:
        (root / "organism.json").parent.mkdir(parents=True, exist_ok=True)
        (root / "organism.json").write_text(json.dumps(report, indent=2))
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="NOMAD organism health")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    g = sub.add_parser("event")
    g.add_argument("kind")
    g.add_argument("--minutes", type=float, default=None)
    g.add_argument("--action", default="")
    g.add_argument("--note", default="")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=2))
    else:
        print(json.dumps(log_event(a.kind, minutes=a.minutes, action=a.action, note=a.note)))
        status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
