"""Generate (once, seeded) the sealed SELFEDIT suite; see docs/SELFEDIT.md.

    python3 scripts/selfedit_suite.py              # write data/deep/selfedit_suite.json + .sha256
    python3 scripts/selfedit_suite.py --check      # verify the committed file + hash
    python3 scripts/selfedit_suite.py --dev --seed 7 --out /tmp/s.json   # a dev suite on DEV_CATALOGUE

Same procedure as scripts/transfer_suite.py / invent2_suite.py (cold control at 10,000 evaluations,
max_size 7 -> easy / candidate hard; lookup guard against every trained arm's memory under every
renaming and against easy twins) on ``nomad.selfedit_tasks.CATALOGUE`` with a new seed. Only the cold
control is run; no field arm is measured here.
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
from nomad import selfedit_tasks as ST  # noqa: E402

SEED = 20261128
OUT = ROOT / "data" / "deep" / "selfedit_suite.json"
HASH = ROOT / "data" / "deep" / "selfedit_suite.sha256"
suite_hash = TS.suite_hash


def generate(seed: int = SEED, dev: bool = False, log=None, priors=None) -> dict:
    old = TS.T
    TS.T = ST.DEV if dev else ST
    try:
        suite = TS.generate(seed, log=log, priors=priors)
    finally:
        TS.T = old
    suite["schema"] = "nomad.selfedit-suite.v1"
    return suite


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("selfedit suite hash mismatch")
    return suite, [ST.to_task(e) for e in suite["easy"]], [ST.to_task(e) for e in suite["hard"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--dev", action="store_true")
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
    suite = generate(a.seed, dev=a.dev, log=lambda m: print(m, file=sys.stderr))
    out = a.out or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(suite, sort_keys=True, indent=1) + "\n")
    h = suite_hash(suite)
    if a.out is None:
        HASH.write_text(f"{h}  data/deep/selfedit_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
