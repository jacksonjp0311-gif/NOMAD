"""Measurement only: the BRIDGE judge (int <-> str bridges + INVENT on string programs); see docs/BRIDGE.md.

    python3 scripts/bridge_judge.py                 # the frozen sealed BRIDGE suite (hash-checked)
    python3 scripts/bridge_judge.py --suite PATH    # a dev suite (no hash check)

Budget 10,000, max_size 7, NOMAD_BRIDGE=on for every arm unless stated. Arms:
- cold:                 the twin control (prior=None)
- empty:                WorldPrior(), every search feature on, no memory
- trained:              16 WORLD families + easy science + the bridge training tasks (scored)
- world_only:           16 WORLD families + easy science, no bridge training (report)
- bridge_only:          the bridge training tasks only (report)
- trained_port_off:     trained with NOMAD_PORT=off (report)
- trained_invent_off:   trained with NOMAD_INVENT=off (report: how much INVENT carries)
- trained_binvent_off:  trained with NOMAD_BRIDGE_INVENT=off (INVENT not run on string goals; report)
- trained_bridge_off:   trained with NOMAD_BRIDGE=off (the bridge ops are not searched; report)
Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bridge_suite as XS  # noqa: E402
from grow_judge import ON, env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000
B_ON = dict(ON, NOMAD_BRIDGE="on")


def arms(fields: dict) -> dict:
    a = {"cold": (B_ON, dict(prior=None)), "empty": (B_ON, dict(prior=WorldPrior(), casesplit=True))}
    for k in ("trained", "world_only", "bridge_only"):
        p, vs = fields[k]
        a[k] = (B_ON, dict(prior=p, variation=vs, casesplit=True))
    p, vs = fields["trained"]
    kw = dict(prior=p, variation=vs, casesplit=True)
    a["trained_port_off"] = (dict(B_ON, NOMAD_PORT="off", NOMAD_ANCHOR2="off", NOMAD_SCALE="off"), kw)
    a["trained_invent_off"] = (dict(B_ON, NOMAD_INVENT="off"), kw)
    a["trained_binvent_off"] = (dict(B_ON, NOMAD_BRIDGE_INVENT="off"), kw)
    a["trained_bridge_off"] = (dict(ON, NOMAD_BRIDGE="off"), kw)
    return a


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse, by_kind = {k: [] for k in arm_kw}, {k: {} for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw) in arm_kw.items():
            with env(**setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0]
        c = res["cold"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            d = by_kind[k].setdefault(e["kind"], [0, 0])
            d[0] += ev.certified
            d[1] += 1
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "by_kind": by_kind,
            "worse_than_cold": worse, "per_task[certified, evals, via, candidate]": per}


def verdict(out: dict) -> dict:
    """Pre-registered (docs/BRIDGE.md) criteria 1-3 on the sealed suite; 4-5 come from scripts/bridge_regress.py."""
    c, ev = out["certified"], out["evaluations"]
    gain = c["trained"] - c["empty"]
    fewer = 1 - ev["trained"] / max(1, ev["empty"])
    v = {"trained_minus_empty": gain, "fewer_evals_vs_empty": round(fewer, 4),
         "c1_trained_beats_empty": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25)),
         "empty_minus_cold": c["empty"] - c["cold"],
         "c2_gain_vanishes_with_empty_field": bool(c["empty"] - c["cold"] <= 1),
         "c3_no_task_worse_than_cold": all(not out["worse_than_cold"][k] for k in ("trained", "empty")),
         "report_trained_minus_world_only": c["trained"] - c["world_only"],
         "report_trained_minus_binvent_off": c["trained"] - c["trained_binvent_off"],
         "report_trained_minus_bridge_off": c["trained"] - c["trained_bridge_off"]}
    v["pass_1_to_3"] = bool(v["c1_trained_beats_empty"] and v["c2_gain_vanishes_with_empty_field"]
                            and v["c3_no_task_worse_than_cold"])
    return v


def main() -> int:
    if "--suite" in sys.argv:
        suite, _e, hard = XS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = XS.load(XS.OUT, check=True)
    out = score(suite["hard"], hard, arms(XS.fields()), suite["max_size"])
    out["sha256"] = XS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
