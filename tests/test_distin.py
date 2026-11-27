"""DISTIN (docs/DISTIN.md): a budget-neutral LET2 guarded by refutation on in-domain distinguishing inputs.

Off by default; an accepted LET2 let fit returns early unless an unoutvoted evidence-consistent rival
disagrees with it on in-domain inputs, or it breaks an evidence relation there; a miss is identical to the
switch-off search; the decision never reads the final split; an empty field is untouched; the controls
change the decision."""
from __future__ import annotations

import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from nomad import discrim as D  # noqa: E402
from nomad import distin as Ds  # noqa: E402
from nomad import world as W  # noqa: E402

KEYS = ("NOMAD_DISTIN", "NOMAD_DISTIN_CONTROL", "NOMAD_LET2", "NOMAD_DISCRIM", "NOMAD_AGREE", "NOMAD_CERT")


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
    with _Env(NOMAD_DISTIN=flag):
        ev = W.evaluate(task, prior=prior, max_eval=kw.pop("max_eval", 3000), max_size=7, casesplit=True, **kw)[0]
    return ev.certified, ev.evaluations, ev.candidate, ev.via


def _task(rows, inputs=("a", "b")):
    rs = [(dict(zip(inputs, r[:-1])), r[-1]) for r in rows]
    return W.make_task("t", "f", "int", {n: "int" for n in inputs}, "int", rs[:5], rs[5:8], rs[8:])


T = ["mul", ["var", "a"], ["var", "b"]]
N = ["var", "n"]


