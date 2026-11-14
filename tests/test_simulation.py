import unittest

from nomad.simulation import run_seed


class SimulationTests(unittest.TestCase):
    def test_contextual_policy_keeps_solve_rate(self):
        result = run_seed(11, train_per_family=3, test_per_family=2)
        rows = {r["policy"]: r for r in result["results"]}
        self.assertEqual(rows["fixed"]["solved"], rows["contextual"]["solved"])


if __name__ == "__main__":
    unittest.main()
