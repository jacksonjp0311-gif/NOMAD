"""VARIATION: variation operator, novelty archive, payoff memory, learner, persistence."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_world import _train  # noqa: E402

II = (("x", "int"), ("y", "int"))


def _overfit_task(honest: bool):
    """Public rows fit max(x, y); challenge/final rows do unless ``honest`` is False."""
    from nomad.world import make_task
    f = (lambda x, y: max(x, y)) if honest else (lambda x, y: max(x, y) + (1 if x != y else 0))
    pub = [({"x": x, "y": y}, max(x, y)) for x, y in ((2, 5), (7, 3), (4, 4), (9, 2))]
    rows = lambda pts: [({"x": x, "y": y}, f(x, y)) for x, y in pts]
    return make_task("t-var", "variation_probe_family", "int", {"x": "int", "y": "int"}, "int",
                     pub, rows([(11, 6), (3, 10), (8, 8)]), rows([(13, 4), (5, 12), (6, 1)]))


def _state_with_elite(tree, family="min_pair"):
    from nomad.variation import VariationState, sig_key
    vs = VariationState()
    vs.add_elite(tree, sig_key(II), family)
    return vs


class VariationOperatorTests(unittest.TestCase):
    def test_kinds_are_correct_one_step_perturbations(self) -> None:
        from nomad.variation import mutants
        from nomad.world import OPSETS
        got = {(k, json.dumps(t)) for k, t in mutants(["sub", ["var", "x"], ["const", 0]], OPSETS["int"], II)}
        kinds = {k for k, _ in got}
        self.assertEqual(kinds, {"op_swap", "const_flip", "var_swap", "reorder"})
        self.assertIn(("op_swap", json.dumps(["add", ["var", "x"], ["const", 0]])), got)
        self.assertIn(("const_flip", json.dumps(["sub", ["var", "x"], ["const", 2]])), got)
        self.assertIn(("var_swap", json.dumps(["sub", ["var", "y"], ["const", 0]])), got)
        self.assertIn(("reorder", json.dumps(["sub", ["const", 0], ["var", "x"]])), got)
        # the original is never re-emitted and there are no duplicates
        trees = [t for _, t in got]
        self.assertNotIn(json.dumps(["sub", ["var", "x"], ["const", 0]]), trees)
        self.assertEqual(len(trees), len(set(trees)))

    def test_op_swap_stays_in_opset_and_signature(self) -> None:
        from nomad.variation import mutants
        from nomad.world import OPS, OPSETS, ops_used
        for opset in ("genesis", "int"):
            for _, t in mutants(["min", ["var", "x"], ["var", "y"]], OPSETS[opset], II):
                for op in ops_used(t):
                    self.assertTrue(op == "min" or op in OPSETS[opset])
                    self.assertEqual(OPS[op].args, ("int", "int"))

    def test_commutative_ops_are_not_reordered(self) -> None:
        from nomad.variation import mutants
        from nomad.world import OPSETS
        kinds = [k for k, _ in mutants(["max", ["var", "x"], ["var", "y"]], OPSETS["int"], II)]
        self.assertNotIn("reorder", kinds)

    def test_string_and_list_mutants_are_type_preserving(self) -> None:
        from nomad.variation import mutants
        from nomad.world import OPSETS, Invalid, run
        for tree, opset, inputs, row in (
            (["upper", ["srev", ["var", "s"]]], "str", (("s", "str"),), {"s": "Nomad"}),
            (["sub", ["lmax", ["var", "xs"]], ["lmin", ["var", "xs"]]], "list", (("xs", "list"),), {"xs": (3, 1, 4)}),
        ):
            ms = mutants(tree, OPSETS[opset], inputs)
            self.assertTrue(ms)
            for _, t in ms:
                try:
                    run(t, row)
                except Invalid:
                    pass  # an out-of-world value is allowed; a type crash is not

    def test_mutation_alone_never_certifies(self) -> None:
        from nomad.world import WorldPrior, evaluate
        vs = _state_with_elite(["min", ["var", "x"], ["var", "y"]])
        p = WorldPrior()
        # max_size=1: the search misses at once, leaving budget for mutants.
        bad, receipt = evaluate(_overfit_task(honest=False), prior=p, max_size=1, variation=vs)
        self.assertEqual(bad.via, "variation:op_swap")
        self.assertEqual(bad.candidate, "max(x, y)")
        self.assertTrue(bad.public_correct)
        self.assertFalse(bad.certified)  # WITNESS / final split reject the public fit
        good, receipt = evaluate(_overfit_task(honest=True), prior=p, max_size=1, variation=vs)
        self.assertTrue(good.certified)
        self.assertTrue(receipt.supported and receipt.verify_checksum())

    def test_control_never_reads_variation(self) -> None:
        from nomad.world import evaluate
        from nomad.world_tasks import HELDOUT
        vs = _state_with_elite(["min", ["var", "x"], ["var", "y"]])
        t = HELDOUT["absdiff"]["task"]
        a, _ = evaluate(t, max_eval=3000)
        b, _ = evaluate(t, prior=None, max_eval=3000, variation=vs)
        self.assertEqual((a.evaluations, a.candidate, a.reason), (b.evaluations, b.candidate, b.reason))
        self.assertEqual(b.variation, ())

    def test_search_tries_are_bounded(self) -> None:
        from nomad.variation import SEARCH_TRIES, VariationState, sig_key
        from nomad.world import WorldPrior, evaluate
        vs = VariationState()
        for tree in (["min", ["var", "x"], ["var", "y"]], ["sub", ["var", "x"], ["const", 1]],
                     ["mul", ["var", "x"], ["add", ["var", "y"], ["const", 2]]]):
            vs.add_elite(tree, sig_key(II), "other")
        from nomad.world import make_task
        never = make_task("t2", "never_fits", "int", {"x": "int", "y": "int"}, "int",
                          [({"x": 1, "y": 2}, 999)], [({"x": 3, "y": 4}, 999)], [({"x": 5, "y": 6}, 999)])
        ev, _ = evaluate(never, prior=WorldPrior(), max_size=1, variation=vs)
        self.assertFalse(ev.certified)
        self.assertEqual(len(ev.variation), SEARCH_TRIES)
        self.assertLessEqual(ev.evaluations, 6 + SEARCH_TRIES)  # atoms + mutants only

    def test_leave_one_family_out_with_variation_never_worse_than_cold(self) -> None:
        from nomad import variation as V
        from nomad.world import synthesize
        from nomad.world_tasks import all_training
        ts = all_training()
        for fam in sorted({t.family for t in ts}):
            p = _train({x.family for x in ts if x.family != fam})
            vs = V.VariationState()
            for x in ts:
                if x.family != fam:
                    s = synthesize(x, prior=p)
                    if s.tree is not None:
                        vs.add_elite(s.tree, V.sig_key(x.inputs), x.family)
            for t in [x for x in ts if x.family == fam]:
                with self.subTest(family=fam):
                    c = synthesize(t, max_eval=20000)
                    f = synthesize(t, prior=p, max_eval=20000, variation=vs)
                    self.assertIsNotNone(f.tree)
                    self.assertLessEqual(f.evaluations, c.evaluations)

    def test_deterministic(self) -> None:
        from nomad import variation as V
        from nomad.world_tasks import by_family
        vs = _state_with_elite(["min", ["var", "x"], ["var", "y"]], family="min_pair")
        t = by_family("max_pair")
        a = V.explore(t, vs)
        b = V.explore(t, vs)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertTrue(any(p["tree"] == ["max", ["var", "x"], ["var", "y"]] for p in a["paid"]))


class NoveltyArchiveTests(unittest.TestCase):
    def test_archive_is_bounded_and_keeps_best_scores(self) -> None:
        from nomad.variation import ARCHIVE_CAP, VariationState, sig_key
        vs = VariationState()
        sig = sig_key(II)
        kept = 0
        for a in range(4):
            for b in range(4):
                for op in ("add", "sub", "mul", "max", "min", "mod", "div"):
                    t = [op, ["mul", ["var", "x"], ["const", a]], ["add", ["var", "y"], ["const", b]]]
                    kept += int(vs.consider(t, sig, "op_swap", fitness=(a + b) / 6))
        self.assertGreater(kept, 0)
        self.assertLessEqual(len(vs.archive), ARCHIVE_CAP)
        scores = [e["score"] for e in vs.archive]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_novel_zero_fitness_mutant_is_retained(self) -> None:
        from nomad.variation import VariationState, sig_key
        vs = VariationState()
        self.assertTrue(vs.consider(["mul", ["var", "x"], ["var", "y"]], sig_key(II), "op_swap", fitness=0.0))
        self.assertEqual(vs.archive[0]["fitness"], 0.0)
        self.assertGreater(vs.archive[0]["novelty"], 0.0)

    def test_duplicate_or_familiar_behaviour_is_rejected(self) -> None:
        from nomad.variation import VariationState, sig_key
        vs = VariationState()
        sig = sig_key(II)
        self.assertTrue(vs.consider(["add", ["var", "x"], ["var", "y"]], sig, "op_swap", 0.0))
        self.assertFalse(vs.consider(["add", ["var", "x"], ["var", "y"]], sig, "op_swap", 0.0))
        self.assertFalse(vs.consider(["add", ["var", "y"], ["var", "x"]], sig, "reorder", 0.0))  # same behaviour
        self.assertFalse(vs.consider(["div", ["var", "x"], ["const", 0]], sig, "const_flip", 0.0))  # invalid everywhere


class PayoffMemoryTests(unittest.TestCase):
    def test_laplace_and_bias(self) -> None:
        from nomad.variation import KINDS, PayoffMemory
        m = PayoffMemory()
        self.assertEqual({round(m.score("a", k), 6) for k in KINDS}, {0.5})
        for _ in range(3):
            m.record("a", "reorder", True)
            m.record("a", "op_swap", False)
        self.assertEqual(m.order("a")[0], "reorder")
        self.assertEqual(m.order("a")[-1], "op_swap")
        self.assertGreater(m.score("a", "reorder"), 0.5)
        # pooled evidence shrinks an unseen situation toward what paid elsewhere
        self.assertEqual(m.order("b")[0], "reorder")
        with self.assertRaises(ValueError):
            m.record("a", "teleport", True)

    def test_decay(self) -> None:
        from nomad.variation import PayoffMemory
        m = PayoffMemory()
        m.record("a", "op_swap", True)
        m.decay(0.5)
        self.assertEqual(m.counts["a"]["op_swap"], [0.5, 0.5])

    def test_memory_orders_candidates(self) -> None:
        from nomad import variation as V
        from nomad.world_tasks import by_family
        t = by_family("max_pair")
        vs = _state_with_elite(["sub", ["var", "x"], ["const", 1]])
        sit = V.situation(t)
        for _ in range(5):
            vs.memory.record(sit, "const_flip", True)
        cands = vs.candidates(t, vs.sources(t), 4)
        self.assertEqual(cands[0][0], "const_flip")

    def test_learner_counts_paid_only_after_reattestation(self) -> None:
        from nomad import variation as V
        from nomad.world_tasks import by_family
        vs = V.VariationState()
        good = ["max", ["var", "x"], ["var", "y"]]
        fake = ["add", ["var", "x"], ["var", "y"]]
        trace = {"family": "max_pair", "tried": [{"kind": "op_swap", "tree": good, "fitness": 1.0},
                                                 {"kind": "reorder", "tree": fake, "fitness": 1.0}],
                 "paid": [{"kind": "op_swap", "tree": good}, {"kind": "reorder", "tree": fake}]}
        res = V.apply_trace(vs, trace, certified_tree=good)
        sit = V.situation(by_family("max_pair"))
        self.assertEqual(res["paid"], 1)
        self.assertEqual(vs.memory.counts[sit]["op_swap"], [1.0, 1.0])
        self.assertEqual(vs.memory.counts[sit]["reorder"], [0.0, 1.0])
        self.assertEqual(len(vs.elites), 1)

    def test_learner_refuses_heldout_and_unknown_families(self) -> None:
        from nomad import variation as V
        vs = V.VariationState()
        for fam in ("absdiff", "quartic_sum", "no_such_family", None):
            self.assertEqual(V.apply_trace(vs, {"family": fam, "tried": [], "paid": []}), {"refused": 1})
        self.assertEqual(vs.memory.counts, {})


class VariationPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nomad-var-")
        self.data = Path(self._tmp.name)
        os.environ["NOMAD_DATA"] = str(self.data)
        for d in ("weights", "continuous", "society"):
            (self.data / d).mkdir(parents=True)

    def tearDown(self) -> None:
        os.environ.pop("NOMAD_DATA", None)
        self._tmp.cleanup()

    def test_snapshot_roundtrip_and_fallback(self) -> None:
        from nomad import variation as V
        vs = _state_with_elite(["min", ["var", "x"], ["var", "y"]])
        vs.memory.record("s", "op_swap", True)
        vs.consider(["mul", ["var", "x"], ["var", "y"]], V.sig_key(II), "op_swap", 0.25)
        V.save_state(vs)
        back = V.load_state()
        self.assertEqual(json.dumps(back.snapshot(), sort_keys=True), json.dumps(vs.snapshot(), sort_keys=True))
        V.save_state(back)  # creates .prev
        V.state_path().write_text("{not json")
        again = V.load_state()
        self.assertEqual(again.memory.counts, vs.memory.counts)
        with self.assertRaises(ValueError):
            V.VariationState.from_snapshot({"schema": "other"})

    def test_world_pair_trace_reaches_single_learner(self) -> None:
        from nomad import variation as V
        from nomad.consolidate import consolidate
        from nomad.world_loop import probe_heldout, world_pair
        for _ in range(3):
            out = world_pair()
            self.assertIn("variation", out)
            self.assertNotIn("variation", out["control"])  # the cold control carries nothing from variation
        self.assertFalse(V.state_path().exists())  # awake never writes variation state
        report = consolidate()
        self.assertGreaterEqual(report["variation_applied"], 1)
        st = V.load_state()
        self.assertGreaterEqual(len(st.elites), 1)
        before = json.dumps(st.snapshot(), sort_keys=True)
        probe_heldout()
        self.assertEqual(json.dumps(V.load_state().snapshot(), sort_keys=True), before)  # held-outs never train

    def test_kill_switch(self) -> None:
        from nomad.world_loop import world_pair
        os.environ["NOMAD_VARIATION"] = "off"
        try:
            out = world_pair()
        finally:
            os.environ.pop("NOMAD_VARIATION", None)
        self.assertNotIn("variation", out)
        self.assertEqual(out["treatment"]["variation_tried"], 0)


if __name__ == "__main__":
    unittest.main()
