"""Measurement only: does learning transfer to a never-trained domain?

    python3 scripts/transfer_judge.py                       # sealed suite, JSON to stdout
    python3 scripts/transfer_judge.py --suite dev.json      # a dev suite (no hash check)

Pre-registered in docs/TRANSFER.md. Budget 10,000, the suite's max_size 7.
Suite: data/deep/transfer_suite.json (integer geometry + finance; hash-checked),
its sealed ``hard`` section only. No arm ever trains on a transfer family.

Arms:
- cold:               the twin control (prior=None)
- empty:              WorldPrior(), every search feature on, no memory
- math:               trained on the 8 WORLD mathematics families only
- math_sci:           math + the 14 easy science families
- all_sci (report):   all 16 WORLD families + easy science (learning_judge `trained`)
- math_sci_port_off (report): math_sci with NOMAD_PORT=off
Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import transfer_suite as TS  # noqa: E402
from learning_judge import port  # noqa: E402
from nomad.world import WorldPrior, evaluate  # noqa: E402

BUDGET = 10000
PRIMARY = ("math", "math_sci")


def arms(fields: dict) -> dict:
    a = {"cold": ("on", dict(prior=None)), "empty": ("on", dict(prior=WorldPrior(), casesplit=True))}
    for k in ("math", "math_sci", "all_sci"):
        p, vs = fields[k]
        a[k] = ("on", dict(prior=p, variation=vs, casesplit=True))
    p, vs = fields["math_sci"]
    a["math_sci_port_off"] = ("off", dict(prior=p, variation=vs, casesplit=True))
    return a


def score(entries, tasks, arm_kw, max_size) -> dict:
    per, cert, evals = {}, {k: 0 for k in arm_kw}, {k: 0 for k in arm_kw}
    worse = {k: [] for k in arm_kw}
    by_dom = {k: {} for k in arm_kw}
    for e, t in zip(entries, tasks):
        res = {}
        for k, (setting, kw) in arm_kw.items():
            with port(setting):
                res[k] = evaluate(t, max_eval=BUDGET, max_size=max_size, **kw)[0]
        c = res["cold"]
        for k, ev in res.items():
            cert[k] += ev.certified
            evals[k] += ev.evaluations
            d = by_dom[k].setdefault(e["domain"], [0, 0])
            d[0] += ev.certified
            d[1] += 1
            if (c.certified and not ev.certified) or (c.certified and ev.certified and ev.evaluations > c.evaluations):
                worse[k].append(e["family"])
        per[e["family"]] = {k: [ev.certified, ev.evaluations, ev.via, ev.candidate if ev.certified else None]
                            for k, ev in res.items()}
    return {"tasks": len(tasks), "certified": cert, "evaluations": evals, "by_domain": by_dom,
            "worse_than_cold": worse, "per_task[certified, evals, via, candidate]": per}


def verdict(out: dict) -> dict:
    c, ev = out["certified"], out["evaluations"]
    v = {}
    for k in ("math", "math_sci", "all_sci"):
        gain = c[k] - c["empty"]
        fewer = 1 - ev[k] / max(1, ev["empty"])
        v[k] = {"minus_empty": gain, "fewer_evals_vs_empty": round(fewer, 4),
                "transfer": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25))}
    v["no_arm_worse_than_cold"] = all(not w for w in out["worse_than_cold"].values())
    v["more_domains_more_transfer"] = c["math_sci"] - c["math"]
    v["pass"] = bool(v["math_sci"]["transfer"] and v["no_arm_worse_than_cold"])
    return v


def main() -> int:
    path = Path(sys.argv[sys.argv.index("--suite") + 1]) if "--suite" in sys.argv else TS.OUT
    suite, _easy, hard = TS.load(path, check=path == TS.OUT)
    fields = TS.fields()
    out = score(suite["hard"], hard, arms(fields), suite["max_size"])
    out["sha256"] = TS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
