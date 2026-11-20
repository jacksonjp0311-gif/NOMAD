"""Phases 3-5: WORLD (wider typed operators), curriculum, library learning, string/list domains."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


def _train(families_filter=None, rounds=2):
    from nomad.world import OPSETS, WorldPrior, evaluate
    from nomad.world_tasks import all_training
    p = WorldPrior()
    for _ in range(rounds):
        for t in all_training():
            if families_filter and t.family not in families_filter:
                continue
            ev, r = evaluate(t, prior=p)
            if ev.certified:
                p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs)
                p.decay(0.97)
    return p


class WorldSafetyTests(unittest.TestCase):
    def test_total_bounded_operators(self) -> None:
        from nomad.world import Invalid, run
        with self.assertRaises(Invalid):
            run(["div", ["var", "x"], ["const", 0]], {"x": 3})
        with self.assertRaises(Invalid):
            run(["lmax", ["var", "xs"]], {"xs": ()})
        with self.assertRaises(Invalid):
            run(["__import__", ["const", 1]], {})
        with self.assertRaises(Invalid):
            run(["add", ["var", "s"], ["const", 1]], {"s": "a"})  # type error
        self.assertEqual(run(["ite", ["sub", ["var", "x"], ["var", "y"]], ["var", "x"], ["const", 0]], {"x": 5, "y": 2}), 5)

    def test_witness_rejects_public_overfit(self) -> None:
        from nomad.world import evaluate, make_task
        # Public rows where head(xs) == second smallest; withheld rows disagree.
        t = make_task("of", "second", "list", {"xs": "list"}, "int",
                      [({"xs": [3, 1, 4]}, 3), ({"xs": [5, 9, 2, 6]}, 5), ({"xs": [1, 1]}, 1)],
                      [({"xs": [10, 4, 7]}, 7), ({"xs": [2, 9]}, 9)],
                      [({"xs": [8, 2, 5]}, 5)])
        ev, receipt = evaluate(t)
        self.assertIsNotNone(ev.candidate)
        self.assertFalse(ev.witness_supported)
        self.assertFalse(ev.certified)

    def test_every_training_family_is_certifiable_cold(self) -> None:
        from nomad.world import evaluate
        from nomad.world_tasks import all_training
        for t in all_training():
            with self.subTest(family=t.family):
                ev, _ = evaluate(t)
                self.assertTrue(ev.certified, (t.family, ev.candidate))


class CurriculumTests(unittest.TestCase):
    def test_level_two_opens_only_after_level_one_is_beaten(self) -> None:
        from nomad.curriculum import choose, open_levels, family_records
        from nomad.world_tasks import TRAIN
        rows = []
        self.assertEqual(open_levels(family_records(rows))["mathematics"], 1)
        l1 = [t.family for t in TRAIN["mathematics"][1]]
        for f in l1[:-1]:
            rows.append({"task": f"world:{f}", "treatment": True, "control": True, "evaluations_saved": 50})
        self.assertEqual(open_levels(family_records(rows))["mathematics"], 1)
        rows.append({"task": f"world:{l1[-1]}", "treatment": True, "control": True, "evaluations_saved": 0})
        self.assertEqual(open_levels(family_records(rows))["mathematics"], 1, "a tie is not a win")
        rows.append({"task": f"world:{l1[-1]}", "treatment": True, "control": False})
        self.assertEqual(open_levels(family_records(rows))["mathematics"], 2)
        task, plan = choose(rows, domain="mathematics")
        self.assertEqual(task.level, 2)

    def test_patience_parks_a_stubborn_family(self) -> None:
        from nomad.curriculum import PATIENCE, choose
        rows = [{"task": "world:rev_upper", "treatment": True, "control": True, "evaluations_saved": 0}] * PATIENCE
        task, _ = choose(rows, domain="language")
        self.assertNotEqual(task.family, "rev_upper")


class LearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.field = _train()

    def test_field_saves_search_on_trained_families(self) -> None:
        from nomad.world import evaluate
        from nomad.world_tasks import by_family
        for fam in ("max_pair", "pick_gt", "double_lower", "second_smallest"):
            with self.subTest(family=fam):
                t = by_family(fam)
                c, _ = evaluate(t)
                f, _ = evaluate(t, prior=self.field)
                self.assertTrue(f.certified)
                self.assertLess(f.evaluations, c.evaluations)

    def test_new_heldout_family_absdiff_field_beats_control(self) -> None:
        # Staged transfer pays the full cold shallow search first, so absdiff
        # no longer fits the 10k probe budget; at 2x budget the field certifies
        # while cold still cannot (honest trade-off, see docs/WORLD.md).
        from nomad.world import evaluate
        from nomad.world_tasks import HELDOUT
        t = HELDOUT["absdiff"]["task"]
        c, _ = evaluate(t, max_eval=20000)
        f, _ = evaluate(t, prior=self.field, use_family=False, max_eval=20000)
        self.assertFalse(c.certified)
        self.assertTrue(f.certified)

    def test_staged_transfer_never_worse_than_cold_on_unfamiliar_shallow(self) -> None:
        from nomad.world import evaluate
        from nomad.world_tasks import HELDOUT
        for name in ("last_first_upper", "sum_minus_max"):
            with self.subTest(heldout=name):
                h = HELDOUT[name]
                c, _ = evaluate(h["task"], max_eval=h["max_eval"])
                f, _ = evaluate(h["task"], prior=self.field, use_family=False, max_eval=h["max_eval"])
                self.assertTrue(f.certified)
                self.assertLessEqual(f.evaluations, c.evaluations)

    def test_library_makes_deep_heldout_reachable(self) -> None:
        from nomad.world import WorldPrior, evaluate
        from nomad.world_tasks import HELDOUT
        h = HELDOUT["quartic_sum"]
        cold, _ = evaluate(h["task"], max_eval=h["max_eval"])
        self.assertFalse(cold.certified)
        self.assertEqual(cold.reason, "frontier")  # whole size-7 space exhausted
        nolib, _ = evaluate(h["task"], prior=self.field, use_family=False, use_library=False, max_eval=h["max_eval"])
        self.assertFalse(nolib.certified)
        f, _ = evaluate(h["task"], prior=self.field, use_family=False, max_eval=h["max_eval"])
        self.assertTrue(f.certified)
        self.assertTrue(f.library_used)
        self.assertEqual(f.candidate, "add(mul(mul(x, x), mul(x, x)), mul(mul(y, y), mul(y, y)))")

    def test_snapshot_roundtrip(self) -> None:
        from nomad.world import WorldPrior
        q = WorldPrior.from_snapshot(json.loads(json.dumps(self.field.snapshot())))
        self.assertEqual(q.witnessed, self.field.witnessed)
        self.assertEqual(q.library, self.field.library)
        self.assertEqual(q.order(("add", "sub", "mul"), "square_plus_y"),
                         self.field.order(("add", "sub", "mul"), "square_plus_y"))


class WorldLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nomad-world-")
        self.data = Path(self._tmp.name)
        os.environ["NOMAD_DATA"] = str(self.data)
        for d in ("weights", "continuous", "society"):
            (self.data / d).mkdir(parents=True)

    def tearDown(self) -> None:
        os.environ.pop("NOMAD_DATA", None)
        self._tmp.cleanup()

    def test_world_pair_enqueues_and_sleep_learns(self) -> None:
        from nomad.consolidate import consolidate
        from nomad.world_loop import load_world_prior, world_pair
        out = world_pair()
        self.assertTrue(out["control"]["certified"])
        self.assertIn("enqueued", out)
        self.assertIsNotNone(out["scoreboard"])
        self.assertEqual(out["scoreboard"]["kind"], "world-certified")
        report = consolidate()
        self.assertEqual(report["world_applied"], 1)
        self.assertEqual(load_world_prior().witnessed, 1)

    def test_tampered_world_receipt_is_rejected(self) -> None:
        from nomad import field_queue
        from nomad.consolidate import consolidate
        from nomad.world_loop import world_pair
        world_pair()
        rows = field_queue.peek()
        rows[0]["receipt"]["receipt_hash"] = "0" * 64
        field_queue.queue_path().write_text("".join(json.dumps(r) + "\n" for r in rows))
        report = consolidate()
        self.assertEqual(report["dropped"], {"bad_receipt": 1})
        self.assertEqual(report["world_applied"], 0)


if __name__ == "__main__":
    unittest.main()
