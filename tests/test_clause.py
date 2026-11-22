"""CLAUSE (docs/CLAUSE.md): one concept per clause, composed; switch NOMAD_CLAUSE (default off)."""
from __future__ import annotations

import os
import random
import unittest

from nomad import clause as Q
from nomad import clause_tasks as QT
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


TRAIN = [e for e in MT.train_story_entries() if e["concept"] in ("boxes_needed", "product")]


def _field():
    p = WorldPrior()
    with _Env(NOMAD_MEANING="on"):
        for _ in range(2):
            for e in TRAIN:
                t = MT.to_task(e)
                ev, r = evaluate(t, prior=p, max_eval=20000)
                if ev.certified:
                    p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                                    words=e["story"], out=t.out)
    return p


def _story():
    fam = MT._f("ut_hall_boxes", "kd_boxes_area", "museum",
                "A museum floor is laid in {a} rows with {b} tiles in each row. The tiles are packed into boxes that "
                "hold {c} each. The museum is {x} years old. How many boxes are needed to hold all the tiles?", ("x",))
    from nomad.meaning_tasks import COMPOSITES, Concept, K, V, _gen, _r, op
    COMPOSITES.setdefault("kd_boxes_area", Concept(
        "kd_boxes_area", ("a", "b", "c"), op("div", op("add", op("mul", V("a"), V("b")), op("sub", V("c"), K(1))), V("c")),
        lambda a, b, c: (a * b + c - 1) // c, _gen(a=_r(2, 12), b=_r(2, 12), c=_r(2, 9))))
    return MT.story_entry(fam, "ut-q0", 3, ("ua", "ub", "uc", "ud", "ue"), shuffle=True)


class ClauseTests(unittest.TestCase):
    def test_default_off(self):
        os.environ.pop("NOMAD_CLAUSE", None)
        self.assertFalse(Q.enabled())
        with _Env(NOMAD_CLAUSE="on"):
            self.assertTrue(Q.enabled())

    def test_split(self):
        self.assertEqual(Q.split("A has 3 rows. B holds 5 each, and the C is 9 old; How many?"),
                         ["A has 3 rows", "B holds 5 each", "and the C is 9 old", "How many"])
        self.assertEqual(Q.split("Three cows give 4, 8 and 28 liters. Next."), ["Three cows give 4, 8 and 28 liters", "Next"])
        self.assertEqual(Q.split("pays 2.5 dollars"), ["pays 2.5 dollars"])
        self.assertEqual(Q.numbers("walks 30, 7 and 5 steps in 3 days"), [30, 7, 5, 3])

    def test_clause_inputs_ambiguity_binds_all(self):
        self.assertEqual(Q.clause_inputs("5 rows of 6", {"p": 5, "q": 6, "r": 6, "s": 9}), ["p", "q", "r"])

    def test_sealed_composites_are_not_meaning_or_combine_concepts_and_have_truths(self):
        from nomad import combine_tasks as CT
        combine = {f.concept for f in CT.SEALED}
        for f in QT.SEALED:
            self.assertNotIn(f.concept, MT.CONCEPTS)
            self.assertNotIn(f.concept, combine)
        for name, c in MT.COMPOSITES.items():
            if not name.startswith("cq_"):
                continue
            rng = random.Random(name)
            for _ in range(20):
                v = c.gen(rng)
                try:
                    got = run(c.tree, v)
                except Exception:
                    continue
                self.assertEqual(got, c.truth(*(v[k] for k in c.roles)))
        self.assertEqual(len({f.family for f in QT.SEALED}), len(QT.SEALED))
        self.assertEqual(len(QT.SEALED), 16)

    def test_stage_composes_clause_concepts_and_is_witness_gated(self):
        p = _field()
        e = _story()
        t = MT.to_task(e)
        self.assertTrue(p.lexicon)
        with _Env(NOMAD_MEANING="on", NOMAD_CLAUSE="on", NOMAD_COMBINE="off", NOMAD_ROLES="off"):
            ev, r = evaluate(t, prior=p, max_eval=20000, words=e["story"])
        self.assertTrue(ev.certified)
        self.assertIsNotNone(r)
        self.assertTrue(r.supported)
        if ev.via and ev.via.startswith("clause:"):
            self.assertLess(ev.evaluations, 600)

    def test_off_is_exactly_the_old_search_and_empty_field_never_runs(self):
        p, e = _field(), _story()
        t = MT.to_task(e)
        with _Env(NOMAD_MEANING="on", NOMAD_CLAUSE="off", NOMAD_COMBINE="off", NOMAD_ROLES="off"):
            a, _ = evaluate(t, prior=p, max_eval=3000, words=e["story"])
        with _Env(NOMAD_MEANING="on", NOMAD_CLAUSE="off", NOMAD_COMBINE="off", NOMAD_ROLES="off"):
            b, _ = evaluate(t, prior=p, max_eval=3000, words=e["story"])
        self.assertEqual((a.certified, a.evaluations, a.via), (b.certified, b.evaluations, b.via))
        with _Env(NOMAD_MEANING="on", NOMAD_CLAUSE="off"):
            c0, _ = evaluate(t, prior=WorldPrior(), max_eval=1500, words=e["story"])
        with _Env(NOMAD_MEANING="on", NOMAD_CLAUSE="on"):
            c1, _ = evaluate(t, prior=WorldPrior(), max_eval=1500, words=e["story"])
        self.assertEqual((c0.certified, c0.evaluations, c0.via), (c1.certified, c1.evaluations, c1.via))

    def test_words_without_numbers_cost_nothing(self):
        p, e = _field(), _story()
        t = MT.to_task(e)
        hit, n, info = Q.stage(t, p, e["words"])   # the description with {placeholders}: no numbers
        self.assertEqual((hit, n), (None, 0))

    def test_rewire_control_changes_only_the_binding(self):
        p, e = _field(), _story()
        t = MT.to_task(e)
        base = Q.plan(t, p, e["story"])
        with _Env(NOMAD_CLAUSE_CONTROL="rewire"):
            rew = Q.plan(t, p, e["story"])
        self.assertEqual([c["text"] for c in base["clauses"]], [c["text"] for c in rew["clauses"]])
        self.assertNotEqual([c["inputs"] for c in base["clauses"]], [c["inputs"] for c in rew["clauses"]])

    def test_budget_is_respected(self):
        p, e = _field(), _story()
        t = MT.to_task(e)
        _h, n, _i = Q.stage(t, p, e["story"], max_eval=7)
        self.assertLessEqual(n, 7)


if __name__ == "__main__":
    unittest.main()
