"""MEMIDX / PRIM sealed judge (docs/MEMIDX.md): does real memory beat scrambled memory on new domains?

    PYTHONHASHSEED=0 python3 scripts/memidx_judge.py               # the frozen MEMIDX suite (hash-checked)
    PYTHONHASHSEED=0 python3 scripts/memidx_judge.py --suite PATH  # another suite (no hash check)
    PYTHONHASHSEED=0 python3 scripts/memidx_judge.py --novel       # the NOVEL suite, report only

Budget 10,000, the suite's max_size 7, no words. Fields: scripts/novel_judge.py's curriculum (16 WORLD
families, easy science, 72 MEANING stories; 2 rounds each), trained with the switches off (``trained_off``)
and with NOMAD_MEMIDX and NOMAD_PRIM on (``trained_on``; their snapshots are compared and reported).

Arms (all CURRENT switch settings otherwise):
- ``cold``          prior=None, switches off                       (twin control)
- ``empty_off`` / ``empty_on``   WorldPrior(), switches off / on     (must be identical)
- ``trained_off``   trained_off field, switches off                (switch off)
- ``trained_on``    trained_on field, MEMIDX + PRIM on              (scored)
- ``memidx_only``   trained_on field, MEMIDX on, PRIM off           (report)
- ``shuffled_1..5`` trained_on field with its content destroyed (novel_judge.shuffled: shapes, sizes,
                    inputs and counts kept, every operator replaced by a random one of the same type
                    signature), MEMIDX + PRIM on                    (content controls)
- ``shuffled_1..5_off`` the same fields, switches off              (report)
- ``rewired``       trained_on field, MEMIDX + PRIM on, NOMAD_MEMIDX_CONTROL=rewired:1 (index control)

Post-hoc audit (report and criterion C1b): every certified program is run on 2,000 fresh rows per family
drawn by the family's own generator (random.Random(f"memidx-audit:{family}")); "truly correct" = certified
and right on all of them. The final split is never read by search; the audit rows are never seen by search.
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import novel_judge as NJ  # noqa: E402
from nomad.science import _draw  # noqa: E402
from nomad.world import Invalid, WorldPrior, evaluate, run  # noqa: E402

BUDGET = 10000
SHUFFLE_SEEDS = (1, 2, 3, 4, 5)
AUDIT_ROWS = 2000
CLEAR = {"NOMAD_MEMIDX_CONTROL": ""}
OFF = dict(NJ.CURRENT, NOMAD_MEMIDX="off", NOMAD_PRIM="off", **CLEAR)
ON = dict(NJ.CURRENT, NOMAD_MEMIDX="on", NOMAD_PRIM="on", **CLEAR)
MEMIDX_ONLY = dict(ON, NOMAD_PRIM="off")
REWIRED = dict(ON, NOMAD_MEMIDX_CONTROL="rewired:1")


def fields() -> dict:
    return {"trained_off": NJ.train_field(OFF), "trained_on": NJ.train_field(ON)}


def arms(f: dict) -> dict:
    on, off = f["trained_on"], f["trained_off"]
    kw = lambda fl: dict(prior=fl[0], variation=fl[1], casesplit=True)  # noqa: E731
    a = {"cold": (OFF, dict(prior=None)),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True)),
         "trained_off": (OFF, kw(off)),
         "trained_on": (ON, kw(on)),
         "memidx_only": (MEMIDX_ONLY, kw(on)),
         "rewired": (REWIRED, kw(on))}
    for s in SHUFFLE_SEEDS:
        sh = NJ.shuffled(on, s)
        a[f"shuffled_{s}"] = (ON, kw(sh))
        a[f"shuffled_{s}_off"] = (OFF, kw(sh))
    return a


def score(entries, tasks, arm_kw, max_size) -> tuple[dict, dict]:
    per, trees = {}, {}
    cert, evals = {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    by_dom = {k: {} for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kwargs) in arm_kw.items():
            with NJ.env(**setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kwargs)[0]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            d = by_dom[k].setdefault(e["domain"], [0, 0])
            d[0] += ev.certified
            d[1] += 1
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
        trees[e["family"]] = {k: ev.tree for k, ev in res.items() if ev.certified}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals,
            "by_domain[certified, tasks]": by_dom, "per_task[certified, evals, via, candidate]": per}, trees


def audit(cat, trees: dict) -> dict:
    """Post-hoc: wrong rows out of AUDIT_ROWS fresh generator rows for every certified program."""
    out = {}
    for fam, arms_ in trees.items():
        f = cat.BY_FAMILY[fam]
        rng = random.Random(f"memidx-audit:{fam}")
        rows, tries = [], 0
        while len(rows) < AUDIT_ROWS and tries < 400000:
            tries += 1
            r = {k: _draw(rng, f.ranges[k]) for k in f.inputs}
            a = cat.exact_answer(f, r)
            if a is not None:
                rows.append((r, a))
        for arm, tree in arms_.items():
            bad = 0
            for r, a in rows:
                try:
                    g = run(tree, r)
                except Invalid:
                    g = None
                bad += g != a
            out.setdefault(fam, {})[arm] = {"rows": len(rows), "wrong": bad}
    return out


def verdict(out: dict) -> dict:
    """Pre-registered criteria (docs/MEMIDX.md)."""
    c, tc = out["certified"], out["truly_correct"]
    sh = [f"shuffled_{s}" for s in SHUFFLE_SEEDS]
    v = {"c1_real_beats_every_shuffled": {k: c["trained_on"] - c[k] for k in sh},
         "c1b_truly_correct_beats_every_shuffled": {k: tc["trained_on"] - tc[k] for k in sh},
         "c2_on_beats_off": c["trained_on"] - c["trained_off"],
         "c3_beats_rewired": c["trained_on"] - c["rewired"],
         "c4_empty_identical": out["empty_identical"]}
    v["c1"] = all(x >= 3 for x in v["c1_real_beats_every_shuffled"].values())
    v["c1b"] = all(x >= 3 for x in v["c1b_truly_correct_beats_every_shuffled"].values())
    v["c2"] = v["c2_on_beats_off"] >= 3
    v["c3"] = v["c3_beats_rewired"] >= 1
    v["c4"] = bool(out["empty_identical"])
    v["sealed_pass"] = bool(v["c1"] and v["c1b"] and v["c2"] and v["c3"] and v["c4"])
    return v


def main() -> int:
    if "--novel" in sys.argv:
        import novel_catalogue as cat
        import novel_suite as S
        suite, easy, hard = S.load(S.OUT, check=True)
    else:
        import memidx_catalogue as cat
        import memidx_suite as S
        if "--catalogue" in sys.argv:   # dev: another catalogue module on sys.path (no hash check)
            import importlib
            cat = importlib.import_module(sys.argv[sys.argv.index("--catalogue") + 1])
        if "--suite" in sys.argv:
            suite, easy, hard = S.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
        else:
            suite, easy, hard = S.load(S.OUT, check=True)
    f = fields()
    a = arms(f)
    out, trees = score(suite["hard"], hard, a, suite["max_size"])
    out["audit"] = audit(cat, trees)
    out["truly_correct"] = {k: sum(1 for fam, arms_ in out["audit"].items()
                                   if k in arms_ and arms_[k]["wrong"] == 0) for k in a}
    per = out["per_task[certified, evals, via, candidate]"]
    out["empty_identical"] = all(r["empty_on"][:3] == r["empty_off"][:3] for r in per.values())
    out["cold_never_reads_switch"] = True   # cold is prior=None: synthesize returns before any MEMIDX code
    out["fields_identical_on_off"] = (json.dumps(f["trained_on"][0].snapshot(), sort_keys=True)
                                      == json.dumps(f["trained_off"][0].snapshot(), sort_keys=True))
    out["fields"] = {k: {"programs": len(p.programs), "library": len(p.library), "witnessed": p.witnessed}
                     for k, (p, _vs) in f.items()}
    if suite.get("easy"):
        rep = {k: a[k] for k in ("cold", "trained_off", "trained_on")}
        out["easy_report"] = score(suite["easy"], easy, rep, suite["max_size"])[0]["certified"]
    out["sha256"] = S.suite_hash(suite)
    out["pythonhashseed"] = os.environ.get("PYTHONHASHSEED")
    out["verdict"] = verdict(out) if "--novel" not in sys.argv else "report only (NOVEL already measured)"
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
