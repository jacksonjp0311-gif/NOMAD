from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from nomad.repo_world import (
    build_graph, candidate_files, file_signature, make_repository_tasks,
    materialize, solve_repository, train_world_models,
)
from nomad.simulation_v8 import run_suite


class WorldModelTests(unittest.TestCase):
    def test_filenames_are_not_signature_features(self):
        task = make_repository_tasks(17, per_kind=1)[0]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); materialize(task, root)
            sig = file_signature(root, task, candidate_files(task)[0], include_failure=True)
            for filename in task.files:
                self.assertNotIn(filename, sig)
                self.assertNotIn(Path(filename).stem, sig)

    def test_graph_has_entry_reachability(self):
        task = make_repository_tasks(17, per_kind=1)[0]
        edges, reverse, distance = build_graph(task)
        entry = f"{task.entry_module}.py"
        self.assertEqual(distance[entry], 0)
        self.assertTrue(any(v < 999 for k, v in distance.items() if k != entry))
        self.assertTrue(any(v == 999 for v in distance.values()))

    def test_flat_solver_repairs_all_kinds(self):
        for task in make_repository_tasks(31, per_kind=1):
            r = solve_repository(task)
            self.assertTrue(r.solved, task.task_id)
            self.assertTrue(r.final_correct, task.task_id)
            self.assertTrue(r.witness_supported, task.task_id)

    def test_world_model_training_uses_verified_repairs(self):
        train = make_repository_tasks(41, per_kind=2)
        wm, static, _ = train_world_models(train)
        self.assertGreater(wm.observations, 0)
        self.assertGreater(static.observations, 0)
        self.assertTrue(wm.pos)

    def test_world_model_localizes_unseen_filenames(self):
        train = make_repository_tasks(53, per_kind=3)
        evals = make_repository_tasks(10053, per_kind=2)
        wm, _, _ = train_world_models(train)
        rows = [solve_repository(t, world_model=wm) for t in evals]
        self.assertTrue(all(r.final_correct for r in rows))
        self.assertGreaterEqual(sum(bool(r.localization_correct) for r in rows), 6)

    def test_physical_multifile_unittest_integration(self):
        train = make_repository_tasks(67, per_kind=2)
        eval_task = make_repository_tasks(10067, per_kind=1)[0]
        wm, _, _ = train_world_models(train)
        row = solve_repository(eval_task, world_model=wm, verify_repo_tests=True)
        self.assertTrue(row.solved)
        self.assertTrue(row.public_tests_passed)
        self.assertTrue(row.witness_supported)
        self.assertTrue(row.final_correct)

    def test_release_study_gate(self):
        report = run_suite((17,))
        s = report["summary"]
        self.assertEqual(s["world_final_correct_rate"], 1.0)
        self.assertGreater(s["world_attempt_reduction_vs_flat"], 0.10)
        self.assertGreater(s["world_localization_accuracy"], 0.70)


if __name__ == "__main__":
    unittest.main()
