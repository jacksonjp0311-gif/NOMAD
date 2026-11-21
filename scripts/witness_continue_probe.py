"""Measurement only: WITNESS_CONTINUE vs its off switch vs the cold control.

    python3 scripts/witness_continue_probe.py            # JSON to stdout

Pre-registered in docs/WITNESS_CONTINUE.md. Budget 10,000, max_size 7.
Each field arm is trained AND measured with its own setting, as the body
would run it (``NOMAD_WITNESS_CONTINUE`` on / off).

Arms:
- cold:       the twin control (``prior=None``); never consults the gate
- empty_on:   empty field (``WorldPrior()``) + continue on; isolates the
              mechanism from anything learned (like cold + split)
- field_off:  the trained field, ``NOMAD_WITNESS_CONTINUE=off`` (main before)
- field:      the trained field, continue on
Sections: lofo (16 families), deep (frozen, hash-checked), science hard
(frozen, hash-checked; field trained on the easy science families).
"""
import json
import os
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
from nomad.world import WorldPrior, evaluate  # noqa: E402
from nomad.world_tasks import all_training  # noqa: E402

BUDGET = 10000


@contextmanager
def wc(v):
    old = os.environ.get("NOMAD_WITNESS_CONTINUE")
    os.environ["NOMAD_WITNESS_CONTINUE"] = v
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("NOMAD_WITNESS_CONTINUE", None)
        else:
            os.environ["NOMAD_WITNESS_CONTINUE"] = old


def trained(setting, families=None, science=None):
    with wc(setting):
        p, vs, _ = VP.train(families)
        if science is not None:
            SP.train_more(p, vs, science)
    return p, vs


def run_arms(t, arms, **kw):
    out = {}
    for k, (setting, akw) in arms.items():
        with wc(setting):
            out[k] = evaluate(t, **akw, **kw)[0]
    return out


def lofo():
    ts = all_training()
    tot = {"cold": 0, "field_off": 0, "field": 0}
    worst = {"field_off": 0.0, "field": 0.0}
    for fam in sorted({t.family for t in ts}):
        fams = {x.family for x in ts if x.family != fam}
        (po, vo), (pn, vn) = trained("off", fams), trained("on", fams)
        arms = {"cold": ("off", dict(prior=None)), "field_off": ("off", dict(prior=po, variation=vo)),
                "field": ("on", dict(prior=pn, variation=vn))}
        for t in [x for x in ts if x.family == fam]:
            r = run_arms(t, arms, max_eval=20000)
            for k, s in r.items():
                tot[k] += s.evaluations
                if k != "cold":
                    worst[k] = max(worst[k], s.evaluations / max(1, r["cold"].evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


def score(entries, tasks, arms, max_size, base="field_off"):
    per, cert, evals = {}, {k: 0 for k in arms}, {k: 0 for k in arms}
    worse, lost = {k: [] for k in arms}, {k: [] for k in arms}
    for e, t in zip(entries, tasks):
        res = run_arms(t, arms, max_eval=BUDGET, max_size=max_size)
        c, b = res["cold"], res[base]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
            if b.certified and not ev.certified:
                lost[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate] for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "worse_than_cold": worse,
            "field_off_wins_lost": lost, "per_task[certified, evals, via, candidate]": per}


def deep():
    suite, tasks = D.load()
    (po, vo), (pn, vn) = trained("off"), trained("on")
    arms = {"cold": ("off", dict(prior=None)), "empty_on": ("on", dict(prior=WorldPrior())),
            "field_off": ("off", dict(prior=po, variation=vo)), "field": ("on", dict(prior=pn, variation=vn))}
    out = score(suite["tasks"], tasks, arms, suite["max_size"])
    out["sha256"] = D.suite_hash(suite)
    return out


def science():
    suite, easy, hard = SS.load(SS.OUT, check=True)
    (po, vo), (pn, vn) = trained("off", science=easy), trained("on", science=easy)
    arms = {"cold": ("off", dict(prior=None)), "empty_on": ("on", dict(prior=WorldPrior(), casesplit=True)),
            "field_off": ("off", dict(prior=po, variation=vo, casesplit=True)),
            "field": ("on", dict(prior=pn, variation=vn, casesplit=True))}
    out = score(suite["hard"], hard, arms, suite["max_size"])
    out["sha256"] = SS.suite_hash(suite)
    return out


if __name__ == "__main__":
    print(json.dumps({"lofo": lofo(), "deep": deep(), "science_hard": science()}, indent=1, default=str))
