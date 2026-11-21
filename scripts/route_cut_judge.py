"""Measurement only: ROUTE_CUT (learned ROUTE relevance fills the tail of the
PORT_SCAN bank cut when memory is large); see docs/ROUTE_CUT.md.

    python3 scripts/route_cut_judge.py                 # primary: the frozen TRANSFER-7 suite
    python3 scripts/route_cut_judge.py --lofo          # leave-one-family-out, ROUTE_CUT off vs on
    python3 scripts/route_cut_judge.py --suite PATH    # a dev suite (any transfer catalogue)

Every earlier frozen suite: SWITCH=NOMAD_ROUTE_CUT scripts/switch_regress.py.

Pre-registered in docs/ROUTE_CUT.md. Budget 10,000, each suite's max_size,
every other switch at its default. Two trained fields: math_sci (scripts/
transfer_suite.py) and practice = math_sci further trained (1 round) on the
1,000 practice tasks (scripts/graph_judge.py practice_field; the bank
overflows PORT_SCAN only there). For each field F: F (ROUTE_CUT off), F_cut,
F_cut_sh0..2 (the same field with its ROUTE table shuffled within each SENSE
key, seeds 0-2: route_judge.permuted). Plus cold / empty / empty_cut.
Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import invent_judge as IJ  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

SHUFFLE_SEEDS = (0, 1, 2)
OFF = {"NOMAD_ROUTE_CUT": "off"}
ON = {"NOMAD_ROUTE_CUT": "on"}


def practice_field():
    import graph_judge as GJ
    return GJ.practice_field()


def field_arms(name: str, p, vs, kw_extra: dict) -> dict:
    import route_judge as RJ
    kw = dict(prior=p, variation=vs, **kw_extra)
    a = {name: (OFF, kw), f"{name}_cut": (ON, kw)}
    for s in SHUFFLE_SEEDS:
        a[f"{name}_cut_sh{s}"] = (ON, dict(kw, prior=RJ.permuted(p, s)))
    return a


def primary_arms() -> dict:
    p, vs = TS.fields()["math_sci"]
    pp, pvs = practice_field()
    a = {"cold": (OFF, dict(prior=None)),
         "empty": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_cut": (ON, dict(prior=WorldPrior(), casesplit=True))}
    a.update(field_arms("trained", p, vs, dict(casesplit=True)))
    a.update(field_arms("practice", pp, pvs, dict(casesplit=True)))
    return a


def field_verdict(out: dict, name: str) -> dict:
    c, per = out["certified"], out["per_task[certified, evals, via, candidate]"]
    lost = [f for f, d in per.items() if d[name][0] and not d[f"{name}_cut"][0]]
    sh = [c[f"{name}_cut_sh{s}"] for s in SHUFFLE_SEEDS]
    return {"off": c[name], "cut": c[f"{name}_cut"], "shuffled": sh, "lost": lost,
            "beats_off": bool(c[f"{name}_cut"] >= c[name] + 1),
            "beats_every_shuffled": bool(all(c[f"{name}_cut"] >= r + 1 for r in sh))}


def verdict(out: dict) -> dict:
    c, ev, per = out["certified"], out["evaluations"], out["per_task[certified, evals, via, candidate]"]
    v = {k: field_verdict(out, k) for k in ("trained", "practice")}
    v["empty_identical"] = bool(c["empty_cut"] == c["empty"] and ev["empty_cut"] == ev["empty"]
                                and all(per[f]["empty_cut"][:2] == per[f]["empty"][:2] for f in per))
    worse = out["worse_than_cold"]
    v["new_worse_than_cold"] = {k: sorted(set(worse[f"{k}_cut"]) - set(worse[k])) for k in ("trained", "practice")}
    v["primary_pass"] = bool(any(v[k]["beats_off"] and v[k]["beats_every_shuffled"] for k in ("trained", "practice"))
                             and not any(v[k]["lost"] for k in ("trained", "practice"))
                             and v["empty_identical"] and not any(v["new_worse_than_cold"].values()))
    return v


def lofo() -> dict:
    import variation_probe as VP
    from nomad.world_tasks import all_training
    ts = all_training()
    tot = {"cold": 0, "trained": 0, "trained_cut": 0}
    worst = {"trained": 0.0, "trained_cut": 0.0}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            c = evaluate(t, max_eval=20000)[0]
            tot["cold"] += c.evaluations
            for k, setting in (("trained", OFF), ("trained_cut", ON)):
                with env(**setting):
                    e = evaluate(t, prior=p, variation=vs, max_eval=20000)[0]
                tot[k] += e.evaluations
                worst[k] = max(worst[k], e.evaluations / max(1, c.evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


def main() -> int:
    if "--lofo" in sys.argv:
        print(json.dumps({"lofo": lofo()}, indent=1))
        return 0
    import route_cut_suite as RCS
    if "--suite" in sys.argv:
        suite, _e, hard = RCS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = RCS.load(RCS.OUT, check=True)
    out = IJ.score(suite["hard"], hard, primary_arms(), suite["max_size"])
    out["sha256"] = RCS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
