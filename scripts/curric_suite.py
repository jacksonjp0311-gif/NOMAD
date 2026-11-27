"""Generate (once, seeded) the frozen CURRIC suite; see docs/CURRIC.md.

    PYTHONHASHSEED=0 python3 scripts/curric_suite.py              # write data/deep/curric_suite.json + .sha256
    python3 scripts/curric_suite.py --check                       # verify the committed file + hash

Same procedure as scripts/memidx_suite.py, on the same never-measured catalogue (scripts/memidx_catalogue.py:
sport / weather / pitch / stock; MEMIDX never measured a field arm on it) with a NEW seed (SEED below;
MEMIDX's 20270917 is not reused). 11 rows per family (5 public, 3 challenge, 3 final, drawn with
random.Random(f"{seed}:{family}")); cold control at 10,000 evaluations, max_size 7 -> easy / candidate hard.
Lookup guard: a candidate is dropped when any whole program or library block of the trained field, or any
tree in the concept memory of the CURRIC field (``curric_log``), renamed onto the task's inputs, certifies it
outright, so no hard task is a concept looked up as-is. Only the cold control and memory lookup touch the suite.
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

SEED = 20271127
OUT = ROOT / "data" / "deep" / "curric_suite.json"
HASH = ROOT / "data" / "deep" / "curric_suite.sha256"
suite_hash = TS.suite_hash


def guard_prior(prior):
    """The concept memory as a lookup-guard field: every logged tree as a two-int program."""
    from nomad.world import WorldPrior, _var_names
    g = WorldPrior()
    for i, (_fam, t) in enumerate(getattr(prior, "curric_log", None) or []):
        g.programs[f"C{i:04d}"] = t
        g.programs_sig[f"C{i:04d}"] = [[v, "int"] for v in _var_names(t, [])]
    return g


def generate(seed: int = SEED, log=None, fields=None) -> dict:
    import curric_judge as CJ
    import novel_judge as NJ
    f = CJ.fields() if fields is None else fields
    priors = [f["trained_off"][0], f["trained_on"][0], guard_prior(f["trained_on"][0])]
    old = TS.T
    TS.T = MC
    try:
        with NJ.env(**CJ.OFF):   # the cold control runs under the CURRENT switch settings
            suite = TS.generate(seed, log=log, priors=priors)
    finally:
        TS.T = old
    suite["schema"] = "nomad.curric-suite.v1"
    return suite


def load(path: Path = OUT, check: bool = True) -> tuple[dict, list, list]:
    suite = json.loads(path.read_text())
    if check and suite_hash(suite) != HASH.read_text().split()[0]:
        raise ValueError("curric suite hash mismatch")
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
        HASH.write_text(f"{h}  data/deep/curric_suite.json\n")
    print(json.dumps({"sha256": h, "stats": suite["stats"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
