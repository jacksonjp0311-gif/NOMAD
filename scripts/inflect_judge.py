"""Measurement only: the INFLECT judge (morphology / expression rule blocks); docs/INFLECT.md.

    python3 scripts/inflect_judge.py                                  # the frozen sealed suite (hash-checked)
    python3 scripts/inflect_judge.py --suite PATH [--module DEV.py]   # a dev suite (no hash check)

Budget 10,000, the suite's max_size, NOMAD_BRIDGE on, PORT / ANCHOR2 / SCALE, INVENT_TEXT, TEXT_CHAIN and
SELFEDIT at their defaults. Fields = scripts/inflect_suite.fields(). Arms (``_on`` / ``_off`` =
NOMAD_INFLECT; off: the ``inflect`` opset collapses to the bridge opset):
cold (switch on, no memory: the twin control), cold_off, empty_off / empty_on, trained_off,
**trained_on** (the field trained on the world, science, bridge and the 9 inflect rule-block tasks; scored);
controls: bridge_on (the same field *without* the inflect training: the switch alone), shuffled_on (the
inflect training tasks with their expected outputs rotated among tasks of the same signature: the
rewired field), inflect_only_on (the 9 inflect tasks only). Changes no live state.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bridge_suite as BS  # noqa: E402
import inflect_suite as IS  # noqa: E402
import text_invent_judge as TIJ  # noqa: E402
from bridge_judge import B_ON  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad import inflect as X  # noqa: E402
from nomad.world import WorldPrior, make_task  # noqa: E402

OFF = dict(B_ON, NOMAD_INFLECT="off")
ON = dict(B_ON, NOMAD_INFLECT="on")


def shuffled_tasks():
    """The inflect training tasks with expected outputs rotated among tasks of the same (inputs, out)."""
    ts = X.train_tasks()
    groups: dict = {}
    for t in ts:
        groups.setdefault((tuple(n for n, _ in t.inputs), t.out), []).append(t)
    out = []
    for g in groups.values():
        for i, t in enumerate(g):
            o = g[(i + 1) % len(g)]
            sw = lambda a, b: tuple((r, e2) for (r, _e), (_r2, e2) in zip(a, b))   # noqa: E731
            out.append(make_task(t.task_id + "-shuf", t.family + "_shuf", t.opset, dict(t.inputs), t.out,
                                 sw(t.public, o.public), sw(t.challenge, o.challenge), sw(t.final, o.final), t.level))
    return out


def fields() -> dict:
    import science_probe as SP
    f = IS.fields()
    with env(**ON):
        p, vs = copy.deepcopy(f["trained"][0]), copy.deepcopy(f["trained"][1])
        SP.train_more(p, vs, shuffled_tasks())
        f["shuffled"] = (p, vs)
    return f


def arms(fields: dict) -> dict:
    p, vs = fields["inflect"]
    kw = dict(prior=p, variation=vs, casesplit=True)
    po, vo = fields["inflect_off"]
    a = {"cold": (ON, dict(prior=None)), "cold_off": (OFF, dict(prior=None)),
         "empty_off": (OFF, dict(prior=WorldPrior(), casesplit=True)),
         "empty_on": (ON, dict(prior=WorldPrior(), casesplit=True)),
         "trained_off": (OFF, dict(prior=po, variation=vo, casesplit=True)), "trained_on": (ON, kw)}
    for k, name in (("trained", "bridge_on"), ("shuffled", "shuffled_on"), ("inflect_only", "inflect_only_on")):
        pp, vv = fields[k]
        a[name] = (ON, dict(prior=pp, variation=vv, casesplit=True))
    return a


def verdict(out: dict) -> dict:
    v = TIJ.verdict(out)
    c = out["certified"]
    v["learned_matters_on_minus_bridge_on"] = c["trained_on"] - c["bridge_on"]
    v["learned_matters_on_minus_shuffled"] = c["trained_on"] - c["shuffled_on"]
    v["c4_learned_matters"] = bool(c["trained_on"] - c["bridge_on"] >= 3 and c["trained_on"] - c["shuffled_on"] >= 3)
    v["pass_1_to_4"] = bool(v["pass_1_to_3"] and v["c4_learned_matters"])
    return v


def main() -> int:
    mod = IS.module_from(sys.argv[sys.argv.index("--module") + 1] if "--module" in sys.argv else None)
    if "--suite" in sys.argv:
        suite, _e, hard = IS.load(Path(sys.argv[sys.argv.index("--suite") + 1]), check=False, mod=mod)
    else:
        suite, _e, hard = IS.load(IS.OUT, check=True)
    out = TIJ.score(suite["hard"], hard, arms(fields()), suite["max_size"])
    out["sha256"] = IS.suite_hash(suite)
    out["verdict"] = verdict(out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
