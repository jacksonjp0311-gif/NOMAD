"""Body-side application of Interlink suggestions.

Sleep checks interlink_feedback.jsonl for unapplied suggestions. If one is a
substrate flag, it sets the flag for that cycle only, runs the pairs, and
records the result. Then it clears the flag and marks the suggestion applied.
One variable. Reversible. Behind the existing gates.

If one is a tree suggestion with a probe name, it verifies the tree still
certifies on that probe and records it in the world prior library. The body
remains the authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from . import interlink_feedback as feedback
from .paths import data_root
from .world import Invalid, consult
from .world import run as world_run
from .world_loop import load_world_prior, save_world_prior
from .world_tasks import HELDOUT


def _mark_applied(key: str, by: str = "kind") -> None:
    p = data_root() / "interlink_feedback.jsonl"
    if not p.exists():
        return
    lines = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                    match = (by == "kind" and row.get("kind") == key) or (
                        by == "probe" and row.get("probe") == key
                    )
                    if match and not row.get("applied"):
                        row["applied"] = True
                    lines.append(json.dumps(row))
                except json.JSONDecodeError:
                    lines.append(line)
    except OSError:
        return
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _tree_certifies(task: Any, tree: list) -> bool:
    try:
        vals = [world_run(tree, r) for r, _e in task.public]
    except (Invalid, Exception):
        return False
    goal = [e for _r, e in task.public]
    if vals != goal:
        return False
    receipt = consult(task, tree)
    return receipt is not None and receipt.supported


def apply_pending() -> dict[str, Any]:
    """Apply one unapplied suggestion for this cycle."""
    pending = feedback.unapplied()
    for s in pending:
        kind = str(s.get("kind") or "")
        if kind.startswith("surgical:substrate."):
            flag = kind.split(".", 1)[-1]
            env = {
                "decay": "NOMAD_PACKET_DECAY",
                "inhibit": "NOMAD_ORBIT_INHIBIT",
                "coact": "NOMAD_COACT",
            }.get(flag)
            if env:
                os.environ[env] = "on"
                _mark_applied(kind)
                return {"applied": True, "kind": kind, "env": env, "note": "set for this cycle only"}
        if kind in ("decay_on", "inhibit_on", "coact_on"):
            env = {"decay_on": "NOMAD_PACKET_DECAY", "inhibit_on": "NOMAD_ORBIT_INHIBIT", "coact_on": "NOMAD_COACT"}[kind]
            os.environ[env] = "on"
            _mark_applied(kind)
            return {"applied": True, "kind": kind, "env": env, "note": "set for this cycle only"}
        # tree suggestion
        probe = s.get("probe")
        tree = s.get("tree")
        if probe and tree and probe in HELDOUT:
            task = HELDOUT[probe]["task"]
            if _tree_certifies(task, tree):
                prior = load_world_prior()
                name = "L" + hashlib.sha256(json.dumps(tree).encode()).hexdigest()[:7]
                prior.library[name] = tree
                save_world_prior(prior)
                _mark_applied(probe, by="probe")
                return {"applied": True, "probe": probe, "name": name, "note": "tree recorded in library"}
    return {"applied": False}


def clear() -> None:
    for env in ("NOMAD_PACKET_DECAY", "NOMAD_ORBIT_INHIBIT", "NOMAD_COACT"):
        os.environ.pop(env, None)
