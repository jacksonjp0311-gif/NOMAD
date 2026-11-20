"""Generate (once, seeded) the frozen SCIENCE suite; see docs/SCIENCE.md.

    python3 scripts/science_suite.py              # write data/deep/science_suite.json + .sha256
    python3 scripts/science_suite.py --check      # verify the committed file + hash
    python3 scripts/science_suite.py --out /tmp/s.json   # write elsewhere (no hash file)

Procedure (fixed before any field arm was measured):

1. For every family in ``nomad.science.CATALOGUE`` (fixed list of integer
   physics / unit / stoichiometry formulas), draw 11 rows (5 public,
   3 challenge, 3 final) with ``random.Random(f"{seed}:{family}")``. A row is
   kept only if the exact Fraction ground truth is an integer and the
   reference tree, run by the WORLD interpreter, reproduces it.
2. Run the cold control (``world.evaluate(task, prior=None)``) at the deep
   suite criterion: 10,000 evaluations, max_size 7.
   - cold does NOT certify -> sealed ``hard`` section (the science analogue
     of data/deep/deep_suite.json);
   - cold certifies -> ``easy`` section (curriculum: a science field may
     train on these; they are never scored as hard).
3. Leakage guard: a hard task is dropped if the reference tree of any easy
   family with the same signature certifies it (identical physics in
   disguise). Science signatures differ from every WORLD held-out
   ((x,y) int, (s) str, (xs) list), so no held-out can be matched.
4. Every task is tagged ``domain: science`` and its ``kind``.

The deep suite (data/deep/deep_suite.json) is not read or touched.
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

from nomad import science as S  # noqa: E402
from nomad.world import certify, evaluate  # noqa: E402

SEED = 20261121
BUDGET = 10000
MAX_SIZE = 7
OUT = ROOT / "data" / "deep" / "science_suite.json"
HASH = ROOT / "data" / "deep" / "science_suite.sha256"


def _canon(suite: dict) -> bytes:
    return json.dumps(suite, sort_keys=True, separators=(",", ":")).encode()


def suite_hash(suite: dict) -> str:
    return hashlib.sha256(_canon(suite)).hexdigest()


def generate(seed: int = SEED, budget: int = BUDGET, log=None) -> dict:
    entries = []
    for i, f in enumerate(S.CATALOGUE):
        rows = S.draw_rows(f, random.Random(f"{seed}:{f.family}"))
        e = {"task_id": f"s-{i:02d}", "family": f.family, "domain": S.DOMAIN, "kind": f.kind,
             "formula": f.text, "inputs": list(f.inputs), "tree": f.tree,
             "rows": [[r, a] for r, a in rows], "curriculum": list(f.curriculum)}
        c, _ = evaluate(S.to_task(e), prior=None, max_eval=budget, max_size=MAX_SIZE)
        e.update(cold_certified=c.certified, cold_evaluations=c.evaluations, cold_reason=c.reason)
        entries.append(e)
        if log:
            log(f"{f.family} cold={c.certified} {c.evaluations} {c.reason}")
    easy = [e for e in entries if e["cold_certified"]]
    hard, leaked = [], []
    for e in entries:
        if e["cold_certified"]:
            continue
        t = S.to_task(e)
        twin = [x["family"] for x in easy if x["inputs"] == e["inputs"]
                and (lambda r: r[0] is not None and r[0].supported and r[2])(certify(t, x["tree"]))]
        (leaked if twin else hard).append(e)
    for sec in (easy, hard):
        for e in sec:
            e["tier"] = "easy" if sec is easy else "hard"
    return {"schema": "nomad.science-suite.v1", "seed": seed, "budget": budget, "max_size": MAX_SIZE,
            "opset": "int", "domain": S.DOMAIN, "kinds": list(S.KINDS),
            "split": {"public": S.N_PUBLIC, "challenge": S.N_CHALLENGE, "final": S.N_FINAL},
            "stats": {"families": len(entries), "easy": len(easy), "hard": len(hard),
                      "leakage_dropped": [e["family"] for e in leaked]},
            "easy": easy, "hard": hard}


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check:
        want = HASH.read_text().split()[0] if HASH.exists() else None
        if want and suite_hash(suite) != want:
            raise ValueError("science suite hash mismatch")
    return suite, [S.to_task(e) for e in suite["easy"]], [S.to_task(e) for e in suite["hard"]]


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
        HASH.write_text(f"{h}  data/deep/science_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
