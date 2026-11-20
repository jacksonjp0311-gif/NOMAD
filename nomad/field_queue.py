"""Versioned packet queue between awake attempts (actors) and sleep (learner).

Idea credited to NVIDIA Molt (Apache-2.0): decoupled rollout producers and a
single trainer joined by a bounded queue (``ray.util.queue.Queue`` in
``molt/trainer/rl_trainer.py``), per-rollout ids for dedup
(``Trajectory.rollout_id`` in ``molt/agents/base.py``), and warm-resume of
finished-but-untrained groups (``state_dict``/``load_state_dict`` in
``molt/trainer/rollout/samples_generator.py``). Re-implemented here as an
append-only JSONL file on the data branch; no Ray, no Molt code.

Rules:
- Awake never writes the field. It reads the field version, attempts, and
  enqueues a packet stamped with that version.
- Only a WITNESS-certified attempt carries a receipt worth consolidating.
  Uncertified packets may be enqueued for observability; the learner drops
  them with reason ``uncertified``.
- The queue is bounded. GitHub runners cannot block on a full queue the way
  Molt's generator blocks on a slot, so overflow drops the *oldest* packets
  and counts them.
- ``claim`` moves the queue to an in-flight file before the learner reads
  it. If a sleep dies mid-way, the next sleep re-reads the in-flight file
  first (warm resume) instead of losing those packets.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root

MAX_QUEUE = 64


def _dir() -> Path:
    return data_root() / "continuous"


def queue_path() -> Path:
    return _dir() / "queue.jsonl"


def inflight_path() -> Path:
    return _dir() / "queue.inflight.jsonl"


def version_path() -> Path:
    return _dir() / "field_version.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # A torn line from an interrupted write is skipped, not fatal.
            continue
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    os.replace(tmp, path)


# ---------------------------------------------------------------- versions

def field_version() -> int:
    """Current field version. Only the learner advances it."""
    p = version_path()
    if not p.exists():
        return 0
    try:
        return int(json.loads(p.read_text()).get("version", 0))
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0


def bump_version(note: str = "") -> int:
    v = field_version() + 1
    version_path().parent.mkdir(parents=True, exist_ok=True)
    version_path().write_text(json.dumps({"version": v, "ts": _now(), "note": note}, indent=2))
    return v


# ---------------------------------------------------------------- packets

def make_packet(
    *,
    task: str,
    arm: str,
    field_version: int,
    certified: bool,
    candidate: str | None,
    context_sig: int,
    receipt: Any = None,
    pair_id: str | None = None,
    predicted: str = "",
    measured: str = "",
    domain: str | None = None,
    query_bits: list[int] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ts = _now()
    receipt_dict = asdict(receipt) if receipt is not None and not isinstance(receipt, dict) else receipt
    ident = json.dumps([task, arm, field_version, candidate, context_sig, pair_id, ts], sort_keys=True)
    return {
        "schema": "nomad.field-packet.v1",
        "packet_id": hashlib.sha256(ident.encode()).hexdigest()[:16],
        "pair_id": pair_id,
        "task": task,
        "arm": arm,
        "domain": domain,
        "field_version": int(field_version),
        "certified": bool(certified),
        "candidate": candidate,
        "context_sig": int(context_sig),
        "receipt": receipt_dict,
        "predicted": predicted,
        "measured": measured,
        "query_bits": sorted(query_bits) if query_bits else [],
        "extra": extra or {},
        "ts": ts,
    }


def enqueue(packet: dict[str, Any], *, max_size: int = MAX_QUEUE) -> dict[str, Any]:
    """Append one packet. Returns {"size": n, "overflow_dropped": k}."""
    if packet.get("arm") == "control":
        # Control is frozen. It has nothing to teach the field.
        raise ValueError("control packets must not enter the learner queue")
    rows = _read_jsonl(queue_path())
    rows.append(packet)
    dropped = 0
    if max_size > 0 and len(rows) > max_size:
        dropped = len(rows) - max_size
        rows = rows[dropped:]
    _write_jsonl(queue_path(), rows)
    return {"size": len(rows), "overflow_dropped": dropped}


def peek() -> list[dict[str, Any]]:
    return _read_jsonl(inflight_path()) + _read_jsonl(queue_path())


def claim() -> list[dict[str, Any]]:
    """Move all queued packets to in-flight and return in-flight + newly claimed."""
    resumed = _read_jsonl(inflight_path())
    fresh = _read_jsonl(queue_path())
    rows = resumed + fresh
    if rows:
        _write_jsonl(inflight_path(), rows)
    if queue_path().exists():
        queue_path().unlink()
    return rows


def ack() -> None:
    """Learner finished: drop the in-flight file."""
    if inflight_path().exists():
        inflight_path().unlink()


def stats() -> dict[str, Any]:
    q = _read_jsonl(queue_path())
    f = _read_jsonl(inflight_path())
    return {
        "queued": len(q),
        "inflight": len(f),
        "certified_queued": sum(1 for r in q if r.get("certified")),
        "field_version": field_version(),
    }
