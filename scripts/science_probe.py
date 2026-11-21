"""Measurement only: the frozen SCIENCE suite, cold vs field. Changes no live state.

    python3 scripts/science_probe.py            # JSON to stdout (sealed suite)
    python3 scripts/science_probe.py --suite /tmp/dev.json --no-diag   # an uncommitted dev suite

Arms (budget 10,000, max_size 7, the deep-suite criterion; see docs/SCIENCE.md):
- cold:            the twin control (prior=None)
- cold_split:      empty field + case split (mechanism only)
- field_main:      the field the body runs: trained on the 16 WORLD families
                   (variation_probe.train), variation + case split
- field_sci:       field_main further trained (2 rounds, same loop) on the
                   suite's ``easy`` science families only; hard families unseen
Sections: ``hard`` (scored, bars A/B) and ``easy`` (report only).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import science_suite as SS  # noqa: E402
import variation_probe as VP  # noqa: E402
from nomad import variation as V  # noqa: E402
from nomad.world import OPSETS, WorldPrior, evaluate, task_route_key  # noqa: E402

BUDGET = 10000


def train_more(p, vs, tasks, rounds=2):
    """Continue the variation_probe.train loop on extra tasks (same rules)."""
    for _ in range(rounds):
        for t in tasks:
            ev, r = evaluate(t, prior=p, variation=vs)
            ex = V.explore(t, vs, V.library_trees(p, t.inputs))
            paid = list(ex["paid"])
            if ev.certified and ev.via and ev.via.startswith("variation:"):
                paid.append({"kind": ev.via.split(":", 1)[1], "tree": ev.tree})
            trace = {"family": t.family, "tried": list(ev.variation) + ex["tried"], "paid": paid}
            if ev.certified:
                p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                                sense_key=task_route_key(t))
                p.decay(0.97)
            V.apply_trace(vs, trace, certified_tree=ev.tree if ev.certified else None,
                          library=V.library_trees(p, t.inputs))
            if ev.certified:
                vs.decay(0.97)
    return p, vs


def section(entries, tasks, arms, max_size):
    per, cert, evals, worse = {}, {k: 0 for k in arms}, {k: 0 for k in arms}, {k: [] for k in arms}
    for e, t in zip(entries, tasks):
        res = {k: evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0] for k, kw in arms.items()}
        c = res["cold"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {"kind": e["kind"], "formula": e["formula"],
                            **{k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                               for k, ev in res.items()}}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals,
            "rate": {k: round(v / max(1, len(tasks)), 4) for k, v in cert.items()},
            "worse_than_cold": worse, "per_task[certified, evals, via, candidate]": per}


def main():
    path = Path(sys.argv[sys.argv.index("--suite") + 1]) if "--suite" in sys.argv else SS.OUT
    suite, easy, hard = SS.load(path, check=path == SS.OUT)
    p, vs, _ = VP.train()
    p2, vs2, _ = VP.train()
    train_more(p2, vs2, easy)
    sci_lib = sorted(n for n, sig in p2.library_sig.items() if n not in p.library)
    arms = {"cold": dict(prior=None),
            "cold_split": dict(prior=WorldPrior(), casesplit=True),
            "field_main": dict(prior=p, variation=vs, casesplit=True),
            "field_sci": dict(prior=p2, variation=vs2, casesplit=True)}
    out = {"sha256": SS.suite_hash(suite), "budget": BUDGET, "max_size": suite["max_size"],
           "science_blocks_learned": {n: p2.library[n] for n in sci_lib},
           "hard": section(suite["hard"], hard, arms, suite["max_size"]),
           "easy": section(suite["easy"], easy, arms, suite["max_size"])}
    if "--no-diag" not in sys.argv:
        # POST-HOC diagnostic (added after the pre-registered measurement missed
        # bar B; not a bar): same arms at 200,000 evaluations, default max_size.
        diag = {}
        for e, t in zip(suite["hard"], hard):
            c, _ = evaluate(t, max_eval=200000)
            f, _ = evaluate(t, prior=p2, variation=vs2, max_eval=200000)
            diag[e["family"]] = {"cold": [c.certified, c.evaluations],
                                 "field_sci": [f.certified, f.evaluations, f.via, f.candidate if f.certified else None]}
        out["post_hoc_diagnostic_200k"] = {
            "note": "not pre-registered; reported only to locate where the budget goes",
            "certified": {"cold": sum(v["cold"][0] for v in diag.values()),
                          "field_sci": sum(v["field_sci"][0] for v in diag.values())},
            "per_task": diag}
    h = out["hard"]
    out["bars"] = {"A_no_harm": all(not v for v in h["worse_than_cold"].values()),
                   "B_field_sci_rate": h["rate"]["field_sci"], "B_met": h["rate"]["field_sci"] >= 0.25}
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
