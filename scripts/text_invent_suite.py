"""Generate (once, seeded) the sealed INVENT_TEXT suite; see docs/INVENT_TEXT.md.

    python3 scripts/text_invent_suite.py          # write data/deep/text_invent_suite.json + .sha256
    python3 scripts/text_invent_suite.py --check  # verify the committed file + hash

The BRIDGE generator (scripts/bridge_suite.py) on ``nomad.text_invent_tasks.CATALOGUE`` (new input
names), seed 20261130; trained fields for the lookup guard are bridge_suite.fields(). Notes of the
original follow.

Procedure (the text suite's, on ``nomad.bridge.CATALOGUE``, always with NOMAD_BRIDGE=on):

1. Per family draw 11 rows (5 public / 3 challenge / 3 final) with
   ``random.Random(f"{seed}:{family}")``; a row is kept only if the reference
   tree reproduces the independent Python truth exactly.
2. Cold control at 10,000 evaluations, max_size 7: certified -> ``easy``
   (recorded, never scored); else candidate ``hard``.
3. Lookup guard: a candidate is dropped if any whole program or library block
   remembered by any trained arm (trained, world_only, bridge_only), renamed
   onto the task's inputs by every type-preserving renaming, certifies it
   outright, or if an easy bridge family's reference tree does.
4. The rest is the sealed ``hard`` section.
"""
from __future__ import annotations

import argparse
import copy
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
from nomad import bridge as XB  # noqa: E402
from nomad import text_invent_tasks as X  # noqa: E402
from nomad.world import certify, evaluate  # noqa: E402

SEED = 20261130
BUDGET = 10000
MAX_SIZE = 7
OUT = ROOT / "data" / "deep" / "text_invent_suite.json"
HASH = ROOT / "data" / "deep" / "text_invent_suite.sha256"
suite_hash = TS.suite_hash


def fields() -> dict:
    """Trained arms (deterministic; never a bridge catalogue task):

    world_only:  all 16 WORLD families + easy science (the text judge's all_sci)
    bridge_only: the 14 bridge training tasks only
    trained:     world_only, then the bridge training tasks (the arm that is scored)
    """
    import science_probe as SP
    import science_suite as SS
    import variation_probe as VP
    from nomad import variation as V
    from nomad.world import WorldPrior
    _, easy, _ = SS.load(SS.OUT, check=True)
    out = {}
    with env(NOMAD_BRIDGE="on"):
        p, vs, _ = VP.train()
        SP.train_more(p, vs, easy)
        out["world_only"] = (p, vs)
        p2, vs2 = copy.deepcopy(p), copy.deepcopy(vs)
        SP.train_more(p2, vs2, XB.train_tasks())
        out["trained"] = (p2, vs2)
        p3, vs3 = WorldPrior(), V.VariationState()
        SP.train_more(p3, vs3, XB.train_tasks())
        out["bridge_only"] = (p3, vs3)
    return out


def generate(seed: int = SEED, catalogue=None, budget: int = BUDGET, log=None, priors=None) -> dict:
    catalogue = X.CATALOGUE if catalogue is None else catalogue
    entries = []
    with env(NOMAD_BRIDGE="on"):
        for i, f in enumerate(catalogue):
            rows = X.draw_rows(f, random.Random(f"{seed}:{f.family}"))
            e = {"task_id": f"x-{i:02d}", "family": f.family, "domain": X.DOMAIN, "kind": f.kind.split(":", 1)[1],
                 "formula": f.text, "inputs": list(f.inputs), "out": f.out, "tree": f.tree,
                 "rows": [[r, a] for r, a in rows]}
            c, _ = evaluate(X.to_task(e), prior=None, max_eval=budget, max_size=MAX_SIZE)
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
            t = X.to_task(e)
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
    return {"schema": "nomad.text-invent-suite.v1", "seed": seed, "budget": budget, "max_size": MAX_SIZE,
            "opset": "bridge", "domains": [X.DOMAIN], "trained_on_by_any_arm": False,
            "split": {"public": 5, "challenge": 3, "final": 3},
            "stats": {"families": len(entries), "easy": len(easy), "hard": len(hard), "lookup_dropped": dropped},
            "easy": easy, "hard": hard}


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("text_invent suite hash mismatch")
    return suite, [X.to_task(e) for e in suite["easy"]], [X.to_task(e) for e in suite["hard"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--dev", action="store_true", help="use DEV_CATALOGUE")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        suite = json.loads(OUT.read_text())
        h, want = suite_hash(suite), HASH.read_text().split()[0]
        print(json.dumps({"sha256": h, "expected": want, "ok": h == want,
                          "easy": len(suite["easy"]), "hard": len(suite["hard"])}))
        return 0 if h == want else 1
    if a.dev and a.out is None:
        raise SystemExit("--dev needs --out")
    suite = generate(a.seed, X.CATALOGUE, log=lambda m: print(m, file=sys.stderr))
    out = a.out or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(suite, sort_keys=True, indent=1) + "\n")
    h = suite_hash(suite)
    if a.out is None:
        HASH.write_text(f"{h}  data/deep/text_invent_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
