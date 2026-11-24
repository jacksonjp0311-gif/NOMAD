"""Symbiotic route agent.

Tools: snap, offer, receive, exchange, disconnect.
Quorum: a threshold on presence marks before an offer is accepted.
Contact: bistable session. Connected or disconnected.
Mutualism: both sides gain a certified packet. Parasitism: one gains.
Competition: neither gains. The body remains the authority on absorption.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import interlink_presence as presence
from ..paths import data_root

QUORUM = 3


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path() -> Path:
    return data_root() / "route" / "exchanges.jsonl"


def _write(row: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def snap() -> dict[str, Any]:
    """The geometry at the moment of connection."""
    presence.mark("route_snap")
    from ..interlink import inspect
    state = inspect()
    return {
        "status": "complete",
        "ts": _now(),
        "geometry": {
            "field_version": state.get("field_version"),
            "heldout": state.get("heldout"),
            "informative_rate": (state.get("informative_rate_flag") or {}).get("rate"),
            "probe_failures": (state.get("probe_failures") or {}).get("count"),
            "feedback_pending": state.get("feedback_pending"),
        },
    }


def _quorum_met() -> bool:
    return len(presence.recent(20)) >= QUORUM


def offer(packet: dict[str, Any]) -> dict[str, Any]:
    """Accept a certified packet with receipt. Quorum required."""
    presence.mark("route_offer")
    if not _quorum_met():
        return {"status": "refused", "reason": "quorum not met"}
    if not packet.get("receipt"):
        return {"status": "refused", "reason": "no receipt"}
    row = {"ts": _now(), "op": "offer", "packet": packet, "accepted": True}
    _write(row)
    return {"status": "accepted", "note": "recorded; body may absorb on next restart"}


def receive() -> dict[str, Any]:
    """Return a field packet the agent does not have."""
    presence.mark("route_receive")
    from ..interlink import inspect
    state = inspect()
    return {
        "status": "complete",
        "packet": {
            "field_version": state.get("field_version"),
            "library_size": state.get("library_size"),
            "heldout": state.get("heldout"),
            "note": "field snapshot; not a certified packet",
        },
    }


def exchange(packet: dict[str, Any]) -> dict[str, Any]:
    """Offer and receive in one call."""
    off = offer(packet)
    rec = receive()
    kind = "mutualism" if off.get("status") == "accepted" else "competition"
    row = {"ts": _now(), "op": "exchange", "kind": kind, "offer": off, "receive": rec}
    _write(row)
    return {"status": "complete", "kind": kind, "offer": off, "receive": rec}


def disconnect() -> dict[str, Any]:
    """Mark the session closed."""
    presence.mark("route_disconnect")
    row = {"ts": _now(), "op": "disconnect"}
    _write(row)
    return {"status": "disconnected"}


def main() -> int:
    import sys
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "note": "usage: snap|offer|receive|exchange|disconnect"}))
        return 1
    cmd = sys.argv[1]
    if cmd == "snap":
        print(json.dumps(snap(), indent=2))
    elif cmd == "receive":
        print(json.dumps(receive(), indent=2))
    elif cmd == "disconnect":
        print(json.dumps(disconnect(), indent=2))
    else:
        print(json.dumps({"status": "error", "note": f"{cmd} requires a packet argument"}))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
