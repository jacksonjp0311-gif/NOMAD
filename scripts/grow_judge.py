"""Measurement only: GROW (program-language growth for PORT) on a sealed transfer suite.

    python3 scripts/grow_judge.py                       # the frozen TRANSFER-2 suite (primary)
    python3 scripts/grow_judge.py --suite1              # the first transfer suite (secondary report)
    python3 scripts/grow_judge.py --suite PATH          # a dev suite

Pre-registered in docs/GROW.md. Budget 10,000, max_size 7. Arms:
- cold:                 the twin control (prior=None)
- empty:                WorldPrior(), every search feature on, GROW on, no memory
- math / math_sci / all_sci: trained fields of scripts/transfer_suite.py, GROW on
- math_sci_grow_off:    math_sci with NOMAD_ANCHOR2=off NOMAD_SCALE=off (PORT as in 3d053ca)
- math_sci_port_off:    math_sci with NOMAD_PORT=off (and GROW, which lives inside PORT)
Changes no live state.
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import grow_suite as GS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000
GROW_VARS = ("NOMAD_ANCHOR2", "NOMAD_SCALE")


@contextmanager
def env(**kv):
    old = {k: os.environ.get(k) for k in kv}
    os.environ.update(kv)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


ON = {"NOMAD_PORT": "on", "NOMAD_ANCHOR2": "on", "NOMAD_SCALE": "on"}
GROW_OFF = {"NOMAD_PORT": "on", "NOMAD_ANCHOR2": "off", "NOMAD_SCALE": "off"}
PORT_OFF = {"NOMAD_PORT": "off", "NOMAD_ANCHOR2": "off", "NOMAD_SCALE": "off"}


def arms(fields: dict) -> dict:
    a = {"cold": (ON, dict(prior=None)), "empty": (ON, dict(prior=WorldPrior(), casesplit=True))}
    for k in ("math", "math_sci", "all_sci"):
        p, vs = fields[k]
        a[k] = (ON, dict(prior=p, variation=vs, casesplit=True))
    p, vs = fields["math_sci"]
    a["math_sci_grow_off"] = (GROW_OFF, dict(prior=p, variation=vs, casesplit=True))
    a["math_sci_port_off"] = (PORT_OFF, dict(prior=p, variation=vs, casesplit=True))
    return a


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse, by_dom = {k: [] for k in arm_kw}, {k: {} for k in arm_kw}
    lost = {k: [] for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw) in arm_kw.items():
            with env(**setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0]
        c, g = res["cold"], res["math_sci_grow_off"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            d = by_dom[k].setdefault(e["domain"], [0, 0])
            d[0] += ev.certified
            d[1] += 1
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
            if g.certified and not ev.certified:
                lost[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "by_domain": by_dom,
            "worse_than_cold": worse, "grow_off_wins_lost": lost,
            "per_task[certified, evals, via, candidate]": per}


def verdict(out: dict) -> dict:
    c, ev = out["certified"], out["evaluations"]
    v = {}
    for k in ("math", "math_sci", "all_sci"):
        gain = c[k] - c["empty"]
        fewer = 1 - ev[k] / max(1, ev["empty"])
        v[k] = {"minus_empty": gain, "fewer_evals_vs_empty": round(fewer, 4),
                "beats_empty": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25))}
    v["grow_gain"] = c["math_sci"] - c["math_sci_grow_off"]
    v["no_arm_worse_than_cold"] = all(not w for w in out["worse_than_cold"].values())
    v["pass"] = bool(v["math_sci"]["beats_empty"] and v["grow_gain"] >= 2 and v["no_arm_worse_than_cold"])
    return v


def main() -> int:
    if "--suite1" in sys.argv:
        suite, _e, hard = TS.load(TS.OUT, check=True)
    elif "--suite" in sys.argv:
        suite, _e, hard = GS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, _e, hard = GS.load(GS.OUT, check=True)
    out = score(suite["hard"], hard, arms(TS.fields()), suite["max_size"])
    out["sha256"] = GS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
