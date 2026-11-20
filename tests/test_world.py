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
        # Exact redundancy skips plus a resumed (not restarted) library stage
        # bring the staged field back under the 10k probe budget; cold still
        # cannot certify there. Measured, not tuned: no parameter reads absdiff.
        from nomad.world import evaluate
        from nomad.world_tasks import HELDOUT
        h = HELDOUT["absdiff"]
        c, _ = evaluate(h["task"], max_eval=h["max_eval"])
        f, _ = evaluate(h["task"], prior=self.field, use_family=False, max_eval=h["max_eval"])
        self.assertFalse(c.certified)
        self.assertTrue(f.certified)
        self.assertLessEqual(f.evaluations, h["max_eval"])

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


class SearchCostTests(unittest.TestCase):
    """Cheaper search must not change what search finds."""

    def test_redundant_skip_is_exact(self) -> None:
        import random
        from nomad.world import INT_CONSTANTS, OPS, Invalid, _redundant
        rng = random.Random(7)
        consts = {tuple([k] * 4) for k in INT_CONSTANTS}
        pick = lambda: tuple(rng.choice([-3, -1, 0, 0, 1, 1, 2, 5]) for _ in range(4))
        skipped = 0
        for _ in range(20000):
            name = rng.choice(["add", "sub", "mul", "div", "mod", "min", "max", "ite"])
            k = len(OPS[name].args)
            vals = [pick() for _ in range(k)]
            if rng.random() < 0.2 and k >= 2:
                vals[-1] = vals[-2]
            combo = [(None, v) for v in vals]
            if not _redundant(name, combo):
                continue
            skipped += 1
            try:
                out = tuple(OPS[name].fn(*args) for args in zip(*vals))
            except Invalid:
                continue
            self.assertTrue(out in vals or out in consts, (name, vals, out))
        self.assertGreater(skipped, 1000)

    def test_skip_leaves_found_programs_unchanged(self) -> None:
        import nomad.world as W
        from nomad.world_tasks import HELDOUT, all_training
        tasks = list(all_training()) + [h["task"] for n, h in HELDOUT.items() if n != "quartic_sum"]
        on = {t.task_id: W.synthesize(t, max_eval=40000) for t in tasks}
        real = W._redundant
        W._redundant = lambda name, combo: False
        try:
            off = {t.task_id: W.synthesize(t, max_eval=40000) for t in tasks}
        finally:
            W._redundant = real
        for t in tasks:
            with self.subTest(task=t.task_id):
                a, b = on[t.task_id], off[t.task_id]
                self.assertEqual(a.tree, b.tree)
                self.assertLessEqual(a.evaluations, b.evaluations)

    def test_resumed_stage_reaches_what_a_restart_reaches(self) -> None:
        # Stage 2 resumes from stage 1 pools; it must still find a program
        # whenever restarting the library search from scratch finds one.
        import nomad.world as W
        from nomad.world_tasks import HELDOUT, all_training
        field = _train()
        for t in list(all_training()) + [h["task"] for h in HELDOUT.values()]:
            lib = field.primitives_for(t.inputs)
            if not lib:
                continue
            order = tuple(W.OPSETS[t.opset])
            with self.subTest(task=t.task_id):
                restart = W._drive(W._search_gen(t, order, lib, 7, 200000))
                staged = W._drive(W._staged_gen(t, order, lib, 7, 200000))
                self.assertEqual(restart.tree is not None, staged.tree is not None)

    def test_leave_one_family_out_staged_never_worse_than_cold(self) -> None:
        from nomad.world import synthesize
        from nomad.world_tasks import all_training
        ts = all_training()
        for fam in sorted({t.family for t in ts}):
            p = _train({x.family for x in ts if x.family != fam})
            for t in [x for x in ts if x.family == fam]:
                with self.subTest(family=fam):
                    c = synthesize(t, max_eval=20000)
                    f = synthesize(t, prior=p, max_eval=20000)
                    self.assertEqual(c.tree is not None, True)
                    self.assertIsNotNone(f.tree)
                    self.assertLessEqual(f.evaluations, c.evaluations)
