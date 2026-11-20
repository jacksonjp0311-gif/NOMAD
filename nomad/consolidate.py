"""Single learner: sleep consolidates queued, versioned awake packets.

Shape credited to NVIDIA Molt (Apache-2.0): many rollout producers, one
trainer (``molt/trainer/rl_trainer.py``), drop-reason counters
(``rollout/dropped/<reason>`` in ``molt/trainer/rollout/samples_generator.py``),
and resume-from-last-good checkpoint fallback
(``molt/trainer/fsdp/checkpoint.py``). Independent re-implementation.

This is the only code path that writes the GENESIS grammar prior and the
weight packets during the continuous loop. Every packet is re-checked here:
it must be a treatment packet, certified, carry a WITNESS receipt that is
supported and whose checksum verifies, and be inside the staleness bound.
Search and memory still never certify; the learner only replays receipts.
"""
from __future__ import annotations

import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import field_queue
from .genesis import GrammarPrior, prior_from_snapshot
from .paths import data_root
from .staleness import StalenessPolicy
from .witness import WitnessReceipt


DEFAULT_DECAY = 0.97


def prior_path() -> Path:
    return data_root() / "continuous" / "prior.json"


def _prev_path() -> Path:
    return data_root() / "continuous" / "prior.prev.json"


def load_prior_safe() -> tuple[GrammarPrior, str]:
    """Load the field prior; fall back to the last good copy, then to cold."""
    for path, source in ((prior_path(), "current"), (_prev_path(), "previous")):
        if path.exists():
            try:
                return prior_from_snapshot(json.loads(path.read_text())), source
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
    return GrammarPrior(), "cold"


def save_prior_atomic(prior: GrammarPrior) -> None:
    path = prior_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copyfile(path, _prev_path())
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(prior.snapshot(), indent=2))
    os.replace(tmp, path)


def policy_from_env() -> StalenessPolicy:
    return StalenessPolicy(
        max_lag=int(os.environ.get("NOMAD_MAX_LAG", "2")),
        mode=os.environ.get("NOMAD_STALENESS_MODE", "mask"),
        decay=float(os.environ.get("NOMAD_STALENESS_DECAY", "0.5")),
        min_weight=float(os.environ.get("NOMAD_STALENESS_MIN_WEIGHT", "0.25")),
    )


def _receipt(packet: dict[str, Any]) -> WitnessReceipt | None:
    raw = packet.get("receipt")
    if not isinstance(raw, dict):
        return None
    try:
        r = WitnessReceipt(**raw)
    except TypeError:
        return None
    if not r.supported or not r.verify_checksum():
        return None
    return r


def consolidate(policy: StalenessPolicy | None = None) -> dict[str, Any]:
    """Drain the queue and apply every packet that survives the checks."""
    from .weights import accumulate, reinforce

    policy = policy or policy_from_env()
    packets = field_queue.claim()
    current = field_queue.field_version()
    prior, prior_source = load_prior_safe()
    from .world_loop import load_world_prior, save_world_prior
    wprior = load_world_prior()
    world_applied = 0
    dropped: dict[str, int] = defaultdict(int)
    applied: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in packets:
        pid = p.get("packet_id")
        if pid in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(pid)
        if p.get("arm") != "treatment":
            dropped["not_treatment"] += 1
            continue
        if not p.get("certified"):
            dropped["uncertified"] += 1
            continue
        receipt = _receipt(p)
        if receipt is None:
            dropped["bad_receipt"] += 1
            continue
        lag = current - int(p.get("field_version", 0))
        ok, weight, reason = policy.decide(lag)
        if not ok:
            dropped[reason or "stale"] += 1
            continue
        extra = p.get("extra") or {}
        if extra.get("world") == "typed":
            from .world import OPSETS
            try:
                wprior.add_witnessed(extra["tree"], receipt, family=extra.get("family"),
                                     opset=OPSETS[extra["opset"]], inputs=extra["inputs"])
            except (ValueError, KeyError, TypeError):
                dropped["bad_receipt"] += 1
                continue
            world_applied += 1
            applied.append({"packet_id": pid, "task": p.get("task"), "lag": lag, "weight": weight, "world": True})
            continue
        try:
            prior.add_witnessed(int(p.get("context_sig", 0)), p.get("candidate") or "", receipt,
                                family=p.get("domain"))
        except (ValueError, SyntaxError):
            dropped["bad_receipt"] += 1
            continue
        accumulate(
            set(p.get("query_bits") or []),
            True,
            label=p.get("task") or "",
            predicted=p.get("predicted", ""),
            measured=p.get("measured", "witness_and_final"),
            context={
                "task": p.get("task"),
                "arm": "treatment",
                "certified": True,
                "packet_id": pid,
                "field_version": p.get("field_version"),
                "lag": lag,
                "weight": weight,
                **(p.get("extra") or {}),
            },
        )
        if p.get("domain"):
            reinforce(f"domain:{p['domain']}", 1)
        applied.append({"packet_id": pid, "task": p.get("task"), "lag": lag, "weight": weight})
    new_version = current
    gamma = float(os.environ.get("NOMAD_DECAY", str(DEFAULT_DECAY)))
    genesis_applied = len(applied) - world_applied
    if genesis_applied:
        # Unlearning: old evidence fades a little each time new evidence lands,
        # so the order follows what is still being re-earned.
        prior.decay(gamma)
        save_prior_atomic(prior)
    if world_applied:
        wprior.decay(gamma)
        save_world_prior(wprior)
    if applied:
        new_version = field_queue.bump_version(f"consolidated {len(applied)} packet(s)")
    field_queue.ack()
    return {
        "claimed": len(packets),
        "applied": applied,
        "dropped": dict(dropped),
        "field_version_before": current,
        "field_version_after": new_version,
        "prior_source": prior_source,
        "prior_witnessed": prior.witnessed,
        "world_applied": world_applied,
        "world_witnessed": wprior.witnessed,
        "decay": gamma if applied else None,
        "policy": {"max_lag": policy.max_lag, "mode": policy.mode, "decay": policy.decay,
                   "min_weight": policy.min_weight},
    }
