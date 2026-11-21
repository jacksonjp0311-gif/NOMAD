"""Measurement only: the COMBINE judge (two retrieved concepts composed); docs/COMBINE.md.

    python3 scripts/combine_judge.py               # the frozen sealed COMBINE suite (hash-checked)
    python3 scripts/combine_judge.py --suite PATH  # a dev suite (no hash check)

Field ``trained`` = scripts/roles_judge.fields() (16 WORLD families + easy science + the 72 MEANING
training families told as stories; single-concept stories only, never a composite). Arms on the
``hard`` section, each task's story as ``words``; NOMAD_MEANING on everywhere except ``cold``:
``cold``; ``empty_off`` / ``empty_on`` (NOMAD_COMBINE off / on); ``trained_off`` (COMBINE off);
**``trained_on``** (COMBINE on; scored); ``shuffled_1..3`` (COMBINE on, the lexicon's words
reassigned to random concepts by ``meaning.shuffled(seed)``, so the composed concepts are the wrong
ones). NOMAD_ROLES is off in every arm (COMBINE does not read roles). Changes no live state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import combine_suite as CS  # noqa: E402
import roles_judge as RJ  # noqa: E402
from nomad import meaning as M  # noqa: E402
from nomad.world import WorldPrior  # noqa: E402

BASE = {"NOMAD_MEANING": "on", "NOMAD_ROLES": "off"}
OFF = dict(BASE, NOMAD_COMBINE="off")
ON = dict(BASE, NOMAD_COMBINE="on")
COLD = {"NOMAD_MEANING": "off", "NOMAD_ROLES": "off", "NOMAD_COMBINE": "off"}
SHUFFLE_SEEDS = (1, 2, 3)


def arms(fields: dict) -> dict:
    p, vs = fields["trained"]
    kw = dict(prior=p, variation=vs, casesplit=True)
    a = {"cold": (COLD, dict(prior=None), False),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True), True),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True), True),
         "trained_off": (OFF, kw, True), "trained_on": (ON, kw, True)}
    for s in SHUFFLE_SEEDS:
        a[f"shuffled_{s}"] = (ON, dict(kw, prior=M.shuffled(p, s)), True)
    return a


def verdict(out: dict) -> dict:
    """Pre-registered criteria 1-4 (docs/COMBINE.md); 5-6 come from switch_regress / LOFO / tests."""
    c, ev = out["certified"], out["evaluations"]
    per = out["per_task[certified, evals, via, candidate]"]
    gain = c["trained_on"] - c["trained_off"]
    sh = [f"shuffled_{s}" for s in SHUFFLE_SEEDS]
    best_sh = max(sh, key=lambda k: (c[k], -ev[k]))
    gain_sh = c["trained_on"] - c[best_sh]
    lost = [f for f, a in per.items() if a["trained_off"][0] and not a["trained_on"][0]]
    v = {"on_minus_off": gain, "c1_on_beats_off": bool(gain >= 3),
         "best_shuffled": best_sh, "on_minus_best_shuffled": gain_sh,
         "c2_on_beats_shuffled_concepts": bool(gain_sh >= 3),
         "empty_on_minus_empty_off": c["empty_on"] - c["empty_off"],
         "c3_gain_vanishes_with_empty_field": bool(c["empty_on"] == c["empty_off"]
                                                  and ev["empty_on"] == ev["empty_off"]),
         "trained_on_lost_vs_off": lost,
         "c4_no_sealed_task_lost": bool(not lost and all(not out["worse_than_cold"][k]
                                                        for k in ("trained_on", "empty_on")))}
    v["pass_1_to_4"] = bool(v["c1_on_beats_off"] and v["c2_on_beats_shuffled_concepts"]
                            and v["c3_gain_vanishes_with_empty_field"] and v["c4_no_sealed_task_lost"])
    return v


def main() -> int:
    if "--suite" in sys.argv:
        suite, easy, hard = CS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False)
    else:
        suite, easy, hard = CS.load(CS.OUT, check=True)
    f = RJ.fields()
    p = f["trained"][0]
    a = arms(f)
    out = RJ.score(suite["hard"], hard, a, suite["max_size"])
    if suite["easy"]:   # report only
        rep = {k: a[k] for k in ("cold", "trained_off", "trained_on")}
        out["easy_report"] = RJ.score(suite["easy"], easy, rep, suite["max_size"])
    out["sha256"] = CS.suite_hash(suite)
    out["field"] = {"tokens": len(p.lexicon), "concepts": len(p.concepts)}
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
