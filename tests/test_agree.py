"""AGREE (docs/AGREE.md): a budget-neutral LET2 with an agreement guard.

Off by default; an accepted LET2 let fit returns early only with positive support (an independently derived
alternative that agrees on distinguishing inputs, and no larger class of agreeing rivals); a miss is identical
to the switch-off search (same certification, program and evaluation count); the decision never reads the
final split; an empty field is untouched; the controls change the decision."""
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

from nomad import agree as A  # noqa: E402
from nomad import agree_tasks as AT  # noqa: E402
from nomad import discrim as D  # noqa: E402
from nomad import world as W  # noqa: E402

KEYS = ("NOMAD_AGREE", "NOMAD_AGREE_CONTROL", "NOMAD_LET2", "NOMAD_DISCRIM")


class _Env:
    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.old = {k: os.environ.pop(k, None) for k in KEYS}
        os.environ.update(self.kv)

    def __exit__(self, *a):
        for k in KEYS:
            os.environ.pop(k, None)
        for k, v in self.old.items():
            if v is not None:
                os.environ[k] = v


def _run(task, prior, flag, **kw):
    with _Env(NOMAD_AGREE=flag):
        ev = W.evaluate(task, prior=prior, max_eval=kw.pop("max_eval", 3000), max_size=7, casesplit=True, **kw)[0]
    return ev.certified, ev.evaluations, ev.candidate, ev.via


def _task(rows, inputs=("a", "b")):
    rs = [(dict(zip(inputs, r[:-1])), r[-1]) for r in rows]
    return W.make_task("t", "f", "int", {n: "int" for n in inputs}, "int", rs[:5], rs[5:8], rs[8:])


T = ["mul", ["var", "a"], ["var", "b"]]


