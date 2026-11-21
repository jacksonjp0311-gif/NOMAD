"""Measurement only: INVENT (NOMAD invents its own building blocks); see docs/INVENT.md.

    python3 scripts/invent_judge.py                  # primary: the frozen TRANSFER-3 suite
    python3 scripts/invent_judge.py --secondary      # deep, science hard, TRANSFER-2, TEXT (frozen)
    python3 scripts/invent_judge.py --suite PATH     # a dev suite of the TRANSFER-3 catalogue
    python3 scripts/invent_judge.py --inventions     # print the fields' invented primitives

Pre-registered in docs/INVENT.md. Budget 10,000, each suite's max_size.
Primary arms (TRANSFER-3; the trained field is math_sci of
scripts/transfer_suite.py, which never trains on a transfer family):
- cold:            the twin control (prior=None)
- empty:           WorldPrior(), every search feature on, INVENT off
- empty_invent:    WorldPrior(), INVENT on (an empty field invents nothing)
- trained:         math_sci, INVENT off (main: PORT + GROW on)
- trained_invent:  math_sci, INVENT on
- math_invent:     the math-only field, INVENT on (report only)
Secondary: for each existing frozen suite, cold / empty / trained /
trained_invent with that suite's own trained field (deep: all 16 WORLD
families; science: + easy science; TRANSFER-2: math_sci; TEXT: lang).
Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import invent_suite as IS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000
OFF = {"NOMAD_INVENT": "off"}
ON = {"NOMAD_INVENT": "on"}


def primary_arms(fields: dict) -> dict:
    p, vs = fields["math_sci"]
    pm, vm = fields["math"]
    return {
        "cold": (OFF, dict(prior=None)),
        "empty": (OFF, dict(prior=WorldPrior(), casesplit=True)),
        "empty_invent": (ON, dict(prior=WorldPrior(), casesplit=True)),
        "trained": (OFF, dict(prior=p, variation=vs, casesplit=True)),
        "trained_invent": (ON, dict(prior=p, variation=vs, casesplit=True)),
        "math_invent": (ON, dict(prior=pm, variation=vm, casesplit=True)),
    }


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse, by_dom = {k: [] for k in arm_kw}, {k: {} for k in arm_kw}
    lost = {k: [] for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw) in arm_kw.items():
            with env(**setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0]
        c, b = res["cold"], res["trained"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            d = by_dom[k].setdefault(e.get("domain") or e.get("kind") or "all", [0, 0])
            d[0] += ev.certified
            d[1] += 1
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
            if b.certified and not ev.certified:
                lost[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "by_domain": by_dom,
            "worse_than_cold": worse, "trained_wins_lost": lost,
            "per_task[certified, evals, via, candidate]": per}


def verdict(out: dict) -> dict:
    c, ev = out["certified"], out["evaluations"]
    gain = c["trained_invent"] - c["trained"]
    fewer = 1 - ev["trained_invent"] / max(1, ev["trained"])
    egain = c["empty_invent"] - c["empty"]
    efewer = 1 - ev["empty_invent"] / max(1, ev["empty"])
    v = {"invent_gain": gain, "invent_fewer_evals": round(fewer, 4),
         "1_invent_adds": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25)),
         "empty_invent_gain": egain, "empty_invent_fewer_evals": round(efewer, 4),
         "2_gain_vanishes_with_empty_field": bool(egain <= 0 and efewer < 0.05),
         "3_no_arm_worse_than_cold": all(not w for w in out["worse_than_cold"].values()),
         "trained_invent_lost": out["trained_wins_lost"]["trained_invent"]}
    v["primary_pass"] = bool(v["1_invent_adds"] and v["2_gain_vanishes_with_empty_field"]
                             and v["3_no_arm_worse_than_cold"])
    return v


def secondary() -> dict:
    import deep_suite as D
    import grow_suite as GS
    import science_probe as SP
    import science_suite as SS
    import text_suite as XS
    import variation_probe as VP
    out = {}

    def arms(p, vs, casesplit):
        kw = dict(casesplit=True) if casesplit else {}
        return {"cold": (OFF, dict(prior=None)), "empty": (OFF, dict(prior=WorldPrior(), **kw)),
                "trained": (OFF, dict(prior=p, variation=vs, **kw)),
                "trained_invent": (ON, dict(prior=p, variation=vs, **kw))}

    suite, tasks = D.load()
    p, vs, _ = VP.train()
    out["deep"] = score(suite["tasks"], tasks, arms(p, vs, False), suite["max_size"])
    out["deep"]["sha256"] = D.suite_hash(suite)
    suite, easy, hard = SS.load(SS.OUT, check=True)
    p, vs, _ = VP.train()
    SP.train_more(p, vs, easy)
    out["science_hard"] = score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    out["science_hard"]["sha256"] = SS.suite_hash(suite)
    suite, _e, hard = GS.load(GS.OUT, check=True)
    p, vs = TS.fields()["math_sci"]
    out["transfer2"] = score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    out["transfer2"]["sha256"] = GS.suite_hash(suite)
    suite, _e, hard = XS.load(XS.OUT, check=True)
    p, vs = XS.fields()["lang"]
    out["text"] = score(suite["hard"], hard, arms(p, vs, True), suite["max_size"])
    out["text"]["sha256"] = XS.suite_hash(suite)
    floor = {"deep": 27, "science_hard": 12, "transfer2": 30, "text": 3}
    out["verdict"] = {k: {"trained": out[k]["certified"]["trained"],
                          "trained_invent": out[k]["certified"]["trained_invent"],
                          "baseline": floor[k],
                          "lost": out[k]["trained_wins_lost"]["trained_invent"],
                          "worse_than_cold": out[k]["worse_than_cold"]["trained_invent"],
                          "no_loss": bool(out[k]["certified"]["trained_invent"] >= max(floor[k], out[k]["certified"]["trained"])
                                          and not out[k]["trained_wins_lost"]["trained_invent"]
                                          and not any(out[k]["worse_than_cold"].values()))}
                      for k in floor}
    out["verdict"]["all_no_loss"] = all(v["no_loss"] for v in out["verdict"].values())
    return out


def show_inventions() -> dict:
    from nomad import invent as I
    from nomad.world import bank_scales
    out = {}
    for k, (p, _vs) in TS.fields().items():
        from transfer_suite import memory_trees
        scales = bank_scales([("m", t) for t, _ in memory_trees(p)])
        out[k] = {"abstractions": [{"name": x.name, "primitive": x.render(), "readable": x.infix(), "arity": len(x.args),
                                    "uses": x.uses, "saving": x.saving, "utility": x.utility,
                                    "example_source": x.example} for x in I.inventions(p)],
                  "learned_scales": [k_ for k_, _ in scales],
                  "derived_constants": [{"value": v, "tree": t} for v, t in I.constants(scales)]}
    return out


def main() -> int:
    if "--inventions" in sys.argv:
        print(json.dumps(show_inventions(), indent=1))
        return 0
    if "--secondary" in sys.argv:
        print(json.dumps(secondary(), indent=1, default=str))
        return 0
    if "--suite" in sys.argv:
        suite, _e, hard = IS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = IS.load(IS.OUT, check=True)
    out = score(suite["hard"], hard, primary_arms(TS.fields()), suite["max_size"])
    out["sha256"] = IS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
