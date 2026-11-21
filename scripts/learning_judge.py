"""Measurement only: does learned memory count? The 3-arm learning judge.

    python3 scripts/learning_judge.py              # JSON to stdout (sealed suites)
    python3 scripts/learning_judge.py --no-practice --no-lofo   # quicker

Pre-registered in docs/PORT.md. Budget 10,000, each suite's max_size.

Arms:
- cold:              the twin control (prior=None)
- empty:             WorldPrior(), every search feature on, no memory
- trained:           trained only on training families (16 WORLD families;
                     science also its 14 easy families), never a sealed task
- trained_port_off:  the same field with NOMAD_PORT=off (main before PORT)
- trained_practice:  deep only, report: trained + 1,000 generated practice
                     tasks (sealed look-alikes excluded by row behaviour)
Sections: lofo (16 families), deep (frozen, hash-checked), science hard
(frozen, hash-checked). Changes no live state.
"""
from __future__ import annotations

import json
import os
import random
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deep_suite as D  # noqa: E402
import science_probe as SP  # noqa: E402
import science_suite as SS  # noqa: E402
import variation_probe as VP  # noqa: E402
from nomad.world import WorldPrior, evaluate, run  # noqa: E402
from nomad.world_tasks import all_training  # noqa: E402

BUDGET = 10000
PRACTICE_SEED = 101
PRACTICE_N = 1000


@contextmanager
def port(v: str):
    old = os.environ.get("NOMAD_PORT")
    os.environ["NOMAD_PORT"] = v
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("NOMAD_PORT", None)
        else:
            os.environ["NOMAD_PORT"] = old


def practice_tasks(seed: int = PRACTICE_SEED, n: int = PRACTICE_N, exclude: set | None = None) -> list:
    """Generated (x, y) int practice tasks, the deep generator's grammar at sizes 5-12.

    Any task whose values on all task rows equal a sealed deep task's are
    skipped (leakage guard; the sealed values are read only for this)."""
    rng = random.Random(seed)
    exclude = exclude or set()
    seen, out = set(), []
    rows = D.ALL_ROWS
    while len(out) < n:
        tree = D.sample(rng, rng.randint(5, 12))
        beh = D._behaviour(lambda r: run(tree, r), D.PROBE_ROWS + rows)
        tv = beh[len(D.PROBE_ROWS):]
        if (any(v is None for v in tv) or len(set(tv[:5])) == 1
                or all(v == r["x"] for v, r in zip(tv, rows)) or all(v == r["y"] for v, r in zip(tv, rows))):
            continue
        if beh in seen or tuple(tv) in exclude:
            continue
        seen.add(beh)
        i = len(out)
        out.append(D.to_task({"task_id": f"p-{i}", "family": f"practice_{i:04d}", "tree": tree, "values": list(tv)}))
    return out


def score(entries, tasks, arms, max_size):
    per, cert, evals = {}, {k: 0 for k in arms}, {k: 0 for k in arms}
    worse, lost = {k: [] for k in arms}, {k: [] for k in arms}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw) in arms.items():
            with port(setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0]
        c, b = res["cold"], res["trained_port_off"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
            if b.certified and not ev.certified:
                lost[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals,
            "trained_minus_empty": cert["trained"] - cert["empty"],
            "worse_than_cold": worse, "port_off_wins_lost": lost,
            "per_task[certified, evals, via, candidate]": per}


def deep(practice: bool = True) -> dict:
    suite, tasks = D.load()
    p, vs, _ = VP.train()
    arms = {"cold": ("on", dict(prior=None)), "empty": ("on", dict(prior=WorldPrior())),
            "trained": ("on", dict(prior=p, variation=vs)),
            "trained_port_off": ("off", dict(prior=p, variation=vs))}
    if practice:
        p2, vs2, _ = VP.train()
        excl = {tuple(e["values"]) for e in suite["tasks"]}
        SP.train_more(p2, vs2, practice_tasks(exclude=excl), rounds=1)
        arms["trained_practice"] = ("on", dict(prior=p2, variation=vs2))
    out = score(suite["tasks"], tasks, arms, suite["max_size"])
    out["sha256"] = D.suite_hash(suite)
    return out


def science() -> dict:
    suite, easy, hard = SS.load(SS.OUT, check=True)
    p, vs, _ = VP.train()
    SP.train_more(p, vs, easy)
    arms = {"cold": ("on", dict(prior=None)), "empty": ("on", dict(prior=WorldPrior(), casesplit=True)),
            "trained": ("on", dict(prior=p, variation=vs, casesplit=True)),
            "trained_port_off": ("off", dict(prior=p, variation=vs, casesplit=True))}
    out = score(suite["hard"], hard, arms, suite["max_size"])
    out["sha256"] = SS.suite_hash(suite)
    return out


def lofo() -> dict:
    ts = all_training()
    tot = {"cold": 0, "trained": 0, "trained_port_off": 0}
    worst = {"trained": 0.0, "trained_port_off": 0.0}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            c = evaluate(t, max_eval=20000)[0]
            tot["cold"] += c.evaluations
            for k, setting in (("trained", "on"), ("trained_port_off", "off")):
                with port(setting):
                    ev = evaluate(t, prior=p, variation=vs, max_eval=20000)[0]
                tot[k] += ev.evaluations
                worst[k] = max(worst[k], ev.evaluations / max(1, c.evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


if __name__ == "__main__":
    out = {}
    if "--no-lofo" not in sys.argv:
        out["lofo"] = lofo()
    out["deep"] = deep(practice="--no-practice" not in sys.argv)
    out["science_hard"] = science()
    print(json.dumps(out, indent=1, default=str))
