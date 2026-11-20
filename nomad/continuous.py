"""Continuous cybernetic loop for NOMAD.

Awake pair: control runs first as a cold prior on the same proposed task;
treatment then uses the field prior. Only a paired, WITNESS-and-final
delta is a learning measurement. Public-only correctness is recorded,
never counted as learning, and never updates the field.

Acting domain is the proposer's domain. Orbit is logged but cannot
redirect the cycle to a different domain.

Treatment may call GrammarPrior.add_witnessed only after a supported
WITNESS receipt and a passing final split. That is what moves synthesis
order. Control never writes packets, prior, or fitness.

Sleep: consolidate, evaluate CA rules, propose a rewrite (no commit).
No transformers. Search and memory do not certify.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .genesis import (
    GrammarPrior,
    SynthesisTask,
    evaluate_task,
    load_prior_file,
    save_prior_file,
)
from .society import post, update_fitness, gate
from .weights import accumulate, merge_similar, reinforce
from .automata import try_rules
from .sensors import telemetry
from .sim import recent, should_reinforce, record as sim_record
from .scoreboard import record_arm
from .proposer import propose
from .rewrite import rewrite
from .observe import write_snapshot
from .domain_tasks import splits_for
from .tools import select as select_tool
from .query import query as field_query
from .orbit import orbit
from .external import load_examples
from .heldout import compare_live
from .paths import data_root

BITS = 4096


def _data() -> Path:
    return data_root() / "continuous"


def _external() -> Path:
    return data_root() / "external"


def _prior_path() -> Path:
    return _data() / "prior.json"


def _log_path() -> Path:
    return _data() / "log.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure() -> None:
    _data().mkdir(parents=True, exist_ok=True)


def _hash_bits(text: str, density: int = 64) -> set[int]:
    h = hashlib.sha256(text.encode()).digest()
    bits = set()
    for i in range(density):
        idx = int.from_bytes(h[i % 32:(i % 32) + 4], "big") % BITS
        bits.add(idx)
    return bits


def _acting_domain(proposal: dict[str, Any]) -> str | None:
    domain = proposal.get("domain")
    if domain:
        return domain
    task = str(proposal.get("task") or "")
    if task.startswith("domain:"):
        return task.split(":", 1)[1]
    return None


def _bias_for_domain(domain: str) -> dict[str, Any]:
    splits = splits_for(domain)
    return {
        "operator": splits["operator"],
        "examples": domain,
        "reason": f"domain:{domain}",
        "overlap": 0,
        "label": f"domain:{domain}",
    }


def _splits_for_bias(bias: dict[str, Any]) -> dict[str, Any]:
    reason = bias.get("reason", "")
    if reason.startswith("domain:"):
        domain = reason.split(":", 1)[1]
        splits = splits_for(domain)
        path = _external() / f"{domain}.txt"
        if path.exists():
            loaded = load_examples(path)
            if loaded:
                # External files currently provide public rows only.
                # Challenge and final stay the domain withheld splits.
                splits = dict(splits)
                splits["public"] = loaded
                splits["source"] = "external"
                return splits
        splits = dict(splits)
        splits["source"] = "domain"
        return splits
    # Non-domain fallback: addition, still with withheld splits.
    splits = dict(splits_for("meta"))
    splits["source"] = "default"
    return splits


def _log(row: dict[str, Any]) -> None:
    _ensure()
    with _log_path().open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def awake(
    task_text: str = "cycle",
    *,
    arm: str = "treatment",
    proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One awake cycle on a single arm.

    Control uses a cold prior and never writes the field. Treatment uses
    the saved field prior and may update it only after WITNESS + final.
    When the proposer names a domain, that domain is the acting domain.
    """
    _ensure()
    snap = telemetry()
    if proposal is None:
        proposal = propose(task_text)
    task_text = proposal.get("task") or task_text
    domain = _acting_domain(proposal)
    query_bits = _hash_bits(task_text)
    context = orbit(query_bits)
    if domain:
        bias = _bias_for_domain(domain)
    else:
        bias = {"operator": None, "examples": "meta", "reason": "default", "overlap": 0, "label": ""}
    tool = select_tool(bias)
    splits = _splits_for_bias(bias)
    if arm == "control":
        prior = GrammarPrior()
    else:
        prior = load_prior_file(_prior_path())
    history = recent(8)
    task = SynthesisTask(
        task_id=f"continuous-{task_text}",
        source="def solve(x, y):\n    return 0\n",
        public=tuple(splits["public"]),
        challenge=tuple(splits["challenge"]),
        final=tuple(splits["final"]),
        hidden_family=domain or "default",
    )
    context_sig = 0
    # Order is read from the prior *before* this cycle's witness update.
    # For treatment this is the field; for control it is always default.
    # Signature is computed inside evaluate_task/synthesize.
    evaluated, receipt = evaluate_task(task, prior=prior)
    context_sig = evaluated.learned_context
    order = list(prior.order(context_sig))
    certified = bool(evaluated.witness_supported and evaluated.final_correct)
    outcome = {
        "mode": "awake",
        "arm": arm,
        "task": task_text,
        "proposal": proposal,
        "acting_domain": domain,
        "context": context,
        "bias": bias,
        "tool": tool,
        "example_source": splits.get("source"),
        "operator_order": order,
        "prior_witnessed": prior.witnessed,
        "sim_history": history,
        "candidate": evaluated.candidate,
        "public_correct": evaluated.public_tests,
        "witness_supported": evaluated.witness_supported,
        "final_correct": evaluated.final_correct,
        "certified": certified,
        "evaluations": evaluated.candidate_evaluations,
        "abstained": evaluated.abstained,
        "telemetry": snap,
        "ts": _now(),
    }
    decision = gate(outcome)
    outcome["gate"] = decision
    _log(outcome)
    post("keeper", outcome)
    predicted = proposal.get("reason", "certified success")
    measured = "witness_and_final" if certified else (
        "public_only" if evaluated.public_tests else "fail"
    )
    sim_record(
        edit=f"packet:{task_text}",
        predicted=predicted,
        measured=measured,
        context={"task": task_text, "arm": arm, "bias": bias, "tool": tool, "certified": certified},
    )
    if arm == "treatment":
        update_fitness(bool(decision.get("pass")))
        if decision.get("pass") and receipt is not None and should_reinforce(predicted):
            prior.add_witnessed(context_sig, evaluated.candidate or "", receipt)
            accumulate(
                query_bits,
                True,
                label=task_text,
                predicted=predicted,
                measured=measured,
                context={
                    "task": task_text,
                    "arm": arm,
                    "proposal": proposal,
                    "bias": bias,
                    "tool": tool,
                    "operator": bias.get("operator"),
                    "certified": True,
                },
            )
            if domain:
                reinforce(f"domain:{domain}", 1)
            save_prior_file(prior, _prior_path())
            outcome["prior_witnessed_after"] = prior.witnessed
            outcome["operator_order_after"] = list(prior.order(context_sig))
    paired = record_arm(task_text, arm, certified, kind="certified")
    if paired:
        outcome["scoreboard"] = paired
        outcome["learning_measurement"] = {
            "paired": True,
            "delta": paired["delta"],
            "kind": "certified",
        }
    else:
        outcome["learning_measurement"] = {
            "paired": False,
            "delta": None,
            "kind": "certified",
            "note": "Unpaired arm result is not a learning measurement.",
        }
    write_snapshot()
    return outcome


