"""Generate (once, seeded) the sealed ROLES word-problem suite; see docs/ROLES.md.

    python3 scripts/roles_suite.py              # write data/deep/roles_suite.json + .sha256 (roles_tasks.SEALED)
    python3 scripts/roles_suite.py --check      # verify the committed file + hash
    python3 scripts/roles_suite.py --catalogue PATH.py:NAME --names a,b,c --seed 7 --out /tmp/r.json   # a dev suite

Per family a story entry (``nomad.meaning_tasks.story_entry``: input names from the name pool,
shuffled, input order shuffled, 11 exact rows from ``random.Random(f"{seed}:{family}")``, the
description written out with the numbers of the first public row). The cold control at 10,000
evaluations, max_size 7, is recorded per task (``cold_certified``); every task is scored (the claim
is about the MEANING stage's renaming trials, easy or hard). No field arm is run here.
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

SEED = 20270209
BUDGET = 10000
MAX_SIZE = 7
OUT = ROOT / "data" / "deep" / "roles_suite.json"
HASH = ROOT / "data" / "deep" / "roles_suite.sha256"
suite_hash = TS.suite_hash


def generate(catalogue, names, seed: int = SEED, prefix: str = "r", log=None) -> dict:
    tasks = []
    for i, f in enumerate(catalogue):
        e = MT.story_entry(f, f"{prefix}-{i:02d}", seed, names, shuffle=True)
        c, _ = evaluate(MT.to_task(e), prior=None, max_eval=BUDGET, max_size=MAX_SIZE)
        e.update(cold_certified=c.certified, cold_evaluations=c.evaluations)
        tasks.append(e)
        if log:
            log(f"{f.family} {f.concept} cold={c.certified} {c.evaluations} | {e['story']}")
    return {"schema": "nomad.roles-suite.v1", "seed": seed, "budget": BUDGET, "max_size": MAX_SIZE,
            "names": list(names), "tasks": tasks}


def load(path: Path = OUT, check: bool = True):
    suite = json.loads(Path(path).read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("roles suite hash mismatch")
    return suite, [MT.to_task(e) for e in suite["tasks"]]


def _catalogue(spec: str):
    path, name = spec.rsplit(":", 1)
    sp = importlib.util.spec_from_file_location("roles_catalogue", path)
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
        suite, _t = load(OUT, check=True)
        print(json.dumps({"ok": True, "sha256": suite_hash(suite), "tasks": len(suite["tasks"])}))
        return 0
    log = lambda m: print(m, file=sys.stderr, flush=True)  # noqa: E731
    if a.catalogue:
        suite = generate(_catalogue(a.catalogue), a.names.split(","), a.seed, prefix="rd", log=log)
        out = a.out or Path("/tmp/roles_dev_suite.json")
        out.write_text(json.dumps(suite, indent=1) + "\n")
    else:
        from nomad import roles_tasks as RT
        suite = generate(RT.SEALED, RT.SEALED_NAMES, a.seed, log=log)
        OUT.write_text(json.dumps(suite, indent=1) + "\n")
        HASH.write_text(f"{suite_hash(suite)}  {OUT.name}\n")
        out = OUT
    print(json.dumps({"out": str(out), "sha256": suite_hash(suite), "tasks": len(suite["tasks"]),
                      "cold_certified": sum(e["cold_certified"] for e in suite["tasks"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
