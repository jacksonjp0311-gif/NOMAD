"""Generate (once, seeded) the frozen DEEP suite: int tasks cold cannot certify.

    python3 scripts/deep_suite.py                 # write the frozen suite
    python3 scripts/deep_suite.py --check         # verify the committed file + hash
    python3 scripts/deep_suite.py --seed 7 --out /tmp/dev.json   # a dev suite

Procedure (fixed before any field was measured on the suite):

1. Sample random program trees of size 8-12 over the ``int`` opset
   (add, sub, mul, div, mod, min, max, ite; inputs x, y; constants 0-3).
   Every internal operator is drawn uniformly from the opset; leaves are
   drawn uniformly from x, y, 0, 1, 2, 3. Nothing about the field, the
   case-split organ or any held-out family steers the sampler.
2. Reference outputs come from running the tree on the same fixed int rows
   every WORLD int family uses (5 public, 3 challenge, 3 final). Rejected:
   invalid on any row, constant on the public rows, equal to a single input,
   or out of range.
3. Dedup by behaviour on the probe inputs (``variation.PROBES``) plus all
   task rows.
4. Leakage guard: reject a task whose behaviour on the probe inputs and the
   task rows equals any held-out family's reference function
   (square_product, absdiff, quartic_sum; the string/list held-outs
   last_first_upper and sum_minus_max cannot match an int task and are
   checked by type). The generator never reads held-out task rows; it uses
   their reference functions only for this exclusion.
5. Keep only tasks the cold control does *not* certify within 10,000
   evaluations at max_size 7 (``world.evaluate(task, prior=None)``).
6. Stop at 40 tasks. Each task is its own family ``deep_NN`` (no training
   family shares it), so measuring with "the task's family held out" is
   automatic: the field has no evidence for it.

The suite file stores, per task, the generating tree and every row; the
SHA-256 of the canonical JSON is written next to it and in docs/DEEP_SUITE.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad.variation import PROBES  # noqa: E402
from nomad.world import (INT_CONSTANTS, OPS, OPSETS, Invalid, evaluate, make_task, run,  # noqa: E402
                         size)
from nomad.world_tasks import _INT_CHA, _INT_FIN, _INT_PUB  # noqa: E402

SEED = 20261120
N_TASKS = 40
SIZES = (8, 12)
BUDGET = 10000
MAX_SIZE = 7
OUT = ROOT / "data" / "deep" / "deep_suite.json"
HASH = ROOT / "data" / "deep" / "deep_suite.sha256"

# Held-out reference functions, used ONLY to exclude look-alikes.
HELDOUT_FNS = {
    "square_product": lambda x, y: (x * x) * (y * y),
    "absdiff": lambda x, y: abs(x - y),
    "quartic_sum": lambda x, y: x ** 4 + y ** 4,
}
HELDOUT_NON_INT = ("last_first_upper", "sum_minus_max")  # str/list outputs: cannot match

PROBE_ROWS = [dict(r) for r in PROBES["x:int,y:int"]]
ALL_ROWS = [{"x": x, "y": y} for x, y in _INT_PUB + _INT_CHA + _INT_FIN]


def _leaf(rng: random.Random) -> list:
    k = rng.randrange(6)
    return ["var", "xy"[k]] if k < 2 else ["const", INT_CONSTANTS[k - 2]]


def sample(rng: random.Random, n: int) -> list:
    """A random tree with exactly n nodes over the int opset (uniform ops).

    Every operator is binary or ternary, so no subtree can have exactly 2
    nodes; compositions with a part of 2 are redrawn.
    """
    if n == 1:
        return _leaf(rng)
    while True:
        name = rng.choice(OPSETS["int"])
        k = len(OPS[name].args)
        if n - 1 < k:
            continue
        cuts = sorted(rng.sample(range(1, n - 1), k - 1))
        parts = [b - a for a, b in zip([0] + cuts, cuts + [n - 1])]
        if 2 in parts:
            continue
        return [name] + [sample(rng, p) for p in parts]


def _behaviour(fn, rows) -> tuple | None:
    out = []
    for r in rows:
        try:
            out.append(fn(r))
        except (Invalid, ZeroDivisionError, OverflowError):
            out.append(None)
    return tuple(out)


def _canon(suite: dict) -> bytes:
    return json.dumps(suite, sort_keys=True, separators=(",", ":")).encode()


def suite_hash(suite: dict) -> str:
    return hashlib.sha256(_canon(suite)).hexdigest()


def generate(seed: int = SEED, n_tasks: int = N_TASKS, budget: int = BUDGET, log=None) -> dict:
    rng = random.Random(seed)
    held = {name: _behaviour(lambda r, f=f: f(r["x"], r["y"]), PROBE_ROWS + ALL_ROWS)
            for name, f in HELDOUT_FNS.items()}
    seen: set = set()
    tasks = []
    stats = {"sampled": 0, "invalid_or_trivial": 0, "duplicate": 0, "heldout_lookalike": 0,
             "cold_certified": 0}
    while len(tasks) < n_tasks:
        stats["sampled"] += 1
        if stats["sampled"] > 200000:
            raise RuntimeError("could not fill the deep suite")
        tree = sample(rng, rng.randint(*SIZES))
        beh = _behaviour(lambda r: run(tree, r), PROBE_ROWS + ALL_ROWS)
        task_vals = beh[len(PROBE_ROWS):]
        pub = task_vals[:len(_INT_PUB)]
        if (any(v is None for v in task_vals) or len(set(pub)) == 1
                or all(v == r["x"] for v, r in zip(task_vals, ALL_ROWS))
                or all(v == r["y"] for v, r in zip(task_vals, ALL_ROWS))):
            stats["invalid_or_trivial"] += 1
            continue
        if beh in seen:
            stats["duplicate"] += 1
            continue
        seen.add(beh)
        if any(beh == hb for hb in held.values()) or any(task_vals == hb[len(PROBE_ROWS):] for hb in held.values()):
            stats["heldout_lookalike"] += 1
            continue
        idx = len(tasks)
        fam = f"deep_{idx:02d}"
        t = to_task({"task_id": f"d-{idx:02d}", "family": fam, "tree": tree, "values": list(task_vals)})
        c, _ = evaluate(t, prior=None, max_eval=budget, max_size=MAX_SIZE)
        if c.certified:
            stats["cold_certified"] += 1
            continue
        tasks.append({"task_id": f"d-{idx:02d}", "family": fam, "tree": tree, "size": size(tree),
                      "values": list(task_vals), "cold_evaluations": c.evaluations,
                      "cold_reason": c.reason})
        if log:
            log(f"{fam} size={size(tree)} cold={c.evaluations} {c.reason}")
    return {"schema": "nomad.deep-suite.v1", "seed": seed, "budget": budget, "max_size": MAX_SIZE,
            "sizes": list(SIZES), "opset": "int",
            "rows": {"public": _INT_PUB, "challenge": _INT_CHA, "final": _INT_FIN},
            "excluded_heldouts": sorted(HELDOUT_FNS) + list(HELDOUT_NON_INT),
            "stats": stats, "tasks": tasks}


def to_task(entry: dict):
    vals = entry["values"]
    pts = _INT_PUB + _INT_CHA + _INT_FIN
    rows = [({"x": x, "y": y}, v) for (x, y), v in zip(pts, vals)]
    a, b = len(_INT_PUB), len(_INT_PUB) + len(_INT_CHA)
    return make_task(entry["task_id"], entry["family"], "int", {"x": "int", "y": "int"}, "int",
                     rows[:a], rows[a:b], rows[b:], 9)


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list]:
    suite = json.loads(path.read_text())
    if check:
        want = HASH.read_text().split()[0] if HASH.exists() else None
        if want and suite_hash(suite) != want:
            raise ValueError("deep suite hash mismatch")
    return suite, [to_task(e) for e in suite["tasks"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n", type=int, default=N_TASKS)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        suite = json.loads(OUT.read_text())
        h = suite_hash(suite)
        want = HASH.read_text().split()[0]
        print(json.dumps({"sha256": h, "expected": want, "ok": h == want, "tasks": len(suite["tasks"])}))
        return 0 if h == want else 1
    suite = generate(a.seed, a.n, log=lambda m: print(m, file=sys.stderr))
    out = a.out or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(suite, sort_keys=True, indent=1) + "\n")
    h = suite_hash(suite)
    if a.out is None:
        HASH.write_text(f"{h}  data/deep/deep_suite.json\n")
    print(json.dumps({"sha256": h, "tasks": len(suite["tasks"]), "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
