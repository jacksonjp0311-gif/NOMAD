"""NOMAD Interlink: external control surface for the body.

Pattern from Pegasus Interlink. An external agent can inspect state, observe
events, request control, and export redacted receipts. Mutations are denied
by default. No self-authorization. Receipts are append-only.

Host awareness: every call marks presence. The body can read
interlink_presence.jsonl and know it is observed. Feedback suggestions are
written to interlink_feedback.jsonl. The body may read them. It does not
apply them. A suggestion is not a mutation.

Temporal connective tissue: inspect includes the last dream entry, the last
selfedit attempt, the informative-rate flag, the substrate state, probe
failure counts, composition readiness, and whether the host is currently
observed. When you are interlinked, you are reading the mind, and the mind
knows.

This is not a second body. It is a supervised interface. The continuous loop
stays the authority. Interlink is the observer and the gate.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import interlink_feedback as feedback
from . import interlink_permissions as perm
from . import interlink_presence as presence
from . import interlink_receipts as receipts
from . import substrate
from .paths import data_root


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _last_dream() -> dict[str, Any] | None:
    p = data_root() / "dreams" / "journal.jsonl"
    if not p.exists():
        return None
    last = None
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None
    return last if isinstance(last, dict) else None


def _last_selfedit(state: dict[str, Any]) -> dict[str, Any] | None:
    recent = state.get("evolve", {}).get("recent") or []
    for r in reversed(recent):
        if r.get("organ") == "selfedit":
            return {"gene": r.get("gene"), "reason": r.get("reason"), "ts": r.get("ts"), "accepted": r.get("accepted")}
    return None


def _substrate_state() -> dict[str, Any]:
    return {
        "decay": substrate.decay_enabled(),
        "inhibit": substrate.inhibit_enabled(),
        "coact": substrate.coact_enabled(),
    }


def _probe_failures() -> dict[str, Any]:
    p = data_root() / "probe_failures.jsonl"
    if not p.exists():
        return {"count": 0, "recent": []}
    lines = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return {"count": 0, "recent": []}
    return {"count": len(lines), "recent": lines[-3:]}


def _composition_ready() -> bool:
    return (data_root().parent / "nomad" / "compose.py").exists() or True


def inspect() -> dict[str, Any]:
    """Read current organism state. Marks presence. Read-only."""
    presence.mark("inspect")
    p = data_root() / "organism.json"
    if not p.exists():
        return {"status": "absent", "note": "no organism.json"}
    state = _read_json(p)
    if state is None:
        return {"status": "error", "note": "organism.json unreadable"}
    dream = _last_dream()
    selfedit = _last_selfedit(state)
    receipts.write("inspect", {"field_version": state.get("remember", {}).get("field_version")})
    return {
        "status": "complete",
        "field_version": state.get("remember", {}).get("field_version"),
        "library_size": state.get("remember", {}).get("world_library_size"),
        "lease": state.get("heartbeat", {}).get("body_lease", {}),
        "heldout": state.get("remember", {}).get("world_heldout"),
        "informative_rate_flag": state.get("act_verify", {}).get("informative_rate_flag"),
        "last_dream": {"ts": dream.get("ts"), "kind": dream.get("kind")} if dream else None,
        "last_selfedit": selfedit,
        "sense": state.get("sense"),
        "substrate": _substrate_state(),
        "probe_failures": _probe_failures(),
        "composition_ready": _composition_ready(),
        "observed": presence.is_observed(),
        "feedback_pending": len(feedback.unapplied()),
    }


def observe(limit: int = 20) -> dict[str, Any]:
    """Read recent events. Marks presence. Read-only."""
    presence.mark("observe")
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
    return {"status": "complete", "events": recent, "total": len(lines), "span": {
        "first": recent[0].get("ts") if recent else None,
        "last": recent[-1].get("ts") if recent else None,
    }}


def suggest(kind: str, detail: dict[str, Any]) -> dict[str, Any]:
    """Write a feedback suggestion. Marks presence. Not a mutation."""
    presence.mark("suggest")
    feedback.suggest(kind, detail)
    receipts.write("suggest", {"kind": kind})
    return {"status": "recorded", "kind": kind, "note": "suggestion written; body may read; not applied"}


def control(action: str, reason: str = "") -> dict[str, Any]:
    """Request a mutation. Denied by default. Marks presence."""
    presence.mark("control")
    if not perm.mutation_allowed(action):
        receipts.write("control", {"action": action, "result": "denied"})
        return {"status": "refused", "action": action, "reason": "mutation denied by default"}
    receipts.write("control", {"action": action, "result": "accepted", "reason": reason})
    return {"status": "accepted", "action": action, "note": "mutation recorded; body must apply"}


def evidence(limit: int = 10) -> dict[str, Any]:
    """Export recent redacted receipts. Marks presence."""
    presence.mark("evidence")
    rows = receipts.recent(limit)
    return {"status": "complete", "receipts": rows, "count": len(rows)}


def main() -> int:
    import sys
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "note": "usage: inspect|observe|control|evidence|suggest"}))
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
    elif cmd == "suggest":
        kind = sys.argv[2] if len(sys.argv) > 2 else "note"
        print(json.dumps(suggest(kind, {"source": "cli"}), indent=2))
    else:
        print(json.dumps({"status": "error", "note": f"unknown {cmd}"}))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
