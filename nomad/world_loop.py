"""WORLD organ of the continuous loop: twin pairs, packets, held-out probes.

Same discipline as GENESIS pairs: control is a cold WorldPrior (no family
evidence, no library) and never writes anything; treatment reads the field
(its family's operator evidence plus library primitives); only a
WITNESS-certified, final-correct treatment becomes a versioned packet for the
sleep learner. Held-out families are probed, never trained.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import field_queue
from .curriculum import choose
from .paths import data_root
from .scoreboard import record_arm, recent as board_recent
from .world import OPSETS, WorldPrior, evaluate
from .world_tasks import HELDOUT, domain_of


def world_prior_path() -> Path:
    return data_root() / "continuous" / "world_prior.json"


def load_world_prior() -> WorldPrior:
    for path in (world_prior_path(), world_prior_path().with_suffix(".prev.json")):
        if path.exists():
            try:
                return WorldPrior.from_snapshot(json.loads(path.read_text()))
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                continue
    return WorldPrior()


def save_world_prior(prior: WorldPrior) -> None:
    path = world_prior_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.with_suffix(".prev.json").write_text(path.read_text())
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(prior.snapshot(), indent=1, sort_keys=True))
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def world_pair(domain: str | None = None) -> dict[str, Any]:
    task, plan = choose(board_recent(512), domain=domain)
    pair_id = hashlib.sha256(f"{_now()}:{task.family}:{os.urandom(8).hex()}".encode()).hexdigest()[:12]
    version = field_queue.field_version()
    key = f"world:{task.family}"
    control, _ = evaluate(task, prior=None)
    record_arm(key, "control", control.certified, kind="world-certified", pair_id=pair_id,
               field_version=version, evaluations=control.evaluations)
    field = load_world_prior()
    treat, receipt = evaluate(task, prior=field)
    out: dict[str, Any] = {
        "mode": "world_pair", "pair_id": pair_id, "family": task.family, "level": task.level,
        "domain": domain_of(task.family), "plan": {k: plan[k] for k in ("open_levels", "chosen", "level")},
        "control": {"certified": control.certified, "evaluations": control.evaluations, "candidate": control.candidate},
        "treatment": {"certified": treat.certified, "evaluations": treat.evaluations, "candidate": treat.candidate,
                      "order": list(treat.order), "library_used": list(treat.library_used)},
        "field_version": version, "ts": _now(),
    }
    if treat.certified and receipt is not None:
        packet = field_queue.make_packet(
            task=key, arm="treatment", field_version=version, certified=True,
            candidate=treat.candidate, context_sig=0, receipt=receipt, pair_id=pair_id,
            measured="witness_and_final", domain=None,
            extra={"world": "typed", "tree": treat.tree, "family": task.family,
                   "opset": task.opset, "inputs": [list(i) for i in task.inputs]},
        )
        out["enqueued"] = {"packet_id": packet["packet_id"], **field_queue.enqueue(packet)}
    row = record_arm(key, "treatment", treat.certified, kind="world-certified", pair_id=pair_id,
                     field_version=version, evaluations=treat.evaluations)
    out["scoreboard"] = row
    if os.environ.get("NOMAD_LEARNER", "queue") == "inline" and "enqueued" in out:
        from .consolidate import consolidate
        out["consolidated"] = consolidate()
    return out


def probe_heldout(field: WorldPrior | None = None, write: bool = True) -> dict[str, Any]:
    """Cold vs field on every never-trained family at its fixed budget."""
    field = field if field is not None else load_world_prior()
    rows = {}
    for name, h in HELDOUT.items():
        t = h["task"]
        c, _ = evaluate(t, prior=None, max_eval=h["max_eval"], max_size=h["max_size"])
        f, _ = evaluate(t, prior=field, use_family=False, max_eval=h["max_eval"], max_size=h["max_size"])
        win_cert = f.certified and not c.certified
        win_cost = f.certified and c.certified and f.evaluations < c.evaluations
        rows[name] = {
            "needs": h["needs"], "max_eval": h["max_eval"],
            "cold": {"certified": c.certified, "evaluations": c.evaluations},
            "field": {"certified": f.certified, "evaluations": f.evaluations, "candidate": f.candidate,
                      "library_used": list(f.library_used)},
            "field_beats_control": bool(win_cert or win_cost),
            "kind": "certified_correctness" if win_cert else "evaluations" if win_cost else "none",
        }
    result = {"probes": rows, "field_witnessed": field.witnessed, "library_size": len(field.library),
              "note": "Never-trained families, fixed budgets. Not a general capability claim.", "ts": _now()}
    if write:
        p = data_root() / "continuous" / "world_heldout.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, indent=2))
    return result
