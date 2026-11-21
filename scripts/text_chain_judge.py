"""Measurement only: the TEXT_CHAIN judge (multi-part concat chains on string goals); docs/TEXT_CHAIN.md.

    python3 scripts/text_chain_judge.py                                  # the frozen sealed suite (hash-checked)
    python3 scripts/text_chain_judge.py --suite PATH [--module DEV.py]   # a dev suite (no hash check)

Budget 10,000, the suite's max_size, NOMAD_BRIDGE on, PORT / ANCHOR2 / SCALE on, INVENT_TEXT and SELFEDIT
at their defaults (on). Fields = scripts/bridge_suite.fields(). Arms: cold; empty_off / empty_on
(NOMAD_TEXT_CHAIN off / on); trained_off; **trained_on** (scored); report: world_only_off / _on,
bridge_only_off / _on,
trained_on_text_off (NOMAD_INVENT_TEXT=off: the chain still runs inside INVENT, anchors off).
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
import text_chain_suite as CS  # noqa: E402
import text_invent_judge as TIJ  # noqa: E402
from bridge_judge import B_ON  # noqa: E402
from nomad.world import WorldPrior  # noqa: E402

OFF = dict(B_ON, NOMAD_TEXT_CHAIN="off")
ON = dict(B_ON, NOMAD_TEXT_CHAIN="on")


def arms(fields: dict) -> dict:
    p, vs = fields["trained"]
    kw = dict(prior=p, variation=vs, casesplit=True)
    a = {"cold": (OFF, dict(prior=None)),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True)),
         "trained_off": (OFF, kw), "trained_on": (ON, kw)}
    for k in ("world_only", "bridge_only"):
        pp, vv = fields[k]
        a[f"{k}_off"] = (OFF, dict(prior=pp, variation=vv, casesplit=True))
        a[f"{k}_on"] = (ON, dict(prior=pp, variation=vv, casesplit=True))
    a["trained_on_text_off"] = (dict(ON, NOMAD_INVENT_TEXT="off"), kw)
    return a


def main() -> int:
    mod = CS.module_from(sys.argv[sys.argv.index("--module") + 1] if "--module" in sys.argv else None)
    if "--suite" in sys.argv:
        suite, _e, hard = CS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False, mod=mod)
    else:
        suite, _e, hard = CS.load(CS.OUT, check=True)
    out = TIJ.score(suite["hard"], hard, arms(BS.fields()), suite["max_size"])
    out["sha256"] = CS.suite_hash(suite)
    out["verdict"] = TIJ.verdict(out)   # criteria 1-3 (same form as INVENT_TEXT); 4-5 from switch_regress / LOFO / tests
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
