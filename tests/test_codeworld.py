import tempfile
import unittest
from pathlib import Path
from nomad.codeworld import make_codeworld_tasks, materialize, run_public_tests, solve_task, train_causal_registry

class CodeWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training = make_codeworld_tasks(17, per_family=4, include_ood=True)
        cls.registry = train_causal_registry(cls.training)

    def test_materialized_repo_really_runs_tests(self):
        task = next(t for t in self.training if t.true_family == "binary_operator")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            materialize(task, root)
            self.assertTrue((root / "solution.py").exists())
            self.assertTrue((root / "tests" / "test_public.py").exists())
            self.assertFalse(run_public_tests(root))

    def test_causal_codeworld_solves_all_registered_families(self):
        tasks = make_codeworld_tasks(1001, per_family=1)
        for task in tasks:
            with self.subTest(task=task.task_id):
                result = solve_task(task, causal=self.registry)
                self.assertTrue(result.solved)
                self.assertTrue(result.final_correct)
                self.assertTrue(result.witness_supported)

    def test_ood_cases_abstain_from_skill_prediction(self):
        tasks = [t for t in make_codeworld_tasks(1001, per_family=1, include_ood=True) if t.true_family == "unavailable"]
        self.assertGreaterEqual(len(tasks), 5)
        for task in tasks:
            with self.subTest(task=task.task_id):
                result = solve_task(task, causal=self.registry, verify_repo_tests=False)
                self.assertIsNone(result.predicted_family)
                self.assertFalse(result.solved)

if __name__ == "__main__": unittest.main()
