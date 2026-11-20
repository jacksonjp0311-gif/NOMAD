"""Measurement only: the SENSE step vs the cold control. Changes no live state.

    python3 scripts/sense_probe.py            # JSON to stdout

Arms (same budget, same max_size):
- cold:        the twin control (``prior=None``); never senses
- field:       the trained field + variation + case split, ``sense=False``
               (what main ran before SENSE)
- field_sense: the same field with SENSE on (what the body runs now)

Sections:
- classifier: sense labels on the 16 training + 4 held-out families vs the
  kind labels fixed below (pre-registered in docs/SENSE.md).
- lofo: leave-one-family-out over the 16 training families.
- deep: the frozen deep suite (hash-checked); certified counts among tasks
  cold misses, evaluations, worse-than-cold, field wins lost, and the sense
  breakdown (kind / shape) with certified counts per class.
- heldout: report-only, at each held-out's fixed budget.
"""
import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deep_suite as D  # noqa: E402
import variation_probe as VP  # noqa: E402
from nomad.sense import sense  # noqa: E402
from nomad.world import evaluate  # noqa: E402
from nomad.world_tasks import HELDOUT, all_training  # noqa: E402

BUDGET = 10000

# Kind labels fixed from each family's reference function (docs/SENSE.md).
KNOWN_KINDS = {
    "max_pair": "selection", "min_pair": "selection", "mod_pair": "quotient", "div_pair": "quotient",
    "relu_diff": "piecewise", "pick_gt": "piecewise", "square_plus_y": "polynomial",
    "ysquare_minus_x": "polynomial",
    "rev_upper": "reorder", "first_last": "reorder", "double_lower": "text_shaping", "len_plus_len": "measure",
    "range": "aggregation", "sum_tail": "aggregation", "second_smallest": "aggregation", "sort_desc": "ordering",
    # held-outs
    "absdiff": "piecewise", "quartic_sum": "polynomial", "last_first_upper": "reorder",
    "sum_minus_max": "aggregation",
}


def classifier():
    tasks = all_training() + [h["task"] for h in HELDOUT.values()]
    rows = {t.family: {"domain": (r := sense(t))["domain"], "kind": r["kind"], "shape": r["shape"],
                       "expected": KNOWN_KINDS[t.family], "ok": r["kind"] == KNOWN_KINDS[t.family]}
            for t in tasks}
    return {"correct": sum(v["ok"] for v in rows.values()), "of": len(rows), "per_family": rows}


def lofo():
    ts = all_training()
    tot = {"cold": 0, "field": 0, "field_sense": 0}
    worst = {"field": 0.0, "field_sense": 0.0}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            r = {"cold": evaluate(t, max_eval=20000)[0],
                 "field": evaluate(t, prior=p, max_eval=20000, variation=vs, sense=False)[0],
                 "field_sense": evaluate(t, prior=p, max_eval=20000, variation=vs, sense=True)[0]}
            for k, s in r.items():
                tot[k] += s.evaluations
                if k != "cold":
                    worst[k] = max(worst[k], s.evaluations / max(1, r["cold"].evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


def deep(p, vs):
    suite, tasks = D.load()
    arms = {"cold": dict(prior=None), "field": dict(prior=p, variation=vs, sense=False),
            "field_sense": dict(prior=p, variation=vs, sense=True)}
    cert = {k: 0 for k in arms}
    evals = {k: 0 for k in arms}
    worse = {k: [] for k in arms}
    lost, per, cold_miss = [], {}, 0
    by_kind = collections.defaultdict(lambda: {"tasks": 0, "field": 0, "field_sense": 0})
    by_shape = collections.defaultdict(lambda: {"tasks": 0, "field": 0, "field_sense": 0})
    for e, t in zip(suite["tasks"], tasks):
        rec = sense(t)
        res = {k: evaluate(t, max_eval=BUDGET, max_size=suite["max_size"], **kw)[0] for k, kw in arms.items()}
        c = res["cold"]
        cold_miss += not c.certified
        for k, ev in res.items():
            cert[k] += ev.certified and not c.certified
            evals[k] += ev.evaluations
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        if res["field"].certified and not res["field_sense"].certified:
            lost.append(e["family"])
        for tab, key in ((by_kind, rec["kind"]), (by_shape, rec["shape"])):
            tab[key]["tasks"] += 1
            tab[key]["field"] += res["field"].certified
            tab[key]["field_sense"] += res["field_sense"].certified
        per[e["family"]] = {"sense": [rec["kind"], rec["shape"]],
                            **{k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                               for k, ev in res.items()}}
    return {"sha256": D.suite_hash(suite), "tasks": len(tasks), "cold_misses": cold_miss,
            "certified_where_cold_misses": cert,
            "rate": {k: round(v / max(1, cold_miss), 4) for k, v in cert.items()},
            "evaluations": evals, "worse_than_cold": worse, "field_wins_lost": lost,
            "by_kind": dict(by_kind), "by_shape": dict(by_shape),
            "per_task[certified, evals, via, candidate]": per}


def heldout(p, vs):
    out = {}
    for name, h in HELDOUT.items():
        t, kw = h["task"], {"max_eval": h["max_eval"], "max_size": h["max_size"]}
        c, _ = evaluate(t, **kw)
        f, _ = evaluate(t, prior=p, use_family=False, variation=vs, sense=False, **kw)
        g, _ = evaluate(t, prior=p, use_family=False, variation=vs, sense=True, **kw)
        out[name] = {"budget": h["max_eval"], "sense": [sense(t)["kind"], sense(t)["shape"]],
                     **{k: [ev.certified, ev.evaluations, ev.via, ev.candidate]
                        for k, ev in (("cold", c), ("field", f), ("field_sense", g))}}
    return out


if __name__ == "__main__":
    os.environ["NOMAD_SENSE"] = "off"   # train the field exactly as main did before SENSE
    p, vs, _ = VP.train()
    out = {"classifier": classifier(), "lofo": lofo(), "deep": deep(p, vs), "heldout": heldout(p, vs)}
    print(json.dumps(out, indent=1, default=str))
