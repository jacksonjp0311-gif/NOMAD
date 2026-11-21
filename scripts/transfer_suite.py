"""Generate (once, seeded) the frozen cross-domain TRANSFER suite; see docs/TRANSFER.md.

    python3 scripts/transfer_suite.py              # write data/deep/transfer_suite.json + .sha256
    python3 scripts/transfer_suite.py --check      # verify the committed file + hash
    python3 scripts/transfer_suite.py --seed 7 --out /tmp/t.json   # a dev suite (no hash file)

Procedure (fixed before any field arm was measured on it):

1. For every family in ``nomad.transfer.CATALOGUE`` (integer geometry and
   finance, domains no field arm ever trains on) draw 11 rows (5 public,
   3 challenge, 3 final) with ``random.Random(f"{seed}:{family}")``; a row is
   kept only if the exact Fraction truth is an integer the reference tree
   reproduces.
2. Cold control (``evaluate(task, prior=None)``) at 10,000 evaluations,
   max_size 7: certified -> ``easy`` (recorded, never trained on, never
   scored); not certified -> candidate ``hard``.
3. Lookup guard (transfer must be more than retrieval): a candidate is
   dropped if any whole program or library block remembered by any trained
   arm of the judge (math, math+science, all+science), instantiated over the
   task's inputs by *every* type-preserving renaming, certifies it outright.
   It is also dropped if an easy transfer family's reference tree certifies it.
4. The rest is the sealed ``hard`` section.

Does not read or modify data/deep/deep_suite.json or science_suite.json
(other than hash-checked loading of the science easy curriculum).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from nomad import transfer as T  # noqa: E402
from nomad.world import WorldPrior, certify, evaluate, subtrees  # noqa: E402
from nomad.world import _rename, _var_names  # noqa: E402
from nomad.world_tasks import TRAIN  # noqa: E402

SEED = 20261122
BUDGET = 10000
MAX_SIZE = 7
OUT = ROOT / "data" / "deep" / "transfer_suite.json"
HASH = ROOT / "data" / "deep" / "transfer_suite.sha256"

MATH_FAMILIES = sorted(t.family for ts in TRAIN["mathematics"].values() for t in ts)


def _canon(suite: dict) -> bytes:
    return json.dumps(suite, sort_keys=True, separators=(",", ":")).encode()


def suite_hash(suite: dict) -> str:
    return hashlib.sha256(_canon(suite)).hexdigest()


def fields() -> dict:
    """The trained arms of the transfer judge (deterministic; never a transfer task).

    math:      the 8 WORLD mathematics families only
    math_sci:  math + the 14 easy science families (data/deep/science_suite.json)
    all_sci:   all 16 WORLD families (math, language, coding) + easy science
               (= the `trained` arm of scripts/learning_judge.py)
    """
    import science_probe as SP
    import science_suite as SS
    import variation_probe as VP
    _, easy, _ = SS.load(SS.OUT, check=True)
    out = {}
    p, vs, _ = VP.train(set(MATH_FAMILIES))
    out["math"] = (p, vs)
    p, vs, _ = VP.train(set(MATH_FAMILIES))
    SP.train_more(p, vs, easy)
    out["math_sci"] = (p, vs)
    p, vs, _ = VP.train()
    SP.train_more(p, vs, easy)
    out["all_sci"] = (p, vs)
    return out


def memory_trees(prior: WorldPrior) -> list[tuple[list, dict]]:
    srcs = [(t, prior.library_sig.get(n)) for n, t in prior.library.items()]
    srcs += [(t, prior.programs_sig.get(n)) for n, t in prior.programs.items()]
    return [(t, {a: b for a, b in (sig or [])}) for t, sig in srcs]


def lookup_hits(task, priors) -> list[str]:
    """Rendered memory trees that, renamed onto the task's inputs, certify it."""
    from nomad.world import render
    names = [n for n, ty in task.inputs if ty == "int"]
    hits, seen = [], set()
    for prior in priors:
        for t, types in memory_trees(prior):
            if any(x[0] == "lib" for x in subtrees(t)):
                continue
            vs = _var_names(t, [])
            if not vs or any(types.get(v) != "int" for v in vs) or len(vs) > len(names):
                continue
            for perm in permutations(names, len(vs)):
                inst = _rename(t, dict(zip(vs, perm)))
                k = json.dumps(inst)
                if k in seen:
                    continue
                seen.add(k)
                r, _, fin = certify(task, inst)
                if r is not None and r.supported and fin:
                    hits.append(render(inst))
    return hits


def generate(seed: int = SEED, budget: int = BUDGET, log=None, priors=None) -> dict:
    entries = []
    for i, f in enumerate(T.CATALOGUE):
        dom, kind = f.kind.split(":", 1)
        rows = T.draw_rows(f, random.Random(f"{seed}:{f.family}"))
        e = {"task_id": f"t-{i:02d}", "family": f.family, "domain": dom, "kind": kind,
             "formula": f.text, "inputs": list(f.inputs), "tree": f.tree,
             "rows": [[r, a] for r, a in rows]}
        c, _ = evaluate(T.to_task(e), prior=None, max_eval=budget, max_size=MAX_SIZE)
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
        t = T.to_task(e)
        twin = [x["family"] for x in easy if x["inputs"] == e["inputs"]
                and (lambda r: r[0] is not None and r[0].supported and r[2])(certify(t, x["tree"]))]
        hits = lookup_hits(t, priors)
        if twin or hits:
            dropped.append({"family": e["family"], "easy_twin": twin, "memory_lookup": hits[:5]})
            if log:
                log(f"  drop {e['family']}: twin={twin} lookup={hits[:3]}")
        else:
            hard.append(e)
    for sec, tier in ((easy, "easy"), (hard, "hard")):
        for e in sec:
            e["tier"] = tier
    return {"schema": "nomad.transfer-suite.v1", "seed": seed, "budget": budget, "max_size": MAX_SIZE,
            "opset": "int", "domains": list(T.DOMAINS), "trained_on_by_any_arm": False,
            "split": {"public": 5, "challenge": 3, "final": 3},
            "stats": {"families": len(entries), "easy": len(easy), "hard": len(hard),
                      "lookup_dropped": dropped},
            "easy": easy, "hard": hard}


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check:
        want = HASH.read_text().split()[0]
        if suite_hash(suite) != want:
            raise ValueError("transfer suite hash mismatch")
    return suite, [T.to_task(e) for e in suite["easy"]], [T.to_task(e) for e in suite["hard"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        suite = json.loads(OUT.read_text())
        h, want = suite_hash(suite), HASH.read_text().split()[0]
        print(json.dumps({"sha256": h, "expected": want, "ok": h == want,
                          "easy": len(suite["easy"]), "hard": len(suite["hard"])}))
        return 0 if h == want else 1
    suite = generate(a.seed, log=lambda m: print(m, file=sys.stderr))
    out = a.out or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(suite, sort_keys=True, indent=1) + "\n")
    h = suite_hash(suite)
    if a.out is None:
        HASH.write_text(f"{h}  data/deep/transfer_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
