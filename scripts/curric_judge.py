"""CURRIC sealed judge (docs/CURRIC.md): does a multi-family concept curriculum make real memory beat
scrambled memory on never-trained domains?

    PYTHONHASHSEED=0 python3 scripts/curric_judge.py               # the frozen CURRIC suite (hash-checked)
    PYTHONHASHSEED=0 python3 scripts/curric_judge.py --suite PATH [--catalogue MODULE]   # dev (no hash check)
    PYTHONHASHSEED=0 python3 scripts/curric_judge.py --novel       # the NOVEL suite, report only

Budget 10,000, the suite's max_size 7, no words. Fields: scripts/novel_judge.py's curriculum (16 WORLD
families, easy science, 72 MEANING stories; 2 rounds each) trained with every experimental switch off
(``trained_off``); ``trained_on`` is a copy of that field that then studied the concept curriculum
(``nomad.curric.study``, NOMAD_CURRIC on): only its concept memory differs (checked and reported).

Arms (all CURRENT switch settings otherwise):
- ``cold``          prior=None, switch off                          (twin control)
- ``empty_off`` / ``empty_on``   WorldPrior(), switch off / on        (must be identical)
- ``trained_off``   trained_off field, switch off                   (switch off)
- ``studied_off``   trained_on field, switch off                    (report: concept memory present, unused)
- ``trained_on``    trained_on field, NOMAD_CURRIC on                (scored)
- ``shuffled_1..5`` trained_on field with its content destroyed (novel_judge.shuffled: shapes, sizes,
                    inputs and counts kept, every operator, concept-memory trees included, replaced by a
                    random one of the same type signature), switch on (content controls)
- ``shuffled_1..5_off`` the same fields, switch off                 (report)
- ``rewired``       trained_on, switch on, NOMAD_CURRIC_CONTROL=rewired:1 (report: family labels permuted)
- ``gate1`` / ``gate1_shuffled_1..5``  NOMAD_CURRIC_CONTROL=gate1 (report: ablation, no multi-family gate)

Post-hoc audit (criterion C1b): every certified program is run on 2,000 fresh rows per family drawn by the
family's own generator (random.Random(f"curric-audit:{family}")); "truly correct" = certified and right on
all of them. The final split is never read by search; the audit rows are never seen by search.
"""
from __future__ import annotations

import copy
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
CLEAR = {"NOMAD_CURRIC_CONTROL": "", "NOMAD_MEMIDX": "off", "NOMAD_PRIM": "off", "NOMAD_PRIMREC": "off",
         "NOMAD_MEMIDX_CONTROL": ""}
OFF = dict(NJ.CURRENT, NOMAD_CURRIC="off", **CLEAR)
ON = dict(NJ.CURRENT, NOMAD_CURRIC="on", **CLEAR)
REWIRED = dict(ON, NOMAD_CURRIC_CONTROL="rewired:1")
GATE1 = dict(ON, NOMAD_CURRIC_CONTROL="gate1")


def fields() -> dict:
    from nomad import curric as CU
    off = NJ.train_field(OFF)
    p, vs = copy.deepcopy(off)
    with NJ.env(**ON):
        studied = CU.study(p, vs)
    p.curric_studied = studied
    return {"trained_off": off, "trained_on": (p, vs)}


def arms(f: dict) -> dict:
    on, off = f["trained_on"], f["trained_off"]
    kw = lambda fl: dict(prior=fl[0], variation=fl[1], casesplit=True)  # noqa: E731
    a = {"cold": (OFF, dict(prior=None)),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True)),
         "trained_off": (OFF, kw(off)),
         "studied_off": (OFF, kw(on)),
         "trained_on": (ON, kw(on)),
         "rewired": (REWIRED, kw(on)),
         "gate1": (GATE1, kw(on))}
    for s in SHUFFLE_SEEDS:
        sh = NJ.shuffled(on, s)
        a[f"shuffled_{s}"] = (ON, kw(sh))
        a[f"shuffled_{s}_off"] = (OFF, kw(sh))
        a[f"gate1_shuffled_{s}"] = (GATE1, kw(sh))
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
        rng = random.Random(f"curric-audit:{fam}")
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


