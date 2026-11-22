"""CLAUSE2 (docs/CLAUSE2.md): one concept per clause, paid only from savings, binding forward too;
switch NOMAD_CLAUSE2 (default off)."""
from __future__ import annotations

import os
import random
import unittest
from types import SimpleNamespace

from nomad import clause2 as Q
from nomad import meaning_tasks as MT
from nomad import world as W
from nomad.world import OPSETS, Invalid, WorldPrior, evaluate, run
from tests.test_clause import TRAIN, _Env, _field, _story

OFF = dict(NOMAD_MEANING="on", NOMAD_CLAUSE2="off", NOMAD_CLAUSE="off", NOMAD_COMBINE="off", NOMAD_ROLES="off",
           NOMAD_CLAUSE2_CONTROL="")
ON = dict(OFF, NOMAD_CLAUSE2="on")

_FIELD = None


def field():
    global _FIELD
    if _FIELD is None:
        _FIELD = _field()
    return _FIELD


def _rand_tree(rng, names, depth):
    if depth == 0 or rng.random() < 0.3:
        return ["var", rng.choice(names)] if rng.random() < 0.7 else ["const", rng.randint(0, 3)]
    op = rng.choice(["add", "sub", "mul", "div", "mod", "max", "min"])
    return [op, _rand_tree(rng, names, depth - 1), _rand_tree(rng, names, depth - 1)]


def _rank_miss_entry():
    """A story worded like the field's concepts (rows of, packed into boxes that hold) whose answer is no
    composition of them: the tiles left over, (a * b) % c. CLAUSE2 spends credit on wrong pairs and misses;
    the normal search finds the program."""
    from nomad.meaning_tasks import COMPOSITES, Concept, V, _gen, _r, op
    COMPOSITES.setdefault("ut_left_area", Concept(
        "ut_left_area", ("a", "b", "c"), op("mod", op("mul", V("a"), V("b")), V("c")),
        lambda a, b, c: (a * b) % c, _gen(a=_r(2, 12), b=_r(2, 12), c=_r(3, 9))))
    fam = MT._f("ut_hall_left", "ut_left_area", "museum",
                "A museum floor is laid in {a} rows with {b} tiles in each row. The tiles are packed into boxes "
                "that hold {c} each. The museum is {x} years old. How many tiles do not fill a box?", ("x",))
    return MT.story_entry(fam, "ut-m0", 5, ("ua", "ub", "uc", "ud", "ue"), shuffle=True)


