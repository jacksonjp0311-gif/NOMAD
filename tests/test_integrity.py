"""INTEGRITY (docs/INTEGRITY.md): evidence-loop defects reported by an external audit.

Each test first reproduced a defect on the pre-fix code (it failed there), then pins the fix:

1. receipt binding: a WITNESS receipt admits only the exact program (hash) and task it attests;
2. crash replay: a packet applied before a crash is not applied again on the next sleep;
3. challenge/final separation: WITNESS consultation during search cannot reach the final split,
   and search receives a task view with no final rows; awake exploration
   (variation.explore) never reads the final split either.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _inc_task():
    from nomad.world import make_task
    rows = lambda xs: [({"x": x}, x + 1) for x in xs]
    return make_task("t-inc", "integrity_inc", "int", {"x": "int"}, "int",
                     rows([1, 2, 3, 5, 8]), rows([13, 21, 34]), rows([55, 89, 144]))


ADD1 = ["add", ["var", "x"], ["const", 1]]
MUL2 = ["mul", ["var", "x"], ["const", 2]]


class ReceiptBinding(unittest.TestCase):
    def test_receipt_for_add1_does_not_admit_mul2(self) -> None:
        from nomad.world import OPSETS, WorldPrior, certify
        t = _inc_task()
        receipt, _pub, fin = certify(t, ADD1)
        self.assertTrue(receipt.supported and receipt.verify_checksum() and fin)
        p = WorldPrior()
        with self.assertRaises(ValueError):
            p.add_witnessed(MUL2, receipt, family=t.family, opset=OPSETS["int"], inputs=t.inputs)
        self.assertEqual(p.witnessed, 0)
        self.assertEqual(p.programs, {})
        self.assertEqual(p.families, {})

    def test_matching_tree_still_admitted(self) -> None:
        from nomad.world import OPSETS, WorldPrior, certify
        t = _inc_task()
        receipt, _pub, _fin = certify(t, ADD1)
        p = WorldPrior()
        p.add_witnessed(ADD1, receipt, family=t.family, opset=OPSETS["int"], inputs=t.inputs,
                        task_id=t.task_id)
        self.assertEqual(p.witnessed, 1)

    def test_task_identity_bound(self) -> None:
        from nomad.world import OPSETS, WorldPrior, certify
        t = _inc_task()
        receipt, _pub, _fin = certify(t, ADD1)
        p = WorldPrior()
        with self.assertRaises(ValueError):
            p.add_witnessed(ADD1, receipt, family=t.family, opset=OPSETS["int"], inputs=t.inputs,
                            task_id="some-other-task")
        self.assertEqual(p.witnessed, 0)

    def test_genesis_prior_binds_candidate(self) -> None:
        from nomad.genesis import GrammarPrior, evaluate_task
        from nomad.simulation_v10 import make_tasks
        t = make_tasks(131, ("square_plus",), n_per_family=1)[0]
        ev, receipt = evaluate_task(t)
        self.assertTrue(receipt is not None and receipt.supported)
        other = "(x+y)" if ev.candidate != "(x+y)" else "(x*y)"
        prior = GrammarPrior()
        with self.assertRaises(ValueError):
            prior.add_witnessed(ev.learned_context, other, receipt)
        self.assertEqual(prior.witnessed, 0)
        prior.add_witnessed(ev.learned_context, ev.candidate, receipt)
        self.assertEqual(prior.witnessed, 1)


class _LoopBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nomad-integrity-")
        self.data = Path(self._tmp.name)
        os.environ["NOMAD_DATA"] = str(self.data)
        for d in ("weights", "continuous", "society"):
            (self.data / d).mkdir(parents=True)

    def tearDown(self) -> None:
        os.environ.pop("NOMAD_DATA", None)
        self._tmp.cleanup()

    def _enqueue_world(self) -> dict:
        from nomad import field_queue
        from nomad.world_loop import world_pair
        out = world_pair()
        self.assertIn("enqueued", out)
        rows = field_queue.peek()
        self.assertTrue(rows and rows[-1]["certified"])
        return rows[-1]


class ConsolidateBinding(_LoopBase):
    def test_swapped_tree_is_refused_and_logged(self) -> None:
        from nomad import field_queue
        from nomad.consolidate import consolidate
        from nomad.world_loop import load_world_prior
        pkt = self._enqueue_world()
        tree = pkt["extra"]["tree"]
        pkt["extra"]["tree"] = ["add", tree, ["const", 0]]       # a different program, same receipt
        field_queue.queue_path().write_text(json.dumps(pkt) + "\n")
        report = consolidate()
        self.assertEqual(report["world_applied"], 0)
        self.assertEqual(report["dropped"], {"receipt_mismatch": 1})
        self.assertEqual(load_world_prior().witnessed, 0)
        log = self.data / "continuous" / "refusals.jsonl"
        self.assertTrue(log.exists())
        row = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual((row["packet_id"], row["reason"]), (pkt["packet_id"], "receipt_mismatch"))

    def test_wrong_task_family_is_refused(self) -> None:
        from nomad import field_queue
        from nomad.consolidate import consolidate
        from nomad.world_tasks import all_training
        pkt = self._enqueue_world()
        other = next(t.family for t in all_training() if t.family != pkt["extra"]["family"])
        pkt["extra"]["family"] = other
        field_queue.queue_path().write_text(json.dumps(pkt) + "\n")
        report = consolidate()
        self.assertEqual(report["world_applied"], 0)
        self.assertEqual(report["dropped"], {"receipt_mismatch": 1})


class CrashReplay(_LoopBase):
    def test_crash_between_save_and_ack_does_not_double_count(self) -> None:
        from nomad import consolidate as C, field_queue
        from nomad.world_loop import load_world_prior
        self._enqueue_world()
        with mock.patch.object(field_queue, "ack", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                C.consolidate()
        self.assertEqual(load_world_prior().witnessed, 1)
        self.assertTrue(field_queue.inflight_path().exists())        # the packet is replayed ...
        report = C.consolidate()
        self.assertEqual(load_world_prior().witnessed, 1)            # ... but not applied twice
        self.assertEqual(report["world_applied"], 0)
        self.assertEqual(report["dropped"], {"already_applied": 1})
        self.assertFalse(field_queue.inflight_path().exists())

    def test_crash_mid_commit_rolls_forward_once(self) -> None:
        from nomad import consolidate as C, field_queue
        from nomad.world_loop import load_world_prior
        self._enqueue_world()
        real = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            if str(src).endswith(".staged"):
                calls["n"] += 1
                if calls["n"] == 2:          # first staged file landed, second did not
                    raise RuntimeError("crash")
            return real(src, dst)
        with mock.patch.object(C.os, "replace", side_effect=flaky):
            with self.assertRaises(RuntimeError):
                C.consolidate()
        report = C.consolidate()
        self.assertEqual(load_world_prior().witnessed, 1)
        self.assertEqual(report["world_applied"], 0)
        self.assertEqual(field_queue.field_version(), 1)

    def test_new_packet_after_replay_still_learns(self) -> None:
        from nomad import consolidate as C, field_queue
        from nomad.world_loop import load_world_prior
        self._enqueue_world()
        C.consolidate()
        self._enqueue_world()
        report = C.consolidate()
        self.assertEqual(report["world_applied"], 1)
        self.assertEqual(load_world_prior().witnessed, 2)

    def test_legacy_world_prior_loads(self) -> None:
        from nomad.world_loop import load_world_prior, world_prior_path
        live = Path(__file__).resolve().parents[1] / "data" / "continuous" / "world_prior.json"
        if not live.exists():
            self.skipTest("no live world prior")
        world_prior_path().write_text(live.read_text())
        p = load_world_prior()
        self.assertEqual(p.witnessed, json.loads(live.read_text())["witnessed"])
        self.assertEqual(json.dumps(p.snapshot(), sort_keys=True),
                         json.dumps({**json.loads(live.read_text())}, sort_keys=True))


class WeightsInMemory(_LoopBase):
    def test_accumulate_list_matches_file_accumulate(self) -> None:
        import random
        from nomad import weights as Wt
        rng = random.Random(3)
        ops = []
        for i in range(40):
            bits = set(rng.sample(range(Wt.BITS), rng.randint(20, 60)) + list(range(i % 3 * 40, i % 3 * 40 + 35)))
            ops.append((bits, f"task{i % 5}", f"domain:d{i % 2}" if i % 4 == 0 else None))
        Wt._ensure()
        Wt.append_packet(Wt.Packet({1, 2, 3}, 1, "domain:d0", {}))
        mem = Wt.load_packets()
        for bits, label, dom in ops:
            Wt.accumulate(bits, True, label=label, context={"i": label})
            mem = Wt.accumulate_list(mem, bits, True, label=label, context={"i": label})
            if dom:
                Wt.reinforce(dom, 1)
                Wt.reinforce_list(mem, dom, 1)
        self.assertEqual(Wt.packets_path().read_text(), Wt.serialize(mem))


class FinalSplitSeparation(unittest.TestCase):
    def test_consult_never_reads_final(self) -> None:
        import dataclasses
        from nomad import world as W

        class Poison(tuple):
            def __iter__(self):
                raise AssertionError("final split read during a WITNESS consultation")
        t = dataclasses.replace(_inc_task(), final=Poison())
        r = W.consult(t, ADD1)
        self.assertTrue(r is not None and r.supported)
        self.assertEqual(r.receipt_hash, W.certify(_inc_task(), ADD1)[0].receipt_hash)

    def test_search_gets_no_final_rows(self) -> None:
        from nomad import world as W
        seen = []
        real = W.synthesize

        def spy(task, **kw):
            seen.append(task.final)
            return real(task, **kw)
        with mock.patch.object(W, "synthesize", side_effect=spy):
            ev, r = W.evaluate(_inc_task(), prior=W.WorldPrior())
        self.assertEqual(seen, [()])
        self.assertTrue(ev.certified)                      # certification still uses the real final rows

    def test_witness_gate_holds_no_final(self) -> None:
        from nomad import world as W
        g = W._WitnessGate(_inc_task(), {})
        self.assertFalse(hasattr(g.view, "final"))
        self.assertTrue(g(ADD1))

    def test_explore_never_reads_final(self) -> None:
        import dataclasses
        from nomad import variation as V
        from nomad import world as W
        from nomad.world_tasks import by_family

        class Poison(tuple):
            def __iter__(self):
                raise AssertionError("final split read during variation.explore")

            def __len__(self):
                raise AssertionError("final split read during variation.explore")
        vs = V.VariationState()
        vs.add_elite(["min", ["var", "x"], ["var", "y"]], V.sig_key(by_family("min_pair").inputs), "min_pair")
        real = by_family("max_pair")
        poisoned = dataclasses.replace(real, final=Poison(real.final))

        def no_final(*_a, **_k):
            raise AssertionError("final split checked during variation.explore")
        with mock.patch.object(W, "final_check", side_effect=no_final), \
                mock.patch.object(V, "certify", side_effect=no_final):
            ex = V.explore(poisoned, vs)
        self.assertTrue(any(p["tree"] == ["max", ["var", "x"], ["var", "y"]] for p in ex["paid"]))
        self.assertEqual(json.dumps(ex, sort_keys=True), json.dumps(V.explore(real, vs), sort_keys=True))
