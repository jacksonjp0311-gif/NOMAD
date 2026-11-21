"""Measurement only: the LET judge (let-bindings over a learned block); docs/LET.md.

    python3 scripts/let_judge.py                # the frozen sealed LET suite (hash-checked)
    python3 scripts/let_judge.py --suite PATH   # a dev suite (no hash check)

Arms (budget 10,000, the suite's max_size, PORT / ANCHOR2 / SCALE on, every other switch at its default;
fields = scripts/transfer_suite.fields()): cold (prior=None) / empty_off / empty_on / trained_off
(all_sci, NOMAD_LET=off) / **trained_on** (all_sci, NOMAD_LET=on; scored) / trained_on_pool (control:
NOMAD_LET_SOURCE=pool binds the probe's unlearned pool values instead of the field's blocks) /
math_sci_off / math_sci_on (report). Changes no live state.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import let_suite as XS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import ON, env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000


def arms(fields: dict) -> dict:
    p, vs = fields["all_sci"]
    pm, vm = fields["math_sci"]
    on, off = dict(ON, NOMAD_LET="on"), dict(ON, NOMAD_LET="off")
    return {
        "cold": (off, dict(prior=None)),
        "empty_off": (off, dict(prior=WorldPrior(), casesplit=True)),
        "empty_on": (on, dict(prior=WorldPrior(), casesplit=True)),
        "trained_off": (off, dict(prior=p, variation=vs, casesplit=True)),
        "trained_on": (on, dict(prior=p, variation=vs, casesplit=True)),
        "trained_on_pool": (dict(on, NOMAD_LET_SOURCE="pool"), dict(prior=p, variation=vs, casesplit=True)),
        "math_sci_off": (off, dict(prior=pm, variation=vm, casesplit=True)),
        "math_sci_on": (on, dict(prior=pm, variation=vm, casesplit=True)),
    }


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw) in arm_kw.items():
            kw = dict(kw)
            if kw.get("prior") is not None:
                kw["prior"] = copy.deepcopy(kw["prior"])
                kw["variation"] = copy.deepcopy(kw.get("variation"))
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
    """Pre-registered criteria 1-3 (docs/LET.md); 4-6 come from switch_regress / LOFO / tests."""
    c, ev = out["certified"], out["evaluations"]
    per = out["per_task[certified, evals, via, candidate]"]
    gain = c["trained_on"] - c["trained_off"]
    fewer = 1 - ev["trained_on"] / max(1, ev["trained_off"])
    losses = [f for f, a in per.items()
              if (a["trained_off"][0] and not a["trained_on"][0])
              or (a["trained_off"][0] and a["trained_on"][0] and a["trained_on"][1] > a["trained_off"][1])]
    v = {"on_minus_off": gain, "fewer_evals_vs_off": round(fewer, 4),
         "c1_it_helps": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25)),
         "empty_on_minus_empty_off": c["empty_on"] - c["empty_off"],
         "empty_on_minus_cold": c["empty_on"] - c["cold"],
         "c2_gain_vanishes_with_empty_field": bool(c["empty_on"] == c["empty_off"]),
         "on_losses_vs_off": losses,
         "c3_no_task_worse": bool(not losses and all(not out["worse_than_cold"][k] for k in ("trained_on", "empty_on"))),
         "pool_control_minus_off": c["trained_on_pool"] - c["trained_off"],
         "c7_learned_blocks_matter": bool(c["trained_on"] - c["trained_on_pool"] >= 2)}
    v["pass_1_2_3_7"] = bool(v["c1_it_helps"] and v["c2_gain_vanishes_with_empty_field"] and v["c3_no_task_worse"]
                             and v["c7_learned_blocks_matter"])
    return v


def main() -> int:
    if "--suite" in sys.argv:
        suite, _e, hard = XS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = XS.load(XS.OUT, check=True)
    out = score(suite["hard"], hard, arms(TS.fields()), suite["max_size"])
    out["sha256"] = XS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
