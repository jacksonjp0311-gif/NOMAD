"""DISCRIM (docs/DISCRIM.md): active distinguishing experiments guarding LET2's fallback let fits.
Off by default; the distinguishing inputs are deterministic and never read the final split; an empty
field is untouched; on a trained toy field every task the switch-off search certifies is certified
with the same evaluation count."""
from __future__ import annotations

import os
import random
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from nomad import discrim as D  # noqa: E402
from nomad import discrim_tasks as DT  # noqa: E402
from nomad import world as W  # noqa: E402

KEYS = ("NOMAD_DISCRIM", "NOMAD_LET2", "NOMAD_DISCRIM_ROWS", "NOMAD_DISCRIM_PICK")


def _run(task, prior, flag, **kw):
    old = {k: os.environ.pop(k, None) for k in KEYS}
    os.environ["NOMAD_DISCRIM"] = flag
    try:
        ev = W.evaluate(task, prior=prior, max_eval=kw.pop("max_eval", 3000), max_size=7, casesplit=True, **kw)[0]
    finally:
        for k, v in old.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    return ev.certified, ev.evaluations, ev.candidate


def _task(rows, inputs=("a", "b")):
    rs = [(dict(zip(inputs, r[:-1])), r[-1]) for r in rows]
    return W.make_task("t", "f", "int", {n: "int" for n in inputs}, "int", rs[:5], rs[5:8], rs[8:])


class DiscrimTests(unittest.TestCase):
    def test_default_off_and_on_switch(self) -> None:
        old = os.environ.pop("NOMAD_DISCRIM", None)
        try:
            self.assertFalse(D.enabled())
            self.assertFalse(W._discrim_on())
            os.environ["NOMAD_DISCRIM"] = "on"
            self.assertTrue(D.enabled())
            self.assertTrue(W._discrim_on())
        finally:
            os.environ.pop("NOMAD_DISCRIM", None)
            if old is not None:
                os.environ["NOMAD_DISCRIM"] = old

    def test_catalogue_truth_matches_tree(self) -> None:
        for f in DT.CATALOGUE:
            rows = DT.draw_rows(f, random.Random(f"test:{f.family}"))
            self.assertEqual(len(rows), 11, f.family)
            for r, a in rows:
                self.assertEqual(W.run(f.tree, r), a, f.family)

    def test_sealed_suite_hash(self) -> None:
        import discrim_suite as XS
        suite, easy, hard = XS.load(XS.OUT, check=True)
        self.assertEqual((len(easy), len(hard)), (2, 22))
        self.assertEqual(suite["seed"], 20270419)

    def test_rows_deterministic_and_never_read_final(self) -> None:
        # a > b on every evidence row (the kite trap); final rows poisoned
        rows = [(20, 3, 30), (22, 5, 55), (18, 2, 18), (25, 4, 50), (30, 7, 105), (21, 6, 63), (24, 1, 12), (19, 8, 76),
                (2, 9, 9), (3, 9, 13), (4, 9, 18)]
        t = _task(rows)
        ev = D.evidence(t)
        self.assertEqual(len(ev), 8)
        a = D.rows(t.inputs, ev)
        self.assertEqual(a, D.rows(t.inputs, ev))
        poisoned = replace(t, final=tuple((dict(r, a=-999), -1) for r, _e in t.final))
        self.assertEqual(D.evidence(poisoned), ev)
        hit = ["div", ["mul", ["max", ["var", "a"], ["var", "b"]], ["var", "b"]], ["const", 2]]
        alts = D.simplifications(hit, t.inputs, ev)
        self.assertIn(["div", ["mul", ["var", "a"], ["var", "b"]], ["const", 2]], alts)
        d1 = D.decide(hit, alts, t.inputs, ev)
        d2 = D.decide(hit, alts, poisoned.inputs, D.evidence(poisoned))
        self.assertEqual(d1, d2)
        self.assertEqual(d1["verdict"], "ambiguous")
        self.assertEqual(d1["pick"], ["div", ["mul", ["var", "a"], ["var", "b"]], ["const", 2]])
        old = os.environ.get("NOMAD_DISCRIM_ROWS")
        os.environ["NOMAD_DISCRIM_ROWS"] = "evidence"     # blind control: can never disagree
        try:
            self.assertEqual(D.decide(hit, alts, t.inputs, ev)["verdict"], "confirmed")
        finally:
            os.environ.pop("NOMAD_DISCRIM_ROWS", None)
            if old is not None:
                os.environ["NOMAD_DISCRIM_ROWS"] = old
        # no swap / recombined / spread row equals an evidence row
        evk = {(r["a"], r["b"]) for r, _e in ev}
        self.assertFalse(any((r["a"], r["b"]) in evk for r in a))

    def test_confirmed_when_alternatives_agree(self) -> None:
        rows = [(i, j, i * j + i) for i, j in ((2, 3), (4, 1), (5, 5), (7, 2), (3, 8), (6, 4), (9, 9), (1, 7), (2, 2), (3, 3), (4, 4))]
        t = _task(rows)
        ev = D.evidence(t)
        hit = ["mul", ["var", "a"], ["add", ["var", "b"], ["const", 1]]]
        same = ["add", ["mul", ["var", "a"], ["var", "b"]], ["var", "a"]]
        self.assertEqual(D.decide(hit, [same], t.inputs, ev)["verdict"], "confirmed")

    def test_empty_field_unchanged(self) -> None:
        f = DT.CATALOGUE[0]
        rows = DT.draw_rows(f, random.Random("t:empty"))
        task = DT.to_task({"task_id": "x", "family": f.family, "inputs": list(f.inputs), "rows": [[r, a] for r, a in rows]})
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
