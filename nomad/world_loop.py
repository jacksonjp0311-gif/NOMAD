"""WORLD organ of the continuous loop: twin pairs, packets, held-out probes.

Same discipline as GENESIS pairs: control is a cold WorldPrior (no family
evidence, no library) and never writes anything; treatment reads the field
(its family's operator evidence plus library primitives); only a
WITNESS-certified, final-correct treatment becomes a versioned packet for the
sleep learner. Held-out families are probed, never trained.

Probe-failure receipt: when a held-out probe returns none, the result records
which library primitives were available and which were tried. The none stays
visible. An append-only log is written via probe_receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import field_queue, probe_receipt, sense, variation
from .curriculum import choose
from .paths import data_root
from .scoreboard import record_arm, recent as board_recent
from .world import OPSETS, WorldPrior, evaluate
from .world_tasks import HELDOUT, domain_of, words_of


def world_prior_path() -> Path:
    return data_root() / "continuous" / "world_prior.json"


def load_world_prior() -> WorldPrior:
    from . import genome
    for path in (world_prior_path(), world_prior_path().with_suffix(".prev.json")):
        if path.exists():
            try:
                p = WorldPrior.from_snapshot(json.loads(path.read_text()))
                p.library_k = int(genome.get("library_k"))
                return p
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                continue
    p = WorldPrior()
    p.library_k = int(genome.get("library_k"))
    return p


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
    vstate = variation.load_state() if variation.enabled() else None
    words = words_of(task.family)
    treat, receipt = evaluate(task, prior=field, variation=vstate, words=words)
    explored = (variation.explore(task, vstate, variation.library_trees(field, task.inputs))
                if vstate is not None else None)
    trace = None
    if explored is not None:
        paid = list(explored["paid"])
        if treat.certified and treat.via and treat.via.startswith("variation:"):
            paid.append({"kind": treat.via.split(":", 1)[1], "tree": treat.tree})
        trace = {"family": task.family, "situation": explored["situation"],
                 "tried": list(treat.variation) + explored["tried"], "paid": paid}
    out: dict[str, Any] = {
        "mode": "world_pair", "pair_id": pair_id, "family": task.family, "level": task.level,
        "domain": domain_of(task.family), "plan": {k: plan[k] for k in ("open_levels", "chosen", "level")},
        "control": {"certified": control.certified, "evaluations": control.evaluations, "candidate": control.candidate},
        "treatment": {"certified": treat.certified, "evaluations": treat.evaluations, "candidate": treat.candidate,
                      "order": list(treat.order), "library_used": list(treat.library_used),
                      "via": treat.via, "variation_tried": len(treat.variation),
                      "sense": sense.brief(treat.sense)},
        "field_version": version, "ts": _now(),
    }
    if explored is not None:
        out["variation"] = {"situation": explored["situation"], "explore_evaluations": explored["evaluations"],
                            "explore_paid": len(explored["paid"]),
                            "note": "exploration is outside the twin comparison"}
    if treat.certified and receipt is not None:
        packet = field_queue.make_packet(
            task=key, arm="treatment", field_version=version, certified=True,
            candidate=treat.candidate, context_sig=0, receipt=receipt, pair_id=pair_id,
            measured="witness_and_final", domain=None,
            extra={"world": "typed", "tree": treat.tree, "family": task.family,
                   "opset": task.opset, "inputs": [list(i) for i in task.inputs],
                   **({"sense": sense.brief(treat.sense)} if treat.sense else {}),
                   **({"words": words, "out": task.out,
                       "sense_kind": (treat.sense or {}).get("kind")} if words else {}),
                   **({"variation": trace} if trace else {})},
        )
        out["enqueued"] = {"packet_id": packet["packet_id"], **field_queue.enqueue(packet)}
    elif trace and trace["tried"]:
        packet = field_queue.make_packet(
            task=key, arm="treatment", field_version=version, certified=False, candidate=None,
            context_sig=0, pair_id=pair_id, measured="variation_trace",
            extra={"world": "variation", "family": task.family, "variation": trace},
        )
        out["enqueued"] = {"packet_id": packet["packet_id"], **field_queue.enqueue(packet)}
    row = record_arm(key, "treatment", treat.certified, kind="world-certified", pair_id=pair_id,
                     field_version=version, evaluations=treat.evaluations)
    out["scoreboard"] = row
    if os.environ.get("NOMAD_LEARNER", "queue") == "inline" and "enqueued" in out:
        from .consolidate import consolidate
        out["consolidated"] = consolidate()
    return out


def _lib_names(field: WorldPrior | None) -> list[str]:
    """Library entries may be strings or objects with .name."""
    if not field or not field.library:
        return []
    out = []
    for p in field.library:
        if isinstance(p, str):
            out.append(p)
        elif hasattr(p, "name"):
            out.append(p.name)
        else:
            out.append(str(p))
    return out


def probe_heldout(field: WorldPrior | None = None, write: bool = True, vstate: Any = None) -> dict[str, Any]:
    """Cold vs field on every never-trained family at its fixed budget.

    When kind is none, a failure receipt lists available library primitives
    and which were tried. The none stays visible. Append-only log via probe_receipt.
    """
    if field is None:
        field = load_world_prior()
        if vstate is None and variation.enabled():
            vstate = variation.load_state()
    available = _lib_names(field)
    rows = {}
    for name, h in HELDOUT.items():
        t = h["task"]
        c, _ = evaluate(t, prior=None, max_eval=h["max_eval"], max_size=h["max_size"])
        f, _ = evaluate(t, prior=field, use_family=False, max_eval=h["max_eval"], max_size=h["max_size"],
                        variation=vstate)
        win_cert = f.certified and not c.certified
        win_cost = f.certified and c.certified and f.evaluations < c.evaluations
        kind = "certified_correctness" if win_cert else "evaluations" if win_cost else "none"
        row = {
            "needs": h["needs"], "max_eval": h["max_eval"],
            "cold": {"certified": c.certified, "evaluations": c.evaluations},
            "field": {"certified": f.certified, "evaluations": f.evaluations, "candidate": f.candidate,
                      "library_used": list(f.library_used), "via": f.via},
            "field_beats_control": bool(win_cert or win_cost),
            "kind": kind,
        }
        if kind == "none":
            tried = list(f.library_used)
            row["failure_receipt"] = {
                "available_primitives": available,
                "tried": tried,
                "not_tried": [p for p in available if p not in tried],
                "note": "Probe returned none. Primitives listed. Not a capability claim.",
            }
            if write:
                probe_receipt.write_failure(name, kind, available, tried)
        rows[name] = row
    result = {"probes": rows, "field_witnessed": field.witnessed, "library_size": len(field.library),
              "note": "Never-trained families, fixed budgets. Not a general capability claim.", "ts": _now()}
    if write:
        p = data_root() / "continuous" / "world_heldout.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, indent=2))
    return result
