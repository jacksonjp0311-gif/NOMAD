"""Self-evolution organ: mutate one genome gene, keep it only if it is better.

propose  -> one bounded mutation of one gene (seeded, replayable)
benchmark-> fixed offline curriculum on frozen families + never-trained probes
accept   -> strictly more held-out wins, or equal wins and less total search,
            AND the full unit-test suite passes
commit   -> the workflow commits data/genome.json + data/evolution.jsonl to
            main with a "nomad-evolve:" message
guard    -> every sleep compares live world twin results before/after the
            last accepted change; on regression it asks the workflow to
            `git revert` that commit

The organism evolves its own parameters, never its own code. WITNESS still
certifies every program; the benchmark only decides between parameter sets.
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import genome
from .paths import PACKAGE_ROOT, data_root

GUARD_MIN_PAIRS = 6
GUARD_MARGIN = 0.15  # relative worsening of mean treatment/control cost ratio that triggers revert


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_path() -> Path:
    return data_root() / "evolution.jsonl"


def _log(row: dict) -> None:
    log_path().parent.mkdir(parents=True, exist_ok=True)
    with log_path().open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def history() -> list[dict]:
    if not log_path().exists():
        return []
    return [json.loads(l) for l in log_path().read_text().splitlines() if l.strip()]


# ------------------------------------------------------------------ propose

def propose(genes: dict[str, Any], seed: int) -> tuple[dict[str, Any], str]:
    rng = random.Random(seed)
    cand = dict(genes)
    gene = rng.choice(["decay", "library_k"])  # the genes the offline benchmark can see
    lo, hi = genome.BOUNDS[gene]
    if gene == "decay":
        step = rng.choice([-0.03, -0.02, -0.01, 0.01, 0.02])
        cand[gene] = round(min(hi, max(lo, genes[gene] + step)), 3)
    else:
        cand[gene] = int(min(hi, max(lo, genes[gene] + rng.choice([-2, -1, 1, 2]))))
    return cand, gene


# ------------------------------------------------------------------ benchmark

def benchmark(genes: dict[str, Any], rounds: int = 2) -> dict[str, Any]:
    """Deterministic offline fitness. Uses frozen training families and probes only."""
    from .world import OPSETS, WorldPrior, evaluate
    from .world_loop import probe_heldout
    from .world_tasks import all_training

    field = WorldPrior()
    field.library_k = int(genes["library_k"])
    train_evals = 0
    certified = 0
    for rnd in range(rounds):
        for t in all_training():
            ev, r = evaluate(t, prior=field)
            if rnd == rounds - 1:
                train_evals += ev.evaluations
                certified += int(ev.certified)
            if ev.certified and r is not None:
                field.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs)
                field.decay(float(genes["decay"]))
    probes = probe_heldout(field, write=False)["probes"]
    wins = sum(1 for v in probes.values() if v["field_beats_control"])
    probe_evals = sum(v["field"]["evaluations"] for v in probes.values())
    return {"heldout_wins": wins, "train_evaluations": train_evals, "train_certified": certified,
            "probe_evaluations": probe_evals, "total_evaluations": train_evals + probe_evals,
            "probes": {k: v["kind"] for k, v in probes.items()}}


def better(a: dict, b: dict) -> bool:
    """Is benchmark a strictly better than b?"""
    if a["train_certified"] < b["train_certified"]:
        return False
    if a["heldout_wins"] != b["heldout_wins"]:
        return a["heldout_wins"] > b["heldout_wins"]
    return a["total_evaluations"] < b["total_evaluations"]


def run_tests() -> bool:
    p = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"],
                       cwd=PACKAGE_ROOT, capture_output=True, text=True, timeout=1200)
    return p.returncode == 0


# ------------------------------------------------------------------ live metric

def live_cost_ratio(rows: list[dict]) -> float | None:
    """Mean treatment/control evaluation ratio over both-certified world pairs (lower is better)."""
    ratios = []
    for r in rows:
        if not str(r.get("task", "")).startswith("world:"):
            continue
        if r.get("treatment") and r.get("control") and r.get("control_evaluations"):
            ratios.append(r["treatment_evaluations"] / max(1, r["control_evaluations"]))
        elif r.get("control") and not r.get("treatment"):
            ratios.append(2.0)  # field lost a program control found: count as heavy regression
    return sum(ratios) / len(ratios) if ratios else None


# ------------------------------------------------------------------ organ entry points

def evolve(*, seed: int | None = None, tests: bool = True) -> dict[str, Any]:
    from .scoreboard import recent
    current = genome.load()
    if seed is None:
        seed = int(hashlib.sha256(_now().encode()).hexdigest()[:8], 16)
    cand, gene = propose(current, seed)
    if cand == current:
        return {"accepted": False, "reason": "no_change", "gene": gene}
    base = benchmark(current)
    new = benchmark(cand)
    row: dict[str, Any] = {"ts": _now(), "seed": seed, "gene": gene, "before": current, "after": cand,
                           "benchmark_before": base, "benchmark_after": new}
    if not better(new, base):
        row.update(accepted=False, reason="not_better")
        _log(row)
        return row
    if tests:
        genome.save(cand, note=f"trial {gene}")
        ok = run_tests()
        if not ok:
            genome.save(current, note="restored after failed tests")
            row.update(accepted=False, reason="tests_failed")
            _log(row)
            return row
    genome.save(cand, note=f"evolved {gene} {current[gene]} -> {cand[gene]}")
    row.update(accepted=True, status="pending_verification",
               live_ratio_before=live_cost_ratio(recent(64)),
               id=hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()[:10])
    _log(row)
    return row


def guard() -> dict[str, Any]:
    """Decide keep / revert / wait for the most recent pending accepted change."""
    from .scoreboard import recent
    hist = history()
    pending = [r for r in hist if r.get("accepted") and r.get("status") == "pending_verification"]
    resolved = {r.get("resolves") for r in hist if r.get("resolves")}
    pending = [r for r in pending if r.get("id") not in resolved]
    if not pending:
        return {"decision": "none"}
    last = pending[-1]
    rows = [r for r in recent(256) if str(r.get("task", "")).startswith("world:") and r.get("ts", "") > last["ts"]]
    if len(rows) < GUARD_MIN_PAIRS:
        return {"decision": "wait", "id": last["id"], "pairs_since": len(rows)}
    after = live_cost_ratio(rows)
    before = last.get("live_ratio_before")
    regressed = before is not None and after is not None and after > before * (1 + GUARD_MARGIN)
    decision = "revert" if regressed else "keep"
    _log({"ts": _now(), "resolves": last["id"], "decision": decision,
          "live_ratio_before": before, "live_ratio_after": after, "pairs": len(rows)})
    return {"decision": decision, "id": last["id"], "before": before, "after": after}


EVOLVE_EVERY_MIN = 120


def should_evolve() -> bool:
    """Evolve only when nothing awaits verification and the last attempt is old enough."""
    hist = history()
    resolved = {r.get("resolves") for r in hist if r.get("resolves")}
    if any(r.get("accepted") and r.get("status") == "pending_verification" and r.get("id") not in resolved
           for r in hist):
        return False
    attempts = [r for r in hist if "gene" in r]
    if not attempts:
        return True
    last = datetime.strptime(attempts[-1]["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() >= EVOLVE_EVERY_MIN * 60


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="NOMAD self-evolution organ")
    ap.add_argument("cmd", choices=("evolve", "guard", "benchmark", "should"))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-tests", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "evolve":
        out = evolve(seed=a.seed, tests=not a.no_tests)
    elif a.cmd == "should":
        out = {"should": should_evolve()}
    elif a.cmd == "guard":
        out = guard()
    else:
        out = benchmark(genome.load())
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
