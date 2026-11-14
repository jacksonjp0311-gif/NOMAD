import unittest

from nomad.benchmarks import dataset
from nomad.learner import ContextualOperatorLearner
from nomad.multi_benchmarks import challenge_passes, make_multi_task
from nomad.operators import FAMILIES
from nomad.search import MultiNomadEngine
from nomad.simulation import train as train_single


class MultiEditSearchTests(unittest.TestCase):
    def test_two_edit_composition_solves_and_challenge_passes(self):
        hidden = make_multi_task(0, 1, 91)
        engine = MultiNomadEngine(fixed_order=FAMILIES)
        result = engine.solve(hidden.public, max_depth=4, max_expansions=320)
        self.assertTrue(result.solved)
        self.assertGreaterEqual(result.depth, 2)
        self.assertTrue(challenge_passes(hidden, result.source))
        self.assertTrue(all(step.source_before_sha256 for step in result.lineage))

    def test_budget_exhaustion_is_explicit(self):
        hidden = make_multi_task(7, 2, 42)
        engine = MultiNomadEngine(fixed_order=FAMILIES)
        result = engine.solve(hidden.public, max_depth=4, max_expansions=1)
        self.assertFalse(result.solved)
        self.assertEqual(result.abstained_reason, "expansion_budget")

    def test_temporal_signature_changes_after_edit(self):
        hidden = make_multi_task(0, 1, 88)
        learner = ContextualOperatorLearner(contextual=True)
        train_single(learner, dataset(5, 4, skew=True))
        result = MultiNomadEngine(learner=learner).solve(hidden.public, max_depth=4, max_expansions=320)
        self.assertTrue(result.solved)
        self.assertGreaterEqual(len(result.lineage), 2)
        signatures = [step.signature for step in result.lineage]
        self.assertGreaterEqual(len(set(signatures)), 2)


if __name__ == "__main__":
    unittest.main()
