"""WITNESS_CONTINUE: a WITNESS rejection is not terminal in the field arm.

Off switch reproduces the old search, the cold control never consults the
gate, rejections are charged and capped, the final split is never read by
the gate, and a continued search certifies what the first-fit search lost.
"""
from __future__ import annotations

import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _int_task(tid, fn):
    from nomad.world_tasks import _int_task as mk
    return mk(tid, f"wcont_{tid}", fn, 9)


# cold stops on div(2, x) (fits the public rows, WITNESS rejects it)
THREE_DIV = lambda x, y: 3 // max(x, 2)                          # noqa: E731
# a case split fits the public rows with the wrong threshold
OVERFIT = lambda x, y: y * y if x > 3 else x + 3                  # noqa: E731
PIECEWISE = lambda x, y: x * y - 1 if y > 2 else x - y           # noqa: E731


def _env(v):
    return mock.patch.dict(os.environ, {"NOMAD_WITNESS_CONTINUE": v})


def _sig(s):
    return (s.tree, s.evaluations, s.reason, s.via, tuple(s.library_used))


class WitnessContinueTests(unittest.TestCase):
    def test_continue_certifies_what_first_fit_lost(self) -> None:
        from nomad.world import WorldPrior, evaluate, run
        t = _int_task("3div", THREE_DIV)
        c, _ = evaluate(t, max_eval=10000)
        with _env("off"):
            o, _ = evaluate(t, prior=WorldPrior(), max_eval=10000)
        with _env("on"):
            f, r = evaluate(t, prior=WorldPrior(), max_eval=10000)
        self.assertFalse(c.certified)
        self.assertFalse(o.certified)
        self.assertEqual(o.candidate, c.candidate)          # same first fit as cold
        self.assertTrue(f.certified, f)
        self.assertTrue(r.supported and r.verify_checksum())
        for row, want in t.public + t.challenge + t.final:
            self.assertEqual(run(f.tree, row), want)

    def test_off_switch_and_zero_cap_reproduce_old_search(self) -> None:
        from nomad import world as W
        for fn in (THREE_DIV, OVERFIT, PIECEWISE):
            t = _int_task("x", fn)
            with _env("off"):
                off = W.synthesize(t, prior=W.WorldPrior(), max_eval=10000, casesplit=True)
            self.assertEqual(off.witness, {})
            with _env("on"), mock.patch.object(W, "WITNESS_MAX_REJECTS", 0):
                zero = W.synthesize(t, prior=W.WorldPrior(), max_eval=10000, casesplit=True)
            self.assertEqual(_sig(off), _sig(zero))
            self.assertEqual(zero.witness, {"rejected": 0})

    def test_cold_control_never_consults_the_gate(self) -> None:
        from nomad import world as W
        t = _int_task("3div", THREE_DIV)
        with _env("on"), mock.patch.object(W._WitnessGate, "__call__", side_effect=AssertionError("cold gated")):
            c = W.synthesize(t, prior=None, max_eval=10000)
        with _env("off"):
            c2 = W.synthesize(t, prior=None, max_eval=10000)
        self.assertEqual(_sig(c), _sig(c2))
        self.assertEqual(c.witness, {})

    def test_rejections_charged_capped_and_first_fit_returned(self) -> None:
        from nomad import world as W
        t = _int_task("ovf", OVERFIT)
        with _env("off"):
            old, _ = W.evaluate(t, prior=W.WorldPrior(), max_eval=10000, casesplit=True)
        for cap in (1, 3, 32):
            with _env("on"), mock.patch.object(W, "WITNESS_MAX_REJECTS", cap):
                s = W.synthesize(t, prior=W.WorldPrior(), max_eval=10000, casesplit=True)
                ev, _ = W.evaluate(t, prior=W.WorldPrior(), max_eval=10000, casesplit=True)
            self.assertLessEqual(s.evaluations, 10000)
            self.assertLessEqual(s.witness["rejected"], cap)
            self.assertGreaterEqual(s.witness["rejected"], 1)
            # after `cap` rejections the next fit is returned unconsulted (it gets
            # the one free certification every arm gets); none passes here
            self.assertTrue(ev.public_correct)
            self.assertFalse(ev.certified)
            self.assertTrue(ev.via.startswith("casesplit:"))
        with _env("on"):
            s = W.synthesize(t, prior=W.WorldPrior(), max_eval=10000, casesplit=True)
            ev, _ = W.evaluate(t, prior=W.WorldPrior(), max_eval=10000, casesplit=True)
        if s.witness.get("returned") == "first_rejected":
            # every fit rejected before the budget ran out: the outcome reads as before
            self.assertEqual(ev.candidate, old.candidate)
            self.assertEqual(ev.via, old.via)
            self.assertFalse(ev.witness_supported)

    def test_gate_never_reads_the_final_split(self) -> None:
        from nomad.world import _WitnessGate
        t = _int_task("3div", THREE_DIV)
        bad_final = replace(t, final=tuple((r, e + 1000) for r, e in t.final))
        for tree in (["div", ["const", 3], ["max", ["var", "x"], ["const", 2]]],
                     ["div", ["const", 2], ["var", "x"]]):
            self.assertEqual(_WitnessGate(t, {})(tree), _WitnessGate(bad_final, {})(tree))
        self.assertTrue(_WitnessGate(bad_final, {})(["div", ["const", 3], ["max", ["var", "x"], ["const", 2]]]))
        self.assertFalse(_WitnessGate(t, {})(["div", ["const", 2], ["var", "x"]]))

    def test_split_gen_moves_to_next_candidate_on_rejection(self) -> None:
        from nomad.casesplit import split_gen
        rows = [{"x": x} for x in (1, 2, 3, 4)]
        goal = (1, 2, 30, 40)
        ents = [(1, ["var", "x"], (1, 2, 3, 4)),
                (3, ["sub", ["var", "x"], ["const", 2]], (-1, 0, 1, 2)),
                (5, ["mul", ["var", "x"], ["add", ["const", 3], ["const", 7]]], (10, 20, 30, 40)),
                (6, ["mul", ["var", "x"], ["add", ["const", 3], ["mul", ["const", 7]]]], (10, 20, 30, 40)),
                (3, ["sub", ["const", 3], ["var", "x"]], (2, 1, 0, -1))]
        base, e0, _ = _finish(split_gen(ents, goal, rows, 0, 1000, depth2=False))
        seen = []

        def reject_first(tree):
            seen.append(tree)
            return len(seen) > 1

        tree, e1, info = _finish(split_gen(ents, goal, rows, 0, 1000, depth2=False, accept=reject_first))
        self.assertEqual(seen[0], base)
        if tree is not None:
            self.assertNotEqual(tree, base)
            self.assertEqual(info["rejected"], 1)
        self.assertEqual(e1, info["charged"])
        self.assertGreater(e1, e0)                           # the rejection was charged


def _finish(g):
    while True:
        try:
            next(g)
        except StopIteration as stop:
            return stop.value


if __name__ == "__main__":
    unittest.main()
