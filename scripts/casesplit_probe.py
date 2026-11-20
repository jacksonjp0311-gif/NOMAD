"""Measurement only: the case-split organ vs the cold control. Changes no live state.

    python3 scripts/casesplit_probe.py            # JSON to stdout

Arms (all at the same budget and max_size):
- cold:        the twin control (``prior=None``), never splits
- cold+split:  empty field (cold order, no library, no variation) + case split;
               isolates the mechanism from anything learned
- field-off:   the trained field + variation, ``casesplit=False``
- field:       the trained field + variation + case split (what the body runs)

Sections:
- lofo: leave-one-family-out over the 16 training families (train 15, solve
  the 16th), totals and worst ratio vs cold.
- deep: the frozen deep suite (hash-checked), field trained on all 16
  training families; every deep family is unseen. Certified counts among
  tasks cold misses, and per-task worse-than-cold check.
- heldout: report-only, at each held-out's fixed budget.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deep_suite as D  # noqa: E402
import variation_probe as VP  # noqa: E402
from nomad.world import WorldPrior, evaluate, synthesize  # noqa: E402
from nomad.world_tasks import HELDOUT, all_training  # noqa: E402

BUDGET = 10000


def lofo():
    ts = all_training()
    tot = {"cold": 0, "cold_split": 0, "field_off": 0, "field": 0}
    worst = {k: 0.0 for k in tot if k != "cold"}
    rows = {}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            r = {"cold": synthesize(t, max_eval=20000),
                 "cold_split": synthesize(t, prior=WorldPrior(), max_eval=20000, casesplit=True),
                 "field_off": synthesize(t, prior=p, max_eval=20000, variation=vs, casesplit=False),
                 "field": synthesize(t, prior=p, max_eval=20000, variation=vs, casesplit=True)}
            for k, s in r.items():
                tot[k] += s.evaluations
                if k != "cold":
                    worst[k] = max(worst[k], s.evaluations / max(1, r["cold"].evaluations))
            rows[fam] = {k: [s.evaluations, s.via] for k, s in r.items()}
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}, "per_family": rows}


def deep(p, vs):
    suite, tasks = D.load()
    arms = {"cold": dict(prior=None),
            "cold_split": dict(prior=WorldPrior(), casesplit=True),
            "field_off": dict(prior=p, variation=vs, casesplit=False),
            "field": dict(prior=p, variation=vs, casesplit=True)}
    per, cert = {}, {k: 0 for k in arms}
    cold_miss, worse = 0, {k: [] for k in arms}
    for e, t in zip(suite["tasks"], tasks):
        res = {k: evaluate(t, max_eval=BUDGET, max_size=suite["max_size"], **kw)[0] for k, kw in arms.items()}
        c = res["cold"]
        cold_miss += not c.certified
        for k, ev in res.items():
            cert[k] += ev.certified and not c.certified
            # worse than cold: cold certified and this arm did not, or both certified and it cost more
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"sha256": D.suite_hash(suite), "tasks": len(tasks), "cold_misses": cold_miss,
            "certified_where_cold_misses": cert,
            "rate": {k: round(v / max(1, cold_miss), 4) for k, v in cert.items()},
            "worse_than_cold": worse, "per_task[certified, evals, via, candidate]": per}


def heldout(p, vs):
    out = {}
    for name, h in HELDOUT.items():
        t, kw = h["task"], {"max_eval": h["max_eval"], "max_size": h["max_size"]}
        c, _ = evaluate(t, **kw)
        cs, _ = evaluate(t, prior=WorldPrior(), use_family=False, casesplit=True, **kw)
        fo, _ = evaluate(t, prior=p, use_family=False, variation=vs, casesplit=False, **kw)
        f, _ = evaluate(t, prior=p, use_family=False, variation=vs, casesplit=True, **kw)
        out[name] = {"budget": h["max_eval"],
                     **{k: [ev.certified, ev.evaluations, ev.via, ev.candidate]
                        for k, ev in (("cold", c), ("cold_split", cs), ("field_off", fo), ("field", f))}}
    return out


if __name__ == "__main__":
    p, vs, _ = VP.train()
    print(json.dumps({"lofo": lofo(), "deep": deep(p, vs), "heldout": heldout(p, vs)}, indent=1, default=str))
