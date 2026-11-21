"""Measurement only: the TEXT (string / language) held-out transfer judge; see docs/TEXT.md.

    python3 scripts/text_judge.py                 # the frozen TEXT suite
    python3 scripts/text_judge.py --suite PATH    # a dev suite

Budget 10,000, max_size 7. Arms (no arm trains on any text family):
- cold:           the twin control (prior=None)
- empty:          WorldPrior(), every search feature on, no memory
- lang:           trained on the 8 WORLD language + coding families only
- math_sci:       trained on the 8 WORLD math families + 14 easy science (report)
- all_sci:        all 16 WORLD families + easy science ("everything")
- all_port_off:   all_sci with NOMAD_PORT=off
- all_grow_off:   all_sci with NOMAD_ANCHOR2=off NOMAD_SCALE=off (report)
Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import text_suite as XS  # noqa: E402
from grow_judge import GROW_OFF, ON, PORT_OFF, env  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000


def arms(fields: dict) -> dict:
    a = {"cold": (ON, dict(prior=None)), "empty": (ON, dict(prior=WorldPrior(), casesplit=True))}
    for k in ("lang", "math_sci", "all_sci"):
        p, vs = fields[k]
        a[k] = (ON, dict(prior=p, variation=vs, casesplit=True))
    p, vs = fields["all_sci"]
    a["all_port_off"] = (PORT_OFF, dict(prior=p, variation=vs, casesplit=True))
    a["all_grow_off"] = (GROW_OFF, dict(prior=p, variation=vs, casesplit=True))
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
    c, ev = out["certified"], out["evaluations"]
    v = {}
    for k in ("lang", "math_sci", "all_sci"):
        gain = c[k] - c["empty"]
        fewer = 1 - ev[k] / max(1, ev["empty"])
        v[k] = {"minus_empty": gain, "fewer_evals_vs_empty": round(fewer, 4),
                "beats_empty": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25))}
    v["combine_all_minus_lang"] = c["all_sci"] - c["lang"]
    v["no_arm_worse_than_cold"] = all(not w for w in out["worse_than_cold"].values())
    v["pass"] = bool(v["lang"]["beats_empty"] and v["no_arm_worse_than_cold"])
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
