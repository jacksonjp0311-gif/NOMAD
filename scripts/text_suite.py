"""Generate (once, seeded) the frozen TEXT transfer suite (string / language); see docs/TEXT.md.

    python3 scripts/text_suite.py              # write data/deep/text_suite.json + .sha256
    python3 scripts/text_suite.py --check      # verify the committed file + hash
    python3 scripts/text_suite.py --seed 7 --out /tmp/t.json   # a dev suite (no hash file)

Procedure (same as scripts/transfer_suite.py, on ``nomad.text.CATALOGUE``):

1. Per family draw 11 rows (5 public / 3 challenge / 3 final) with
   ``random.Random(f"{seed}:{family}")``; a row is kept only if the reference
   tree reproduces the independent Python truth exactly.
2. Cold control at 10,000 evaluations, max_size 7: certified -> ``easy``
   (recorded, never trained on, never scored); else candidate ``hard``.
3. Lookup guard: a candidate is dropped if any whole program or library
   block remembered by any trained arm (lang, math_sci, all_sci), renamed
   onto the task's inputs by every type-preserving renaming, certifies it
   outright, or if an easy text family's reference tree does.
4. The rest is the sealed ``hard`` section.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import transfer_suite as TS  # noqa: E402
from nomad import text as X  # noqa: E402
from nomad.world import certify, evaluate, render, subtrees  # noqa: E402
from nomad.world import _rename, _var_names  # noqa: E402
from nomad.world_tasks import TRAIN  # noqa: E402

SEED = 20261124
BUDGET = 10000
MAX_SIZE = 7
OUT = ROOT / "data" / "deep" / "text_suite.json"
HASH = ROOT / "data" / "deep" / "text_suite.sha256"
suite_hash = TS.suite_hash
LANG_FAMILIES = sorted(t.family for d in ("language", "coding") for ts in TRAIN[d].values() for t in ts)


def fields() -> dict:
    """Trained arms: lang (language + coding WORLD families only), plus the
    transfer judge's math_sci and all_sci. Never a text task."""
    import variation_probe as VP
    out = {}
    p, vs, _ = VP.train(set(LANG_FAMILIES))
    out["lang"] = (p, vs)
    out.update(TS.fields())
    return out


def lookup_hits(task, priors) -> list[str]:
    by_type: dict[str, list[str]] = {}
    for n, ty in task.inputs:
        by_type.setdefault(ty, []).append(n)
    hits, seen = [], set()
    for prior in priors:
        for t, types in TS.memory_trees(prior):
            if any(x[0] == "lib" for x in subtrees(t)):
                continue
            vs = _var_names(t, [])
            if not vs or any(v not in types for v in vs):
                continue
            groups: dict[str, list[str]] = {}
            for v in vs:
                groups.setdefault(types[v], []).append(v)
            if any(len(g) > len(by_type.get(ty, [])) for ty, g in groups.items()):
                continue
            maps = [{}]
            for ty, g in groups.items():
                maps = [dict(m, **dict(zip(g, perm))) for m in maps for perm in permutations(by_type[ty], len(g))]
            for m in maps:
                inst = _rename(t, m)
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
    for i, f in enumerate(X.CATALOGUE):
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
    return {"schema": "nomad.text-suite.v1", "seed": seed, "budget": budget, "max_size": MAX_SIZE,
            "opset": "text", "domains": [X.DOMAIN], "trained_on_by_any_arm": False,
            "split": {"public": 5, "challenge": 3, "final": 3},
            "stats": {"families": len(entries), "easy": len(easy), "hard": len(hard), "lookup_dropped": dropped},
            "easy": easy, "hard": hard}


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("text suite hash mismatch")
    return suite, [X.to_task(e) for e in suite["easy"]], [X.to_task(e) for e in suite["hard"]]


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
        HASH.write_text(f"{h}  data/deep/text_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
