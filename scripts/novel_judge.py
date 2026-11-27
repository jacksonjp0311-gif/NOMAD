"""Measurement only: honest generalization to never-trained task families (docs/NOVEL.md).

    PYTHONHASHSEED=0 python3 scripts/novel_judge.py               # the frozen NOVEL suite (hash-checked)
    PYTHONHASHSEED=0 python3 scripts/novel_judge.py --suite PATH  # a dev suite (no hash check)

Not a new ability: nothing in nomad/ changes. Budget 10,000, the suite's max_size 7, no words.

Curriculum of every trained field (deterministic; never a NOVEL family): the 16 WORLD families
(variation_probe.train, 2 rounds), the easy science curriculum (science_probe.train_more, 2 rounds),
then the 72 MEANING training families told as stories (2 rounds; the story is passed to
add_witnessed only, so the lexicon learns while training searches never read words). This is the
CLAUSE2 / ROLES ``trained`` curriculum without NOMAD_ROLES.

Switch settings:
- CURRENT: every switch at its present default (the post-Nov-20 switches PORT, ANCHOR2, SCALE,
  INVENT, BRIDGE, BRIDGE_INVENT, SELFEDIT, INVENT_TEXT, TEXT_CHAIN, MEANING, CLAUSE2 on; Nov-20
  switches CASESPLIT, SENSE, BLOCKPROBE, WITNESS_CONTINUE, VARIATION on; experimental switches off).
- OLD ("older NOMAD"): CURRENT with every post-Nov-20 switch off.

Arms on the sealed ``hard`` section:
- ``cold``         prior=None, CURRENT
- ``empty``        WorldPrior(), CURRENT
- ``trained_on``   field trained under CURRENT, evaluated under CURRENT        (scored)
- ``trained_old``  field trained under OLD, evaluated under OLD               (the older-NOMAD baseline)
- ``shuffled_1..3`` the trained_on field with its content rewired (every remembered tree keeps its
  shape, size and inputs, each operator replaced by a seeded random operator of the same type
  signature; per-family operator-order tables permuted within each signature), CURRENT
Report only: ``empty_old`` (WorldPrior(), OLD) and ``trained_on_field_old`` (the CURRENT field
evaluated under OLD) to separate switch effects from field effects. Changes no live state.
"""
from __future__ import annotations

import copy
import json
import os
import pickle
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from grow_judge import env  # noqa: E402
from nomad import meaning_tasks as MT  # noqa: E402
from nomad import sense as _sense  # noqa: E402
from nomad import variation as V  # noqa: E402
from nomad.world import OPS, OPSETS, WorldPrior, evaluate, task_route_key  # noqa: E402

BUDGET = 10000
SHUFFLE_SEEDS = (1, 2, 3)
POST_NOV20 = ("NOMAD_PORT", "NOMAD_ANCHOR2", "NOMAD_SCALE", "NOMAD_INVENT", "NOMAD_BRIDGE",
              "NOMAD_BRIDGE_INVENT", "NOMAD_SELFEDIT", "NOMAD_INVENT_TEXT", "NOMAD_TEXT_CHAIN",
              "NOMAD_MEANING", "NOMAD_CLAUSE2")
NOV20_ON = ("NOMAD_CASESPLIT", "NOMAD_SENSE", "NOMAD_BLOCKPROBE", "NOMAD_WITNESS_CONTINUE", "NOMAD_VARIATION")
EXPERIMENTAL_OFF = ("NOMAD_ROLES", "NOMAD_COMBINE", "NOMAD_CLAUSE", "NOMAD_LET", "NOMAD_LET2", "NOMAD_DISCRIM",
                    "NOMAD_MERGE", "NOMAD_CEIL", "NOMAD_ROUTE", "NOMAD_ROUTE_CUT", "NOMAD_GRAPH", "NOMAD_SPLICE",
                    "NOMAD_CONST", "NOMAD_INFLECT", "NOMAD_TEXT_ABSTRACT", "NOMAD_LIVE_BRIDGE", "NOMAD_LIVE_WORDS")
