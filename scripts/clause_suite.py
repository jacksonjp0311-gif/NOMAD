"""Generate (once, seeded) the sealed CLAUSE suite; see docs/CLAUSE.md.

    python3 scripts/clause_suite.py              # write data/deep/clause_suite.json + .sha256 (clause_tasks.SEALED)
    python3 scripts/clause_suite.py --check
    python3 scripts/clause_suite.py --catalogue PATH.py:NAME --names a,b,c --seed 7 --out /tmp/c.json   # a dev suite

Same procedure as scripts/combine_suite.py (story entries, cold control at 10,000 / max_size 7 recorded
per task; cold-certified tasks go to ``easy``, reported and never scored). No field arm is run here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import combine_suite as CS  # noqa: E402
import roles_suite as RS  # noqa: E402
from nomad import meaning_tasks as MT  # noqa: E402

SEED = 20270415
OUT = ROOT / "data" / "deep" / "clause_suite.json"
HASH = ROOT / "data" / "deep" / "clause_suite.sha256"
suite_hash = RS.suite_hash


def generate(catalogue, names, seed: int = SEED, prefix: str = "q", log=None) -> dict:
    s = CS.generate(catalogue, names, seed, prefix=prefix, log=log)
    s["schema"] = "nomad.clause-suite.v1"
    return s


def load(path: Path = OUT, check: bool = True):
    suite = json.loads(Path(path).read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("clause suite hash mismatch")
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
        suite = generate(RS._catalogue(a.catalogue), a.names.split(","), a.seed, prefix="qd", log=log)
        out = a.out or Path("/tmp/clause_dev_suite.json")
        out.write_text(json.dumps(suite, indent=1) + "\n")
    else:
        from nomad import clause_tasks as QT
        suite = generate(QT.SEALED, QT.SEALED_NAMES, a.seed, log=log)
        OUT.write_text(json.dumps(suite, indent=1) + "\n")
        HASH.write_text(f"{suite_hash(suite)}  {OUT.name}\n")
        out = OUT
    print(json.dumps({"out": str(out), "sha256": suite_hash(suite), "easy": len(suite["easy"]), "hard": len(suite["hard"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
