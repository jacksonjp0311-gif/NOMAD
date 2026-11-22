"""Generate (once, seeded) the sealed CERT suite; see docs/CERT.md.

    python3 scripts/cert_suite.py          # write data/deep/cert_suite.json + .sha256
    python3 scripts/cert_suite.py --check  # verify the committed file + hash

The TRANSFER generator (scripts/transfer_suite.generate: 5/3/3 rows, a row kept only when the
reference tree reproduces the exact Fraction truth, cold control at 10,000 / max_size 7 -> easy /
hard, lookup guard on every trained arm's memory under every renaming, easy-twin guard) on
``nomad.cert_tasks.CATALOGUE`` (new input names), seed 20270803 (unused). Only the cold control is run.
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
from nomad import cert_tasks as LT  # noqa: E402

SEED = 20270803
OUT = ROOT / "data" / "deep" / "cert_suite.json"
HASH = ROOT / "data" / "deep" / "cert_suite.sha256"
suite_hash = TS.suite_hash


def generate(seed: int = SEED, log=None, priors=None) -> dict:
    old = TS.T
    TS.T = LT
    try:
        suite = TS.generate(seed, log=log, priors=priors)
    finally:
        TS.T = old
    suite["schema"] = "nomad.cert-suite.v1"
    return suite


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("cert suite hash mismatch")
    return suite, [LT.to_task(e) for e in suite["easy"]], [LT.to_task(e) for e in suite["hard"]]


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
        HASH.write_text(f"{h}  data/deep/cert_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