def sleep(*, arm: str = "treatment") -> dict[str, Any]:
    """Consolidation, independent CA evaluation, rewrite proposal. Control freezes."""
    _ensure()
    snap = telemetry()
    if arm != "treatment":
        return {"mode": "sleep", "arm": arm, "status": "frozen", "telemetry": snap, "ts": _now()}
    merged = merge_similar()
    rules = try_rules(steps=1)
    rewrite_result = rewrite()
    row = {
        "mode": "sleep",
        "arm": arm,
        "status": "consolidated",
        "merged": merged,
        "rules": rules,
        "rewrite": rewrite_result,
        "telemetry": snap,
        "ts": _now(),
    }
    _log(row)
    post("spark", row)
    write_snapshot()
    return row


def pair(task_text: str = "cycle") -> dict[str, Any]:
    """Run control then treatment on one proposed task and record the twin delta.

    Control is evaluated first so treatment field updates cannot leak into it.
    A held-out live comparison is written afterward and never trains on the
    held-out family.
    """
    proposal = propose(task_text)
    control = awake(task_text, arm="control", proposal=proposal)
    treatment = awake(task_text, arm="treatment", proposal=proposal)
    scoreboard = treatment.get("scoreboard") or control.get("scoreboard")
    heldout = compare_live()
    heldout_path = _data() / "heldout.json"
    heldout_path.write_text(json.dumps(heldout, indent=2))
    result = {
        "mode": "pair",
        "proposal": proposal,
        "control": control,
        "treatment": treatment,
        "scoreboard": scoreboard,
        "learning_measurement": (
            {
                "paired": True,
                "delta": scoreboard["delta"],
                "task": scoreboard["task"],
                "kind": "certified",
                "note": "Only this paired certified delta is a learning measurement.",
            }
            if scoreboard
            else {
                "paired": False,
                "delta": None,
                "note": "No paired scoreboard row was produced.",
            }
        ),
        "heldout_live": heldout,
        "ts": _now(),
    }
    _log({"mode": "pair", "task": proposal.get("task"), "learning_measurement": result["learning_measurement"], "ts": result["ts"]})
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="NOMAD continuous cybernetic loop")
    parser.add_argument("mode", choices=("awake", "sleep", "query", "pair", "heldout"))
    parser.add_argument("--arm", choices=("treatment", "control"), default="treatment")
    parser.add_argument("--task", default="cycle")
    parser.add_argument("--question", default="")
    args = parser.parse_args(argv)
    if args.mode == "awake":
        result = awake(args.task, arm=args.arm)
        print(json.dumps(result, indent=2))
    elif args.mode == "pair":
        print(json.dumps(pair(args.task), indent=2))
    elif args.mode == "query":
        print(json.dumps(field_query(args.question or args.task), indent=2))
    elif args.mode == "heldout":
        print(json.dumps(compare_live(), indent=2))
    else:
        print(json.dumps(sleep(arm=args.arm), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