CONTROLS_CLEAR = {"NOMAD_CLAUSE_CONTROL": "", "NOMAD_CLAUSE2_CONTROL": "", "NOMAD_MERGE_CONTROL": ""}
CURRENT = {**{k: "on" for k in POST_NOV20 + NOV20_ON}, **{k: "off" for k in EXPERIMENTAL_OFF}, **CONTROLS_CLEAR}
OLD = dict(CURRENT, **{k: "off" for k in POST_NOV20})


def _train_loop(p, vs, items, rounds=2):
    """variation_probe.train / science_probe.train_more's loop; items = [(task, words or None)]."""
    for _ in range(rounds):
        for t, words in items:
            ev, r = evaluate(t, prior=p, variation=vs)
            ex = V.explore(t, vs, V.library_trees(p, t.inputs))
            paid = list(ex["paid"])
            if ev.certified and ev.via and ev.via.startswith("variation:"):
                paid.append({"kind": ev.via.split(":", 1)[1], "tree": ev.tree})
            trace = {"family": t.family, "tried": list(ev.variation) + ex["tried"], "paid": paid}
            if ev.certified:
                kw = dict(family=t.family, opset=OPSETS[t.opset], inputs=t.inputs, sense_key=task_route_key(t))
                if words:
                    kw.update(words=words, out=t.out, kind=_sense.sense(t).get("kind"))
                p.add_witnessed(ev.tree, r, **kw)
                p.decay(0.97)
            V.apply_trace(vs, trace, certified_tree=ev.tree if ev.certified else None,
                          library=V.library_trees(p, t.inputs))
            if ev.certified:
                vs.decay(0.97)
    return p, vs


def train_field(setting: dict):
    import science_suite as SS
    from nomad.world_tasks import all_training
    _, easy, _ = SS.load(SS.OUT, check=True)
    stories = [(MT.to_task(e), e["story"]) for e in MT.train_story_entries()]
    with env(**setting):
        p, vs = WorldPrior(), V.VariationState()
        _train_loop(p, vs, [(t, None) for t in all_training()])
        _train_loop(p, vs, [(t, None) for t in easy])
        _train_loop(p, vs, stories)
    return p, vs


def fields() -> dict:
    cache = os.environ.get("NOVEL_FIELDS_CACHE")     # dev convenience only (same code -> same fields)
    if cache and Path(cache).exists():
        return pickle.loads(Path(cache).read_bytes())
    out = {"trained_on": train_field(CURRENT), "trained_old": train_field(OLD)}
    if cache:
        Path(cache).write_bytes(pickle.dumps(out))
    return out


# ---------------------------------------------------------------- shuffled-field control
_SIG = {}
for _o in OPS.values():
    _SIG.setdefault((_o.args, _o.out), []).append(_o.name)
_GROUP = {n: sorted(g) for g in _SIG.values() for n in g}


def rewire_tree(tree, rng: random.Random):
    if not isinstance(tree, list) or not tree or tree[0] in ("var", "const", "lib"):
        return tree
    g = _GROUP.get(tree[0], [tree[0]])
    return [rng.choice(g)] + [rewire_tree(c, rng) for c in tree[1:]]


def shuffled(field, seed: int):
    """Control: same memory slots, sizes, inputs and counts; operators replaced (content destroyed)."""
    p, vs = copy.deepcopy(field[0]), copy.deepcopy(field[1])
    rng = random.Random(f"novel-shuffle:{seed}")
    for n in sorted(p.library):
        p.library[n] = rewire_tree(p.library[n], rng)
    for n in sorted(p.programs):
        p.programs[n] = rewire_tree(p.programs[n], rng)
    for c in sorted(p.concepts):
        if "tree" in p.concepts[c]:
            p.concepts[c]["tree"] = rewire_tree(p.concepts[c]["tree"], rng)
    for k in sorted(vs.elites):
        if "tree" in vs.elites[k]:
            vs.elites[k]["tree"] = rewire_tree(vs.elites[k]["tree"], rng)
    for a in vs.archive:
        if "tree" in a:
            a["tree"] = rewire_tree(a["tree"], rng)
    for table in [p.global_counts, *[p.families[f] for f in sorted(p.families)]]:
        for g in sorted({tuple(v) for v in _GROUP.values()}):
            have = [o for o in g if o in table]
            perm = have[:]
            rng.shuffle(perm)
            vals = [table[o] for o in have]
            for o, v in zip(perm, vals):
                table[o] = v
    for e in getattr(p, "curric_log", None) or []:   # CURRIC (docs/CURRIC.md): logged concept trees
        e[1] = rewire_tree(e[1], rng)
    return p, vs


