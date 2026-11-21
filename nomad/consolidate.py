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


def _genome_lag() -> int:
    from . import genome
    return int(genome.get("max_lag"))


def policy_from_env() -> StalenessPolicy:
    return StalenessPolicy(
        max_lag=int(os.environ.get("NOMAD_MAX_LAG", str(_genome_lag()))),
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


# ---------------------------------------------------------------- INTEGRITY: atomic commit
#
# docs/INTEGRITY.md. A sleep used to save each state file and only then acknowledge the
# in-flight queue, with duplicate detection per call only: a crash between the two replayed
# an applied packet on the next sleep (witnessed 1 -> 2). Now every file a sleep changes is
# staged first, a commit manifest naming them is written atomically (the commit point), the
# staged files are moved into place, and only then is the queue acknowledged. The set of
# applied packet ids is one of the committed files, so it lands atomically with the state.
# A sleep first rolls forward any committed-but-unfinished manifest, then drops replayed
# packets whose id is already in the ledger (reason ``already_applied``).

LEDGER_MAX = 4096
BINDING_REFUSALS = ("receipt_mismatch", "reattest_mismatch", "unbound_task")


def ledger_path() -> Path:
    return data_root() / "continuous" / "applied_packets.json"


def commit_path() -> Path:
    return data_root() / "continuous" / "consolidate.commit.json"


def refusals_path() -> Path:
    return data_root() / "continuous" / "refusals.jsonl"


def load_ledger() -> list[str]:
    for path in (ledger_path(), ledger_path().with_suffix(".prev.json")):
        if path.exists():
            try:
                ids = json.loads(path.read_text()).get("ids")
            except (json.JSONDecodeError, AttributeError):
                continue
            if isinstance(ids, list):
                return [str(i) for i in ids]
    return []


def _ledger_text(ids: list[str]) -> str:
    return json.dumps({"schema": "nomad.applied-packets.v1", "ids": ids[-LEDGER_MAX:]}, indent=0)


def recover() -> bool:
    """Finish a committed sleep whose files were not all moved into place. Idempotent."""
    cp = commit_path()
    if not cp.exists():
        return False
    try:
        manifest = json.loads(cp.read_text())
        files = manifest["files"]
    except (json.JSONDecodeError, KeyError, TypeError):
        cp.unlink()   # written by os.replace, so never torn; unreadable means not ours
        return False
    root = data_root()
    for staged, final, keep_prev in files:
        st, fi = root / staged, root / final
        if st.exists():
            if keep_prev and fi.exists():
                shutil.copyfile(fi, fi.with_suffix(".prev.json"))
            os.replace(st, fi)
    cp.unlink()
    return True


def _commit(writes: list[tuple[Path, str, bool]]) -> None:
    """Stage every (final path, text, keep_prev) write, commit the manifest, move files into place."""
    root = data_root()
    files = []
    for final, text, keep_prev in writes:
        final.parent.mkdir(parents=True, exist_ok=True)
        st = final.with_name(final.name + ".staged")
        st.write_text(text)
        files.append([str(st.relative_to(root)), str(final.relative_to(root)), keep_prev])
    cp = commit_path()
    tmp = cp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"schema": "nomad.consolidate-commit.v1", "files": files}))
    os.replace(tmp, cp)   # commit point
    recover()


def _refuse(pid: Any, packet: dict[str, Any], reason: str, detail: str = "") -> None:
    """Log a binding refusal (append-only; a log, not state)."""
    path = refusals_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": field_queue._now(), "packet_id": pid, "task": packet.get("task"),
           "family": (packet.get("extra") or {}).get("family"), "reason": reason, "detail": detail}
    with path.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _bind_world(packet: dict[str, Any], receipt: WitnessReceipt) -> tuple[Any, str | None, str]:
    """INTEGRITY: resolve the packet's task from trusted task data, bind the receipt to the exact
    program and task, and re-attest the program on that task. Returns (task, refusal, detail)."""
    from .world import certify, check_binding
    from .world_tasks import by_family
    from .witness import ReceiptMismatch
    extra = packet.get("extra") or {}
    fam = extra.get("family")
    task = by_family(fam) if isinstance(fam, str) else None
    if task is None:
        return None, "unbound_task", f"unknown family {fam!r}"
    tree = extra.get("tree")
    try:
        check_binding(tree, receipt, task.task_id)
    except ReceiptMismatch as e:
        return task, "receipt_mismatch", str(e)
    try:
        again, _pub, final_ok = certify(task, tree)
    except Exception as e:   # noqa: BLE001 - a malformed tree is a refusal, not a crash
        return task, "reattest_mismatch", f"re-attestation raised {type(e).__name__}"
    if again is None or again.receipt_hash != receipt.receipt_hash or not final_ok:
        return task, "reattest_mismatch", "re-attestation on trusted task rows differs"
    return task, None, ""


