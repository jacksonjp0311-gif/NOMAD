"""Measurement only: ROUTE (learned routing table over the portable bank); see docs/ROUTE.md.

    python3 scripts/route_judge.py                 # primary: the frozen TRANSFER-5 suite
    python3 scripts/route_judge.py --secondary     # every earlier frozen suite (deep, science hard,
                                                   # TRANSFER-1..4, TEXT): ROUTE off vs on
    python3 scripts/route_judge.py --lofo          # leave-one-family-out, ROUTE off vs on
    python3 scripts/route_judge.py --suite PATH    # a dev suite (any transfer catalogue)
    python3 scripts/route_judge.py --table         # the trained fields' learned routing tables

Pre-registered in docs/ROUTE.md. Budget 10,000, each suite's max_size, every
other switch at its default (PORT, ANCHOR2, SCALE, INVENT on). Primary arms
on TRANSFER-5 (trained field = math_sci of scripts/transfer_suite.py, which
never trains on a transfer family): cold / empty / empty_route / trained
(ROUTE off) / trained_route / trained_route_perm0..2 (the same field with
each routing table's counts shuffled among its groups, seeds 0-2: the same
re-sorting machinery fed wrong evidence), and, report only, math_route
(math-only field). Secondary: cold / empty / trained / trained_route on each earlier
frozen suite with that suite's own trained field. Changes no live state.
"""
from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import invent_judge as IJ  # noqa: E402
import route_suite as RS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

PERM_SEEDS = (0, 1, 2)
OFF = {"NOMAD_ROUTE": "off"}
ON = {"NOMAD_ROUTE": "on"}


def permuted(p: WorldPrior, seed: int = 0) -> WorldPrior:
    q = copy.deepcopy(p)
    rng = random.Random(seed)
    for key in sorted(q.route):
        groups = sorted(q.route[key])
        vals = [q.route[key][g] for g in groups]
        rng.shuffle(vals)
        q.route[key] = dict(zip(groups, vals))
    return q


def primary_arms(fields: dict) -> dict:
    p, vs = fields["math_sci"]
    pm, vm = fields["math"]
    return {
        "cold": (OFF, dict(prior=None)),
        "empty": (OFF, dict(prior=WorldPrior(), casesplit=True)),
        "empty_route": (ON, dict(prior=WorldPrior(), casesplit=True)),
        "trained": (OFF, dict(prior=p, variation=vs, casesplit=True)),
        "trained_route": (ON, dict(prior=p, variation=vs, casesplit=True)),
        **{f"trained_route_perm{i}": (ON, dict(prior=permuted(p, i), variation=vs, casesplit=True)) for i in PERM_SEEDS},
        "math_route": (ON, dict(prior=pm, variation=vm, casesplit=True)),
    }


def verdict(out: dict) -> dict:
    c, ev, per = out["certified"], out["evaluations"], out["per_task[certified, evals, via, candidate]"]
    gain = c["trained_route"] - c["trained"]
    lost = out["trained_wins_lost"]["trained_route"]
    new_worse = sorted(set(out["worse_than_cold"]["trained_route"]) - set(out["worse_than_cold"]["trained"]))
    v = {"route_gain": gain, "trained_route_lost": lost,
         "1_route_beats_off": bool(gain >= 1 and not lost),
         "empty_route_minus_empty": [c["empty_route"] - c["empty"], ev["empty_route"] - ev["empty"]],
         "2_gain_vanishes_with_empty_field": bool(c["empty_route"] == c["empty"] and ev["empty_route"] == ev["empty"]
                                                  and all(per[f]["empty_route"][:2] == per[f]["empty"][:2] for f in per)),
         "new_worse_than_cold": new_worse,
         "3_no_new_worse_than_cold": not new_worse}
    perm = [c[f"trained_route_perm{i}"] for i in PERM_SEEDS]
    v["permuted_certified"] = perm
    v["route_minus_permuted_mean"] = round(c["trained_route"] - sum(perm) / len(perm), 3)
    v["4_gain_needs_the_learned_table"] = bool(v["route_minus_permuted_mean"] >= 1)
    v["report_only"] = {"math_route": c["math_route"]}
    v["primary_pass"] = bool(v["1_route_beats_off"] and v["2_gain_vanishes_with_empty_field"]
                             and v["3_no_new_worse_than_cold"] and v["4_gain_needs_the_learned_table"])
    return v


