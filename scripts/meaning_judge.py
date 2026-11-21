"""Measurement only: the MEANING judge (words -> certified concepts first); docs/MEANING.md.

    python3 scripts/meaning_judge.py               # the frozen sealed MEANING suite (hash-checked)
    python3 scripts/meaning_judge.py --suite PATH  # a dev suite (no hash check)

Budget 10,000, max_size 7 (the suite's). Fields (deterministic; never a held-out word family):

- ``trained``:    the 16 WORLD families (variation_probe.train) + easy science (science_probe.train_more),
                  then the MEANING training word families (``nomad.meaning_tasks.TRAIN``, 2 rounds, same loop),
                  learned with NOMAD_MEANING on, so the lexicon is filled from verified receipts only.
                  Training searches never read words, so this field is the same with or without its lexicon.
- ``words_only``: an empty field trained on the word families only (report).

Arms on the sealed ``hard`` section (each task's description passed as ``words``):
``cold`` (prior=None), ``empty_off`` / ``empty_on`` (empty field, NOMAD_MEANING off / on),
``trained_off`` (NOMAD_MEANING=off), **``trained_on``** (scored), ``shuffled_1..3`` (trained field,
switch on, lexicon rows reassigned to random concepts by ``meaning.shuffled(seed)``),
``words_only_on`` (report). Changes no live state.
"""
from __future__ import annotations

import copy
import json
import os
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import meaning_suite as MS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad import meaning as M  # noqa: E402
from nomad import meaning_tasks as MT  # noqa: E402
from nomad import sense as _sense  # noqa: E402
from nomad import variation as V  # noqa: E402
from nomad.world import OPSETS, WorldPrior, evaluate, task_route_key  # noqa: E402

BUDGET = 10000
OFF = {"NOMAD_MEANING": "off"}
ON = {"NOMAD_MEANING": "on"}
SHUFFLE_SEEDS = (1, 2, 3)


def train_words(p, vs, entries, rounds: int = 2):
    """science_probe.train_more's loop on word tasks; the receipt also teaches the lexicon (switch on)."""
    with env(**ON):
        for _ in range(rounds):
            for e in entries:
                t = MT.to_task(e)
                ev, r = evaluate(t, prior=p, variation=vs)     # no words: the search is the plain field's
                ex = V.explore(t, vs, V.library_trees(p, t.inputs))
                paid = list(ex["paid"])
                if ev.certified and ev.via and ev.via.startswith("variation:"):
                    paid.append({"kind": ev.via.split(":", 1)[1], "tree": ev.tree})
                trace = {"family": t.family, "tried": list(ev.variation) + ex["tried"], "paid": paid}
                if ev.certified:
                    p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                                    sense_key=task_route_key(t), words=e["words"], out=t.out,
                                    kind=_sense.sense(t).get("kind"))
                    p.decay(0.97)
                V.apply_trace(vs, trace, certified_tree=ev.tree if ev.certified else None,
                              library=V.library_trees(p, t.inputs))
                if ev.certified:
                    vs.decay(0.97)
    return p, vs


def fields() -> dict:
    cache = os.environ.get("MEANING_FIELDS_CACHE")     # dev convenience only
    if cache and Path(cache).exists():
        return pickle.loads(Path(cache).read_bytes())
    import science_probe as SP
    import science_suite as SS
    import variation_probe as VP
    _, easy, _ = SS.load(SS.OUT, check=True)
    tr = MT.train_entries()
    p, vs, _ = VP.train()
    SP.train_more(p, vs, easy)
    train_words(p, vs, tr)
    p2, vs2 = train_words(WorldPrior(), V.VariationState(), tr)
    out = {"trained": (p, vs), "words_only": (p2, vs2)}
    if cache:
        Path(cache).write_bytes(pickle.dumps(out))
    return out


def arms(fields: dict) -> dict:
    p, vs = fields["trained"]
    kw = dict(prior=p, variation=vs, casesplit=True)
    a = {"cold": (OFF, dict(prior=None), False),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True), True),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True), True),
         "trained_off": (OFF, kw, True), "trained_on": (ON, kw, True)}
    for s in SHUFFLE_SEEDS:
        a[f"shuffled_{s}"] = (ON, dict(kw, prior=M.shuffled(p, s)), True)
    pw, vw = fields["words_only"]
    a["words_only_on"] = (ON, dict(prior=pw, variation=vw, casesplit=True), True)
    return a


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw, words) in arm_kw.items():
            with env(**setting):
                # every arm gets a fresh copy of mutable state (variation state is read, never written,
                # by evaluate; the copy guards the arms from each other anyway)
                kw2 = dict(kw)
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size,
                                  words=e["words"] if words else None, **kw2)[0]
        c = res["cold"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "worse_than_cold": worse,
            "per_task[certified, evals, via, candidate]": per}


def verdict(out: dict) -> dict:
    """Pre-registered criteria 1-4 (docs/MEANING.md); 5-6 come from switch_regress / LOFO / tests."""
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
         "best_shuffled": best_sh, "on_minus_best_shuffled": gain_sh, "fewer_evals_vs_best_shuffled": round(fewer_sh, 4),
         "c2_on_beats_shuffled_lexicon": bool(gain_sh >= 3 or (gain_sh >= 0 and fewer_sh >= 0.25)),
         "empty_on_minus_empty_off": c["empty_on"] - c["empty_off"],
         "c3_gain_vanishes_with_empty_field": bool(c["empty_on"] == c["empty_off"]
                                                  and ev["empty_on"] == ev["empty_off"]),
         "trained_on_lost_vs_off": lost,
         "c4_no_sealed_task_lost": bool(not lost and all(not out["worse_than_cold"][k]
                                                        for k in ("trained_on", "empty_on")))}
    v["pass_1_to_4"] = bool(v["c1_on_beats_off"] and v["c2_on_beats_shuffled_lexicon"]
                            and v["c3_gain_vanishes_with_empty_field"] and v["c4_no_sealed_task_lost"])
    return v


def main() -> int:
    if "--suite" in sys.argv:
        suite, _e, hard = MS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = MS.load(MS.OUT, check=True)
    f = fields()
    p = f["trained"][0]
    a = arms(f)
    out = score(suite["hard"], hard, a, suite["max_size"])
    if suite["easy"]:   # report only (cold certifies these): what the words save on easy tasks
        easy = [MT.to_task(e) for e in suite["easy"]]
        rep = {k: a[k] for k in ("cold", "trained_off", "trained_on", "shuffled_1")}
        out["easy_report"] = score(suite["easy"], easy, rep, suite["max_size"])
    out["sha256"] = MS.suite_hash(suite)
    out["lexicon"] = {"tokens": len(p.lexicon), "concepts": len(p.concepts)}
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
