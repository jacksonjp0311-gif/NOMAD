"""Measurement only: does VARIATION (mutants + novelty + payoff memory) change
cost vs the cold control? Changes no live state. Run from repo root:

    python3 scripts/variation_probe.py

Prints, as JSON:
- lofo: leave-one-family-out on the 16 training families; field without and
  with variation vs cold (totals, worst ratio, never-worse check).
- heldout: each held-out at its fixed budget: cold, field, field+variation.
  Held-outs are reported, never used to choose anything.
- twin: an offline 2-round twin run over the training families (last round
  totals), plus exploration evaluations, mutants paid, archive size and the
  payoff-memory table it learned.
"""
import json
import sys

sys.path.insert(0, ".")
from nomad import variation as V  # noqa: E402
from nomad.world import OPSETS, WorldPrior, evaluate, synthesize, task_route_key  # noqa: E402
from nomad.world_tasks import HELDOUT, all_training  # noqa: E402


def train(families=None, rounds=2, with_var=True):
    """Mirror of tests/test_world.py::_train plus the variation learner."""
    p, vs = WorldPrior(), V.VariationState()
    stats = {"explore_evals": 0, "paid": 0, "search_hits": 0, "field": 0, "cold": 0}
    for rnd in range(rounds):
        for t in all_training():
            if families and t.family not in families:
                continue
            ev, r = evaluate(t, prior=p, variation=vs if with_var else None)
            if rnd == rounds - 1:
                stats["field"] += ev.evaluations
                stats["cold"] += evaluate(t)[0].evaluations
            if with_var:
                ex = V.explore(t, vs, V.library_trees(p, t.inputs))
                stats["explore_evals"] += ex["evaluations"]
                paid = list(ex["paid"])
                if ev.certified and ev.via and ev.via.startswith("variation:"):
                    stats["search_hits"] += 1
                    paid.append({"kind": ev.via.split(":", 1)[1], "tree": ev.tree})
                trace = {"family": t.family, "tried": list(ev.variation) + ex["tried"], "paid": paid}
            if ev.certified:
                p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                                sense_key=task_route_key(t))
                p.decay(0.97)
            if with_var:
                res = V.apply_trace(vs, trace, certified_tree=ev.tree if ev.certified else None,
                                    library=V.library_trees(p, t.inputs))
                stats["paid"] += res.get("paid", 0)
                if ev.certified:
                    vs.decay(0.97)
    return p, vs, stats


def lofo():
    ts = all_training()
    tot = {"cold": 0, "field": 0, "field_var": 0}
    worst = {"field": 0.0, "field_var": 0.0}
    never_worse = True
    rows = {}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            c = synthesize(t, max_eval=20000)
            f = synthesize(t, prior=p, max_eval=20000)
            fv = synthesize(t, prior=p, max_eval=20000, variation=vs)
            tot["cold"] += c.evaluations
            tot["field"] += f.evaluations
            tot["field_var"] += fv.evaluations
            worst["field"] = max(worst["field"], f.evaluations / max(1, c.evaluations))
            worst["field_var"] = max(worst["field_var"], fv.evaluations / max(1, c.evaluations))
            if fv.tree is None or fv.evaluations > c.evaluations:
                never_worse = False
            rows[fam] = [c.evaluations, f.evaluations, fv.evaluations, fv.via, len(fv.variation)]
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()},
            "field_var_never_worse_than_cold": never_worse,
            "per_family[cold, field, field_var, via, mutants_tried]": rows}


def heldout(p, vs):
    out = {}
    for name, h in HELDOUT.items():
        t, kw = h["task"], {"max_eval": h["max_eval"], "max_size": h["max_size"]}
        c, _ = evaluate(t, **kw)
        f, _ = evaluate(t, prior=p, use_family=False, **kw)
        fv, _ = evaluate(t, prior=p, use_family=False, variation=vs, **kw)
        out[name] = {"budget": h["max_eval"],
                     "cold": [c.certified, c.evaluations],
                     "field": [f.certified, f.evaluations],
                     "field_var": [fv.certified, fv.evaluations, fv.via, fv.candidate if fv.certified else None]}
    return out


if __name__ == "__main__":
    p0, _, s0 = train(with_var=False)
    p1, vs, s1 = train(with_var=True)
    print(json.dumps({
        "lofo": lofo(),
        "heldout": heldout(p1, vs),
        "twin_last_round": {"without_variation": {k: s0[k] for k in ("cold", "field")},
                            "with_variation": s1,
                            "archive": len(vs.archive), "elites": len(vs.elites),
                            "memory": {sit: {k: [round(a, 2), round(b, 2)] for k, (a, b) in t.items()}
                                       for sit, t in vs.memory.counts.items()}},
    }, indent=1, default=str))
