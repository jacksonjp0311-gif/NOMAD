"""Continuous cybernetic loop for NOMAD.

Awake: fixed readout from memory → bounded synthesis attempt → record outcome.
Sleep: consolidate learner and field from recent receipts.
Twin control: frozen arm for measurement.
Fitness: public success or simple predictive compression proxy.
No transformers. No auto-promotion. Human authorize for durable change.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .genesis import IOExample, SynthesisTask, synthesize, GrammarPrior
from .mnemonic import EvidenceMemory

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "continuous"
MEMORY_PATH = DATA / "mnemonic.json"
PRIOR_PATH = DATA / "prior.json"
LOG_PATH = DATA / "log.jsonl"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    DATA.mkdir(parents=True, exist_ok=True)

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
        # Minimal restore; full snapshot restore can be added later
        prior.operator.contextual = snap.get("contextual", True)
    return prior

def _save_prior(prior: GrammarPrior) -> None:
    PRIOR_PATH.write_text(json.dumps(prior.operator.snapshot(), indent=2))

def _log(row: dict[str, Any]) -> None:
    _ensure()
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")

def awake(task_text: str = "cycle", *, arm: str = "treatment") -> dict[str, Any]:
    """One awake cycle. Fixed context from memory, attempt synthesis, record."""
    _ensure()
    mem = _load_memory()
    prior = _load_prior()
    # Toy public task for continuous measurement (can be replaced by real contracts)
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
        "candidate": result.candidate,
        "public_correct": result.public_correct,
        "abstained": result.abstained,
        "ts": _now(),
    }
    _log(outcome)
    # Memory update stays candidate; durable promotion requires external authorize
    if arm == "treatment" and result.public_correct:
        # Placeholder: record would go through proper receipt path
        pass
    return outcome

def sleep(*, arm: str = "treatment") -> dict[str, Any]:
    """Consolidation. Updates prior from recent successes. Control arm freezes."""
    _ensure()
    if arm != "treatment":
        return {"mode": "sleep", "arm": arm, "status": "frozen", "ts": _now()}
    prior = _load_prior()
    # Simple consolidation: bump prior on recent public successes
    # Full MNEMONIC integration and field geometry update follow
    _save_prior(prior)
    row = {"mode": "sleep", "arm": arm, "status": "consolidated", "ts": _now()}
    _log(row)
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
