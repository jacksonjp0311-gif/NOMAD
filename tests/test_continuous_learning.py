"""Tests for true-twin measurement, prior bias, and the frozen held-out family.

All field I/O is redirected to a temporary NOMAD_DATA directory so these
tests never mutate the repository's live field.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


class DataIsolationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nomad-field-")
        self.data = Path(self._tmp.name)
        os.environ["NOMAD_DATA"] = str(self.data)
        (self.data / "weights").mkdir(parents=True)
        (self.data / "continuous").mkdir(parents=True)
        (self.data / "society").mkdir(parents=True)

    def tearDown(self) -> None:
        os.environ.pop("NOMAD_DATA", None)
        self._tmp.cleanup()


class WeightTests(DataIsolationTest):
    def test_overlap_readout_and_reinforce(self) -> None:
        from nomad.weights import Packet, append_packet, load_packets, readout, reinforce, accumulate

        append_packet(Packet({1, 2, 3}, 1, "alpha", {"measured": "witness_and_final"}))
        append_packet(Packet({3, 4, 5}, 2, "beta", {"measured": "witness_and_final"}))
        packets = load_packets()
        self.assertEqual(len(packets), 2)
        self.assertEqual(packets[0].overlap({1, 2, 9}), 2)
        hits = readout({3, 4, 9}, k=2)
        self.assertEqual(hits[0]["label"], "beta")
        self.assertEqual(hits[0]["overlap"], 4)  # 2 bits * count 2
        self.assertEqual(reinforce("beta", 1), 3)
        self.assertEqual(load_packets()[1].count, 3)
        accumulate({7, 8}, True, label="new", measured="witness_and_final")
        labels = [p.label for p in load_packets()]
        self.assertIn("new", labels)

    def test_accumulate_ignores_failure(self) -> None:
        from nomad.weights import accumulate, load_packets

        accumulate({1}, False, label="nope")
        self.assertEqual(load_packets(), [])


class OrbitTests(DataIsolationTest):
    def test_orbit_pulls_related_packet_without_query_overlap(self) -> None:
        from nomad.orbit import orbit
        from nomad.weights import Packet, append_packet

        append_packet(Packet({10, 11, 12}, 1, "direct", {"context": {"operator": "Mult"}}))
        append_packet(Packet({20, 21, 22}, 1, "neighbor", {"context": {"operator": "Mult"}}))
        append_packet(Packet({30}, 1, "unrelated", {"context": {"operator": "Add"}}))
        result = orbit({10, 11}, k=8)
        labels = [row["label"] for row in result]
        self.assertIn("direct", labels)
        self.assertIn("neighbor", labels)
        # neighbor shares no query bits; it enters by shared operator
        neighbor = next(row for row in result if row["label"] == "neighbor")
        self.assertEqual(neighbor["overlap"], 0)
        self.assertTrue(neighbor["orbit"])


class ScoreboardTests(DataIsolationTest):
    def test_unpaired_arm_is_not_learning(self) -> None:
        from nomad.scoreboard import record_arm, recent

        row = record_arm("domain:mathematics", "treatment", True)
        self.assertIsNone(row)
        self.assertEqual(recent(), [])
        pending = json.loads((self.data / "scoreboard_pending.json").read_text())
        self.assertIn("domain:mathematics", pending)

    def test_pair_records_real_delta(self) -> None:
        from nomad.scoreboard import record_arm, recent

        self.assertIsNone(record_arm("task-a", "control", False))
        paired = record_arm("task-a", "treatment", True)
        self.assertIsNotNone(paired)
        assert paired is not None
        self.assertEqual(paired["treatment"], True)
        self.assertEqual(paired["control"], False)
        self.assertEqual(paired["delta"], 1)
        self.assertEqual(paired["kind"], "certified")
        self.assertEqual(paired["task"], "task-a")
        self.assertEqual(recent(1)[0]["delta"], 1)
        pending = json.loads((self.data / "scoreboard_pending.json").read_text())
        self.assertNotIn("task-a", pending)

    def test_no_hard_coded_control_failure(self) -> None:
        from nomad.scoreboard import record_arm

        record_arm("task-b", "control", True)
        paired = record_arm("task-b", "treatment", True)
        assert paired is not None
        self.assertEqual(paired["control"], True)
        self.assertEqual(paired["delta"], 0)


class PriorBiasTests(DataIsolationTest):
    def test_public_success_does_not_move_order(self) -> None:
        from nomad.genesis import GrammarPrior

        prior = GrammarPrior()
        prior.operator.update(0, "Mult", True)
        self.assertEqual(prior.witnessed, 0)
        self.assertEqual(prior.order(0), ("Add", "Sub", "Mult"))

    def test_witnessed_multiply_training_moves_order_and_beats_cold_heldout(self) -> None:
        from nomad.heldout import compare_mechanism, train_multiply_prior

        prior = train_multiply_prior()
        self.assertGreater(prior.witnessed, 0)
        # Training tasks share the return-0 failure signature used by held-out.
        order = prior.order(1216)
        self.assertEqual(order[0], "Mult")
        result = compare_mechanism()
        self.assertEqual(result["family"], "square_product")
        self.assertEqual(result["max_eval"], 2000)
        self.assertFalse(result["cold"]["certified"])
        self.assertFalse(result["cold"]["public_correct"])
        self.assertTrue(result["field"]["certified"])
        self.assertTrue(result["field"]["public_correct"])
        self.assertTrue(result["advantage"])
        self.assertEqual(result["advantage_kind"], "certified_correctness")
        self.assertEqual(result["field"]["candidate"], "((x*x)*(y*y))")
        self.assertLessEqual(result["field"]["evaluations"], 2000)
        self.assertGreater(result["cold"]["evaluations"], result["field"]["evaluations"])

    def test_prior_snapshot_roundtrip_preserves_witnessed(self) -> None:
        from nomad.genesis import load_prior_file, save_prior_file
        from nomad.heldout import train_multiply_prior

        prior = train_multiply_prior()
        path = self.data / "continuous" / "prior.json"
        save_prior_file(prior, path)
        loaded = load_prior_file(path)
        self.assertEqual(loaded.witnessed, prior.witnessed)
        self.assertEqual(loaded.order(1216)[0], "Mult")

    def test_legacy_snapshot_without_witnessed_stays_cold(self) -> None:
        from nomad.genesis import load_prior_file

        path = self.data / "continuous" / "prior.json"
        path.write_text(json.dumps({
            "contextual": True,
            "global": {"Mult": {"success": 5, "failure": 0}},
            "contexts": {},
        }))
        prior = load_prior_file(path)
        self.assertEqual(prior.witnessed, 0)
        self.assertEqual(prior.order(1216), ("Add", "Sub", "Mult"))


class PairAndDomainTests(DataIsolationTest):
    def test_pair_writes_scoreboard_and_control_does_not_update_field(self) -> None:
        from nomad.continuous import pair
        from nomad.weights import Packet, append_packet, load_packets
        from nomad.scoreboard import recent

        # Seed a mathematics domain packet so the proposer acts under that domain.
        append_packet(Packet(
            set(range(1100, 1130)),
            1,
            "domain:mathematics",
            {"measured": "seeded", "predicted": "domain prior", "context": {"domain": "mathematics", "operator": "Mult"}},
        ))
        result = pair()
        self.assertEqual(result["proposal"]["domain"], "mathematics")
        self.assertEqual(result["treatment"]["acting_domain"], "mathematics")
        self.assertEqual(result["control"]["acting_domain"], "mathematics")
        self.assertEqual(result["treatment"]["bias"]["reason"], "domain:mathematics")
        self.assertEqual(result["control"]["bias"]["reason"], "domain:mathematics")
        self.assertEqual(result["control"]["prior_witnessed"], 0)
        self.assertEqual(result["control"]["operator_order"][0], "Add")
        self.assertTrue(result["learning_measurement"]["paired"])
        self.assertIn("delta", result["learning_measurement"])
        board = recent(1)
        self.assertEqual(len(board), 1)
        self.assertEqual(board[0]["kind"], "certified")
        # Control must not write packets or prior. Treatment may, if certified.
        labels = [p.label for p in load_packets()]
        self.assertIn("domain:mathematics", labels)
        if result["treatment"]["certified"]:
            # Awake is an actor: it enqueues a versioned packet. Sleep is the
            # single learner that moves the prior.
            self.assertIn("enqueued", result["treatment"])
            from nomad.continuous import sleep
            from nomad.genesis import load_prior_file
            slept = sleep(arm="treatment")
            self.assertEqual(len(slept["learner"]["applied"]), 1)
            prior = load_prior_file(self.data / "continuous" / "prior.json")
            self.assertGreater(prior.witnessed, 0)
            self.assertEqual(prior.order(result["treatment"]["context_sig"])[0], "Mult")
        else:
            # If treatment was not certified, the field prior must still be absent or unwitnessed.
            prior_path = self.data / "continuous" / "prior.json"
            if prior_path.exists():
                from nomad.genesis import load_prior_file
                self.assertEqual(load_prior_file(prior_path).witnessed, 0)

    def test_gate_rejects_public_only(self) -> None:
        from nomad.society import gate

        self.assertEqual(
            gate({"public_correct": True, "witness_supported": False, "final_correct": False}),
            {"pass": False, "reason": "public_only_not_certified"},
        )
        self.assertEqual(
            gate({"public_correct": True, "witness_supported": True, "final_correct": True}),
            {"pass": True, "reason": "witness_and_final"},
        )


if __name__ == "__main__":
    unittest.main()
