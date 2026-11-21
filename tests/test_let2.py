"""LET2 (docs/LET2.md): LET's let-bindings as a fallback paid only from MERGE's saved evaluations.
Off by default; an empty field is untouched; on a trained toy field every task the switch-off
search certifies is certified with the same evaluation count (LET2 runs only after main's int
stages missed, and on a miss its WITNESS rejections are forgotten)."""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from nomad import let2_tasks as LT  # noqa: E402
from nomad import world as W  # noqa: E402


def _run(task, prior, flag, **kw):
    old = os.environ.get("NOMAD_LET2")
    os.environ["NOMAD_LET2"] = flag
    try:
        ev = W.evaluate(task, prior=prior, max_eval=kw.pop("max_eval", 3000), max_size=7, casesplit=True, **kw)[0]
    finally:
        os.environ.pop("NOMAD_LET2", None)
        if old is not None:
            os.environ["NOMAD_LET2"] = old
    return ev.certified, ev.evaluations, ev.candidate


class Let2Tests(unittest.TestCase):
    def test_default_off_and_on_switch(self) -> None:
        old = os.environ.pop("NOMAD_LET2", None)
        try:
            self.assertFalse(W.let2_enabled())
            os.environ["NOMAD_LET2"] = "on"
            self.assertTrue(W.let2_enabled())
        finally:
            os.environ.pop("NOMAD_LET2", None)
            if old is not None:
                os.environ["NOMAD_LET2"] = old

    def test_catalogue_truth_matches_tree(self) -> None:
        for f in LT.CATALOGUE:
            rows = LT.draw_rows(f, random.Random(f"test:{f.family}"))
            self.assertEqual(len(rows), 11, f.family)
            for r, a in rows:
                self.assertEqual(W.run(f.tree, r), a, f.family)

    def test_sealed_suite_hash(self) -> None:
        import let2_suite as XS
        suite, easy, hard = XS.load(XS.OUT, check=True)
        self.assertEqual((len(easy), len(hard)), (2, 22))
        self.assertEqual(suite["seed"], 20270331)

    def test_empty_field_unchanged(self) -> None:
        f = LT.CATALOGUE[0]
        rows = LT.draw_rows(f, random.Random("t:empty"))
        task = LT.to_task({"task_id": "x", "family": f.family, "inputs": list(f.inputs), "rows": [[r, a] for r, a in rows]})
        self.assertEqual(_run(task, W.WorldPrior(), "off"), _run(task, W.WorldPrior(), "on"))

    def test_trained_toy_never_loses(self) -> None:
        import test_merge as TM
        for seed, fn in ((5, lambda a, b: a * b + 2 * a), (7, lambda a, b: (a + b) * (a + b) - a),
                         (9, lambda a, b: max(a, 3) * b)):
            task = TM._task(seed, fn)
            off, on = _run(task, TM._prior(), "off"), _run(task, TM._prior(), "on")
            if off[0]:
                self.assertEqual(off, on)
            self.assertGreaterEqual(on[0], off[0])


if __name__ == "__main__":
    unittest.main()
