"""Measurement only: INVENT round 2 (budget-safe phase + iterated invention); see docs/INVENT.md.

    python3 scripts/invent2_judge.py                 # primary: the frozen TRANSFER-4 suite
    python3 scripts/invent2_judge.py --secondary     # every earlier frozen suite: deep, science hard,
                                                     # TRANSFER(-1), TRANSFER-2, TEXT, TRANSFER-3
    python3 scripts/invent2_judge.py --suite PATH    # a dev suite of the TRANSFER-4 catalogue
    python3 scripts/invent2_judge.py --inventions    # the fields' invented primitives (all rounds)

Pre-registered in docs/INVENT.md ("Round 2"). Budget 10,000, each suite's
max_size. Primary arms on TRANSFER-4 (trained field = math_sci of
scripts/transfer_suite.py, which never trains on a transfer family):
cold / empty / empty_invent / trained (INVENT off) / trained_invent, and,
report only, math_invent (math-only field) and trained_invent_r1 (INVENT on,
round 1 only: NOMAD_INVENT_ROUNDS=1, to show what composition adds).
Secondary: cold / empty / trained / trained_invent on each earlier frozen
suite with that suite's own trained field. Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import invent2_suite as IS2  # noqa: E402
import invent_judge as IJ  # noqa: E402
import transfer_suite as TS  # noqa: E402
from nomad.world import WorldPrior  # noqa: E402

OFF, ON = IJ.OFF, IJ.ON
ON_R1 = {"NOMAD_INVENT": "on", "NOMAD_INVENT_ROUNDS": "1"}


def primary_arms(fields: dict) -> dict:
    p, vs = fields["math_sci"]
    pm, vm = fields["math"]
    return {
        "cold": (OFF, dict(prior=None)),
        "empty": (OFF, dict(prior=WorldPrior(), casesplit=True)),
        "empty_invent": (ON, dict(prior=WorldPrior(), casesplit=True)),
        "trained": (OFF, dict(prior=p, variation=vs, casesplit=True)),
        "trained_invent": (ON, dict(prior=p, variation=vs, casesplit=True)),
        "trained_invent_r1": (ON_R1, dict(prior=p, variation=vs, casesplit=True)),
        "math_invent": (ON, dict(prior=pm, variation=vm, casesplit=True)),
    }


def verdict(out: dict) -> dict:
    v = IJ.verdict(out)
    # report-only arms never decide criterion 3 beyond the decision arms
    dec = ("empty", "empty_invent", "trained", "trained_invent")
    v["3_no_arm_worse_than_cold"] = all(not out["worse_than_cold"][k] for k in dec)
    v["report_only_worse_than_cold"] = {k: out["worse_than_cold"][k] for k in ("trained_invent_r1", "math_invent")}
    v["primary_pass"] = bool(v["1_invent_adds"] and v["2_gain_vanishes_with_empty_field"]
                             and v["3_no_arm_worse_than_cold"])
    return v


def secondary() -> dict:
    import invent_suite as IS
    out = IJ.secondary()
    fl = out.pop("verdict")
    fl.pop("all_no_loss", None)
    p, vs = TS.fields()["math_sci"]
    arms = {"cold": (OFF, dict(prior=None)), "empty": (OFF, dict(prior=WorldPrior(), casesplit=True)),
            "trained": (OFF, dict(prior=p, variation=vs, casesplit=True)),
            "trained_invent": (ON, dict(prior=p, variation=vs, casesplit=True))}
    suite, _e, hard = TS.load(TS.OUT, check=True)
    out["transfer"] = IJ.score(suite["hard"], hard, arms, suite["max_size"])
    out["transfer"]["sha256"] = TS.suite_hash(suite)
    suite, _e, hard = IS.load(IS.OUT, check=True)
    out["transfer3"] = IJ.score(suite["hard"], hard, arms, suite["max_size"])
    out["transfer3"]["sha256"] = IS.suite_hash(suite)
    floor = {k: v["baseline"] for k, v in fl.items()}
    floor.update(transfer=0, transfer3=0)   # no earlier floor: trained (INVENT off) is the bar
    ver = {}
    for k in ("deep", "science_hard", "transfer", "transfer2", "text", "transfer3"):
        c = out[k]["certified"]
        ver[k] = {"trained": c["trained"], "trained_invent": c["trained_invent"], "floor": floor[k],
                  "lost": out[k]["trained_wins_lost"]["trained_invent"],
                  "worse_than_cold": {a: w for a, w in out[k]["worse_than_cold"].items() if w},
                  "no_loss": bool(c["trained_invent"] >= max(floor[k], c["trained"])
                                  and not out[k]["trained_wins_lost"]["trained_invent"]
                                  and not any(out[k]["worse_than_cold"].values()))}
    ver["all_no_loss"] = all(v["no_loss"] for v in ver.values())
    out["verdict"] = ver
    return out


def show_inventions() -> dict:
    from nomad import invent as I
    from transfer_suite import memory_trees
    out = {}
    for k, (p, _vs) in TS.fields().items():
        progs = [("m", t) for t, _ in memory_trees(p)]
        out[k] = {"primitives": [{"name": x.name, "round": x.round, "readable": x.infix(), "primitive": x.render(),
                                  "arity": len(x.args), "uses_or_evidence": x.uses, "saving": x.saving,
                                  "built_from": list(x.parts), "source": x.example} for x in I.inventions(p)],
                  "learned_and_derived_constants": [kk for kk, _ in I.memory_scales(progs)]}
    return out


def main() -> int:
    if "--inventions" in sys.argv:
        print(json.dumps(show_inventions(), indent=1))
        return 0
    if "--secondary" in sys.argv:
        print(json.dumps(secondary(), indent=1, default=str))
        return 0
    if "--suite" in sys.argv:
        suite, _e, hard = IS2.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = IS2.load(IS2.OUT, check=True)
    out = IJ.score(suite["hard"], hard, primary_arms(TS.fields()), suite["max_size"])
    out["sha256"] = IS2.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
