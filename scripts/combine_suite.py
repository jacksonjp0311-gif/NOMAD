"""Generate (once, seeded) the sealed COMBINE two-concept suite; see docs/COMBINE.md.

    python3 scripts/combine_suite.py              # write data/deep/combine_suite.json + .sha256 (combine_tasks.SEALED)
    python3 scripts/combine_suite.py --check
    python3 scripts/combine_suite.py --catalogue PATH.py:NAME --names a,b,c --seed 7 --out /tmp/c.json   # a dev suite

Same procedure as scripts/roles_suite.py (story entries, cold control at 10,000 / max_size 7 recorded
per task); tasks the cold control certifies go to ``easy`` (reported, never scored), the rest are the
sealed ``hard`` section. No field arm is run here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import roles_suite as RS  # noqa: E402
from nomad import combine_tasks as CT  # noqa: E402,F401  (registers the composites)
from nomad import meaning_tasks as MT  # noqa: E402

SEED = 20270223
OUT = ROOT / "data" / "deep" / "combine_suite.json"
HASH = ROOT / "data" / "deep" / "combine_suite.sha256"
suite_hash = RS.suite_hash


def generate(catalogue, names, seed: int = SEED, prefix: str = "c", log=None) -> dict:
    s = RS.generate(catalogue, names, seed, prefix=prefix, log=log)
    easy = [e for e in s["tasks"] if e["cold_certified"]]
    hard = [e for e in s["tasks"] if not e["cold_certified"]]
    return {"schema": "nomad.combine-suite.v1", "seed": seed, "budget": s["budget"], "max_size": s["max_size"],
            "names": list(names), "easy": easy, "hard": hard}


def load(path: Path = OUT, check: bool = True):
    suite = json.loads(Path(path).read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("combine suite hash mismatch")
    return suite, [MT.to_task(e) for e in suite["easy"]], [MT.to_task(e) for e in suite["hard"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--catalogue", default=None)
    ap.add_argument("--names", default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        suite, _e, h = load(OUT, check=True)
        print(json.dumps({"ok": True, "sha256": suite_hash(suite), "hard": len(h)}))
        return 0
    log = lambda m: print(m, file=sys.stderr, flush=True)  # noqa: E731
    if a.catalogue:
        suite = generate(RS._catalogue(a.catalogue), a.names.split(","), a.seed, prefix="cd", log=log)
        out = a.out or Path("/tmp/combine_dev_suite.json")
        out.write_text(json.dumps(suite, indent=1) + "\n")
    else:
        suite = generate(CT.SEALED, CT.SEALED_NAMES, a.seed, log=log)
        OUT.write_text(json.dumps(suite, indent=1) + "\n")
        HASH.write_text(f"{suite_hash(suite)}  {OUT.name}\n")
        out = OUT
    print(json.dumps({"out": str(out), "sha256": suite_hash(suite), "easy": len(suite["easy"]),
                      "hard": len(suite["hard"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
