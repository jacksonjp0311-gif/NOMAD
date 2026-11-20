"""Tests for the Molt-derived actor/learner split.

All field I/O goes to a temporary NOMAD_DATA directory.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


def _certified_packet(field_version: int = 0, pair_id: str | None = "p1"):
    """A real WITNESS-certified multiply attempt turned into a packet."""
    from nomad.domain_tasks import TRAIN_MULTIPLY
    from nomad.field_queue import make_packet
    from nomad.genesis import GrammarPrior, SynthesisTask, evaluate_task

    rows = TRAIN_MULTIPLY[0]
    task = SynthesisTask(
        task_id="t-mult",
        source="def solve(x, y):\n    return 0\n",
        public=tuple(rows["public"]),
        challenge=tuple(rows["challenge"]),
        final=tuple(rows["final"]),
        hidden_family="mathematics",
    )
    ev, receipt = evaluate_task(task, prior=GrammarPrior())
    assert ev.witness_supported and ev.final_correct and receipt is not None
    return make_packet(
        task="domain:mathematics", arm="treatment", field_version=field_version,
        certified=True, candidate=ev.candidate, context_sig=ev.learned_context,
        receipt=receipt, pair_id=pair_id, measured="witness_and_final",
        domain="mathematics", query_bits=[1, 2, 3],
    ), ev


class Isolated(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nomad-molt-")
        self.data = Path(self._tmp.name)
        os.environ["NOMAD_DATA"] = str(self.data)
        for d in ("weights", "continuous", "society"):
            (self.data / d).mkdir(parents=True)

    def tearDown(self) -> None:
        os.environ.pop("NOMAD_DATA", None)
        os.environ.pop("NOMAD_LEARNER", None)
        self._tmp.cleanup()


class StalenessTests(unittest.TestCase):
    def test_mask_bounds_lag(self) -> None:
        from nomad.staleness import StalenessPolicy
        p = StalenessPolicy(max_lag=2, mode="mask")
        self.assertEqual(p.decide(0), (True, 1.0, None))
        self.assertEqual(p.decide(2)[0], True)
        self.assertEqual(p.decide(3), (False, 0.0, "stale"))
        self.assertEqual(p.decide(-1)[2], "future_version")

    def test_decay_discounts_and_gates(self) -> None:
        from nomad.staleness import StalenessPolicy
        p = StalenessPolicy(max_lag=5, mode="decay", decay=0.5, min_weight=0.25)
        self.assertAlmostEqual(p.weight(1), 0.5)
        self.assertTrue(p.decide(2)[0])
        self.assertEqual(p.decide(3)[2], "stale_discounted")
        t = StalenessPolicy(max_lag=5, mode="trunc", decay=0.5, min_weight=0.25)
        self.assertEqual(t.weight(4), 0.25)

    def test_importance_weight_modes(self) -> None:
        from nomad.staleness import importance_weight
        self.assertEqual(importance_weight(3.0, "none"), 1.0)
        self.assertEqual(importance_weight(3.0, "trunc", high=2.0), 2.0)
        self.assertEqual(importance_weight(0.1, "clip", 0.5, 2.0), 0.5)
        self.assertEqual(importance_weight(3.0, "mask", 0.5, 2.0), 0.0)
        with self.assertRaises(ValueError):
            importance_weight(1.0, "bogus")


class AdvantageTests(unittest.TestCase):
    def test_estimators(self) -> None:
        from nomad.advantage import estimator
        self.assertEqual(estimator("rloo")([0.0, 1.0]), [-1.0, 1.0])
        self.assertEqual(estimator("dr_grpo")([0.0, 1.0]), [-0.5, 0.5])
        self.assertEqual(estimator("rloo")([1.0]), [1.0])
        g = estimator("grpo")([1.0, 1.0])
        self.assertEqual(g, [0.0, 0.0])

    def test_twin_summary_filters_uniform_pairs(self) -> None:
        from nomad.advantage import twin_summary
        rows = [
            {"control": True, "treatment": True},
            {"control": False, "treatment": False},
            {"control": False, "treatment": True},
            {"control": True, "treatment": False},
            {"control": False, "treatment": True},
        ]
        s = twin_summary(rows)
        self.assertEqual(s["groups"], 5)
        self.assertEqual(s["informative_pairs"], 3)
        self.assertAlmostEqual(s["mean_treatment_advantage"], 1 / 3)
        self.assertAlmostEqual(s["all_pass_rate"], 0.2)


class QueueTests(Isolated):
    def test_control_cannot_enqueue_and_queue_is_bounded(self) -> None:
        from nomad import field_queue
        with self.assertRaises(ValueError):
            field_queue.enqueue({"arm": "control"})
        for i in range(5):
            out = field_queue.enqueue({"arm": "treatment", "packet_id": str(i)}, max_size=3)
        self.assertEqual(out, {"size": 3, "overflow_dropped": 1})
        self.assertEqual([r["packet_id"] for r in field_queue.peek()], ["2", "3", "4"])

    def test_claim_survives_crash_and_resumes(self) -> None:
        from nomad import field_queue
        field_queue.enqueue({"arm": "treatment", "packet_id": "a"})
        first = field_queue.claim()  # learner "dies" without ack
        self.assertEqual(len(first), 1)
        field_queue.enqueue({"arm": "treatment", "packet_id": "b"})
        resumed = field_queue.claim()
        self.assertEqual([r["packet_id"] for r in resumed], ["a", "b"])
        field_queue.ack()
        self.assertEqual(field_queue.peek(), [])


class LearnerTests(Isolated):
    def test_certified_packet_moves_prior_and_bumps_version(self) -> None:
        from nomad import field_queue
        from nomad.consolidate import consolidate, load_prior_safe
        from nomad.weights import load_packets
        packet, ev = _certified_packet()
        field_queue.enqueue(packet)
        field_queue.enqueue(packet)  # duplicate id
        report = consolidate()
        self.assertEqual(len(report["applied"]), 1)
        self.assertEqual(report["dropped"].get("duplicate"), 1)
        self.assertEqual(report["field_version_after"], 1)
        prior, source = load_prior_safe()
        self.assertEqual(source, "current")
        self.assertEqual(prior.witnessed, 1)
        self.assertIn("domain:mathematics", [p.label for p in load_packets()])

    def test_rejects_stale_uncertified_tampered_and_control(self) -> None:
        from nomad import field_queue
        from nomad.consolidate import consolidate
        from nomad.staleness import StalenessPolicy
        good, _ = _certified_packet(field_version=0)
        for _ in range(3):
            field_queue.bump_version()
        stale = dict(good, packet_id="stale")
        unc = dict(good, packet_id="unc", certified=False)
        bad = dict(good, packet_id="bad", field_version=3,
                   receipt=dict(good["receipt"], verdict="supported", receipt_hash="0" * 64))
        ctl = dict(good, packet_id="ctl", arm="control")
        path = field_queue.queue_path()
        path.write_text("".join(json.dumps(r) + "\n" for r in (stale, unc, bad, ctl)))
        report = consolidate(StalenessPolicy(max_lag=2))
        self.assertEqual(report["applied"], [])
        self.assertEqual(report["dropped"], {"stale": 1, "uncertified": 1, "bad_receipt": 1, "not_treatment": 1})
        self.assertEqual(report["field_version_after"], 3)
        self.assertFalse((self.data / "continuous" / "prior.json").exists())

    def test_corrupt_prior_falls_back_to_previous(self) -> None:
        from nomad import field_queue
        from nomad.consolidate import consolidate, load_prior_safe
        for v in range(2):
            p, _ = _certified_packet(field_version=v, pair_id=f"p{v}")
            field_queue.enqueue(p)
            consolidate()
        (self.data / "continuous" / "prior.json").write_text("{torn")
        prior, source = load_prior_safe()
        self.assertEqual(source, "previous")
        self.assertEqual(prior.witnessed, 1)


class PendingStalenessTests(Isolated):
    def test_old_unpaired_row_is_discarded_not_paired(self) -> None:
        from nomad.scoreboard import record_arm, recent
        pending = self.data / "scoreboard_pending.json"
        pending.write_text(json.dumps({"domain:mathematics": {"treatment": True, "ts": "2026-11-20T03:31:45Z"}}))
        self.assertIsNone(record_arm("domain:mathematics", "control", False, pair_id="new"))
        row = record_arm("domain:mathematics", "treatment", False, pair_id="new")
        self.assertIsNotNone(row)
        self.assertEqual(row["delta"], 0)
        self.assertEqual(row["pair_id"], "new")
        disc = (self.data / "scoreboard_discarded.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(disc[0])["reason"], "pair_id_mismatch")
        self.assertEqual(len(recent()), 1)

    def test_prune_pending_drops_aged_rows(self) -> None:
        from nomad.scoreboard import prune_pending
        pending = self.data / "scoreboard_pending.json"
        pending.write_text(json.dumps({"old": {"treatment": True, "ts": "2026-01-01T00:00:00Z"}}))
        self.assertEqual(prune_pending(), 1)
        self.assertEqual(json.loads(pending.read_text()), {})


class LoopWiringTests(Isolated):
    def test_inline_learner_mode_matches_queue_mode(self) -> None:
        os.environ["NOMAD_LEARNER"] = "inline"
        from nomad.continuous import pair
        from nomad.weights import Packet, append_packet
        append_packet(Packet(set(range(1100, 1130)), 1, "domain:mathematics",
                             {"measured": "seeded", "context": {"domain": "mathematics", "operator": "Mult"}}))
        result = pair()
        self.assertTrue(result["learning_measurement"]["paired"])
        self.assertEqual(result["control"].get("enqueued"), None)
        if result["treatment"]["certified"]:
            self.assertIn("consolidated", result["treatment"])
            self.assertGreater(result["treatment"]["prior_witnessed_after"], 0)


if __name__ == "__main__":
    unittest.main()
