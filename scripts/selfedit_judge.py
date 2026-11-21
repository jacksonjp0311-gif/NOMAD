"""Measurement only: the SELFEDIT judge (self-edit sandbox + tunable invention genes); docs/SELFEDIT.md.

    python3 scripts/selfedit_judge.py                     # the frozen sealed SELFEDIT suite (hash-checked)
    python3 scripts/selfedit_judge.py --suite PATH        # a dev suite (no hash check)
    python3 scripts/selfedit_judge.py ... --genome-out P  # also write the tuned genome to P

Protocol (pre-registered):
1. The sandbox runs K = 24 steps offline (``nomad.selfedit.run_offline``, base seed 20261128) from the
   default genome: dev benchmark + keep set on the reference field (16 WORLD families + easy science),
   window = the 16 WORLD training families replayed on a copy of that field; no unit tests inside the
   loop (the full suite is criterion 5); data/ is fingerprinted before and after.
2. The final genome G* is frozen; the sealed suite is scored once:
   cold (prior=None) / empty_default / empty_tuned / trained_off (NOMAD_SELFEDIT=off) /
   trained_default (on, default genome) / **trained_tuned** (on, G*; scored) / math_sci_tuned (report).
Budget 10,000, the suite's max_size, PORT / ANCHOR2 / SCALE on (grow_judge.ON). Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import selfedit_suite as XS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import ON, env  # noqa: E402
from nomad import genome as G  # noqa: E402
from nomad import selfedit as S  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402
from nomad.world_tasks import all_training  # noqa: E402

BUDGET = 10000
K = 24
BASE_SEED = 20261128


def tune(fields: dict) -> dict:
    p, vs = fields["all_sci"]
    tasks = all_training()
    win = {"pairs": 0, "families": [t.family for t in tasks], "tasks": tasks, "recorded": {}}
    fp0 = S._data_fingerprint()
    with env(**ON):
        out = S.run_offline(K, BASE_SEED, dev_field=(p, vs), live_prior=p, win=win)
    out["data_untouched"] = fp0 == S._data_fingerprint()
    return out


def arms(fields: dict, tuned: dict) -> dict:
    d = dict(G.DEFAULTS)
    p, vs = fields["all_sci"]
    pm, vm = fields["math_sci"]
    on, off = dict(ON, NOMAD_SELFEDIT="on"), dict(ON, NOMAD_SELFEDIT="off")
    return {
        "cold": (off, d, dict(prior=None)),
        "empty_default": (on, d, dict(prior=WorldPrior(), casesplit=True)),
        "empty_tuned": (on, tuned, dict(prior=WorldPrior(), casesplit=True)),
        "trained_off": (off, d, dict(prior=p, variation=vs, casesplit=True)),
        "trained_default": (on, d, dict(prior=p, variation=vs, casesplit=True)),
        "trained_tuned": (on, tuned, dict(prior=p, variation=vs, casesplit=True)),
        "math_sci_tuned": (on, tuned, dict(prior=pm, variation=vm, casesplit=True)),
    }


def score(entries, tasks, arm_kw, max_size) -> dict:
    import copy
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, genes, kw) in arm_kw.items():
            kw = dict(kw)
            if kw.get("prior") is not None:
                kw["prior"] = copy.deepcopy(kw["prior"])
                kw["variation"] = copy.deepcopy(kw.get("variation"))
            with env(**setting), G.override(genes):
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
    """Pre-registered criteria 1-3 and 6 (docs/SELFEDIT.md); 4-5 come from switch_regress / LOFO / tests."""
    c, ev = out["certified"], out["evaluations"]
    per = out["per_task[certified, evals, via, candidate]"]
    gain = c["trained_tuned"] - c["trained_default"]
    fewer = 1 - ev["trained_tuned"] / max(1, ev["trained_default"])
    loss_vs_default = [f for f, a in per.items()
                       if (a["trained_default"][0] and not a["trained_tuned"][0])
                       or (a["trained_default"][0] and a["trained_tuned"][0] and a["trained_tuned"][1] > a["trained_default"][1])]
    off_eq = all(a["trained_off"][:2] == a["trained_default"][:2] for a in per.values())
    v = {"tuned_minus_default": gain, "fewer_evals_vs_default": round(fewer, 4),
         "c1_tuned_beats_default": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25)),
         "empty_tuned_minus_empty_default": c["empty_tuned"] - c["empty_default"],
         "empty_tuned_minus_cold": c["empty_tuned"] - c["cold"],
         "c2_gain_vanishes_with_empty_field": bool(c["empty_tuned"] - c["empty_default"] <= 1
                                                   and c["empty_tuned"] - c["cold"] <= 1),
         "tuned_losses_vs_default": loss_vs_default,
         "c3_no_task_worse": bool(not loss_vs_default
                                  and all(not out["worse_than_cold"][k] for k in ("trained_tuned", "empty_tuned"))),
         "c6_off_equals_default_genome": off_eq,
         "c6_sandbox_left_data_untouched": out["tune"]["data_untouched"],
         "accepted_edits": out["tune"]["accepted"]}
    v["c6_safety"] = bool(off_eq and out["tune"]["data_untouched"])
    v["pass_1_2_3_6"] = bool(v["c1_tuned_beats_default"] and v["c2_gain_vanishes_with_empty_field"]
                             and v["c3_no_task_worse"] and v["c6_safety"])
    return v


def main() -> int:
    if "--suite" in sys.argv:
        suite, _e, hard = XS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = XS.load(XS.OUT, check=True)
    fields = TS.fields()
    t = tune(fields)
    if "--genome-out" in sys.argv:
        Path(sys.argv[sys.argv.index("--genome-out") + 1]).write_text(
            json.dumps({"schema": "nomad.genome.v1", "genes": t["final"], "note": "SELFEDIT judge G*"}, indent=2))
    out = score(suite["hard"], hard, arms(fields, t["final"]), suite["max_size"])
    out["tune"] = t
    out["sha256"] = XS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
