"""Measurement only: CERT (stronger functional certification by distinguishing inputs); see docs/CERT.md.

    PYTHONHASHSEED=0 python3 scripts/cert_judge.py                      # the frozen sealed CERT suite (hash-checked)
    PYTHONHASHSEED=0 python3 scripts/cert_judge.py --suite PATH [--catalogue MODULE]   # another suite (no hash check)
    PYTHONHASHSEED=0 python3 scripts/cert_judge.py --lofo               # leave-one-family-out, CERT off vs on

Every earlier frozen suite: PYTHONHASHSEED=0 SWITCH=NOMAD_CERT scripts/switch_regress.py.

Pre-registered in docs/CERT.md. Budget 10,000, the suite's max_size, every other switch at its default
(NOMAD_LET2, NOMAD_DISCRIM, NOMAD_AGREE, NOMAD_LET and NOMAD_MERGE off). Re-executes itself under
PYTHONHASHSEED=0. Arms: cold (prior=None) / empty_off / empty_on; for each field F in trained (all_sci, scored),
math_sci and practice: F_off, **F_on** (NOMAD_CERT=on), F_let2 (NOMAD_LET2=on, unguarded; report),
F_shuf (control: outputs checked against the wrong generated rows), F_rw (control: the fit run on rows whose int
inputs are rotated and incremented by one). Every certified program is audited on AUDIT_N fresh exact rows of the
task's own formula (written independently of the reference tree); ``wrong`` is the number it gets wrong.
Parallel processes (CERT_JOBS, default 8); deterministic per (task, arm). Changes no live state.
"""
from __future__ import annotations

import importlib
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import cert_suite as XS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad.science import _draw, exact_answer  # noqa: E402
from nomad.world import Invalid, WorldPrior, evaluate, run  # noqa: E402

BUDGET = 10000
AUDIT_N = 1000
BASE = {"NOMAD_LET2": "off", "NOMAD_DISCRIM": "off", "NOMAD_AGREE": "off", "NOMAD_CERT": "off", "NOMAD_CERT_CONTROL": ""}
OFF = dict(BASE)
ON = dict(BASE, NOMAD_CERT="on")
LET2 = dict(BASE, NOMAD_LET2="on")
SHUF = dict(ON, NOMAD_CERT_CONTROL="shuffled")
RW = dict(ON, NOMAD_CERT_CONTROL="rewired")
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


def audit(tree, formula, n: int = AUDIT_N) -> int:
    """How many of n fresh exact rows (seeded by the family) the program gets wrong."""
    rng = random.Random(f"audit:{formula.family}")
    rows, tries = [], 0
    while len(rows) < n and tries < 50 * n:
        tries += 1
        r = {k: _draw(rng, formula.ranges[k]) for k in formula.inputs}
        a = exact_answer(formula, r)
        if a is not None:
            rows.append((r, a))
    bad = 0
    for r, a in rows:
        try:
            g = run(tree, r)
        except Invalid:
            g = None
        bad += g != a
    return bad


_G: dict = {}


def _one(job):
    i, k = job
    setting, kw = _G["arms"][k]
    with env(**setting):
        ev = evaluate(_G["tasks"][i], max_eval=BUDGET, max_size=_G["max_size"], **kw)[0]
    wrong = audit(ev.tree, _G["formulas"][_G["tasks"][i].family]) if (ev.certified and ev.tree) else None
    return i, k, ev, wrong


def score(entries, tasks, arm_kw, max_size, formulas) -> dict:
    from multiprocessing import get_context
    _G.update(arms=arm_kw, tasks=tasks, max_size=max_size, formulas=formulas)
    jobs = [(i, k) for i in range(len(tasks)) for k in arm_kw]
    with get_context("fork").Pool(int(os.environ.get("CERT_JOBS", "8"))) as pool:
        res = pool.map(_one, jobs, chunksize=1)
    got = {(i, k): (ev, w) for i, k, ev, w in res}
    per, ncert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    good, bad = {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    for i, e in enumerate(entries):
        r = {k: got[(i, k)] for k in arm_kw}
        c = r["cold"][0]
        for k, (ev, w) in r.items():
            ncert[k] += ev.certified
            evals[k] += ev.evaluations
            if ev.certified:
                good[k] += w == 0
                bad[k] += w != 0
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate, w] for k, (ev, w) in r.items()}
    return {"tasks": len(tasks), "certified": ncert, "audited_correct": good, "certified_wrong": bad,
            "evaluations": evals, "worse_than_cold": worse,
            "per_task[certified, evals, via, candidate, audit_wrong]": per}


def lost(per: dict, a: str, b: str) -> list:
    """Tasks arm ``a`` certifies (audited right) and arm ``b`` does not (or certifies wrong)."""
    return sorted(f for f, d in per.items() if d[a][0] and d[a][4] == 0 and not (d[b][0] and d[b][4] == 0))


