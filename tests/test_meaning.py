"""MEANING (docs/MEANING.md): words grounded in certified concepts; switch NOMAD_MEANING (default on)."""
from __future__ import annotations

import json
import os
import unittest

from nomad import meaning as M
from nomad import meaning_tasks as MT
from nomad.world import OPSETS, WorldPrior, certify, evaluate, run


def _env(v):
    class E:
        def __enter__(self):
            self.old = os.environ.get("NOMAD_MEANING")
            os.environ["NOMAD_MEANING"] = v

        def __exit__(self, *a):
            if self.old is None:
                os.environ.pop("NOMAD_MEANING", None)
            else:
                os.environ["NOMAD_MEANING"] = self.old
    return E()


def _learn(p, entries):
    for e in entries:
        t = MT.to_task(e)
        ev, r = evaluate(t, prior=p, max_eval=20000)
        if ev.certified:
            p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                            words=e["words"], out=t.out)
    return p


def _held_out():
    fam = MT._f("ut_crowd_seats", "two_areas", "stadium",
                "The east stand has {a} rows of {b} seats and the west stand has {c} rows of {d} seats; "
                "a program costs {x}. How many seats do both stands hold altogether?", ("x",))
    return MT.entry(fam, "ut-0", 5, ("ua", "ub", "uc", "ud", "ue"), shuffle=True)


TRAIN = [e for e in MT.train_entries() if e["concept"] in ("product", "two_areas", "triple_sum")]


class MeaningTests(unittest.TestCase):
    def test_default_on_and_off_switch(self):
        os.environ.pop("NOMAD_MEANING", None)
        self.assertTrue(M.enabled())     # default ON since the sealed PASS (docs/MEANING.md)
        with _env("off"):
            self.assertFalse(M.enabled())

    def test_tokens_drop_placeholders_numbers_and_stop_words(self):
        t = M.tokens("A hall has {a} rows with 12 seats in each row. How many seats in total?")
        self.assertNotIn("a", t)
        self.assertNotIn("12", t)
        self.assertIn("row", t)
        self.assertIn("seat", t)
        self.assertIn("each", t)
        self.assertIn("seat_total", t)

    def test_simplify_is_exact(self):
        tree = ["add", ["mul", ["var", "x"], ["const", 1]], ["const", 0]]
        self.assertEqual(M.simplify(tree), ["var", "x"])
        for x in (-3, 0, 7):
            self.assertEqual(run(tree, {"x": x}), run(M.simplify(tree), {"x": x}))

    def test_catalogue_rows_are_exact(self):
        for e in MT.train_entries():
            c = MT.CONCEPTS[e["concept"]]
            for r, a in e["rows"]:
                self.assertEqual(run(e["tree"], r), a, e["family"])
            self.assertEqual(len(e["rows"]), MT.N_PUBLIC + MT.N_CHALLENGE + MT.N_FINAL)
            self.assertTrue(set(e["inputs"]) >= set(c.roles) or len(e["inputs"]) == len(c.roles))
        self.assertTrue(all("{" in f.text for f in MT.TRAIN))
        names = {f.family for f in MT.TRAIN} & {f.family for f in MT.SEALED}
        self.assertEqual(names, set())

    def test_switch_off_learns_and_reads_nothing(self):
        with _env("off"):
            p = _learn(WorldPrior(), TRAIN)
            self.assertEqual(p.lexicon, {})
            self.assertNotIn("lexicon", p.snapshot())
            e = _held_out()
            t = MT.to_task(e)
            a = evaluate(t, prior=p, words=e["words"])[0]
            b = evaluate(t, prior=p)[0]
            self.assertEqual((a.certified, a.evaluations, a.candidate, a.via),
                             (b.certified, b.evaluations, b.candidate, b.via))

    def test_empty_field_and_cold_control_never_use_words(self):
        e = _held_out()
        t = MT.to_task(e)
        with _env("on"):
            for prior in (None, WorldPrior()):
                a = evaluate(t, prior=prior, words=e["words"], max_eval=3000)[0]
                b = evaluate(t, prior=prior, max_eval=3000)[0]
                self.assertEqual((a.evaluations, a.candidate, a.via), (b.evaluations, b.candidate, b.via))

    def test_words_retrieve_a_certified_concept_first(self):
        with _env("on"):
            p = _learn(WorldPrior(), TRAIN)
            self.assertTrue(p.lexicon and p.concepts)
            e = _held_out()
            t = MT.to_task(e)
            ev, r = evaluate(t, prior=p, words=e["words"])
            self.assertTrue(ev.certified, ev)
            self.assertTrue(ev.via.startswith("meaning:"), ev.via)
            self.assertLessEqual(ev.evaluations, M.MEANING_BUDGET)
            self.assertTrue(r.supported)
            # the field without words pays the normal search for the same task
            off = evaluate(t, prior=p)[0]
            self.assertGreater(off.evaluations, ev.evaluations)
            snap = WorldPrior.from_snapshot(json.loads(json.dumps(p.snapshot())))
            self.assertEqual(snap.lexicon, p.lexicon)
            self.assertEqual(snap.concepts, p.concepts)

    def test_shuffled_lexicon_keeps_words_and_scrambles_concepts(self):
        with _env("on"):
            p = _learn(WorldPrior(), TRAIN)
        q = M.shuffled(p, 1)
        self.assertEqual(set(q.lexicon), set(p.lexicon))
        self.assertEqual(q.concepts, p.concepts)
        self.assertEqual(sorted(sum(r.values()) for r in q.lexicon.values()),
                         sorted(sum(r.values()) for r in p.lexicon.values()))
        self.assertNotEqual(q.lexicon, p.lexicon)

    def test_learning_needs_a_verified_receipt(self):
        e = TRAIN[0]
        t = MT.to_task(e)
        wrong = ["var", t.inputs[0][0]]
        receipt, _p, _f = certify(t, wrong)
        p = WorldPrior()
        with _env("on"):
            with self.assertRaises(ValueError):
                p.add_witnessed(wrong, receipt, family=t.family, opset=OPSETS["int"], inputs=t.inputs,
                                words=e["words"], out="int")
        self.assertEqual(p.lexicon, {})

    def test_stage_budget_is_bounded(self):
        with _env("on"):
            p = _learn(WorldPrior(), TRAIN)
            e = _held_out()
            t = MT.to_task(e)
            hit, spent, info = M.stage(t, M.shuffled(p, 3), "nothing relevant here at all, elephants")
            self.assertLessEqual(spent, M.MEANING_BUDGET)


if __name__ == "__main__":
    unittest.main()
