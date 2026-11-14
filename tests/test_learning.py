import unittest

from nomad.benchmarks import dataset
from nomad.engine import NomadEngine
from nomad.learner import ContextualOperatorLearner
from nomad.operators import FAMILIES
from nomad.simulation import train


class LearningTests(unittest.TestCase):
    def test_learning_changes_ranking(self):
        learner = ContextualOperatorLearner(contextual=True)
        train(learner, dataset(17, 4, skew=True))
        self.assertTrue(learner.context_counts)
        self.assertTrue(learner.global_counts)

    def test_frozen_evaluation_does_not_mutate(self):
        learner = ContextualOperatorLearner(contextual=True)
        train(learner, dataset(17, 2, skew=True))
        before = learner.snapshot()
        engine = NomadEngine(learner=learner, learn=False)
        for hidden in dataset(99, 1, skew=False):
            engine.solve(hidden.public)
        self.assertEqual(before, learner.snapshot())


if __name__ == "__main__":
    unittest.main()