def verdict(out: dict) -> dict:
    """Pre-registered criteria 1-4 and 6 (docs/CERT.md); 5 comes from switch_regress / LOFO / tests."""
    c, ev, ac, cw = out["certified"], out["evaluations"], out["audited_correct"], out["certified_wrong"]
    per = out["per_task[certified, evals, via, candidate, audit_wrong]"]
    worse = out["worse_than_cold"]
    v = {"fields": {f: {"off": c[f"{f}_off"], "on": c[f"{f}_on"], "let2_unguarded": c[f"{f}_let2"],
                        "audited_correct": {x: ac[f"{f}_{x}"] for x, _s in VARIANTS},
                        "certified_wrong": {x: cw[f"{f}_{x}"] for x, _s in VARIANTS},
                        "lost_on": lost(per, f"{f}_off", f"{f}_on"),
                        "lost_let2": lost(per, f"{f}_off", f"{f}_let2"),
                        "plain_lost_on": sorted(t for t, d in per.items() if d[f"{f}_off"][0] and not d[f"{f}_on"][0]),
                        "more_evals_on": sorted(t for t, d in per.items() if d[f"{f}_off"][0] and d[f"{f}_on"][0]
                                                and d[f"{f}_off"][4] == 0 and d[f"{f}_on"][4] == 0
                                                and d[f"{f}_on"][1] > d[f"{f}_off"][1]),
                        "evals": {x: ev[f"{f}_{x}"] for x, _s in VARIANTS},
                        "new_worse_than_cold": sorted(set(worse[f"{f}_on"]) - set(worse[f"{f}_off"]))}
                    for f in FIELDS}}
    fl = v["fields"]
    g = ac["trained_on"] - ac["trained_off"]
    v["c1_trained_audited_gain"] = g
    v["c1_wrong_off_on"] = [cw["trained_off"], cw["trained_on"]]
    # 1: it helps: audited-correct gain >= 2, or (when off certifies a wrong program) every one of them rejected
    v["criterion_1"] = bool(g >= 2 and cw["trained_on"] <= cw["trained_off"])
    v["criterion_2_empty_identical"] = bool(all(d["empty_on"][:2] == d["empty_off"][:2] for d in per.values()))
    v["criterion_3_no_loss"] = bool(all(not fl[f]["lost_on"] and not fl[f]["new_worse_than_cold"]
                                        and not fl[f]["more_evals_on"] for f in FIELDS)
                                    and set(worse["empty_on"]) <= set(worse["empty_off"]))
    on_sum = sum(ac[f"{f}_on"] for f in FIELDS)
    for ctl in ("shuf", "rw"):
        ctl_sum = sum(ac[f"{f}_{ctl}"] for f in FIELDS)
        v[f"c4_{ctl}"] = {"on_sum": on_sum, "control_sum": ctl_sum, "pass": bool(on_sum > ctl_sum)}
    v["criterion_4_distinguishing_inputs_carry_it"] = bool(v["c4_shuf"]["pass"] and v["c4_rw"]["pass"])
    gl = c["trained_let2"] - c["trained_off"]
    v["c6_let2_gain"] = {"let2_unguarded_minus_off": gl, "on_minus_off": c["trained_on"] - c["trained_off"]}
    v["criterion_6_let2_kept"] = bool(gl < 2 or (c["trained_on"] - c["trained_off"]) * 2 >= gl)
    return v


def lofo() -> dict:
    import variation_probe as VP
    from nomad.world_tasks import all_training
    ts = all_training()
    tot = {"cold": 0, "trained": 0, "trained_cert": 0}
    worst = {"trained": 0.0, "trained_cert": 0.0}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            c = evaluate(t, max_eval=20000)[0]
            tot["cold"] += c.evaluations
            for k, setting in (("trained", OFF), ("trained_cert", ON)):
                with env(**setting):
                    e = evaluate(t, prior=p, variation=vs, max_eval=20000)[0]
                tot[k] += e.evaluations
                worst[k] = max(worst[k], e.evaluations / max(1, c.evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


def load_suite(argv):
    """(suite dict, hard tasks, {family: Formula}). --suite PATH --catalogue MODULE reads another suite
    (e.g. data/deep/agree_suite.json with nomad.agree_tasks), no hash check; default the sealed CERT suite."""
    module = argv[argv.index("--catalogue") + 1] if "--catalogue" in argv else "nomad.cert_tasks"
    cat = importlib.import_module(module)
    if "--suite" in argv:
        suite = json.loads(Path(argv[argv.index("--suite") + 1]).read_text())
    else:
        suite = json.loads(XS.OUT.read_text())
        if XS.suite_hash(suite) != XS.HASH.read_text().split()[0]:
            raise ValueError("cert suite hash mismatch")
    return suite, [cat.to_task(e) for e in suite["hard"]], {f.family: f for f in cat.CATALOGUE}


def main() -> int:
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.execve(sys.executable, [sys.executable] + sys.argv, dict(os.environ, PYTHONHASHSEED="0"))
    if "--lofo" in sys.argv:
        print(json.dumps({"lofo": lofo()}, indent=1))
        return 0
    suite, hard, fam = load_suite(sys.argv)
    out = score(suite["hard"], hard, arms(), suite["max_size"], fam)
    out["sha256"] = XS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