def secondary() -> dict:
    import deep_suite as D
    import grow_suite as GS
    import invent2_suite as IS2
    import invent_suite as IS
    import science_probe as SP
    import science_suite as SS
    import text_suite as XS
    import variation_probe as VP
    out = {}

    def arms(p, vs, casesplit):
        kw = dict(casesplit=True) if casesplit else {}
        return {"cold": (OFF, dict(prior=None)), "empty": (OFF, dict(prior=WorldPrior(), **kw)),
                "trained": (OFF, dict(prior=p, variation=vs, **kw)),
                "trained_route": (ON, dict(prior=p, variation=vs, **kw))}

    suite, tasks = D.load()
    p, vs, _ = VP.train()
    out["deep"] = IJ.score(suite["tasks"], tasks, arms(p, vs, False), suite["max_size"])
    suite, _e, hard = SS.load(SS.OUT, check=True)
    p, vs, _ = VP.train()
    SP.train_more(p, vs, _e)
    out["science_hard"] = IJ.score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    p, vs = TS.fields()["math_sci"]
    for name, mod in (("transfer", TS), ("transfer2", GS), ("transfer3", IS), ("transfer4", IS2)):
        suite, _e, hard = mod.load(mod.OUT, check=True)
        out[name] = IJ.score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    suite, _e, hard = XS.load(XS.OUT, check=True)
    p, vs = XS.fields()["lang"]
    out["text"] = IJ.score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    ver = {}
    for k, o in out.items():
        c = o["certified"]
        ver[k] = {"trained": c["trained"], "trained_route": c["trained_route"], "empty": c["empty"], "cold": c["cold"],
                  "of": o["tasks"], "lost": o["trained_wins_lost"]["trained_route"],
                  "new_worse_than_cold": sorted(set(o["worse_than_cold"]["trained_route"]) - set(o["worse_than_cold"]["trained"])),
                  "no_loss": bool(c["trained_route"] >= c["trained"] and not o["trained_wins_lost"]["trained_route"])}
    ver["all_no_loss"] = all(v["no_loss"] for v in ver.values())
    out["verdict"] = ver
    return out


def lofo() -> dict:
    import variation_probe as VP
    from nomad.world_tasks import all_training
    ts = all_training()
    tot = {"cold": 0, "trained": 0, "trained_route": 0}
    worst = {"trained": 0.0, "trained_route": 0.0}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            c = evaluate(t, max_eval=20000)[0]
            tot["cold"] += c.evaluations
            for k, setting in (("trained", OFF), ("trained_route", ON)):
                with env(**setting):
                    e = evaluate(t, prior=p, variation=vs, max_eval=20000)[0]
                tot[k] += e.evaluations
                worst[k] = max(worst[k], e.evaluations / max(1, c.evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


def tables() -> dict:
    return {k: p.route for k, (p, _vs) in TS.fields().items()}


def main() -> int:
    if "--table" in sys.argv:
        print(json.dumps(tables(), indent=1))
        return 0
    if "--secondary" in sys.argv:
        print(json.dumps(secondary(), indent=1, default=str))
        return 0
    if "--lofo" in sys.argv:
        print(json.dumps(lofo(), indent=1))
        return 0
    if "--suite" in sys.argv:
        suite, _e, hard = RS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = RS.load(RS.OUT, check=True)
    out = IJ.score(suite["hard"], hard, primary_arms(TS.fields()), suite["max_size"])
    out["sha256"] = RS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