def consolidate(policy: StalenessPolicy | None = None) -> dict[str, Any]:
    """Drain the queue and apply every packet that survives the checks."""
    from .weights import accumulate_list, load_packets, packets_path, reinforce_list, serialize

    policy = policy or policy_from_env()
    recovered = recover()
    packets = field_queue.claim()
    current = field_queue.field_version()
    prior, prior_source = load_prior_safe()
    from .world_loop import load_world_prior, world_prior_path
    wprior = load_world_prior()
    from . import variation as _var
    vstate = _var.load_state()
    ledger = load_ledger()
    done = set(ledger)
    wpk: list | None = None   # weight packets, loaded on first genesis packet
    var_applied = 0
    world_applied = 0
    dropped: dict[str, int] = defaultdict(int)
    applied: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    seen: set[str] = set()
    processed: list[str] = []
    for p in packets:
        pid = p.get("packet_id")
        if pid in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(pid)
        if pid is not None and str(pid) in done:
            dropped["already_applied"] += 1
            continue
        if pid is not None:
            processed.append(str(pid))
        if p.get("arm") != "treatment":
            dropped["not_treatment"] += 1
            continue
        extra = p.get("extra") or {}
        if not p.get("certified") and extra.get("world") == "variation" and isinstance(extra.get("variation"), dict):
            # Uncertified variation trace: tried counts and novelty only. The
            # learner re-attests any "paid" mutant itself; nothing is certified here.
            ok, _, reason = policy.decide(current - int(p.get("field_version", 0)))
            if not ok:
                dropped[reason or "stale"] += 1
                continue
            fam = extra.get("family")
            lib: list = []
            from .world_tasks import by_family
            t = by_family(fam) if isinstance(fam, str) else None
            if t is not None:
                lib = _var.library_trees(wprior, t.inputs)
            res = _var.apply_trace(vstate, {**extra["variation"], "family": fam}, library=lib)
            if res.get("refused"):
                dropped["variation_refused"] += 1
            else:
                var_applied += 1
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
            from .world import OPSETS, task_route_key
            _t, why, detail = _bind_world(p, receipt)
            if why is not None:
                dropped[why] += 1
                refused.append({"packet_id": pid, "reason": why})
                _refuse(pid, p, why, detail)
                continue
            try:
                wprior.add_witnessed(extra["tree"], receipt, family=extra.get("family"),
                                     opset=OPSETS[extra["opset"]], inputs=extra["inputs"],
                                     sense_key=task_route_key(_t),
                                     # MEANING (docs/MEANING.md): a packet whose task carried words
                                     words=extra.get("words") if isinstance(extra.get("words"), str) else None,
                                     out=extra.get("out"), kind=extra.get("sense_kind"),
                                     task_id=_t.task_id)
            except (ValueError, KeyError, TypeError):
                dropped["bad_receipt"] += 1
                continue
            world_applied += 1
            applied.append({"packet_id": pid, "task": p.get("task"), "lag": lag, "weight": weight, "world": True})
            # Variation: the receipt-verified tree becomes an elite source; any
            # trace updates payoff memory and the novelty archive.
            fam = extra.get("family")
            trace = extra.get("variation") if isinstance(extra.get("variation"), dict) else {}
            res = _var.apply_trace(vstate, {**trace, "family": fam}, certified_tree=extra["tree"],
                                   library=_var.library_trees(wprior, _t.inputs))
            if not res.get("refused"):
                var_applied += 1
            continue
        # GENESIS packet: the receipt must be the one attested on this packet's task.
        if receipt.task_id != f"continuous-{p.get('task')}":
            dropped["receipt_mismatch"] += 1
            refused.append({"packet_id": pid, "reason": "receipt_mismatch"})
            _refuse(pid, p, "receipt_mismatch", "receipt was attested on a different task")
            continue
        try:
            prior.add_witnessed(int(p.get("context_sig", 0)), p.get("candidate") or "", receipt,
                                family=p.get("domain"))
        except (ValueError, SyntaxError) as e:
            from .witness import ReceiptMismatch
            why = "receipt_mismatch" if isinstance(e, ReceiptMismatch) else "bad_receipt"
            dropped[why] += 1
            if why == "receipt_mismatch":
                refused.append({"packet_id": pid, "reason": why})
                _refuse(pid, p, why, str(e))
            continue
        if wpk is None:
            wpk = load_packets()
        wpk = accumulate_list(
            wpk,
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
            reinforce_list(wpk, f"domain:{p['domain']}", 1)
        applied.append({"packet_id": pid, "task": p.get("task"), "lag": lag, "weight": weight})
    new_version = current
    from . import genome
    gamma = float(os.environ.get("NOMAD_DECAY", str(genome.get("decay"))))
    genesis_applied = len(applied) - world_applied
    writes: list[tuple[Path, str, bool]] = []
    if genesis_applied:
        # Unlearning: old evidence fades a little each time new evidence lands,
        # so the order follows what is still being re-earned.
        prior.decay(gamma)
        writes.append((prior_path(), json.dumps(prior.snapshot(), indent=2), True))
        writes.append((packets_path(), serialize(wpk or []), False))
    if world_applied:
        wprior.decay(gamma)
        writes.append((world_prior_path(), json.dumps(wprior.snapshot(), indent=1, sort_keys=True), True))
    if var_applied:
        vstate.decay(gamma)
        writes.append((_var.state_path(), json.dumps(vstate.snapshot(), indent=1, sort_keys=True), True))
    if writes:
        writes.append((ledger_path(), _ledger_text(ledger + processed), True))
    if applied:
        new_version = current + 1
        writes.append((field_queue.version_path(), field_queue.version_text(
            new_version, f"consolidated {len(applied)} packet(s)"), False))
    if writes:
        _commit(writes)
    field_queue.ack()
    return {
        "claimed": len(packets),
        "applied": applied,
        "dropped": dict(dropped),
        "refused": refused,
        "recovered": recovered,
        "field_version_before": current,
        "field_version_after": new_version,
        "prior_source": prior_source,
        "prior_witnessed": prior.witnessed,
        "world_applied": world_applied,
        "world_witnessed": wprior.witnessed,
        "variation_applied": var_applied,
        "variation_archive": len(vstate.archive),
        "decay": gamma if applied else None,
        "policy": {"max_lag": policy.max_lag, "mode": policy.mode, "decay": policy.decay,
                   "min_weight": policy.min_weight},
    }
