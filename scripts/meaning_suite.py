"""Generate (once, seeded) the sealed MEANING word-problem suite; see docs/MEANING.md.

    python3 scripts/meaning_suite.py              # write data/deep/meaning_suite.json + .sha256 (SEALED catalogue)
    python3 scripts/meaning_suite.py --check      # verify the committed file + hash
    python3 scripts/meaning_suite.py --catalogue PATH.py:NAME --names a,b,c --seed 7 --out /tmp/m.json   # a dev suite

Procedure: per family an entry (``nomad.meaning_tasks.entry``: input names from the
catalogue's name pool, shuffled, input order shuffled, 11 exact rows drawn with
``random.Random(f"{seed}:{family}")``); the cold control at 10,000 evaluations,
max_size 7: certified -> ``easy`` (recorded, never scored), else ``hard`` (sealed).
No field arm is run here.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import transfer_suite as TS  # noqa: E402
from nomad import meaning_tasks as MT  # noqa: E402
from nomad.world import evaluate  # noqa: E402

SEED = 20261211
BUDGET = 10000
MAX_SIZE = 7
OUT = ROOT / "data" / "deep" / "meaning_suite.json"
HASH = ROOT / "data" / "deep" / "meaning_suite.sha256"
suite_hash = TS.suite_hash


def generate(catalogue, names, seed: int = SEED, prefix: str = "m", log=None) -> dict:
    easy, hard = [], []
    for i, f in enumerate(catalogue):
        e = MT.entry(f, f"{prefix}-{i:02d}", seed, names, shuffle=True)
        c, _ = evaluate(MT.to_task(e), prior=None, max_eval=BUDGET, max_size=MAX_SIZE)
        e.update(cold_certified=c.certified, cold_evaluations=c.evaluations)
        (easy if c.certified else hard).append(e)
        if log:
            log(f"{f.family} {f.concept} cold={c.certified} {c.evaluations}")
    return {"schema": "nomad.meaning-suite.v1", "seed": seed, "budget": BUDGET, "max_size": MAX_SIZE,
            "names": list(names), "easy": easy, "hard": hard}


def load(path: Path = OUT, check: bool = True):
    suite = json.loads(Path(path).read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("meaning suite hash mismatch")
    return suite, [MT.to_task(e) for e in suite["easy"]], [MT.to_task(e) for e in suite["hard"]]


def _catalogue(spec: str):
    path, name = spec.rsplit(":", 1)
    sp = importlib.util.spec_from_file_location("meaning_catalogue", path)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return getattr(mod, name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--catalogue", default=None)
    ap.add_argument("--names", default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        suite, _e, _h = load(OUT, check=True)
        print(json.dumps({"ok": True, "sha256": suite_hash(suite), "hard": len(suite["hard"])}))
        return 0
    log = lambda m: print(m, file=sys.stderr, flush=True)  # noqa: E731
    if a.catalogue:
        suite = generate(_catalogue(a.catalogue), a.names.split(","), a.seed, prefix="md", log=log)
        out = a.out or Path("/tmp/meaning_dev_suite.json")
        out.write_text(json.dumps(suite, indent=1) + "\n")
    else:
        suite = generate(MT.SEALED, MT.SEALED_NAMES, a.seed, log=log)
        OUT.write_text(json.dumps(suite, indent=1) + "\n")
        HASH.write_text(f"{suite_hash(suite)}  {OUT.name}\n")
        out = OUT
    print(json.dumps({"out": str(out), "sha256": suite_hash(suite), "easy": len(suite["easy"]),
                      "hard": len(suite["hard"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
