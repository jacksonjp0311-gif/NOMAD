"""Generate (once, seeded) the sealed INFLECT suite; see docs/INFLECT.md.

    python3 scripts/inflect_suite.py          # write data/deep/inflect_suite.json + .sha256
    python3 scripts/inflect_suite.py --check  # verify the committed file + hash
    python3 scripts/inflect_suite.py --module PATH.py --seed N --out P   # a dev suite (dev catalogue module)

The TEXT_CHAIN generator (5/3/3 rows, a row kept only when the reference tree reproduces the Python truth,
cold control at 10,000 / max_size 7 -> easy / hard, lookup guard on every trained arm's memory under every
renaming, easy-twin guard) on ``nomad.inflect.CATALOGUE`` with NOMAD_INFLECT=on, seed 20261221. Only the cold
control is run.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import text_suite as XS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from grow_judge import env  # noqa: E402
from nomad import inflect as X  # noqa: E402
from nomad.world import certify, evaluate  # noqa: E402

SEED = 20261221
BUDGET = 10000
MAX_SIZE = 7
OUT = ROOT / "data" / "deep" / "inflect_suite.json"
HASH = ROOT / "data" / "deep" / "inflect_suite.sha256"
suite_hash = TS.suite_hash
ON = dict(NOMAD_BRIDGE="on", NOMAD_INFLECT="on")
OFF = dict(NOMAD_BRIDGE="on", NOMAD_INFLECT="off")


def module_from(path: str | None):
    if not path:
        return X
    spec = importlib.util.spec_from_file_location("inflect_dev", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fields() -> dict:
    """Trained arms (deterministic; never a sealed inflect task):

    world_only:   bridge_suite's world_only (all 16 WORLD families + easy science)
    bridge_only:  the 14 bridge training tasks only (bridge_suite's)
    trained:      world_only, then the bridge training tasks (the BRIDGE arm; no inflection)
    inflect_only: the 9 inflect training tasks only
    inflect:      trained, then the inflect training tasks (the arm that is scored)
    inflect_off:  the same training run with NOMAD_INFLECT off (what a field learns without the switch)
    """
    import bridge_suite as BS
    import science_probe as SP
    from nomad import variation as V
    from nomad.world import WorldPrior
    out = BS.fields()
    with env(**ON):
        p, vs = copy.deepcopy(out["trained"][0]), copy.deepcopy(out["trained"][1])
        SP.train_more(p, vs, X.train_tasks())
        out["inflect"] = (p, vs)
        p3, vs3 = WorldPrior(), V.VariationState()
        SP.train_more(p3, vs3, X.train_tasks())
        out["inflect_only"] = (p3, vs3)
    with env(**OFF):    # the same training with the switch off: the inflect opset collapses to the bridge opset
        p4, vs4 = copy.deepcopy(out["trained"][0]), copy.deepcopy(out["trained"][1])
        SP.train_more(p4, vs4, X.train_tasks())
        out["inflect_off"] = (p4, vs4)
    return out


def generate(seed: int = SEED, mod=X, budget: int = BUDGET, log=None, priors=None) -> dict:
    entries = []
    with env(**ON):
        for i, f in enumerate(mod.CATALOGUE):
            rows = mod.draw_rows(f, random.Random(f"{seed}:{f.family}"))
            e = {"task_id": f"i-{i:02d}", "family": f.family, "domain": mod.DOMAIN, "kind": f.kind.split(":", 1)[1],
                 "formula": f.text, "inputs": list(f.inputs), "out": f.out, "tree": f.tree,
                 "rows": [[r, a] for r, a in rows]}
            c, _ = evaluate(mod.to_task(e), prior=None, max_eval=budget, max_size=MAX_SIZE)
            e.update(cold_certified=c.certified, cold_evaluations=c.evaluations, cold_reason=c.reason)
            entries.append(e)
            if log:
                log(f"{f.family} cold={c.certified} {c.evaluations} {c.reason}")
        if priors is None:
            priors = [p for p, _ in fields().values()]
        easy = [e for e in entries if e["cold_certified"]]
        hard, dropped = [], []
        for e in entries:
            if e["cold_certified"]:
                continue
            t = mod.to_task(e)
            twin = [x["family"] for x in easy if x["inputs"] == e["inputs"] and x["out"] == e["out"]
                    and (lambda r: r[0] is not None and r[0].supported and r[2])(certify(t, x["tree"]))]
            hits = XS.lookup_hits(t, priors)
            if twin or hits:
                dropped.append({"family": e["family"], "easy_twin": twin, "memory_lookup": hits[:5]})
                if log:
                    log(f"  drop {e['family']}: twin={twin} lookup={hits[:3]}")
            else:
                hard.append(e)
    for sec, tier in ((easy, "easy"), (hard, "hard")):
        for e in sec:
            e["tier"] = tier
    return {"schema": "nomad.inflect-suite.v1", "seed": seed, "budget": budget, "max_size": MAX_SIZE,
            "opset": "inflect", "domains": [mod.DOMAIN], "trained_on_by_any_arm": False,
            "split": {"public": 5, "challenge": 3, "final": 3},
            "stats": {"families": len(entries), "easy": len(easy), "hard": len(hard), "lookup_dropped": dropped},
            "easy": easy, "hard": hard}


def load(path: Path = OUT, check: bool = True, mod=X) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("inflect suite hash mismatch")
    return suite, [mod.to_task(e) for e in suite["easy"]], [mod.to_task(e) for e in suite["hard"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--module", default=None, help="a dev catalogue module (file path)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        suite = json.loads(OUT.read_text())
        h, want = suite_hash(suite), HASH.read_text().split()[0]
        print(json.dumps({"sha256": h, "expected": want, "ok": h == want,
                          "easy": len(suite["easy"]), "hard": len(suite["hard"])}))
        return 0 if h == want else 1
    if a.module and a.out is None:
        raise SystemExit("--module needs --out")
    suite = generate(a.seed, module_from(a.module), log=lambda m: print(m, file=sys.stderr))
    out = a.out or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(suite, sort_keys=True, indent=1) + "\n")
    h = suite_hash(suite)
    if a.out is None:
        HASH.write_text(f"{h}  data/deep/inflect_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
