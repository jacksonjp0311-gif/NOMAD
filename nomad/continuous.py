"""Continuous cybernetic loop for NOMAD.

Awake: proposer generates the next task from field and SIM, readout biases prior, then synthesis.
Sleep: consolidate, evaluate CA rules on independent snapshots, propose rewrite (no auto-commit).
SIM: one receipt per outcome. No double-count.
Scoreboard: each arm records itself; delta is computed only when both are present.
Observation: writes a live snapshot for external agents on every cycle.
No transformers. Field builds, evolves, proposes, and rewrites itself only after evidence.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .genesis import IOExample, SynthesisTask, synthesize, GrammarPrior
from .mnemonic import EvidenceMemory
from .society import post, update_fitness, gate
from .weights import accumulate, readout, merge_similar
from .automata import try_rules
from .sensors import telemetry
from .sim import recent, should_reinforce, record as sim_record
from .scoreboard import record_arm
from .proposer import propose
from .rewrite import rewrite
from .observe import write_snapshot
from .learner import Counts

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "continuous"
MEMORY_PATH = DATA / "mnemonic.json"
PRIOR_PATH = DATA / "prior.json"
LOG_PATH = DATA / "log.jsonl"
BITS = 4096

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    DATA.mkdir(parents=True, exist_ok=True)

def _hash_bits(text: str, density: int = 64) -> set[int]:
    h = hashlib.sha256(text.encode()).digest()
    bits = set()
    for i in range(density):
        idx = int.from_bytes(h[i % 32:(i % 32) + 4], "big") % BITS
        bits.add(idx)
    return bits

def _examples_for(task: str) -> tuple:
    """Bounded examples that vary with the task label."""
    if "variant" in task or "cycle" not in task:
        return (
            IOExample(2, 3, 5),
            IOExample(5, 7, 12),
            IOExample(1, 1, 2),
        )
    return (
        IOExample(1, 2, 3),
        IOExample(2, 3, 5),
        IOExample(4, 5, 9),
    )

def _load_memory() -> EvidenceMemory:
    if MEMORY_PATH.exists():
        return EvidenceMemory.load(MEMORY_PATH)
    return EvidenceMemory()

def _save_memory(mem: EvidenceMemory) -> None:
    mem.save(MEMORY_PATH)

def _load_prior() -> GrammarPrior:
    prior = GrammarPrior()
    if PRIOR_PATH.exists():
        snap = json.loads(PRIOR_PATH.read_text())
        prior.operator.contextual = snap.get("contextual", True)
        for fam, counts in snap.get("global", {}).items():
            prior.operator.global_counts[fam] = Counts(**counts)
        for key, counts in snap.get("contexts", {}).items():
            if ":" in key:
                sig_s, fam = key.split(":", 1)
                try:
                    sig = int(sig_s)
                    prior.operator.context_counts[(sig, fam)] = Counts(**counts)
                except ValueError:
                    pass
    return prior

def _save_prior(prior: GrammarPrior) -> None:
    PRIOR_PATH.write_text(json.dumps(prior.operator.snapshot(), indent=2))

def _log(row: dict[str, Any]) -> None:
    _ensure()
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")

def awake(task_text: str = "cycle", *, arm: str = "treatment") -> dict[str, Any]:
    """One awake cycle. Proposer generates the task, readout biases the prior, then synthesis."""
    _ensure()
    snap = telemetry()
    proposal = propose(task_text)
    task_text = proposal["task"]
    prior = _load_prior()
    query_bits = _hash_bits(task_text)
    context = readout(query_bits)
    if context and any(c["overlap"] > 0 for c in context):
        prior.operator.contextual = True
    history = recent(8)
    public = _examples_for(task_text)
    task = SynthesisTask(
        task_id=f"continuous-{task_text}-{_now()[:13]}",
        source="def solve(x, y):\n    return 0\n",
        public=public,
        challenge=(),
        final=(),
    )
    result = synthesize(task, prior=prior)
    outcome = {
        "mode": "awake",
        "arm": arm,
        "task": task_text,
        "proposal": proposal,
        "context": context,
        "sim_history": history,
        "candidate": result.candidate,
        "public_correct": result.public_correct,
        "abstained": result.abstained,
        "telemetry": snap,
        "ts": _now(),
    }
    decision = gate(outcome)
    outcome["gate"] = decision
    _log(outcome)
    post("keeper", outcome)
    predicted = proposal.get("reason", "public success")
    measured = "public_correct" if decision.get("pass") else "fail"
    sim_record(
        edit=f"packet:{task_text}",
        predicted=predicted,
        measured=measured,
        context={"task": task_text, "arm": arm},
    )
    if arm == "treatment":
        update_fitness(bool(decision.get("pass")))
        if decision.get("pass") and should_reinforce(predicted):
            accumulate(
                query_bits,
                True,
                label=task_text,
                predicted=predicted,
                measured=measured,
                context={"task": task_text, "arm": arm, "proposal": proposal},
            )
    paired = record_arm(task.task_id, arm, bool(decision.get("pass")))
    if paired:
        outcome["scoreboard"] = paired
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
    prior = _load_prior()
    _save_prior(prior)
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

def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="NOMAD continuous cybernetic loop")
    parser.add_argument("mode", choices=("awake", "sleep"))
    parser.add_argument("--arm", choices=("treatment", "control"), default="treatment")
    parser.add_argument("--task", default="cycle")
    args = parser.parse_args(argv)
    if args.mode == "awake":
        result = awake(args.task, arm=args.arm)
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(sleep(arm=args.arm), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
