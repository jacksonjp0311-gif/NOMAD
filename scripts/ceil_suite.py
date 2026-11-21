"""Generate (once, seeded) the sealed CEIL suite; see docs/CEIL.md.

    python3 scripts/ceil_suite.py              # write data/deep/ceil_suite.json + .sha256
    python3 scripts/ceil_suite.py --check      # verify the committed file + hash

Same procedure as scripts/transfer_suite.py / selfedit_suite.py (cold control at 10,000 evaluations,
max_size 7 -> easy / candidate hard; lookup guard against every trained arm's memory under every
renaming and against easy twins) on ``nomad.ceil_tasks.CATALOGUE`` with a new seed (20270307: unused;
20261120-20261231, 20270117, 20270209 and 20270223 are taken). Only the cold control is run; no field arm is
measured here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import transfer_suite as TS  # noqa: E402
from nomad import ceil_tasks as CT  # noqa: E402

SEED = 20270307
OUT = ROOT / "data" / "deep" / "ceil_suite.json"
HASH = ROOT / "data" / "deep" / "ceil_suite.sha256"
suite_hash = TS.suite_hash


def generate(seed: int = SEED, log=None, priors=None) -> dict:
    old = TS.T
    TS.T = CT
    try:
        suite = TS.generate(seed, log=log, priors=priors)
    finally:
        TS.T = old
    suite["schema"] = "nomad.ceil-suite.v1"
    return suite


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(Path(path).read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("ceil suite hash mismatch")
    return suite, [CT.to_task(e) for e in suite["easy"]], [CT.to_task(e) for e in suite["hard"]]


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
    if a.out is None:
        HASH.write_text(f"{suite_hash(suite)}  {OUT.name}\n")
    print(json.dumps({"out": str(out), "sha256": suite_hash(suite), "easy": len(suite["easy"]),
                      "hard": len(suite["hard"]), "dropped": len(suite["stats"]["lookup_dropped"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
