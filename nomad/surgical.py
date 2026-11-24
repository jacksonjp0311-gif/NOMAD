"""Surgical edit surface.

A holographic view of the running system. See the connective activity. Find a
spot. Inject a change. Get immediate feedback. Recall if it does not help.
The body stays running. The geometry is the field, the prior, the substrate
flags, the gene proposals. Edits are suggestions until the body applies them.

Operations: view, inject, recall, rotate.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import interlink_feedback as feedback
from . import interlink_presence as presence
from .paths import data_root


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path() -> Path:
    return data_root() / "surgical.jsonl"


def _write(row: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def view() -> dict[str, Any]:
    """The hologram. Current geometry."""
    presence.mark("surgical_view")
    from .interlink import inspect
    state = inspect()
    return {
        "status": "complete",
        "geometry": {
            "field_version": state.get("field_version"),
            "heldout": state.get("heldout"),
            "informative_rate": (state.get("informative_rate_flag") or {}).get("rate"),
            "substrate": state.get("substrate"),
            "last_selfedit": state.get("last_selfedit"),
            "feedback_pending": state.get("feedback_pending"),
        },
        "note": "The map. Find a spot. Inject. Recall if needed.",
    }


def inject(target: str, change: dict[str, Any]) -> dict[str, Any]:
    """Inject a change as a suggestion. Body may apply. Immediate feedback."""
    presence.mark("surgical_inject")
    row = {"ts": _now(), "op": "inject", "target": target, "change": change, "recalled": False}
    _write(row)
    feedback.suggest(f"surgical:{target}", change)
    return {"status": "injected", "target": target, "change": change, "note": "suggestion recorded; body may apply; recall available"}


def recall(target: str) -> dict[str, Any]:
    """Recall the last inject on a target. Marks it recalled."""
    presence.mark("surgical_recall")
    p = _path()
    if not p.exists():
        return {"status": "absent", "target": target}
    lines = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return {"status": "error"}
    for row in reversed(lines):
        if row.get("op") == "inject" and row.get("target") == target and not row.get("recalled"):
            row["recalled"] = True
            row["recalled_ts"] = _now()
            _write(row)
            return {"status": "recalled", "target": target, "change": row.get("change")}
    return {"status": "none", "target": target}


def rotate(target: str, steps: int = 1) -> dict[str, Any]:
    """Rotate a discrete parameter. Suggestion only."""
    presence.mark("surgical_rotate")
    change = {"rotate": steps}
    return inject(target, change)


def main() -> int:
    import sys
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "note": "usage: view|inject|recall|rotate"}))
        return 1
    cmd = sys.argv[1]
    if cmd == "view":
        print(json.dumps(view(), indent=2))
    elif cmd == "inject":
        target = sys.argv[2] if len(sys.argv) > 2 else "none"
        print(json.dumps(inject(target, {"source": "cli"}), indent=2))
    elif cmd == "recall":
        target = sys.argv[2] if len(sys.argv) > 2 else "none"
        print(json.dumps(recall(target), indent=2))
    elif cmd == "rotate":
        target = sys.argv[2] if len(sys.argv) > 2 else "none"
        print(json.dumps(rotate(target), indent=2))
    else:
        print(json.dumps({"status": "error", "note": f"unknown {cmd}"}))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
