"""Continuous cybernetic loop for NOMAD.

Awake: fixed readout from weight packets → bounded synthesis → record outcome.
Sleep: consolidate and evolve the field with cellular automata. Treatment updates; control freezes.
Society layer: registry, bus, fitness, gate.
Weight packets: sparse binary, splittable, integer overlap. The living field.
Self-Improvement Memory: every successful packet carries predicted and measured effect.
Sensors: local telemetry for the swarm.
No transformers. Field builds and evolves itself on measured success.
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
from .automata import evolve
from .sensors import telemetry
from .sim import recent

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
    return prior

def _save_prior(prior: GrammarPrior) -> None:
    PRIOR_PATH.write_text(json.dumps(prior.operator.snapshot(), indent=2))

def _log(row: dict[str, Any]) -> None:
    _ensure()
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")

def awake(task_text: str = "cycle", *, arm: str = "treatment") -> dict[str, Any]:
    """One awake cycle. Readout from weight packets, attempt synthesis, record."""
    _ensure()
    snap = telemetry()
    prior = _load_prior()
    query_bits = _hash_bits(task_text)
    context = readout(query_bits)
    history = recent(8)
    public = (
        IOExample(1, 2, 3),
        IOExample(2, 3, 5),
        IOExample(4, 5, 9),
    )
    task = SynthesisTask(
        task_id=f"continuous-{_now()}",
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
    if arm == "treatment":
        update_fitness(bool(decision.get("pass")))
        if decision.get("pass"):
            accumulate(
                query_bits,
                True,
                label=task_text,
                predicted="public success on arithmetic",
                measured="public_correct",
                context={"task": task_text, "arm": arm},
            )
    return outcome

def sleep(*, arm: str = "treatment") -> dict[str, Any]:
    """Consolidation and CA evolution. Control arm freezes."""
    _ensure()
    snap = telemetry()
    if arm != "treatment":
        return {"mode": "sleep", "arm": arm, "status": "frozen", "telemetry": snap, "ts": _now()}
    merged = merge_similar()
    evolved = evolve(steps=1)
    prior = _load_prior()
    _save_prior(prior)
    row = {
        "mode": "sleep",
        "arm": arm,
        "status": "consolidated",
        "merged": merged,
        "evolved": evolved,
        "telemetry": snap,
        "ts": _now(),
    }
    _log(row)
    post("spark", row)
    return row

def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="NOMAD continuous cybernetic loop")
    parser.add_argument("mode", choices=("awake", "sleep"))
    parser.add_argument("--arm", choices=("treatment", "control"), default="treatment")
    parser.add_argument("--task", default="cycle")
    args = parser.parse_args(argv)
    if args.mode == "awake":
        print(json.dumps(awake(args.task, arm=args.arm), indent=2))
    else:
        print(json.dumps(sleep(arm=args.arm), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