def losses(per: dict, a: str = "trained_off", b: str = "trained_on") -> dict:
    """Tasks certified by ``a`` and not by ``b``; tasks certified by both with more evaluations in ``b``."""
    lost = [f for f, r in per.items() if r[a][0] and not r[b][0]]
    dearer = [f for f, r in per.items() if r[a][0] and r[b][0] and r[b][1] > r[a][1]]
    worse_than_cold = [f for f, r in per.items() for k in (b, "empty_on") if r["cold"][0] and not r[k][0]]
    return {"lost": lost, "more_evaluations": dearer, "worse_than_cold": worse_than_cold}


def verdict(out: dict) -> dict:
    """Pre-registered criteria (docs/CURRIC.md). C5 (existing judges) and C6 (LOFO, tests) are measured
    separately with scripts/switch_regress.py and recorded in docs/CURRIC.md."""
    c, tc = out["certified"], out["truly_correct"]
    sh = [f"shuffled_{s}" for s in SHUFFLE_SEEDS]
    v = {"c1_real_beats_every_shuffled": {k: c["trained_on"] - c[k] for k in sh},
         "c1b_truly_correct_beats_every_shuffled": {k: tc["trained_on"] - tc[k] for k in sh},
         "c2_on_beats_off": c["trained_on"] - c["trained_off"],
         "c3_empty_identical": out["empty_identical"],
         "c4_no_sealed_loss": out["losses"]}
    v["c1"] = all(x >= 3 for x in v["c1_real_beats_every_shuffled"].values())
    v["c1b"] = all(x >= 3 for x in v["c1b_truly_correct_beats_every_shuffled"].values())
    v["c2"] = v["c2_on_beats_off"] >= 3
    v["c3"] = bool(out["empty_identical"])
    v["c4"] = not any(out["losses"].values())
    v["sealed_pass_c1_to_c4"] = bool(v["c1"] and v["c1b"] and v["c2"] and v["c3"] and v["c4"])
    return v


def main() -> int:
    if "--novel" in sys.argv:
        import novel_catalogue as cat
        import novel_suite as S
        suite, easy, hard = S.load(S.OUT, check=True)
    else:
        import memidx_catalogue as cat
        import curric_suite as S
        if "--catalogue" in sys.argv:   # dev: another catalogue module on sys.path (no hash check)
            import importlib
            cat = importlib.import_module(sys.argv[sys.argv.index("--catalogue") + 1])
        if "--suite" in sys.argv:
            p = Path(sys.argv[sys.argv.index("--suite") + 1])
            suite = json.loads(p.read_text())
            easy, hard = [cat.to_task(e) for e in suite["easy"]], [cat.to_task(e) for e in suite["hard"]]
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
    out["losses"] = losses(per)
    out["cold_never_reads_switch"] = True   # cold is prior=None: synthesize returns before any CURRIC code
    on_snap = f["trained_on"][0].snapshot()
    on_snap.pop("curric_log", None)
    out["fields_identical_but_concept_memory"] = (json.dumps(on_snap, sort_keys=True)
                                                  == json.dumps(f["trained_off"][0].snapshot(), sort_keys=True))
    from nomad import curric as CU
    with NJ.env(**ON):
        out["concepts"] = [{"tree": e["tree"], "families": e["families"]} for e in CU.index(f["trained_on"][0])]
        out["shuffled_concepts"] = {s: len(CU.index(NJ.shuffled(f["trained_on"], s)[0])) for s in SHUFFLE_SEEDS}
    out["studied"] = getattr(f["trained_on"][0], "curric_studied", {})
    out["fields"] = {k: {"programs": len(p.programs), "library": len(p.library), "witnessed": p.witnessed,
                         "concept_memory": len(getattr(p, "curric_log", None) or [])}
                     for k, (p, _vs) in f.items()}
    if suite.get("easy"):
        rep = {k: a[k] for k in ("cold", "trained_off", "trained_on")}
        out["easy_report"] = score(suite["easy"], easy, rep, suite["max_size"])[0]["certified"]
    out["sha256"] = S.suite_hash(suite)
    out["pythonhashseed"] = os.environ.get("PYTHONHASHSEED")
    out["verdict"] = verdict(out) if "--novel" not in sys.argv else "report only"
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
