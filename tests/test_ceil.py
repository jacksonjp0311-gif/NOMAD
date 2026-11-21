"""CEIL (docs/CEIL.md): ceiling-division fit by learned / derived constants in the INVENT phase.

Default OFF; switch off == main's path (exact); an empty field gains nothing (no constants); the
rewired control keeps the number of constants and avoids the learned ones; the sealed catalogue's
ground truth matches its reference trees and its input names are new."""
import os
import random
import sys
import unittest
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from nomad import ceil_tasks as CT  # noqa: E402
from nomad import invent as I  # noqa: E402
from nomad.science import Formula, V, draw_rows, to_task  # noqa: E402
from nomad.selfedit_tasks import _add, _ceil_tree, _k  # noqa: E402
from nomad.world import WorldPrior, evaluate, run  # noqa: E402


class _Env:
    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in self.kv}
        for k, v in self.kv.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __exit__(self, *exc):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# a test-only task (not a sealed or dev suite family): ceil((ka + kb) / 6)
_T = Formula("test_ceil_six", "test:packing", "ceil((ka + kb) / 6)", ("ka", "kb"), {"ka": (1, 40), "kb": (1, 12)},
             lambda ka, kb: F(-(-(ka + kb) // 6)), _ceil_tree(_add(V("ka"), V("kb")), _k(6)))
ON = {"NOMAD_PORT": "on", "NOMAD_ANCHOR2": "on", "NOMAD_SCALE": "on"}


def _task():
    rows = draw_rows(_T, random.Random("ceil-test"))
    e = {"task_id": "t-ceil", "family": _T.family, "domain": "test", "kind": "packing", "formula": _T.text,
         "inputs": list(_T.inputs), "tree": _T.tree, "rows": [[r, a] for r, a in rows]}
    return to_task(e)


class Unit(unittest.TestCase):
    def test_default_off(self):
        with _Env(NOMAD_CEIL=None):
            self.assertFalse(I.ceil_enabled())
        with _Env(NOMAD_CEIL="on"):
            self.assertTrue(I.ceil_enabled())

    def test_constants_and_rewired_control(self):
        learned = [(2, ["const", 2]), (3, ["const", 3]), (9, ["mul", ["const", 3], ["const", 3]])]
        consts = [(4, ["mul", ["const", 2], ["const", 2]]), (6, ["mul", ["const", 2], ["const", 3]])]
        ks = I.ceil_constants(learned, consts)
        self.assertEqual([k for k, _ in ks], [2, 3, 4, 6, 9])
        self.assertEqual(I.ceil_constants([], []), [])
        try:
            for seed in (1, 2, 3):
                I.CEIL_REWIRE = seed
                rw = I.ceil_constants(learned, consts)
                self.assertEqual(len(rw), 5)
                self.assertFalse({k for k, _ in rw} & {2, 3, 4, 6, 9})
                for k, t in rw:
                    self.assertEqual(run(t, {}), k)
                self.assertEqual(I.ceil_constants([], []), [])   # an empty field stays empty
        finally:
            I.CEIL_REWIRE = None

    def test_const_tree(self):
        for k in range(2, 40):
            self.assertEqual(run(I._const_tree(k), {}), k)


class Catalogue(unittest.TestCase):
    def test_reference_trees_match_truth(self):
        self.assertEqual(len(CT.CATALOGUE), 24)
        for f in CT.CATALOGUE:
            for r, a in draw_rows(f, random.Random(f"t:{f.family}")):
                self.assertEqual(run(f.tree, r), a, f.family)

    def test_input_names_new(self):
        from nomad import science, selfedit_tasks, transfer, transfer2, transfer3, transfer4
        other = set()
        for m in (science, transfer, transfer2, transfer3, transfer4):
            for f in m.CATALOGUE:
                other |= set(f.inputs)
        for f in selfedit_tasks.DEV_CATALOGUE + selfedit_tasks.CATALOGUE + selfedit_tasks.CATALOGUE2:
            other |= set(f.inputs)
        for m in ("transfer5", "transfer6", "transfer7"):
            for f in __import__(f"nomad.{m}", fromlist=["CATALOGUE"]).CATALOGUE:
                other |= set(f.inputs)
        self.assertFalse({n for f in CT.CATALOGUE for n in f.inputs} & other)

    def test_sealed_suite_hash(self):
        import ceil_suite as CS
        suite, _e, hard = CS.load(CS.OUT, check=True)
        self.assertEqual(len(hard), 23)


class Search(unittest.TestCase):
    def test_empty_field_unchanged(self):
        t = _task()
        with _Env(NOMAD_CEIL="off", **ON):
            a = evaluate(t, prior=WorldPrior(), max_eval=3000, max_size=7, casesplit=True)[0]
        with _Env(NOMAD_CEIL="on", **ON):
            b = evaluate(t, prior=WorldPrior(), max_eval=3000, max_size=7, casesplit=True)[0]
        self.assertEqual((a.certified, a.evaluations, a.candidate), (b.certified, b.evaluations, b.candidate))

    def test_trained_field_fits_a_ceiling(self):
        from nomad import selfedit as S
        import copy
        p, vs = S.reference_field()
        t = _task()
        with _Env(NOMAD_CEIL="off", **ON):
            a = evaluate(t, prior=copy.deepcopy(p), variation=copy.deepcopy(vs), max_eval=10000, max_size=7,
                         casesplit=True)[0]
        with _Env(NOMAD_CEIL="on", **ON):
            b = evaluate(t, prior=copy.deepcopy(p), variation=copy.deepcopy(vs), max_eval=10000, max_size=7,
                         casesplit=True)[0]
        self.assertFalse(a.certified)
        self.assertTrue(b.certified)
        self.assertIn(":ceil", str(b.via))


if __name__ == "__main__":
    unittest.main()