class Clause2Tests(unittest.TestCase):
    def test_default_on(self):
        os.environ.pop("NOMAD_CLAUSE2", None)
        self.assertTrue(Q.enabled())
        with _Env(NOMAD_CLAUSE2="off"):
            self.assertFalse(Q.enabled())

    def test_forward_pool_borrows_from_the_next_clause_first(self):
        items = [{"inputs": ["p", "q"]}, {"inputs": []}, {"inputs": ["r", "s", "t"]}]
        self.assertEqual(Q.pool(items, 1, 3), ["p", "q", "r", "s", "t"])  # back first (CLAUSE), whole clauses
        self.assertEqual(Q.pool(items, 1, 3, forward=True), ["r", "s", "t"])
        self.assertEqual(Q.pool(items, 2, 2, forward=True), ["r", "s", "t"])  # own inputs suffice

    def test_plan_binds_an_average_clause_forward(self):
        # stub field: "average" names a 3-input mean; "back" names a doubling
        concepts = {"avg": {"types": {"_v0": "int", "_v1": "int", "_v2": "int"}, "out": "int", "uses": 1,
                            "tree": ["div", ["add", ["add", ["var", "_v0"], ["var", "_v1"]], ["var", "_v2"]], ["const", 3]]},
                    "dbl": {"types": {"_v0": "int", "_v1": "int"}, "out": "int", "uses": 1,
                            "tree": ["mul", ["mul", ["var", "_v0"], ["var", "_v1"]], ["const", 2]]}}
        prior = SimpleNamespace(lexicon={"average": {"avg": 1.0}, "back": {"dbl": 1.0}}, concepts=concepts)
        words = "A cart holds 4 and 5 kilos. What is the average of the three loads? They are 12, 15 and 9. It goes there and back 3 times."
        row = {"x1": 4, "x2": 5, "y1": 12, "y2": 15, "y3": 9, "z": 3}
        task = SimpleNamespace(public=[(row, 0)], inputs=[(k, "int") for k in row], out="int")
        pl = Q.plan(task, prior, words)
        avg_clause = next(c for c in pl["clauses"] if "average" in c["text"])
        self.assertEqual(avg_clause["inputs"], [])
        self.assertIn(("avg", ("y1", "y2", "y3")), avg_clause["inner"])            # forward
        first = [x for x in avg_clause["inner"] if x[0] == "avg"][0]
        self.assertEqual(first, ("avg", ("y1", "y2", "y3")))                         # ranked first (gap 0 forward)

    def test_record_and_memo_are_exactly_run(self):
        rng = random.Random(7)
        names = ["a", "b", "c"]
        rows = [{"a": rng.randint(-5, 9), "b": rng.randint(-5, 9), "c": rng.randint(0, 9)} for _ in range(4)]
        task = SimpleNamespace(public=[(r, 0) for r in rows], inputs=[(n, "int") for n in names], out="int")
        L = Q.Ledger(task, SimpleNamespace(lexicon={}, concepts={}), "1")
        for _ in range(400):
            t = _rand_tree(rng, names, 4)
            try:
                want = [run(t, r) for r in rows]
            except Invalid:
                want = None
            try:
                got = L.record(t)
            except Invalid:
                got = None
            self.assertEqual(got, want, t)
        # main's hook reads exactly what was recorded, and each read is one credit
        before = L.credit
        va, vb = tuple(r["a"] for r in rows), tuple(r["b"] for r in rows)
        L.record(["add", ["var", "a"], ["var", "b"]])
        v = L.node("add", True, (vb, va), lambda: (_ for _ in ()).throw(AssertionError("recomputed")))
        self.assertEqual(v, tuple(x + y for x, y in zip(va, vb)))
        self.assertEqual(L.credit, before + 1)

    def test_a_miss_is_identical_to_off(self):
        p = field()
        e = _rank_miss_entry()
        t = MT.to_task(e)
        with _Env(**OFF):
            a, ra = evaluate(t, prior=p, max_eval=20000, words=e["story"])
        self.assertTrue(a.certified)                  # the normal search solves it (where CLAUSE lost evaluations)
        Q.LAST = None
        with _Env(**ON):
            b, rb = evaluate(t, prior=p, max_eval=20000, words=e["story"])
        L = Q.LAST
        self.assertIsNotNone(L)                       # the ledger ran
        self.assertFalse((b.via or "").startswith("clause2:"))
        self.assertEqual((a.certified, a.evaluations, a.candidate, a.via, a.reason),
                         (b.certified, b.evaluations, b.candidate, b.via, b.reason))
        self.assertEqual(ra.receipt_hash if ra else None, rb.receipt_hash if rb else None)
        self.assertGreater(L.spent, 0)                # CLAUSE2 really searched (and missed)
        self.assertLessEqual(L.spent, L.banked)       # never spends more than main's savings
        self.assertGreaterEqual(L.credit, 0)

    def test_main_search_is_unchanged_under_the_ledger(self):
        # the ledger's hooks alone (CLAUSE2's own search disabled) leave every search identical
        p = field()
        for e in TRAIN[:4] + [_rank_miss_entry(), _story()]:
            t = W.search_view(MT.to_task(e))
            s0 = W.synthesize(t, prior=p, max_eval=4000)
            L = Q.Ledger(t, p, e["story"])
            L.done = True
            tok = W._C2.set(L)
            try:
                s1 = W.synthesize(t, prior=p, max_eval=4000)
            finally:
                W._C2.reset(tok)
            self.assertEqual((s0.tree, s0.evaluations, s0.reason, s0.via), (s1.tree, s1.evaluations, s1.reason, s1.via))

    def test_hit_is_certified_and_never_costs_more_than_off(self):
        p, e = field(), _story()
        t = MT.to_task(e)
        with _Env(**OFF):
            a, _ = evaluate(t, prior=p, max_eval=20000, words=e["story"])
        with _Env(**ON):
            b, r = evaluate(t, prior=p, max_eval=20000, words=e["story"])
        self.assertTrue(b.certified)
        self.assertTrue(r.supported)
        if a.certified:
            self.assertLessEqual(b.evaluations, a.evaluations)

    def test_empty_field_and_words_without_numbers_never_run(self):
        p, e = field(), _story()
        t = MT.to_task(e)
        for prior, words in ((WorldPrior(), e["story"]), (p, e["words"])):
            with _Env(**OFF):
                a, _ = evaluate(t, prior=prior, max_eval=1500, words=words)
            Q.LAST = None
            with _Env(**ON):
                b, _ = evaluate(t, prior=prior, max_eval=1500, words=words)
            self.assertIsNone(Q.LAST)
            self.assertEqual((a.certified, a.evaluations, a.via), (b.certified, b.evaluations, b.via))

    def test_search_never_holds_final_rows(self):
        p, e = field(), _story()
        t = MT.to_task(e)
        Q.LAST = None
        with _Env(**ON):
            evaluate(t, prior=p, max_eval=3000, words=e["story"])
        self.assertEqual(tuple(Q.LAST.task.final), ())

    def test_rewire_control_changes_only_the_binding(self):
        p, e = field(), _story()
        t = MT.to_task(e)
        base = Q.plan(t, p, e["story"])
        with _Env(NOMAD_CLAUSE2_CONTROL="rewire"):
            rew = Q.plan(t, p, e["story"])
        self.assertEqual([c["text"] for c in base["clauses"]], [c["text"] for c in rew["clauses"]])
        self.assertNotEqual([c["inputs"] for c in base["clauses"]], [c["inputs"] for c in rew["clauses"]])


if __name__ == "__main__":
    unittest.main()
