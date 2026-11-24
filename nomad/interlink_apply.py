"""Body-side application of Interlink suggestions.

Sleep checks interlink_feedback.jsonl for unapplied suggestions. If one is a
substrate flag, it sets the flag for that cycle only, runs the pairs, and
records the result. Then it clears the flag and marks the suggestion applied.
One variable. Reversible. Behind the existing gates.
"""
from __future__ import annotations

import os
from typing import Any

from . import interlink_feedback as feedback


def apply_pending() -> dict[str, Any]:
    """Apply one unapplied substrate suggestion for this cycle."""
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
                return {"applied": True, "kind": kind, "env": env, "note": "set for this cycle only"}
        if kind in ("decay_on", "inhibit_on", "coact_on"):
            env = {"decay_on": "NOMAD_PACKET_DECAY", "inhibit_on": "NOMAD_ORBIT_INHIBIT", "coact_on": "NOMAD_COACT"}[kind]
            os.environ[env] = "on"
            return {"applied": True, "kind": kind, "env": env, "note": "set for this cycle only"}
    return {"applied": False}


def clear() -> None:
    for env in ("NOMAD_PACKET_DECAY", "NOMAD_ORBIT_INHIBIT", "NOMAD_COACT"):
        os.environ.pop(env, None)
