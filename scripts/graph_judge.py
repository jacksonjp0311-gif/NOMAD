"""Measurement only: GRAPH (co-occurrence graph + spreading activation proposing
two-block anchor pairs); see docs/GRAPH.md.

    python3 scripts/graph_judge.py                 # primary: the frozen TRANSFER-6 suite
    python3 scripts/graph_judge.py --secondary     # every earlier frozen suite (deep, science hard,
                                                   # TRANSFER-1..5, TEXT, BRIDGE): GRAPH off vs on
    python3 scripts/graph_judge.py --lofo          # leave-one-family-out, GRAPH off vs on
    python3 scripts/graph_judge.py --suite PATH    # a dev suite (any transfer catalogue)
    python3 scripts/graph_judge.py --graph         # the fields' learned graphs (sizes)

Pre-registered in docs/GRAPH.md. Budget 10,000, each suite's max_size, every
other switch at its default. Two trained fields: math_sci (scripts/
transfer_suite.py) and practice = math_sci further trained (1 round, same
loop) on the 1,000 generated practice tasks of scripts/learning_judge.py (the
memory-size test). For each field: trained (GRAPH off), trained_graph, and
trained_graph_rw0..2 (the same graph with edges rewired, degree-preserving,
seeds 0-2: the same machinery fed wrong structure). Plus cold / empty /
empty_graph. Changes no live state.
"""
from __future__ import annotations

import copy
import functools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import invent_judge as IJ  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad.world import WorldPrior, evaluate, graph_edge  # noqa: E402

REWIRE_SEEDS = (0, 1, 2)
OFF = {"NOMAD_GRAPH": "off"}
ON = {"NOMAD_GRAPH": "on"}


def rewired(p: WorldPrior, seed: int = 0, swaps_per_edge: int = 10) -> WorldPrior:
    """Degree-preserving rewiring of the co-occurrence graph (edge weights travel with edges)."""
    q = copy.deepcopy(p)
    E = [(*e.split("|"), w) for e, w in sorted(q.graph_edges.items())]
    rng = random.Random(seed)
    cur = {graph_edge(a, b) for a, b, _ in E}
    for _ in range(swaps_per_edge * len(E)):
        if len(E) < 2:
            break
        i, j = rng.sample(range(len(E)), 2)
        a, b, w1 = E[i]
        c, d, w2 = E[j]
        if rng.random() < 0.5:
            c, d = d, c
        if a == d or c == b:
            continue
        k1, k2 = graph_edge(a, d), graph_edge(c, b)
        if k1 in cur or k2 in cur or k1 == k2:
            continue
        cur -= {graph_edge(a, b), graph_edge(E[j][0], E[j][1])}
        cur |= {k1, k2}
        E[i], E[j] = (a, d, w1), (c, b, w2)
    q.graph_edges = {graph_edge(a, b): w for a, b, w in E}
    return q


@functools.lru_cache(maxsize=1)
def practice_field():
    """math_sci + 1 round on learning_judge's 1,000 practice tasks (deep-suite leakage guard)."""
    import deep_suite as D
    import learning_judge as LJ
    import science_probe as SP
    p, vs = TS.fields()["math_sci"]
    suite, _t = D.load()
    excl = {tuple(e["values"]) for e in suite["tasks"]}
    SP.train_more(p, vs, LJ.practice_tasks(exclude=excl), rounds=1)
    return p, vs


def field_arms(name: str, p, vs, kw_extra: dict) -> dict:
    kw = dict(prior=p, variation=vs, **kw_extra)
    a = {name: (OFF, kw), f"{name}_graph": (ON, kw)}
    for s in REWIRE_SEEDS:
        a[f"{name}_graph_rw{s}"] = (ON, dict(kw, prior=rewired(p, s)))
    return a