class AgreeTests(unittest.TestCase):
    def test_default_off_and_on_switch(self) -> None:
        with _Env():
            self.assertFalse(A.enabled())
            self.assertFalse(W._agree_on())
        with _Env(NOMAD_AGREE="on"):
            self.assertTrue(A.enabled())
            self.assertTrue(W._agree_on())

    def test_catalogue_truth_matches_tree(self) -> None:
        for f in AT.CATALOGUE:
            rows = AT.draw_rows(f, random.Random(f"test:{f.family}"))
            self.assertEqual(len(rows), 11, f.family)
            for r, a in rows:
                self.assertEqual(W.run(f.tree, r), a, f.family)

    def test_sealed_suite_hash(self) -> None:
        import agree_suite as XS
        suite, easy, hard = XS.load(XS.OUT, check=True)
        self.assertEqual(suite["seed"], 20270521)
        self.assertEqual(len(easy) + len(hard), len(AT.CATALOGUE))

    def test_no_support_is_unsupported(self) -> None:
        # the cl_h_rafts failure mode: t // 2 - t // 3 equals ceil(t / 6) on every evidence row
        # (t mod 6 in {0, 2, 4, 5}); with no independent alternative, nothing may return early
        pairs = [(2, 3), (4, 2), (5, 2), (3, 4), (2, 7), (4, 4), (6, 3), (5, 4), (1, 7), (3, 1), (5, 5)]
        rows = [(a, b, -(-(a * b) // 6)) for a, b in pairs]
        t = _task(rows)
        ev = D.evidence(t)
        hit = ["sub", ["div", T, ["const", 2]], ["div", T, ["const", 3]]]
        self.assertTrue(D.fits(hit, ev))
        self.assertEqual(A.decide(hit, [], [], t.inputs, ev)["verdict"], "unsupported")
        # the truth found by the offset quotients is a rival, not a supporter
        truth = ["add", ["div", ["sub", T, ["const", 1]], ["const", 6]], ["const", 1]]
        self.assertTrue(D.fits(truth, ev))
        d = A.decide(hit, [truth], [], t.inputs, ev)
        self.assertEqual((d["verdict"], d["veto"]), ("unsupported", 1))
        # a disagreeing rival class at least as large as the hit's own class vetoes a supported hit
        same = ["sub", ["div", ["mul", ["var", "b"], ["var", "a"]], ["const", 2]], ["div", T, ["const", 3]]]
        d = A.decide(hit, [same, truth], [["add", ["div", ["add", T, ["const", 5]], ["const", 6]], ["const", 0]]],
                     t.inputs, ev)
        self.assertEqual((d["verdict"], d["support"], d["rival_class"]), ("vetoed", 1, 2))

    def test_supported_and_pick_and_controls(self) -> None:
        rows = [(i, j, i * j + i) for i, j in ((2, 3), (4, 1), (5, 5), (7, 2), (3, 8), (6, 4), (9, 9), (1, 7),
                                               (2, 2), (3, 3), (4, 4))]
        t = _task(rows)
        ev = D.evidence(t)
        hit = ["add", ["mul", ["var", "a"], ["var", "b"]], ["var", "a"]]
        same = ["mul", ["var", "a"], ["add", ["var", "b"], ["const", 1]]]
        with _Env():
            d = A.decide(hit, [same], [], t.inputs, ev)
        self.assertEqual(d["verdict"], "supported")
        self.assertEqual(d["pick"], hit)        # same size: the hit is kept
        bloated = ["add", hit, ["mul", ["const", 0], ["var", "b"]]]
        with _Env():
            d = A.decide(bloated, [same], [], t.inputs, ev)
        self.assertEqual(d["verdict"], "supported")
        self.assertEqual(d["pick"], same)       # Occam inside the agreement class
        with _Env(NOMAD_AGREE_CONTROL="shuffled"):
            self.assertNotEqual(A.decide(hit, [same], [], t.inputs, ev)["verdict"], "supported")

    def test_decision_never_reads_final(self) -> None:
        rows = [(i, j, i * j + i) for i, j in ((2, 3), (4, 1), (5, 5), (7, 2), (3, 8), (6, 4), (9, 9), (1, 7),
                                               (2, 2), (3, 3), (4, 4))]
        t = _task(rows)
        poisoned = replace(t, final=tuple((dict(r, a=-999), -1) for r, _e in t.final))
        hit = ["add", ["mul", ["var", "a"], ["var", "b"]], ["var", "a"]]
        same = ["mul", ["var", "a"], ["add", ["var", "b"], ["const", 1]]]
        self.assertEqual(A.decide(hit, [same], [], t.inputs, D.evidence(t)),
                         A.decide(hit, [same], [], poisoned.inputs, D.evidence(poisoned)))

    def test_empty_field_unchanged(self) -> None:
        f = AT.CATALOGUE[0]
        rows = AT.draw_rows(f, random.Random("t:empty"))
        task = AT.to_task({"task_id": "x", "family": f.family, "inputs": list(f.inputs), "rows": [[r, a] for r, a in rows]})
        self.assertEqual(_run(task, W.WorldPrior(), "off"), _run(task, W.WorldPrior(), "on"))

    def test_a_miss_is_identical_to_off(self) -> None:
        # the guard runs (an accepted let fit) and finds no support: the task is exactly as off
        import test_merge as TM
        task = TM._task(11, lambda a, b: a * b + (a * b) // 3)
        seen = []
        old = A.note
        A.note = lambda task_, hit, i, s, d: seen.append(d["verdict"])
        try:
            off, on = _run(task, TM._prior(), "off"), _run(task, TM._prior(), "on")
        finally:
            A.note = old
        self.assertEqual(seen, ["unsupported"])
        self.assertEqual(off, on)

    def test_forced_misses_are_identical_to_off(self) -> None:
        # every guard decision forced to "unsupported": every task is byte-identical to off
        import test_merge as TM
        old = A.decide
        A.decide = lambda hit, indep, simp, inputs, ev_rows: {"verdict": "unsupported", "support": 0, "veto": 0,
                                                              "rival_class": 0, "rows": 0, "pick": hit}
        try:
            for seed, fn in ((5, lambda a, b: a * b + 2 * a), (11, lambda a, b: a * b + (a * b) // 3),
                             (7, lambda a, b: (a + b) * (a + b) - a), (9, lambda a, b: max(a, 3) * b)):
                task = TM._task(seed, fn)
                self.assertEqual(_run(task, TM._prior(), "off"), _run(task, TM._prior(), "on"))
        finally:
            A.decide = old

    def test_trained_toy_never_loses(self) -> None:
        import test_merge as TM
        for seed, fn in ((5, lambda a, b: a * b + 2 * a), (7, lambda a, b: (a + b) * (a + b) - a),
                         (9, lambda a, b: max(a, 3) * b), (11, lambda a, b: a * b + (a * b) // 3)):
            task = TM._task(seed, fn)
            off, on = _run(task, TM._prior(), "off"), _run(task, TM._prior(), "on")
            if off[0]:
                self.assertEqual(off[:3], on[:3])
            self.assertGreaterEqual(on[0], off[0])

    def test_let2_and_discrim_take_precedence(self) -> None:
        import test_merge as TM
        task = TM._task(11, lambda a, b: a * b + (a * b) // 3)
        with _Env(NOMAD_LET2="on"):
            a = W.evaluate(task, prior=TM._prior(), max_eval=3000, max_size=7, casesplit=True)[0]
        with _Env(NOMAD_LET2="on", NOMAD_AGREE="on"):
            b = W.evaluate(task, prior=TM._prior(), max_eval=3000, max_size=7, casesplit=True)[0]
        self.assertEqual((a.certified, a.evaluations, a.candidate), (b.certified, b.evaluations, b.candidate))


if __name__ == "__main__":
    unittest.main()
