"""Generate (once, seeded) the frozen MEMIDX suite; see docs/MEMIDX.md.

    PYTHONHASHSEED=0 python3 scripts/memidx_suite.py              # write data/deep/memidx_suite.json + .sha256
    python3 scripts/memidx_suite.py --check                       # verify the committed file + hash

Same procedure as scripts/novel_suite.py (11 rows per family: 5 public, 3 challenge, 3 final, drawn with
random.Random(f"{seed}:{family}"); cold control at 10,000 evaluations, max_size 7 -> easy / candidate hard;
lookup guard: a candidate is dropped when any whole program or library block remembered by either trained
field of scripts/memidx_judge.py, renamed onto the task's inputs, certifies it outright), on the catalogue
scripts/memidx_catalogue.py with a new seed. Only the cold control and memory lookup touch the suite here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import memidx_catalogue as MC  # noqa: E402
import transfer_suite as TS  # noqa: E402

SEED = 20270917
OUT = ROOT / "data" / "deep" / "memidx_suite.json"
HASH = ROOT / "data" / "deep" / "memidx_suite.sha256"
suite_hash = TS.suite_hash


def generate(seed: int = SEED, log=None, priors=None) -> dict:
    import memidx_judge as MJ
    import novel_judge as NJ
    if priors is None:
        priors = [p for p, _ in MJ.fields().values()]
    old = TS.T
    TS.T = MC
    try:
        with NJ.env(**MJ.OFF):   # the cold control runs under the CURRENT switch settings
            suite = TS.generate(seed, log=log, priors=priors)
    finally:
        TS.T = old
    suite["schema"] = "nomad.memidx-suite.v1"
    return suite


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("memidx suite hash mismatch")
    return suite, [MC.to_task(e) for e in suite["easy"]], [MC.to_task(e) for e in suite["hard"]]


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
        HASH.write_text(f"{h}  data/deep/memidx_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
