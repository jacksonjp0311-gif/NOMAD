"""Measurement only: the TEXT_ABSTRACT judge (reusable string templates); docs/TEXTPAT.md.

    python3 scripts/textpat_judge.py                                  # the frozen sealed suite (hash-checked)
    python3 scripts/textpat_judge.py --suite PATH [--module DEV.py]   # a dev suite (no hash check)

Budget 10,000, the suite's max_size, NOMAD_BRIDGE on, PORT / ANCHOR2 / SCALE on, INVENT_TEXT,
TEXT_CHAIN and SELFEDIT at their defaults (on). Fields:

- ``trained``:     scripts/bridge_suite.fields()['trained'] plus the TEXT_ABSTRACT training
                   families (``nomad.textpat_tasks.train_tasks``, 2 rounds)
- ``world_only``:  the text judge's world + easy science field (report)
- ``bridge_only``: the 16 bridge training tasks (report)
- ``patterns_only``: an empty field trained only on the TEXT_ABSTRACT training families (report)

Arms: cold; empty_off / empty_on; trained_off; **trained_on** (scored);
shuffled_1..3 (trained field, switch on, templates rewired by ``textpat.shuffled(seed)``);
report: world_only_on, bridge_only_on, patterns_only_on, trained_on_chain_off (NOMAD_TEXT_CHAIN=off).
Changes no live state.
"""
from __future__ import annotations

import copy
import json
import os
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bridge_suite as BS  # noqa: E402
import science_probe as SP  # noqa: E402
import text_invent_judge as TIJ  # noqa: E402
import textpat_suite as PS  # noqa: E402
from bridge_judge import B_ON  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad import textpat as TP  # noqa: E402
from nomad import textpat_tasks as XT  # noqa: E402
from nomad import variation as V  # noqa: E402
from nomad.world import WorldPrior  # noqa: E402

OFF = dict(B_ON, NOMAD_TEXT_ABSTRACT="off")
ON = dict(B_ON, NOMAD_TEXT_ABSTRACT="on")
SHUFFLE_SEEDS = (1, 2, 3)


def fields() -> dict:
    cache = os.environ.get("TEXTPAT_FIELDS_CACHE")
    if cache and Path(cache).exists():
        return pickle.loads(Path(cache).read_bytes())
    out = BS.fields()
    # trained = existing bridge trained field + pattern-training families
    p, vs = out["trained"]
    p, vs = copy.deepcopy(p), copy.deepcopy(vs)
    with env(NOMAD_BRIDGE="on", NOMAD_TEXT_ABSTRACT="off"):
        SP.train_more(p, vs, XT.train_tasks())
    out["trained"] = (p, vs)
    p2, vs2 = WorldPrior(), V.VariationState()
    with env(NOMAD_BRIDGE="on", NOMAD_TEXT_ABSTRACT="off"):
        SP.train_more(p2, vs2, XT.train_tasks())
    out["patterns_only"] = (p2, vs2)
    if cache:
        Path(cache).write_bytes(pickle.dumps(out))
    return out


def arms(flds: dict) -> dict:
    p, vs = flds["trained"]
    kw = dict(prior=p, variation=vs, casesplit=True)
    a = {"cold": (OFF, dict(prior=None)),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True)),
         "trained_off": (OFF, kw), "trained_on": (ON, kw)}
    for s in SHUFFLE_SEEDS:
        a[f"shuffled_{s}"] = (ON, dict(kw, prior=TP.shuffled(p, s)))
    for k in ("world_only", "bridge_only", "patterns_only"):
        pp, vv = flds[k]
        a[f"{k}_on"] = (ON, dict(prior=pp, variation=vv, casesplit=True))
    a["trained_on_chain_off"] = (dict(ON, NOMAD_TEXT_CHAIN="off"), kw)
    return a


def verdict(out: dict) -> dict:
    """Pre-registered criteria 1-3 (docs/TEXTPAT.md); 4-5 come from switch_regress / LOFO / tests."""
    c, ev = out["certified"], out["evaluations"]
    per = out["per_task[certified, evals, via, candidate]"]
    gain = c["trained_on"] - c["trained_off"]
    fewer = 1 - ev["trained_on"] / max(1, ev["trained_off"])
    loss = [f for f, a in per.items() if (a["trained_off"][0] and not a["trained_on"][0])
            or (a["trained_off"][0] and a["trained_on"][0] and a["trained_on"][1] > a["trained_off"][1])]
    sh = [f"shuffled_{s}" for s in SHUFFLE_SEEDS]
    best_sh = max(c[k] for k in sh)
    # fewest-eval shuffled arm among those tied for most certifications
    sh_evals = min(ev[k] for k in sh if c[k] == best_sh)
    gain_sh = c["trained_on"] - best_sh
    fewer_sh = 1 - ev["trained_on"] / max(1, sh_evals)
    v = {"on_minus_off": gain, "fewer_evals_vs_off": round(fewer, 4),
         "c1_on_beats_off": bool(gain >= 3 or (gain >= 0 and fewer >= 0.25)),
         "best_shuffled": best_sh, "on_minus_best_shuffled": gain_sh,
         "fewer_evals_vs_best_shuffled": round(fewer_sh, 4),
         "c2_on_beats_shuffled": bool(gain_sh >= 3 or (gain_sh >= 0 and fewer_sh >= 0.25)),
         "empty_on_minus_empty_off": c["empty_on"] - c["empty_off"],
         "report_empty_on_minus_cold": c["empty_on"] - c["cold"],
         "c3_gain_vanishes_with_empty_field": bool(c["empty_on"] - c["empty_off"] <= 1),
         "trained_on_losses_vs_off": loss,
         "c4_no_task_worse": bool(not loss and all(not out["worse_than_cold"][k] for k in ("trained_on", "empty_on")))}
    v["pass_1_to_4"] = bool(v["c1_on_beats_off"] and v["c2_on_beats_shuffled"]
                            and v["c3_gain_vanishes_with_empty_field"] and v["c4_no_task_worse"])
    return v


def main() -> int:
    mod = PS.module_from(sys.argv[sys.argv.index("--module") + 1] if "--module" in sys.argv else None)
    if "--suite" in sys.argv:
        suite, _e, hard = PS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False, mod=mod)
    else:
        suite, _e, hard = PS.load(PS.OUT, check=True)
    out = TIJ.score(suite["hard"], hard, arms(fields()), suite["max_size"])
    out["sha256"] = PS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