class DistinTests(unittest.TestCase):
    def test_default_off_and_on_switch(self) -> None:
        with _Env():
            self.assertFalse(Ds.enabled())
            self.assertFalse(W._distin_on())
        with _Env(NOMAD_DISTIN="on"):
            self.assertTrue(Ds.enabled())
            self.assertTrue(W._distin_on())

    def test_catalogue_and_sealed_suite_hash(self) -> None:
        import random
        from nomad import distin_tasks as DT
        sys.path.insert(0, str(ROOT / "scripts"))
        import distin_suite as XS
        for f in DT.CATALOGUE:
            rows = DT.draw_rows(f, random.Random(f"test:{f.family}"))
            self.assertEqual(len(rows), 11, f.family)
            for r, a in rows:
                self.assertEqual(W.run(f.tree, r), a, f.family)
        suite, easy, hard = XS.load(XS.OUT, check=True)
        self.assertEqual(suite["seed"], 20271019)
        self.assertEqual(len(easy) + len(hard), len(DT.CATALOGUE))

    def test_in_domain_rows_respect_declared_structure(self) -> None:
        # a constant column stays constant, every input stays in its observed range, orderings are kept
        rows = [(n, 10, (n + 5) // 10 * 10) for n in (101, 237, 455, 598, 640, 719, 876, 991, 333, 512, 777)]
        t = _task(rows, ("n", "k"))
        ev = D.evidence(t)
        g = Ds.drows(t.inputs, ev)
        self.assertTrue(g)
        self.assertTrue(all(r["k"] == 10 and 101 <= r["n"] <= 991 for r in g))

    def test_round10_lucky_fit_refuted_truth_kept(self) -> None:
        # docs/NOVEL.md: 10 * ceil((n - 1) / 10) matched every row of nv_d_round10 by chance
        ns = (101, 237, 455, 598, 640, 719, 876, 991)
        rows = [(n, 10, (n + 5) // 10 * 10) for n in ns]
        t = _task(rows + rows[:3], ("n", "k"))
        ev = D.evidence(t)
        K = ["var", "k"]
        lucky = ["mul", ["sub", ["const", 0], K], ["div", ["sub", ["const", 1], N], K]]
        truth = ["mul", ["div", ["add", N, ["div", K, ["const", 2]]], K], K]
        self.assertTrue(D.fits(lucky, ev) and D.fits(truth, ev))
        self.assertEqual(Ds.decide(lucky, [], [], t.inputs, ev)["verdict"], "relation")
        self.assertEqual(Ds.decide(truth, [], [], t.inputs, ev)["verdict"], "kept")

    def test_rafts_refuted_by_relation_and_by_rival(self) -> None:
        # cl_h_rafts: t // 2 - t // 3 equals ceil(t / 6) on the evidence; no alternative at all (DISCRIM
        # confirmed it vacuously); here the in-domain sweep breaks the evidence's monotone relation
        ts = (6, 8, 10, 11, 12, 14, 16, 17)
        rows = [(x, 1, -(-x // 6)) for x in ts]
        t = _task(rows + rows[:3])
        ev = D.evidence(t)
        hit = ["sub", ["div", T, ["const", 2]], ["div", T, ["const", 3]]]
        self.assertTrue(D.fits(hit, ev))
        self.assertEqual(Ds.decide(hit, [], [], t.inputs, ev)["verdict"], "relation")
        truth = ["add", ["div", ["sub", T, ["const", 1]], ["const", 6]], ["const", 1]]
        self.assertEqual(Ds.decide(hit, [truth], [], t.inputs, ev)["verdict"], "rival")
        self.assertEqual(Ds.decide(truth, [], [], t.inputs, ev)["verdict"], "kept")

    def test_regrouping_rival_refutes_handshakes(self) -> None:
        # (n - 1) * (n // 2) equals n (n - 1) / 2 whenever n is even, as on this evidence
        ns = (12, 70, 72, 80, 182, 184, 220, 400)
        rows = [(n, 1, n * (n - 1) // 2) for n in ns]
        t = _task(rows + rows[:3], ("n", "u"))
        ev = D.evidence(t)
        hit = ["mul", ["sub", N, ["const", 1]], ["div", N, ["const", 2]]]
        regs = Ds.regroupings(hit)
        self.assertIn(["div", ["mul", ["sub", N, ["const", 1]], N], ["const", 2]], regs)
        fit = [a for a in regs if D.fits(a, ev)]
        self.assertEqual(Ds.decide(hit, [], fit, t.inputs, ev)["verdict"], "rival")

    def test_supported_hit_kept_and_controls(self) -> None:
        rows = [(i, j, i * j + i) for i, j in ((2, 3), (4, 1), (5, 5), (7, 2), (3, 8), (6, 4), (9, 9), (1, 7),
                                               (2, 2), (3, 3), (4, 4))]
        t = _task(rows)
        ev = D.evidence(t)
        hit = ["add", T, ["var", "a"]]
        same = ["mul", ["var", "a"], ["add", ["var", "b"], ["const", 1]]]
        with _Env():
            d = Ds.decide(hit, [same], [], t.inputs, ev)
        self.assertEqual((d["verdict"], d["support"]), ("kept", 1))
        with _Env(NOMAD_DISTIN_CONTROL="shuffled"):
            self.assertEqual(Ds.decide(hit, [same], [], t.inputs, ev)["verdict"], "rival")

    def test_decision_never_reads_final(self) -> None:
        rows = [(i, j, i * j + i) for i, j in ((2, 3), (4, 1), (5, 5), (7, 2), (3, 8), (6, 4), (9, 9), (1, 7),
                                               (2, 2), (3, 3), (4, 4))]
        t = _task(rows)
        poisoned = replace(t, final=tuple((dict(r, a=-999), -1) for r, _e in t.final))
        hit = ["add", T, ["var", "a"]]
        same = ["mul", ["var", "a"], ["add", ["var", "b"], ["const", 1]]]
        self.assertEqual(Ds.decide(hit, [same], [], t.inputs, D.evidence(t)),
                         Ds.decide(hit, [same], [], poisoned.inputs, D.evidence(poisoned)))

    def test_empty_field_unchanged(self) -> None:
        import test_merge as TM
        task = TM._task(11, lambda a, b: a * b + (a * b) // 3)
        self.assertEqual(_run(task, W.WorldPrior(), "off"), _run(task, W.WorldPrior(), "on"))

    def test_forced_misses_are_identical_to_off(self) -> None:
        # every refutation decision forced to a miss: every task is byte-identical to off
        import test_merge as TM
        old = Ds.decide
        Ds.decide = lambda hit, indep, simp, inputs, ev_rows, out_type="int": {
            "verdict": "rival", "support": 0, "veto": 1, "rival_class": 1, "rows": 0, "why": None, "pick": hit}
        try:
            for seed, fn in ((5, lambda a, b: a * b + 2 * a), (11, lambda a, b: a * b + (a * b) // 3),
                             (7, lambda a, b: (a + b) * (a + b) - a), (9, lambda a, b: max(a, 3) * b)):
                task = TM._task(seed, fn)
                self.assertEqual(_run(task, TM._prior(), "off"), _run(task, TM._prior(), "on"))
        finally:
            Ds.decide = old

    def test_trained_toy_never_loses(self) -> None:
        import test_merge as TM
        for seed, fn in ((5, lambda a, b: a * b + 2 * a), (7, lambda a, b: (a + b) * (a + b) - a),
                         (9, lambda a, b: max(a, 3) * b), (11, lambda a, b: a * b + (a * b) // 3)):
            task = TM._task(seed, fn)
            off, on = _run(task, TM._prior(), "off"), _run(task, TM._prior(), "on")
            self.assertGreaterEqual(on[0], off[0])
            if off[0] and on[0]:
                self.assertLessEqual(on[1], off[1])

    def test_other_guards_take_precedence(self) -> None:
        import test_merge as TM
        task = TM._task(11, lambda a, b: a * b + (a * b) // 3)
        for k in ("NOMAD_LET2", "NOMAD_AGREE"):
            with _Env(**{k: "on"}):
                a = W.evaluate(task, prior=TM._prior(), max_eval=3000, max_size=7, casesplit=True)[0]
            with _Env(**{k: "on", "NOMAD_DISTIN": "on"}):
                b = W.evaluate(task, prior=TM._prior(), max_eval=3000, max_size=7, casesplit=True)[0]
            self.assertEqual((a.certified, a.evaluations, a.candidate), (b.certified, b.evaluations, b.candidate))


if __name__ == "__main__":
    unittest.main()
