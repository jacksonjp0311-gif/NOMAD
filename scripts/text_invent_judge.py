"""Measurement only: the INVENT_TEXT judge (concat residual anchors on string goals); docs/INVENT_TEXT.md.

    python3 scripts/text_invent_judge.py               # the frozen sealed INVENT_TEXT suite (hash-checked)
    python3 scripts/text_invent_judge.py --suite PATH  # a dev suite (no hash check)

Budget 10,000, max_size 7, NOMAD_BRIDGE=on, PORT / ANCHOR2 / SCALE on. Fields = scripts/bridge_suite.fields().
Arms: cold; empty_off / empty_on (NOMAD_INVENT_TEXT off / on); trained_off; **trained_on** (scored);
world_only_on, bridge_only_on, trained_on_invent_off (NOMAD_INVENT=off: no kit, so no anchors) report.
Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bridge_suite as BS  # noqa: E402
import text_invent_suite as XS  # noqa: E402
from bridge_judge import B_ON  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000
OFF = dict(B_ON, NOMAD_INVENT_TEXT="off")
ON = dict(B_ON, NOMAD_INVENT_TEXT="on")


def arms(fields: dict) -> dict:
    p, vs = fields["trained"]
    kw = dict(prior=p, variation=vs, casesplit=True)
    a = {"cold": (OFF, dict(prior=None)),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True)),
         "trained_off": (OFF, kw), "trained_on": (ON, kw)}
    for k in ("world_only", "bridge_only"):
        pp, vv = fields[k]
        a[f"{k}_on"] = (ON, dict(prior=pp, variation=vv, casesplit=True))
    a["trained_on_invent_off"] = (dict(ON, NOMAD_INVENT="off"), kw)
    return a


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw) in arm_kw.items():
            with env(**setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0]
        c = res["cold"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "worse_than_cold": worse,
            "per_task[certified, evals, via, candidate]": per}


def verdict(out: dict) -> dict:
    """Pre-registered criteria 1-3 (docs/INVENT_TEXT.md); 4-5 come from switch_regress / LOFO / tests."""
    c, ev = out["certified"], out["evaluations"]
    per = out["per_task[certified, evals, via, candidate]"]
    gain = c["trained_on"] - c["trained_off"]
    fewer = 1 - ev["trained_on"] / max(1, ev["trained_off"])
    loss = [f for f, a in per.items() if (a["trained_off"][0] and not a["trained_on"][0])
            or (a["trained_off"][0] and a["trained_on"][0] and a["trained_on"][1] > a["trained_off"][1])]
    v = {"on_minus_off": gain, "fewer_evals_vs_off": round(fewer, 4),
         "c1_on_beats_off": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25)),
         "empty_on_minus_empty_off": c["empty_on"] - c["empty_off"],
         "report_empty_on_minus_cold": c["empty_on"] - c["cold"],
         "c2_gain_vanishes_with_empty_field": bool(c["empty_on"] - c["empty_off"] <= 1),
         "trained_on_losses_vs_off": loss,
         "c3_no_task_worse": bool(not loss and all(not out["worse_than_cold"][k] for k in ("trained_on", "empty_on")))}
    v["pass_1_to_3"] = bool(v["c1_on_beats_off"] and v["c2_gain_vanishes_with_empty_field"] and v["c3_no_task_worse"])
    return v


def main() -> int:
    if "--suite" in sys.argv:
        suite, _e, hard = XS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = XS.load(XS.OUT, check=True)
    out = score(suite["hard"], hard, arms(BS.fields()), suite["max_size"])
    out["sha256"] = XS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
