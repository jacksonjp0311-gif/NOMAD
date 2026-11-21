"""Measurement only: the ROLES judge (numbers and roles read from the story); docs/ROLES.md.

    python3 scripts/roles_judge.py               # the frozen sealed ROLES suite (hash-checked)
    python3 scripts/roles_judge.py --suite PATH  # a dev suite (no hash check)

Budget 10,000, max_size 7. Field ``trained`` (deterministic; never a held-out family): the 16 WORLD
families + easy science, then the 72 MEANING training word families told as stories (numbers written
out, ``meaning_tasks.train_story_entries``), 2 rounds, NOMAD_MEANING and NOMAD_ROLES on, so the lexicon
and the role tables are filled from verified receipts only. Training searches never read words.

Arms on every sealed task, each given its story as ``words``:
``cold`` (prior=None), ``empty_off`` / ``empty_on`` (empty field, NOMAD_ROLES off / on, MEANING on),
``meaning_off`` (report: trained field, MEANING and ROLES off), ``trained_off`` (MEANING on, ROLES off),
**``trained_on``** (both on; scored), ``shuffled_1..3`` (trained field, both on, role tables re-pointed
by ``roles.shuffled(seed)``). Changes no live state.
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import roles_suite as RS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad import meaning_tasks as MT  # noqa: E402
from nomad import roles as R  # noqa: E402
from nomad import sense as _sense  # noqa: E402
from nomad import variation as V  # noqa: E402
from nomad.world import OPSETS, WorldPrior, evaluate, task_route_key  # noqa: E402

BUDGET = 10000
BOTH_OFF = {"NOMAD_MEANING": "off", "NOMAD_ROLES": "off"}
OFF = {"NOMAD_MEANING": "on", "NOMAD_ROLES": "off"}
ON = {"NOMAD_MEANING": "on", "NOMAD_ROLES": "on"}
SHUFFLE_SEEDS = (1, 2, 3)


def train_stories(p, vs, entries, rounds: int = 2):
    """meaning_judge.train_words on stories; the receipt also teaches the role tables (row = public row 0)."""
    with env(**ON):
        for _ in range(rounds):
            for e in entries:
                t = MT.to_task(e)
                ev, r = evaluate(t, prior=p, variation=vs)
                ex = V.explore(t, vs, V.library_trees(p, t.inputs))
                paid = list(ex["paid"])
                if ev.certified and ev.via and ev.via.startswith("variation:"):
                    paid.append({"kind": ev.via.split(":", 1)[1], "tree": ev.tree})
                trace = {"family": t.family, "tried": list(ev.variation) + ex["tried"], "paid": paid}
                if ev.certified:
                    p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                                    sense_key=task_route_key(t), words=e["story"], out=t.out,
                                    kind=_sense.sense(t).get("kind"), row=t.public[0][0])
                    p.decay(0.97)
                V.apply_trace(vs, trace, certified_tree=ev.tree if ev.certified else None,
                              library=V.library_trees(p, t.inputs))
                if ev.certified:
                    vs.decay(0.97)
    return p, vs


def fields() -> dict:
    cache = os.environ.get("ROLES_FIELDS_CACHE")     # dev convenience only
    if cache and Path(cache).exists():
        return pickle.loads(Path(cache).read_bytes())
    import science_probe as SP
    import science_suite as SS
    import variation_probe as VP
    _, easy, _ = SS.load(SS.OUT, check=True)
    p, vs, _ = VP.train()
    SP.train_more(p, vs, easy)
    train_stories(p, vs, MT.train_story_entries())
    out = {"trained": (p, vs)}
    if cache:
        Path(cache).write_bytes(pickle.dumps(out))
    return out


def arms(fields: dict) -> dict:
    p, vs = fields["trained"]
    kw = dict(prior=p, variation=vs, casesplit=True)
    a = {"cold": (BOTH_OFF, dict(prior=None), False),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True), True),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True), True),
         "meaning_off": (BOTH_OFF, kw, True),
         "trained_off": (OFF, kw, True), "trained_on": (ON, kw, True)}
    for s in SHUFFLE_SEEDS:
        a[f"shuffled_{s}"] = (ON, dict(kw, prior=R.shuffled(p, s)), True)
    return a


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    via_meaning = {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw, words) in arm_kw.items():
            with env(**setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size,
                                  words=e["story"] if words else None, **dict(kw))[0]
        c = res["cold"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            via_meaning[k] += bool(ev.certified and ev.via and ev.via.startswith(("meaning:", "combine:")))
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "via_meaning": via_meaning,
            "worse_than_cold": worse, "per_task[certified, evals, via, candidate]": per}


def verdict(out: dict) -> dict:
    """Pre-registered criteria 1-4 (docs/ROLES.md); 5-6 come from switch_regress / LOFO / tests."""
    c, ev = out["certified"], out["evaluations"]
    per = out["per_task[certified, evals, via, candidate]"]
    gain = c["trained_on"] - c["trained_off"]
    fewer = 1 - ev["trained_on"] / max(1, ev["trained_off"])
    sh = [f"shuffled_{s}" for s in SHUFFLE_SEEDS]
    best_sh = max(sh, key=lambda k: (c[k], -ev[k]))
    gain_sh = c["trained_on"] - c[best_sh]
    fewer_sh = 1 - ev["trained_on"] / max(1, ev[best_sh])
    lost = [f for f, a in per.items() if a["trained_off"][0] and not a["trained_on"][0]]
    v = {"on_minus_off": gain, "fewer_evals_vs_off": round(fewer, 4),
         "c1_on_beats_off": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25)),
         "best_shuffled": best_sh, "on_minus_best_shuffled": gain_sh,
         "fewer_evals_vs_best_shuffled": round(fewer_sh, 4),
         "c2_on_beats_shuffled_roles": bool(gain_sh >= 3 or (gain_sh >= 0 and fewer_sh >= 0.25)),
         "empty_on_minus_empty_off": c["empty_on"] - c["empty_off"],
         "c3_gain_vanishes_with_empty_field": bool(c["empty_on"] == c["empty_off"]
                                                  and ev["empty_on"] == ev["empty_off"]),
         "trained_on_lost_vs_off": lost,
         "c4_no_sealed_task_lost": bool(not lost and all(not out["worse_than_cold"][k]
                                                        for k in ("trained_on", "empty_on")))}
    v["pass_1_to_4"] = bool(v["c1_on_beats_off"] and v["c2_on_beats_shuffled_roles"]
                            and v["c3_gain_vanishes_with_empty_field"] and v["c4_no_sealed_task_lost"])
    return v


def main() -> int:
    if "--suite" in sys.argv:
        suite, tasks = RS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, tasks = RS.load(RS.OUT, check=True)
    f = fields()
    p = f["trained"][0]
    out = score(suite["tasks"], tasks, arms(f), suite["max_size"])
    out["sha256"] = RS.suite_hash(suite)
    out["field"] = {"tokens": len(p.lexicon), "concepts": len(p.concepts),
                    "concepts_with_roles": sum(1 for r in p.concepts.values() if r.get("roles"))}
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