def arms(f: dict) -> dict:
    on = f["trained_on"]
    kw_on = dict(prior=on[0], variation=on[1], casesplit=True)
    old = f["trained_old"]
    a = {"cold": (CURRENT, dict(prior=None)),
         "empty": (CURRENT, dict(prior=WorldPrior(), casesplit=True)),
         "trained_on": (CURRENT, kw_on),
         "trained_old": (OLD, dict(prior=old[0], variation=old[1], casesplit=True))}
    for s in SHUFFLE_SEEDS:
        p, vs = shuffled(on, s)
        a[f"shuffled_{s}"] = (CURRENT, dict(prior=p, variation=vs, casesplit=True))
    a["empty_old"] = (OLD, dict(prior=WorldPrior(), casesplit=True))
    a["trained_on_field_old"] = (OLD, kw_on)
    return a


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse, by_dom = {k: [] for k in arm_kw}, {k: {} for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw) in arm_kw.items():
            with env(**setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0]
        c = res["cold"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            d = by_dom[k].setdefault(e["domain"], [0, 0, 0])
            d[0] += ev.certified
            d[1] += 1
            d[2] += ev.evaluations
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals,
            "by_domain[certified, tasks, evaluations]": by_dom, "worse_than_cold": worse,
            "per_task[certified, evals, via, candidate]": per}


def beats(c, ev, a: str, b: str) -> dict:
    """Pre-registered rule (docs/NOVEL.md): a beats b when it certifies >= 3 more, or certifies at least
    as many with >= 25% fewer evaluations."""
    gain = c[a] - c[b]
    fewer = 1 - ev[a] / max(1, ev[b])
    return {"certified_gain": gain, "fewer_evals": round(fewer, 4),
            "beats": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25))}


def verdict(out: dict) -> dict:
    c, ev = out["certified"], out["evaluations"]
    sh = [f"shuffled_{s}" for s in SHUFFLE_SEEDS]
    v = {"on_vs_empty": beats(c, ev, "trained_on", "empty"),
         "on_vs_cold": beats(c, ev, "trained_on", "cold"),
         "on_vs_old": beats(c, ev, "trained_on", "trained_old"),
         "on_vs_shuffled": {k: beats(c, ev, "trained_on", k) for k in sh},
         "old_vs_empty_old": beats(c, ev, "trained_old", "empty_old")}
    v["c1_transfer"] = bool(v["on_vs_empty"]["beats"] and v["on_vs_cold"]["beats"])
    v["c2_current_beats_old"] = bool(v["on_vs_old"]["beats"])
    v["c3_content_attributable"] = bool(all(x["beats"] for x in v["on_vs_shuffled"].values()))
    v["no_scored_arm_worse_than_cold"] = bool(not out["worse_than_cold"]["trained_on"])
    v["evidence_of_transfer"] = bool(v["c1_transfer"] and v["c2_current_beats_old"])
    v["verdict"] = ("TRANSFER (content-attributable)" if v["evidence_of_transfer"] and v["c3_content_attributable"]
                    else "TRANSFER (not attributable to learned content)" if v["evidence_of_transfer"]
                    else "NO EVIDENCE OF TRANSFER")
    return v


def main() -> int:
    import novel_suite as NS
    if "--suite" in sys.argv:
        suite, easy, hard = NS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, easy, hard = NS.load(NS.OUT, check=True)
    f = fields()
    a = arms(f)
    out = score(suite["hard"], hard, a, suite["max_size"])
    if suite["easy"]:   # report only: cold already certifies these
        rep = {k: a[k] for k in ("cold", "empty", "trained_on", "trained_old")}
        out["easy_report"] = score(suite["easy"], easy, rep, suite["max_size"])
    out["sha256"] = NS.suite_hash(suite)
    out["pythonhashseed"] = os.environ.get("PYTHONHASHSEED")
    out["fields"] = {k: {"programs": len(p.programs), "library": len(p.library), "concepts": len(p.concepts),
                         "lexicon": len(p.lexicon), "archive": len(vs.archive), "elites": len(vs.elites),
                         "witnessed": p.witnessed} for k, (p, vs) in f.items()}
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
