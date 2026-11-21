"""Measurement only: MERGE (probe-equivalent portable-bank blocks are one idea;
the evaluations duplicates would cost buy distinct anchors); see docs/MERGE.md.

    python3 scripts/merge_judge.py                 # primary: the frozen TRANSFER-8 suite
    python3 scripts/merge_judge.py --science       # control part of criterion 2: science hard, trained field
    python3 scripts/merge_judge.py --lofo          # leave-one-family-out, MERGE off vs on
    python3 scripts/merge_judge.py --suite PATH    # a dev suite (any transfer catalogue)

Every earlier frozen suite: SWITCH=NOMAD_MERGE scripts/switch_regress.py.

Pre-registered in docs/MERGE.md. Budget 10,000, each suite's max_size, every
other switch at its default. Fields: trained = math_sci (scripts/
transfer_suite.py), practice = math_sci + 1 round on the 1,000 practice tasks
(scripts/graph_judge.py practice_field). For each field F: F (MERGE off),
F_merge, F_rw0..2 (MERGE on with every duplicate re-pointed to a random
non-equivalent earlier block: same number of skipped evaluations, wrong
merges; NOMAD_MERGE_CONTROL=rewired:<seed>). Plus cold / empty / empty_merge.
Arms run in parallel processes (MERGE_JOBS, default 8); results are
deterministic per (task, arm). Changes no live state.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import transfer_suite as TS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000
RW_SEEDS = (0, 1, 2)
OFF = {"NOMAD_MERGE": "off", "NOMAD_MERGE_CONTROL": ""}
ON = {"NOMAD_MERGE": "on", "NOMAD_MERGE_CONTROL": ""}


def RW(s: int) -> dict:
    return {"NOMAD_MERGE": "on", "NOMAD_MERGE_CONTROL": f"rewired:{s}"}


def field_arms(name: str, p, vs, kw_extra: dict) -> dict:
    kw = dict(prior=p, variation=vs, **kw_extra)
    a = {name: (OFF, kw), f"{name}_merge": (ON, kw)}
    for s in RW_SEEDS:
        a[f"{name}_rw{s}"] = (RW(s), kw)
    return a


def primary_arms() -> dict:
    import graph_judge as GJ
    p, vs = TS.fields()["math_sci"]
    pp, pvs = GJ.practice_field()
    a = {"cold": (OFF, dict(prior=None)),
         "empty": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_merge": (ON, dict(prior=WorldPrior(), casesplit=True))}
    a.update(field_arms("trained", p, vs, dict(casesplit=True)))
    a.update(field_arms("practice", pp, pvs, dict(casesplit=True)))
    return a


_G: dict = {}


def _one(job):
    i, k = job
    setting, kw = _G["arms"][k]
    with env(**setting):
        ev = evaluate(_G["tasks"][i], max_eval=BUDGET, max_size=_G["max_size"], **kw)[0]
    return i, k, ev


def score(entries, tasks, arms, max_size, base: str = "trained") -> dict:
    from multiprocessing import get_context
    _G.update(arms=arms, tasks=tasks, max_size=max_size)
    jobs = [(i, k) for i in range(len(tasks)) for k in arms]
    with get_context("fork").Pool(int(os.environ.get("MERGE_JOBS", "8"))) as pool:
        res = pool.map(_one, jobs, chunksize=1)
    got = {(i, k): ev for i, k, ev in res}
    per, cert, evals = {}, {k: 0 for k in arms}, {k: 0 for k in arms}
    worse, by_dom = {k: [] for k in arms}, {k: {} for k in arms}
    for i, e in enumerate(entries):
        r = {k: got[(i, k)] for k in arms}
        c = r.get("cold")
        for k, ev in r.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            d = by_dom[k].setdefault(e.get("domain") or e.get("kind") or "all", [0, 0])
            d[0] += ev.certified
            d[1] += 1
            if c is not None and ((c.certified and not ev.certified)
                                  or (c.certified and ev.certified and ev.evaluations > c.evaluations)):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in r.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "by_domain": by_dom,
            "worse_than_cold": worse, "per_task[certified, evals, via, candidate]": per}


def lost(per: dict, a: str, b: str) -> list:
    """Tasks arm ``a`` certifies and arm ``b`` does not."""
    return sorted(f for f, d in per.items() if d[a][0] and not d[b][0])


def field_verdict(out: dict, name: str) -> dict:
    c, per = out["certified"], out["per_task[certified, evals, via, candidate]"]
    rw = [c[f"{name}_rw{s}"] for s in RW_SEEDS]
    return {"off": c[name], "merge": c[f"{name}_merge"], "rewired": rw,
            "lost": lost(per, name, f"{name}_merge"),
            "rewired_lost": {s: lost(per, name, f"{name}_rw{s}") for s in RW_SEEDS},
            "beats_off": bool(c[f"{name}_merge"] >= c[name] + 1),
            "at_least_every_rewired": bool(all(c[f"{name}_merge"] >= r for r in rw))}


def verdict(out: dict) -> dict:
    c, ev, per = out["certified"], out["evaluations"], out["per_task[certified, evals, via, candidate]"]
    v = {k: field_verdict(out, k) for k in ("trained", "practice")}
    v["empty_identical"] = bool(c["empty_merge"] == c["empty"] and ev["empty_merge"] == ev["empty"]
                                and all(d["empty"][:2] == d["empty_merge"][:2] for d in per.values()))
    worse = out["worse_than_cold"]
    v["new_worse_than_cold"] = {k: sorted(set(worse[f"{k}_merge"]) - set(worse[k])) for k in ("trained", "practice")}
    v["criterion_1_fields"] = [k for k in ("trained", "practice") if v[k]["beats_off"]]
    v["criterion_3_empty"] = v["empty_identical"]
    v["criterion_4_no_loss"] = bool(not any(v[k]["lost"] for k in ("trained", "practice"))
                                    and not any(v["new_worse_than_cold"].values()))
    return v


def science() -> dict:
    """Control part of criterion 2: the science-hard sealed suite on its trained field."""
    import science_suite as SS
    import science_probe as SP
    import variation_probe as VP
    suite, easy, hard = SS.load(SS.OUT, check=True)
    p, vs, _ = VP.train()
    SP.train_more(p, vs, easy)
    arms = {"cold": (OFF, dict(prior=None))}
    arms.update(field_arms("trained", p, vs, dict(casesplit=True)))
    out = score(suite["hard"], hard, arms, suite["max_size"])
    out["sha256"] = SS.suite_hash(suite)
    per = out["per_task[certified, evals, via, candidate]"]
    out["verdict"] = {"merge_lost": lost(per, "trained", "trained_merge"),
                      "rewired_lost": {s: lost(per, "trained", f"trained_rw{s}") for s in RW_SEEDS}}
    return out


def lofo() -> dict:
    import variation_probe as VP
    from nomad.world_tasks import all_training
    ts = all_training()
    tot = {"cold": 0, "trained": 0, "trained_merge": 0}
    worst = {"trained": 0.0, "trained_merge": 0.0}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            c = evaluate(t, max_eval=20000)[0]
            tot["cold"] += c.evaluations
            for k, setting in (("trained", OFF), ("trained_merge", ON)):
                with env(**setting):
                    e = evaluate(t, prior=p, variation=vs, max_eval=20000)[0]
                tot[k] += e.evaluations
                worst[k] = max(worst[k], e.evaluations / max(1, c.evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


def main() -> int:
    if "--lofo" in sys.argv:
        print(json.dumps({"lofo": lofo()}, indent=1))
        return 0
    if "--science" in sys.argv:
        print(json.dumps(science(), indent=1, default=str))
        return 0
    import merge_suite as MS
    if "--suite" in sys.argv:
        suite, _e, hard = MS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = MS.load(MS.OUT, check=True)
    out = score(suite["hard"], hard, primary_arms(), suite["max_size"])
    out["sha256"] = MS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
