"""Phase 2: unlearning and per-domain balance."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


class BalanceTests(unittest.TestCase):
    def test_balance_bar_heldout_won_and_no_domain_regresses(self) -> None:
        from nomad.heldout import balance_report
        r = balance_report()
        self.assertTrue(r["heldout"]["field_certified"])
        self.assertFalse(r["heldout"]["cold_certified"])
        self.assertEqual(r["regressions"], [])
        self.assertTrue(r["pass"])
        lang = r["domains"]["language"]
        self.assertLess(lang["field"]["evaluations"], lang["cold"]["evaluations"])

    def test_multiply_only_field_used_to_slow_subtract(self) -> None:
        """The regression the balance fixes: global Mult-first order hurt subtract."""
        from nomad.domain_tasks import splits_for
        from nomad.genesis import GrammarPrior, SynthesisTask, evaluate_task
        from nomad.heldout import train_multiply_prior
        sp = splits_for("language")
        task = SynthesisTask("lang", "def solve(x, y):\n    return 0\n", sp["public"], sp["challenge"], sp["final"], "language")
        cold, _ = evaluate_task(task, prior=GrammarPrior())
        glob, _ = evaluate_task(task, prior=train_multiply_prior())
        fam, _ = evaluate_task(task, prior=train_multiply_prior(), family="language")
        self.assertGreater(glob.candidate_evaluations, cold.candidate_evaluations)
        self.assertEqual(fam.candidate_evaluations, cold.candidate_evaluations)

    def test_decay_shrinks_counts_and_snapshot_roundtrips_families(self) -> None:
        from nomad.genesis import prior_from_snapshot
        from nomad.heldout import train_balanced_prior
        p = train_balanced_prior()
        self.assertIn("language", p.families)
        before = p.families["language"]["Sub"][0]
        p.decay(0.5)
        self.assertAlmostEqual(p.families["language"]["Sub"][0], before * 0.5)
        q = prior_from_snapshot(json.loads(json.dumps(p.snapshot())))
        self.assertEqual(q.order(0, family="language")[0], "Sub")
        self.assertEqual(q.order(0, family="science"), ("Add", "Sub", "Mult"))
        with self.assertRaises(ValueError):
            p.decay(0.0)


class ScoreboardCostTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["NOMAD_DATA"] = self._tmp.name

    def tearDown(self) -> None:
        os.environ.pop("NOMAD_DATA", None)
        self._tmp.cleanup()

    def test_pair_records_evaluations_saved(self) -> None:
        from nomad.scoreboard import record_arm
        record_arm("t", "control", True, pair_id="a", evaluations=65)
        row = record_arm("t", "treatment", True, pair_id="a", evaluations=8)
        self.assertEqual(row["evaluations_saved"], 57)


if __name__ == "__main__":
    unittest.main()
