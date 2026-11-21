"""ROLES (docs/ROLES.md): numbers and their roles read from a story; switch NOMAD_ROLES (default off)."""
from __future__ import annotations

import os
import unittest

from nomad import meaning as M
from nomad import meaning_tasks as MT
from nomad import roles as R
from nomad.world import OPSETS, WorldPrior, evaluate


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


def _learn(p, entries):
    with _Env(NOMAD_MEANING="on", NOMAD_ROLES="on"):
        for e in entries:
            t = MT.to_task(e)
            ev, r = evaluate(t, prior=p, max_eval=20000)
            if ev.certified:
                p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                                words=e["story"], out=t.out, row=t.public[0][0])
    return p


TRAIN = [e for e in MT.train_story_entries() if e["concept"] in ("change", "product")]


def _held_out():
    fam = MT._f("ut_coat_change", "change", "museum",
                "A visitor with {x} friends pays with {c} dollars for {a} coat tickets at {b} dollars each "
                "on floor {y}. How much change comes back?", ("x", "y"))
    return MT.story_entry(fam, "ut-r0", 11, ("ua", "ub", "uc", "ud", "ue"), shuffle=True)


class RolesTests(unittest.TestCase):
    def test_default_off(self):
        os.environ.pop("NOMAD_ROLES", None)
        self.assertFalse(R.enabled())
        with _Env(NOMAD_ROLES="on"):
            self.assertTrue(R.enabled())

    def test_mentions_parse_numbers_and_context(self):
        ms = R.mentions("A cook pays with 40 coins for 3 bags costing 7 coins each. How much change?")
        self.assertEqual([v for v, _f in ms], [40, 3, 7])
        self.assertIn("L1:with", ms[0][1])
        self.assertIn("R1:bag", ms[1][1])
        self.assertIn("C:each", ms[2][1])

    def test_story_entry_keeps_meaning_entry_identical(self):
        a, b = MT.train_entries(), MT.train_story_entries()
        for x, y in zip(a, b):
            self.assertEqual({k: v for k, v in y.items() if k != "story"}, x)
            self.assertEqual(M.tokens(y["story"]), M.tokens(x["words"]))   # numbers carry no lexicon tokens

    def test_learning_needs_switch_and_row(self):
        p = WorldPrior()
        with _Env(NOMAD_MEANING="on", NOMAD_ROLES="off"):
            for e in TRAIN:
                t = MT.to_task(e)
                ev, r = evaluate(t, prior=p, max_eval=20000)
                if ev.certified:
                    p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs,
                                    words=e["story"], out=t.out, row=t.public[0][0])
        self.assertTrue(p.concepts)
        self.assertFalse(any(r.get("roles") for r in p.concepts.values()))
        self.assertNotIn("roles", str(p.snapshot()))

    def test_roles_put_the_right_renaming_first_and_off_is_meaning(self):
        p = _learn(WorldPrior(), TRAIN)
        self.assertTrue(any(r.get("roles") for r in p.concepts.values()))
        e = _held_out()
        t = MT.to_task(e)
        with _Env(NOMAD_MEANING="on", NOMAD_ROLES="off"):
            off = M.stage(t, p, e["story"])
            off_ev = evaluate(t, prior=p, max_eval=20000, words=e["story"])[0]
            off_w = evaluate(t, prior=p, max_eval=20000, words=e["words"])[0]
        with _Env(NOMAD_MEANING="on", NOMAD_ROLES="on"):
            on = M.stage(t, p, e["story"])
            on_w = evaluate(t, prior=p, max_eval=20000, words=e["words"])[0]   # no numbers: MEANING's stage
        self.assertIsNotNone(on[0])
        self.assertLessEqual(on[1], off[1])
        self.assertEqual((off_w.certified, off_w.evaluations, off_w.candidate),
                         (on_w.certified, on_w.evaluations, on_w.candidate))
        self.assertEqual((off_ev.certified, off_ev.evaluations), (off_w.certified, off_w.evaluations))

    def test_shuffled_control_keeps_counts(self):
        p = _learn(WorldPrior(), TRAIN)
        q = R.shuffled(p, 1)
        for k, rec in p.concepts.items():
            a = sorted(sum(t.values()) for t in rec.get("roles", {}).values())
            b = sorted(sum(t.values()) for t in q.concepts[k].get("roles", {}).values())
            self.assertEqual(a, b)
        self.assertEqual(p.lexicon, q.lexicon)

    def test_empty_field_unchanged(self):
        e = _held_out()
        t = MT.to_task(e)
        res = []
        for v in ("off", "on"):
            with _Env(NOMAD_MEANING="on", NOMAD_ROLES=v):
                ev = evaluate(t, prior=WorldPrior(), max_eval=3000, words=e["story"])[0]
                res.append((ev.certified, ev.evaluations, ev.candidate))
        self.assertEqual(res[0], res[1])


if __name__ == "__main__":
    unittest.main()
