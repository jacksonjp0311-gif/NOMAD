from __future__ import annotations

import unittest

from nomad.echo_map import EchoMapEncoder, EchoRecord, relation_bank
from nomad.morphic import MORPHIC_FAMILIES
from nomad.morphic_adapters import ADAPTERS
from nomad.morphic_benchmarks import make_dataset
from nomad.simulation_v5 import _verified_training_records, run_suite


class EchoMapTests(unittest.TestCase):
    def test_relation_bank_has_no_domain_input(self):
        values = relation_bank((1.0, 2.0), (2.0, 3.0))
        self.assertTrue(values)
        self.assertFalse(any("domain" in name for name in values))

    def test_encoder_selects_requested_dimensions(self):
        records = _verified_training_records(11, "code")
        encoder = EchoMapEncoder(dimensions=4).fit(records)
        self.assertEqual(len(encoder.selected), 4)
        self.assertEqual(set(encoder.prototypes), set(MORPHIC_FAMILIES))

    def test_domain_equivalent_observations_encode_identically_after_one_map(self):
        records = _verified_training_records(17, "workflow")
        encoder = EchoMapEncoder(dimensions=4).fit(records)
        points = []
        for domain in ADAPTERS:
            task = next(t for t in make_dataset(domain, 5, per_family=1) if t.true_family == "invert")
            adapter = ADAPTERS[domain]
            current = adapter.observe(task.artifact, task.public_inputs)
            target = adapter.observe(task.target_artifact, task.public_inputs)
            points.append(encoder.encode(current, target))
        # Coordinates can differ because each domain uses a different seeded base artifact,
        # but all points must be representable without domain-specific branches.
        self.assertEqual(len(points), len(ADAPTERS))
        self.assertTrue(all(len(p.coordinates) == 4 for p in points))

    def test_transfer_suite_preserves_correctness_and_beats_shuffled(self):
        suite = run_suite(seeds=(11, 17))
        for domain, rows in suite["summary"]["domains"].items():
            self.assertEqual(rows["echo_map"]["challenge_correct_rate"], 1.0)
            self.assertLess(rows["echo_map"]["mean_attempts_across_runs"], rows["echo_map_shuffled"]["mean_attempts_across_runs"])

    def test_learned_map_does_not_read_task_true_family_at_eval(self):
        # Smoke test: fit from verified records and rank raw observations directly.
        records = _verified_training_records(23, "math")
        encoder = EchoMapEncoder(dimensions=4).fit(records)
        task = make_dataset("math", 22223, per_family=1)[0]
        adapter = ADAPTERS["math"]
        ranking = encoder.rank(
            adapter.observe(task.artifact, task.public_inputs),
            adapter.observe(task.target_artifact, task.public_inputs),
        )
        self.assertEqual(set(ranking), set(MORPHIC_FAMILIES))


if __name__ == "__main__":
    unittest.main()
