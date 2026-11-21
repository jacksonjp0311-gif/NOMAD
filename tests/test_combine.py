"""COMBINE (docs/COMBINE.md): two retrieved concepts composed; switch NOMAD_COMBINE (default off)."""
from __future__ import annotations

import os
import random
import unittest

from nomad import combine as C
from nomad import combine_tasks as CT
from nomad import meaning_tasks as MT
from nomad.world import OPSETS, WorldPrior, evaluate, run


class _Env:
    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in self.kv}
        os.environ.update(self.kv)

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


TRAIN = [e for e in MT.train_story_entries() if e["concept"] in ("triple_sum", "round_trip", "product")]


def _field():
    p = WorldPrior()
    with _Env(NOMAD_MEANING="on"):
        for e in TRAIN:
            t = MT.to_task(e)
            ev, r = evaluate(t, prior=p, max_eval=20000)
            if ev.certified:
                p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                                words=e["story"], out=t.out)
    return p


def _story():
    fam = MT._f("ut_hall_legs", "cb_trip_legs", "museum",
                "The guide walks {a} steps to the hall, {b} steps to the gallery and {c} steps to the shop, "
                "and goes there and back {d} times with {x} visitors. How many steps in total?", ("x",))
    return MT.story_entry(fam, "ut-c0", 3, ("ua", "ub", "uc", "ud", "ue"), shuffle=True)


class CombineTests(unittest.TestCase):
    def test_default_off(self):
        os.environ.pop("NOMAD_COMBINE", None)
        self.assertFalse(C.enabled())
        with _Env(NOMAD_COMBINE="on"):
            self.assertTrue(C.enabled())

    def test_composites_are_not_meaning_concepts_and_have_truths(self):
        for name, c in MT.COMPOSITES.items():
            self.assertNotIn(name, MT.CONCEPTS)
            rng = random.Random(name)
            for _ in range(20):
                v = c.gen(rng)
                try:
                    got = run(c.tree, v)
                except Exception:
                    continue
                self.assertEqual(got, c.truth(*(v[k] for k in c.roles)))
        self.assertEqual(len({f.family for f in CT.SEALED}), len(CT.SEALED))

    def test_invert_is_exact(self):
        rng = random.Random(7)
        trees = [["add", ["var", "s"], ["var", "y"]], ["sub", ["var", "y"], ["var", "s"]],
                 ["mul", ["var", "s"], ["var", "y"]], ["div", ["var", "s"], ["var", "y"]],
                 ["sub", ["const", 0], ["div", ["var", "s"], ["sub", ["const", 0], ["var", "y"]]]],
                 ["mul", ["const", 2], ["mul", ["var", "s"], ["var", "y"]]]]
        for tree in trees:
            for _ in range(200):
                y, s = rng.randint(-9, 9), rng.randint(-60, 60)
                row = {"y": y, "s": s}
                try:
                    goal = run(tree, row)
                except Exception:
                    continue
                try:
                    bd = C._invert(tree, "s", goal, goal, {"y": y})
                except C._Empty:
                    self.fail(f"{tree} {row}: true value excluded")
                if bd is not None:
                    self.assertTrue(bd[0] <= s <= bd[1], (tree, row, bd))

    def test_composes_two_retrieved_concepts_and_off_is_unchanged(self):
        p = _field()
        e = _story()
        t = MT.to_task(e)
        with _Env(NOMAD_MEANING="on", NOMAD_COMBINE="off"):
            off = evaluate(t, prior=p, max_eval=3000, words=e["story"])[0]
        with _Env(NOMAD_MEANING="on", NOMAD_COMBINE="on"):
            on = evaluate(t, prior=p, max_eval=3000, words=e["story"])[0]
            hit, n, _info = C.stage(t, p, e["story"])
        self.assertIsNotNone(hit)
        self.assertTrue(on.certified)
        self.assertTrue(on.via.startswith("combine:"))
        self.assertLessEqual(n, C.COMBINE_BUDGET)
        self.assertFalse(off.via and off.via.startswith("combine:"))

    def test_empty_field_and_no_words_unchanged(self):
        e = _story()
        t = MT.to_task(e)
        res = []
        for v in ("off", "on"):
            with _Env(NOMAD_MEANING="on", NOMAD_COMBINE=v):
                a = evaluate(t, prior=WorldPrior(), max_eval=2000, words=e["story"])[0]
                b = evaluate(t, prior=_field(), max_eval=2000)[0]
                res.append((a.certified, a.evaluations, b.certified, b.evaluations, b.candidate))
        self.assertEqual(res[0], res[1])


if __name__ == "__main__":
    unittest.main()