def primary_arms() -> dict:
    p, vs = TS.fields()["math_sci"]
    pp, pvs = practice_field()
    a = {"cold": (OFF, dict(prior=None)),
         "empty": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_graph": (ON, dict(prior=WorldPrior(), casesplit=True))}
    a.update(field_arms("trained", p, vs, dict(casesplit=True)))
    a.update(field_arms("practice", pp, pvs, dict(casesplit=True)))
    return a


def field_verdict(out: dict, name: str) -> dict:
    c, per = out["certified"], out["per_task[certified, evals, via, candidate]"]
    lost = [f for f, d in per.items() if d[name][0] and not d[f"{name}_graph"][0]]
    rw = [c[f"{name}_graph_rw{s}"] for s in REWIRE_SEEDS]
    return {"off": c[name], "graph": c[f"{name}_graph"], "rewired": rw, "lost": lost,
            "beats_off": bool(c[f"{name}_graph"] >= c[name] + 1 and not lost),
            "beats_every_rewired": bool(all(c[f"{name}_graph"] >= r + 1 for r in rw))}


def verdict(out: dict) -> dict:
    c, ev, per = out["certified"], out["evaluations"], out["per_task[certified, evals, via, candidate]"]
    v = {k: field_verdict(out, k) for k in ("trained", "practice")}
    v["empty_identical"] = bool(c["empty_graph"] == c["empty"] and ev["empty_graph"] == ev["empty"]
                                and all(per[f]["empty_graph"][:2] == per[f]["empty"][:2] for f in per))
    worse = out["worse_than_cold"]
    v["new_worse_than_cold"] = {k: sorted(set(worse[f"{k}_graph"]) - set(worse[k])) for k in ("trained", "practice")}
    v["primary_pass"] = bool(any(v[k]["beats_off"] and v[k]["beats_every_rewired"] for k in ("trained", "practice"))
                             and not any(v[k]["lost"] for k in ("trained", "practice"))
                             and v["empty_identical"] and not any(v["new_worse_than_cold"].values()))
    return v


def secondary() -> dict:
    import bridge_suite as BS
    import deep_suite as D
    import grow_suite as GS
    import invent2_suite as IS2
    import invent_suite as IS
    import route_suite as RS
    import science_probe as SP
    import science_suite as SS
    import text_suite as XS
    import variation_probe as VP
    out = {}

    def arms(p, vs, casesplit, base=None):
        kw = dict(casesplit=True) if casesplit else {}
        b = dict(base or {})
        return {"cold": (dict(b, **OFF), dict(prior=None)), "empty": (dict(b, **OFF), dict(prior=WorldPrior(), **kw)),
                "trained": (dict(b, **OFF), dict(prior=p, variation=vs, **kw)),
                "trained_graph": (dict(b, **ON), dict(prior=p, variation=vs, **kw))}

    suite, tasks = D.load()
    p, vs, _ = VP.train()
    out["deep"] = IJ.score(suite["tasks"], tasks, arms(p, vs, False), suite["max_size"])
    suite, _e, hard = SS.load(SS.OUT, check=True)
    p, vs, _ = VP.train()
    SP.train_more(p, vs, _e)
    out["science_hard"] = IJ.score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    p, vs = TS.fields()["math_sci"]
    for name, mod in (("transfer", TS), ("transfer2", GS), ("transfer3", IS), ("transfer4", IS2), ("transfer5", RS)):
        suite, _e, hard = mod.load(mod.OUT, check=True)
        out[name] = IJ.score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    suite, _e, hard = XS.load(XS.OUT, check=True)
    p, vs = XS.fields()["lang"]
    out["text"] = IJ.score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    suite, _e, hard = BS.load(BS.OUT, check=True)
    p, vs = BS.fields()["trained"]
    out["bridge"] = IJ.score(suite["hard"], hard, arms(p, vs, True, {"NOMAD_BRIDGE": "on"}), suite["max_size"])
    ver = {}
    for k, o in out.items():
        c = o["certified"]
        ver[k] = {"trained": c["trained"], "trained_graph": c["trained_graph"], "empty": c["empty"], "cold": c["cold"],
                  "of": o["tasks"], "lost": o["trained_wins_lost"]["trained_graph"],
                  "new_worse_than_cold": sorted(set(o["worse_than_cold"]["trained_graph"]) - set(o["worse_than_cold"]["trained"])),
                  "no_loss": bool(c["trained_graph"] >= c["trained"] and not o["trained_wins_lost"]["trained_graph"])}
    ver["all_no_loss"] = all(v["no_loss"] for v in ver.values())
    out["verdict"] = ver
    return out


def lofo() -> dict:
    import variation_probe as VP
    from nomad.world_tasks import all_training
    ts = all_training()
    tot = {"cold": 0, "trained": 0, "trained_graph": 0}
    worst = {"trained": 0.0, "trained_graph": 0.0}
    for fam in sorted({t.family for t in ts}):
        p, vs, _ = VP.train({x.family for x in ts if x.family != fam})
        for t in [x for x in ts if x.family == fam]:
            c = evaluate(t, max_eval=20000)[0]
            tot["cold"] += c.evaluations
            for k, setting in (("trained", OFF), ("trained_graph", ON)):
                with env(**setting):
                    e = evaluate(t, prior=p, variation=vs, max_eval=20000)[0]
                tot[k] += e.evaluations
                worst[k] = max(worst[k], e.evaluations / max(1, c.evaluations))
    return {"totals": tot, "worst_ratio": {k: round(v, 3) for k, v in worst.items()}}


def main() -> int:
    if "--graph" in sys.argv:
        f = dict(TS.fields())
        f["practice"] = practice_field()
        print(json.dumps({k: {"nodes": len(p.graph_nodes), "edges": len(p.graph_edges)} for k, (p, _v) in f.items()}))
        return 0
    if "--secondary" in sys.argv:
        print(json.dumps(secondary(), indent=1, default=str))
        return 0
    if "--lofo" in sys.argv:
        print(json.dumps(lofo(), indent=1))
        return 0
    import graph_suite as GS6
    if "--suite" in sys.argv:
        suite, _e, hard = GS6.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = GS6.load(GS6.OUT, check=True)
    out = IJ.score(suite["hard"], hard, primary_arms(), suite["max_size"])
    out["sha256"] = GS6.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
