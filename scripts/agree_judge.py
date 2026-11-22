"""Measurement only: AGREE (a budget-neutral LET2 with an agreement guard); see docs/AGREE.md.

    PYTHONHASHSEED=0 python3 scripts/agree_judge.py                 # the frozen sealed AGREE suite (hash-checked)
    PYTHONHASHSEED=0 python3 scripts/agree_judge.py --suite PATH    # a dev suite (no hash check)
    PYTHONHASHSEED=0 python3 scripts/agree_judge.py --lofo          # leave-one-family-out, AGREE off vs on

Every earlier frozen suite: PYTHONHASHSEED=0 SWITCH=NOMAD_AGREE scripts/switch_regress.py.

Pre-registered in docs/AGREE.md. Budget 10,000, the suite's max_size, every other switch at its default
(NOMAD_LET2, NOMAD_DISCRIM, NOMAD_LET and NOMAD_MERGE off). The script re-executes itself under
PYTHONHASHSEED=0 when that is not already set. Arms: cold (prior=None) / empty_off / empty_on; for each
field F in trained (all_sci, scored), math_sci and practice (math_sci + 1 practice round,
scripts/graph_judge.py): F_off, **F_on** (NOMAD_AGREE=on), F_let2 (NOMAD_LET2=on: the same stage
unguarded, report), F_shuf (control: each alternative's outcomes compared on the wrong distinguishing
rows), F_rw (control: each alternative's outcomes compared with the hit's on rows whose int inputs are
rotated and incremented by one: agreement on the wrong question). Parallel processes (AGREE_JOBS, default 8); deterministic per
(task, arm). Changes no live state.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import agree_suite as XS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000
BASE = {"NOMAD_LET2": "off", "NOMAD_DISCRIM": "off", "NOMAD_AGREE": "off", "NOMAD_AGREE_CONTROL": ""}
OFF = dict(BASE)
ON = dict(BASE, NOMAD_AGREE="on")
LET2 = dict(BASE, NOMAD_LET2="on")
SHUF = dict(ON, NOMAD_AGREE_CONTROL="shuffled")
RW = dict(ON, NOMAD_AGREE_CONTROL="rewired")
FIELDS = ("trained", "math_sci", "practice")
VARIANTS = (("off", OFF), ("on", ON), ("let2", LET2), ("shuf", SHUF), ("rw", RW))


def arms() -> dict:
    import graph_judge as GJ
    f = TS.fields()
    fl = {"trained": f["all_sci"], "math_sci": f["math_sci"], "practice": GJ.practice_field()}
    a = {"cold": (OFF, dict(prior=None)),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True))}
    for name, (p, vs) in fl.items():
        kw = dict(prior=p, variation=vs, casesplit=True)
        for v, setting in VARIANTS:
            a[f"{name}_{v}"] = (setting, kw)
    return a


_G: dict = {}


def _one(job):
    i, k = job
    setting, kw = _G["arms"][k]
    with env(**setting):
        ev = evaluate(_G["tasks"][i], max_eval=BUDGET, max_size=_G["max_size"], **kw)[0]
    return i, k, ev


def score(entries, tasks, arm_kw, max_size) -> dict:
    from multiprocessing import get_context
    _G.update(arms=arm_kw, tasks=tasks, max_size=max_size)
    jobs = [(i, k) for i in range(len(tasks)) for k in arm_kw]
    with get_context("fork").Pool(int(os.environ.get("AGREE_JOBS", "8"))) as pool:
        res = pool.map(_one, jobs, chunksize=1)
    got = {(i, k): ev for i, k, ev in res}
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    for i, e in enumerate(entries):
        r = {k: got[(i, k)] for k in arm_kw}
        c = r["cold"]
        for k, ev in r.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate]
                            for k, ev in r.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "worse_than_cold": worse,
            "per_task[certified, evals, via, candidate]": per}


def lost(per: dict, a: str, b: str) -> list:
    """Tasks arm ``a`` certifies and arm ``b`` does not."""
    return sorted(f for f, d in per.items() if d[a][0] and not d[b][0])


def verdict(out: dict) -> dict:
    """Pre-registered criteria 1-4 (docs/AGREE.md); 5-6 come from switch_regress / LOFO / tests."""
    c, ev = out["certified"], out["evaluations"]
    per, worse = out["per_task[certified, evals, via, candidate]"], out["worse_than_cold"]

    def wrong_hits(arm):
        return sorted(t for t, d in per.items() if d[arm][2] == "port:let2" and not d[arm][0])

    v = {"fields": {f: {"off": c[f"{f}_off"], "on": c[f"{f}_on"], "let2_unguarded": c[f"{f}_let2"],
                        "shuffled_control": c[f"{f}_shuf"], "rewired_control": c[f"{f}_rw"],
                        "lost_on": lost(per, f"{f}_off", f"{f}_on"),
                        "lost_let2": lost(per, f"{f}_off", f"{f}_let2"),
                        "lost_shuf": lost(per, f"{f}_off", f"{f}_shuf"),
                        "lost_rw": lost(per, f"{f}_off", f"{f}_rw"),
                        "more_evals_on": sorted(t for t, d in per.items() if d[f"{f}_off"][0] and d[f"{f}_on"][0]
                                                and d[f"{f}_on"][1] > d[f"{f}_off"][1]),
                        "wrong_let2_returns": {v_: wrong_hits(f"{f}_{v_}") for v_ in ("on", "let2", "shuf", "rw")},
                        "evals": {v_: ev[f"{f}_{v_}"] for v_, _s in VARIANTS},
                        "new_worse_than_cold": sorted(set(worse[f"{f}_on"]) - set(worse[f"{f}_off"]))}
                    for f in FIELDS}}
    fl = v["fields"]
    v["c1_trained_gain"] = c["trained_on"] - c["trained_off"]
    v["criterion_1"] = bool(v["c1_trained_gain"] >= 2)
    v["criterion_2_empty_identical"] = bool(all(d["empty_on"][:2] == d["empty_off"][:2] for d in per.values()))
    v["criterion_3_no_loss"] = bool(all(not fl[f]["lost_on"] and not fl[f]["new_worse_than_cold"]
                                        and not fl[f]["more_evals_on"] for f in FIELDS)
                                    and set(worse["empty_on"]) <= set(worse["empty_off"]))
    on_sum = sum(c[f"{f}_on"] for f in FIELDS)
    for ctl in ("shuf", "rw"):
        ctl_sum = sum(c[f"{f}_{ctl}"] for f in FIELDS)
        kept = sorted({(f, t) for f in FIELDS for t in fl[f][f"lost_{ctl}"]} - {(f, t) for f in FIELDS for t in fl[f]["lost_on"]})
        v[f"c4_{ctl}"] = {"on_sum": on_sum, "control_sum": ctl_sum, "control_losses_on_keeps": kept,
                          "pass": bool(on_sum > ctl_sum or (on_sum >= ctl_sum and kept))}
    v["criterion_4_agreement_carries_it"] = bool(v["c4_shuf"]["pass"] and v["c4_rw"]["pass"])
    v["report_let2_unguarded"] = {f: {"let2": c[f"{f}_let2"], "on": c[f"{f}_on"], "lost_let2": fl[f]["lost_let2"]}
                                  for f in FIELDS}
    return v


def lofo() -> dict:
    import variation_probe as VP
    from nomad.world_tasks import all_training
    ts = all_training()
    tot = {"cold": 0, "trained": 0, "trained_agree": 0}
    worst = {"trained": 0.0, "trained_agree": 0.0}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            c = evaluate(t, max_eval=20000)[0]
            tot["cold"] += c.evaluations
            for k, setting in (("trained", OFF), ("trained_agree", ON)):
                with env(**setting):
                    e = evaluate(t, prior=p, variation=vs, max_eval=20000)[0]
                tot[k] += e.evaluations
                worst[k] = max(worst[k], e.evaluations / max(1, c.evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


def main() -> int:
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.execve(sys.executable, [sys.executable] + sys.argv, dict(os.environ, PYTHONHASHSEED="0"))
    if "--lofo" in sys.argv:
        print(json.dumps({"lofo": lofo()}, indent=1))
        return 0
    if "--suite" in sys.argv:
        suite, _e, hard = XS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = XS.load(XS.OUT, check=True)
    out = score(suite["hard"], hard, arms(), suite["max_size"])
    out["sha256"] = XS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
