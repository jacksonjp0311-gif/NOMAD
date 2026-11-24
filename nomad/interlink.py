"""NOMAD Interlink: external control surface for the body.

Pattern from Pegasus Interlink. An external agent can inspect state, observe
events, request control, and export redacted receipts. Mutations are denied
by default. No self-authorization. Receipts are append-only.

This is not a second body. It is a supervised interface. The continuous loop
stays the authority. Interlink is the observer and the gate.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import interlink_permissions as perm
from . import interlink_receipts as receipts
from .paths import data_root


def inspect() -> dict[str, Any]:
    """Read current organism state. Read-only."""
    p = data_root() / "organism.json"
    if not p.exists():
        return {"status": "absent", "note": "no organism.json"}
    try:
        state = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {"status": "error", "note": str(e)[:200]}
    receipts.write("inspect", {"field_version": state.get("remember", {}).get("field_version")})
    return {
        "status": "complete",
        "field_version": state.get("remember", {}).get("field_version"),
        "library_size": state.get("remember", {}).get("world_library_size"),
        "lease": state.get("heartbeat", {}).get("body_lease", {}),
        "heldout": state.get("remember", {}).get("world_heldout"),
        "informative_rate_flag": state.get("act_verify", {}).get("informative_rate_flag"),
    }


def observe(limit: int = 20) -> dict[str, Any]:
    """Read recent events. Read-only."""
    p = data_root() / "organism_events.jsonl"
    if not p.exists():
        return {"status": "absent", "events": []}
    lines = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return {"status": "error", "events": []}
    recent = lines[-limit:]
    receipts.write("observe", {"count": len(recent)})
    return {"status": "complete", "events": recent, "total": len(lines)}


def control(action: str, reason: str = "") -> dict[str, Any]:
    """Request a mutation. Denied by default."""
    if not perm.mutation_allowed(action):
        receipts.write("control", {"action": action, "result": "denied"})
        return {"status": "refused", "action": action, "reason": "mutation denied by default"}
    receipts.write("control", {"action": action, "result": "accepted", "reason": reason})
    return {"status": "accepted", "action": action, "note": "mutation recorded; body must apply"}


def evidence(limit: int = 10) -> dict[str, Any]:
    """Export recent redacted receipts."""
    rows = receipts.recent(limit)
    return {"status": "complete", "receipts": rows, "count": len(rows)}


def main() -> int:
    import sys
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "note": "usage: inspect|observe|control|evidence"}))
        return 1
    cmd = sys.argv[1]
    if cmd == "inspect":
        print(json.dumps(inspect(), indent=2))
    elif cmd == "observe":
        print(json.dumps(observe(), indent=2))
    elif cmd == "control":
        action = sys.argv[2] if len(sys.argv) > 2 else "none"
        print(json.dumps(control(action), indent=2))
    elif cmd == "evidence":
        print(json.dumps(evidence(), indent=2))
    else:
        print(json.dumps({"status": "error", "note": f"unknown {cmd}"}))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
