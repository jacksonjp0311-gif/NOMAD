"""Measurement only: the CEIL judge (ceiling-division fit by learned constants); docs/CEIL.md.

    python3 scripts/ceil_judge.py                  # the frozen sealed CEIL suite (hash-checked)
    python3 scripts/ceil_judge.py --suite PATH     # a dev suite (no hash check)

Field `trained` = all_sci (16 WORLD families + easy science; scripts/transfer_suite.fields), as in
the SELFEDIT / TRANSFER judges. Arms, every hard task, budget 10,000, the suite's max_size, PORT /
ANCHOR2 / SCALE on (grow_judge.ON), every other switch at its default:
cold (prior=None) / empty_off / empty_on (NOMAD_CEIL off / on, empty field) / trained_off /
**trained_on** (scored) / rewired_1..3 (trained, NOMAD_CEIL on, ``invent.CEIL_REWIRE`` = 1 / 2 / 3:
the fit's constants replaced by as many seeded constants from 2..12 outside the learned set).
Changes no live state.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import ceil_suite as CS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import ON, env  # noqa: E402
from nomad import invent as I  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000


def arms(fields: dict) -> dict:
    p, vs = fields["all_sci"]
    on, off = dict(ON, NOMAD_CEIL="on"), dict(ON, NOMAD_CEIL="off")
    tr = dict(prior=p, variation=vs, casesplit=True)
    return {
        "cold": (off, None, dict(prior=None)),
        "empty_off": (off, None, dict(prior=WorldPrior(), casesplit=True)),
        "empty_on": (on, None, dict(prior=WorldPrior(), casesplit=True)),
        "trained_off": (off, None, tr),
        "trained_on": (on, None, tr),
        "rewired_1": (on, 1, tr),
        "rewired_2": (on, 2, tr),
        "rewired_3": (on, 3, tr),
    }


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, rewire, kw) in arm_kw.items():
            kw = dict(kw)
            if kw.get("prior") is not None:
                kw["prior"] = copy.deepcopy(kw["prior"])
                kw["variation"] = copy.deepcopy(kw.get("variation"))
            I.CEIL_REWIRE = rewire
            try:
                with env(**setting):
                    res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0]
            finally:
                I.CEIL_REWIRE = None
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


def _bar(c, ev, a, b) -> bool:
    gain = c[a] - c[b]
    fewer = 1 - ev[a] / max(1, ev[b])
    return bool(gain >= 3 or (gain >= 0 and fewer >= 0.25))


def verdict(out: dict) -> dict:
    """Pre-registered criteria 1-4 (docs/CEIL.md); 5-6 come from switch_regress / LOFO / tests."""
    c, ev = out["certified"], out["evaluations"]
    per = out["per_task[certified, evals, via, candidate]"]
    best = max(("rewired_1", "rewired_2", "rewired_3"), key=lambda k: (c[k], -ev[k]))
    lost = [f for f, a in per.items() if a["trained_off"][0] and not a["trained_on"][0]]
    more = {f: [a["trained_off"][1], a["trained_on"][1]] for f, a in per.items()
            if a["trained_off"][0] and a["trained_on"][0] and a["trained_on"][1] > a["trained_off"][1]}
    empty_eq = all(a["empty_on"][:2] == a["empty_off"][:2] for a in per.values())
    v = {"on_minus_off": c["trained_on"] - c["trained_off"],
         "fewer_evals_vs_off": round(1 - ev["trained_on"] / max(1, ev["trained_off"]), 4),
         "c1_on_beats_off": _bar(c, ev, "trained_on", "trained_off"),
         "best_rewired": best, "on_minus_best_rewired": c["trained_on"] - c[best],
         "fewer_evals_vs_best_rewired": round(1 - ev["trained_on"] / max(1, ev[best]), 4),
         "c2_learned_constants_carry_it": _bar(c, ev, "trained_on", best),
         "c3_empty_on_equals_empty_off": empty_eq,
         "lost_vs_off": lost, "eval_increases_vs_off": more,
         "c4_no_task_lost_none_worse_than_cold": bool(not lost and not out["worse_than_cold"]["trained_on"]
                                                       and not out["worse_than_cold"]["empty_on"])}
    v["pass_1_2_3_4"] = bool(v["c1_on_beats_off"] and v["c2_learned_constants_carry_it"]
                             and v["c3_empty_on_equals_empty_off"] and v["c4_no_task_lost_none_worse_than_cold"])
    return v


def main() -> int:
    if "--suite" in sys.argv:
        suite, _e, hard = CS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = CS.load(CS.OUT, check=True)
    fields = TS.fields()
    out = score(suite["hard"], hard, arms(fields), suite["max_size"])
    out["suite_sha256"] = CS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
