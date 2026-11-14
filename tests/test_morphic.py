from __future__ import annotations
import unittest
from nomad.morphic import MORPHIC_FAMILIES, MorphicLearner, Observation, effect_signature
from nomad.morphic_adapters import ADAPTERS
from nomad.morphic_benchmarks import make_dataset
from nomad.morphic_engine import MorphicEngine
from nomad.simulation_v4 import run_suite


class MorphicTests(unittest.TestCase):
    def test_each_adapter_can_apply_all_families(self):
        for domain in ADAPTERS:
            tasks = make_dataset(domain, 3, per_family=1)
            self.assertEqual({t.true_family for t in tasks}, set(MORPHIC_FAMILIES))
            engine = MorphicEngine(fixed_order=MORPHIC_FAMILIES)
            for task in tasks:
                result = engine.solve(task)
                self.assertTrue(result.challenge_correct)

    def test_signature_ignores_domain_name(self):
        keys = {}
        for domain in ADAPTERS:
            task = next(t for t in make_dataset(domain, 5, per_family=1) if t.true_family == "invert")
            adapter = ADAPTERS[domain]
            keys[domain] = effect_signature(Observation(
                adapter.observe(task.artifact, task.public_inputs),
                adapter.observe(task.target_artifact, task.public_inputs),
            )).key
        self.assertEqual(len(set(keys.values())), 1)

    def test_transfer_suite(self):
        suite = run_suite(seeds=(11, 17))
        for domain, rows in suite["summary"]["domains"].items():
            self.assertEqual(rows["morphic_transfer"]["challenge_correct_rate"], 1.0)
            self.assertLess(rows["morphic_transfer"]["mean_attempts_across_runs"], rows["global_frequency"]["mean_attempts_across_runs"])


if __name__ == "__main__":
    unittest.main()
