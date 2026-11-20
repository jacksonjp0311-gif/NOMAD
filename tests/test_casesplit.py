"""CASESPLIT organ and the frozen DEEP suite.

Case-split correctness, budget accounting, the WITNESS gate, the cold control
untouched, the off switch, and the deep suite's held-out exclusion and hash.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _int_task(tid, fn):
    from nomad.world_tasks import _int_task as mk
    return mk(tid, f"casesplit_{tid}", fn, 9)


PIECEWISE = lambda x, y: x * y - 1 if y > 2 else x - y           # noqa: E731
PIECEWISE2 = lambda x, y: (x + y) * 2 if x - y > 0 else y * 3     # noqa: E731
# public rows: x > 2 exactly where x > 3, so a split fits them; withheld rows differ
OVERFIT = lambda x, y: y * y if x > 3 else x + 3                  # noqa: E731


class CaseSplitTests(unittest.TestCase):
    def test_split_finds_piecewise_programs_cold_cannot(self) -> None:
        from nomad.world import WorldPrior, evaluate, run
        for tid, fn in (("pw1", PIECEWISE), ("pw2", PIECEWISE2)):
            t = _int_task(tid, fn)
            c, _ = evaluate(t, max_eval=10000)
            f, r = evaluate(t, prior=WorldPrior(), max_eval=10000, casesplit=True)
            self.assertFalse(c.certified)
            self.assertTrue(f.certified, f)
            self.assertTrue(f.via.startswith("casesplit:"))
            self.assertEqual(f.tree[0], "ite")
            self.assertTrue(r.supported and r.verify_checksum())
            for row, want in t.public + t.challenge + t.final:
                self.assertEqual(run(f.tree, row), want)

    def test_split_gen_unit_occam_and_cover(self) -> None:
        from nomad.casesplit import split_gen
        rows = [{"x": x} for x in (1, 2, 3, 4)]
        goal = (1, 2, 30, 40)            # x on x <= 2, 10 * x on x >= 3
        ents = [(1, ["var", "x"], (1, 2, 3, 4)),
                (3, ["sub", ["var", "x"], ["const", 2]], (-1, 0, 1, 2)),
                (5, ["mul", ["var", "x"], ["add", ["const", 3], ["const", 7]]], (10, 20, 30, 40)),
                (9, ["mul", ["var", "x"], ["add", ["add", ["const", 3], ["const", 3]],
                                               ["add", ["const", 2], ["const", 2]]]], (10, 20, 30, 40))]
        tree, evals, info = _finish(split_gen(ents, goal, rows, 0, 1000, depth2=False))
        self.assertEqual(tree, ["ite", ["sub", ["var", "x"], ["const", 2]],
                                ["mul", ["var", "x"], ["add", ["const", 3], ["const", 7]]], ["var", "x"]])
        self.assertEqual(info["depth"], 1)  # smallest program wins (size-5 term, not size-9)
        self.assertEqual(evals, info["charged"])

    def test_budget_accounting_is_charged_and_capped(self) -> None:
        from nomad.world import WorldPrior, synthesize
        t = _int_task("pw1", PIECEWISE)
        # sense=False: this pins the split right after the cold stage (SENSE's
        # lead block would otherwise run first on this growth-shaped task)
        s = synthesize(t, prior=WorldPrior(), max_eval=10000, casesplit=True, sense=False)
        base = synthesize(t, prior=None, max_size=6, max_eval=10**7)  # the cold stage alone
        info = s.casesplit
        self.assertEqual(info["charged"], info["conditions"] + info["terms"] + info["pairs"] + info["candidates"])
        self.assertGreater(info["terms"], 0)
        self.assertGreater(info["conditions"], 0)
        self.assertEqual(s.evaluations, base.evaluations + info["charged"])
        for cap in (base.evaluations + 1, base.evaluations + 50, base.evaluations + 400):
            s2 = synthesize(t, prior=WorldPrior(), max_eval=cap, casesplit=True, sense=False)
            self.assertLessEqual(s2.evaluations, cap)
            self.assertIsNone(s2.tree)
            self.assertEqual(s2.reason, "candidate_budget")

    def test_witness_gate_rejects_public_only_split(self) -> None:
        from nomad.world import WorldPrior, evaluate, run
        t = _int_task("ovf", OVERFIT)
        f, r = evaluate(t, prior=WorldPrior(), max_eval=10000, casesplit=True)
        self.assertTrue(f.via and f.via.startswith("casesplit:"))
        self.assertTrue(all(run(f.tree, row) == want for row, want in t.public))  # fits public rows
        self.assertFalse(f.certified)                                            # WITNESS/final say no

    def test_cold_control_never_splits(self) -> None:
        from nomad.world import evaluate
        t = _int_task("pw1", PIECEWISE)
        with mock.patch("nomad.casesplit.split_gen", side_effect=AssertionError("control split")):
            for env in ("on", "off", "depth2"):
                with mock.patch.dict(os.environ, {"NOMAD_CASESPLIT": env}):
                    c, _ = evaluate(t, prior=None, max_eval=10000)
                    self.assertFalse(c.certified)
                    self.assertEqual(c.evaluations, 10000)
                    self.assertIsNone(c.via)

    def test_off_switch_restores_previous_search(self) -> None:
        from nomad.world import WorldPrior, evaluate
        t = _int_task("pw1", PIECEWISE)
        with mock.patch.dict(os.environ, {"NOMAD_CASESPLIT": "off"}):
            off, _ = evaluate(t, prior=WorldPrior(), max_eval=10000)
        explicit, _ = evaluate(t, prior=WorldPrior(), max_eval=10000, casesplit=False)
        cold, _ = evaluate(t, max_eval=10000)
        self.assertEqual((off.evaluations, off.candidate, off.via), (explicit.evaluations, explicit.candidate, None))
        self.assertEqual((off.evaluations, off.candidate), (cold.evaluations, cold.candidate))

    def test_only_int_ite_opsets_are_eligible(self) -> None:
        from nomad.casesplit import applicable
        from nomad.world_tasks import HELDOUT, all_training
        kinds = {t.family: applicable(t) for t in all_training()}
        self.assertTrue(kinds["max_pair"])
        self.assertFalse(kinds["square_plus_y"])  # genesis opset has no ite
        self.assertFalse(kinds["rev_upper"])      # str output
        self.assertFalse(kinds["range"])          # list opset has no ite
        self.assertFalse(applicable(HELDOUT["quartic_sum"]["task"]))

    def test_lofo_with_split_never_worse_than_cold(self) -> None:
        from nomad.world import synthesize
        from nomad.world_tasks import all_training
        from test_world import _train
        ts = all_training()
        cold_total = field_total = 0
        for fam in sorted({t.family for t in ts}):
            p = _train({x.family for x in ts if x.family != fam})
            for t in [x for x in ts if x.family == fam]:
                c = synthesize(t, max_eval=20000)
                f = synthesize(t, prior=p, max_eval=20000, casesplit=True)
                self.assertIsNotNone(f.tree)
                self.assertLessEqual(f.evaluations, c.evaluations, fam)
                cold_total += c.evaluations
                field_total += f.evaluations
        self.assertLessEqual(field_total, cold_total)


def _finish(g):
    while True:
        try:
            next(g)
        except StopIteration as stop:
            return stop.value


class DeepSuiteTests(unittest.TestCase):
    def test_committed_suite_matches_its_hash(self) -> None:
        import deep_suite as D
        suite = json.loads(D.OUT.read_text())
        self.assertEqual(D.suite_hash(suite), D.HASH.read_text().split()[0])
        self.assertIn(D.HASH.read_text().split()[0], (ROOT / "docs" / "DEEP_SUITE.md").read_text())
        _, tasks = D.load()
        self.assertEqual(len(tasks), 40)
        self.assertEqual(len({t.family for t in tasks}), 40)

    def test_suite_tasks_are_deep_unseen_and_not_heldout_lookalikes(self) -> None:
        import deep_suite as D
        from nomad.world import run, size
        from nomad.world_tasks import HELDOUT, all_training
        suite, tasks = D.load()
        train = {t.family for t in all_training()} | set(HELDOUT)
        rows = D.PROBE_ROWS + D.ALL_ROWS
        held = [D._behaviour(lambda r, f=f: f(r["x"], r["y"]), rows) for f in D.HELDOUT_FNS.values()]
        for e, t in zip(suite["tasks"], tasks):
            self.assertNotIn(t.family, train)
            self.assertTrue(8 <= size(e["tree"]) <= 12)
            beh = D._behaviour(lambda r: run(e["tree"], r), rows)
            self.assertNotIn(beh, held)
            for row, want in t.public + t.challenge + t.final:
                self.assertEqual(run(e["tree"], row), want)

    def test_generator_excludes_heldout_lookalikes(self) -> None:
        import deep_suite as D
        absdiff_like = ["max", ["sub", ["var", "x"], ["var", "y"]], ["sub", ["var", "y"], ["var", "x"]]]
        real = D.sample
        calls = {"n": 0}

        def fake(rng, n):
            calls["n"] += 1
            return absdiff_like if calls["n"] <= 3 else real(rng, n)
        with mock.patch.object(D, "sample", side_effect=fake):
            suite = D.generate(seed=3, n_tasks=2, budget=300)
        self.assertEqual(suite["stats"]["heldout_lookalike"], 1)  # later copies are behaviour duplicates
        self.assertNotIn(absdiff_like, [e["tree"] for e in suite["tasks"]])

    def test_generator_does_not_read_heldout_rows(self) -> None:
        src = (ROOT / "scripts" / "deep_suite.py").read_text()
        self.assertNotIn("HELDOUT[", src)
        self.assertNotIn("import HELDOUT", src)
        self.assertNotIn("heldout import", src)

    def test_cold_does_not_certify_any_suite_task(self) -> None:
        import deep_suite as D
        from nomad.world import evaluate
        suite, tasks = D.load()
        for t in tasks[:8]:
            c, _ = evaluate(t, max_eval=suite["budget"], max_size=suite["max_size"])
            self.assertFalse(c.certified, t.family)


if __name__ == "__main__":
    unittest.main()
