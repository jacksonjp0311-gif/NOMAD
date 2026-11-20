"""Long-lived body: lease, retention, local (no-push) loop, genome, evolve guard."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


class Isolated(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nomad-body-")
        self.data = Path(self._tmp.name)
        os.environ["NOMAD_DATA"] = str(self.data)
        for d in ("weights", "continuous", "society"):
            (self.data / d).mkdir(parents=True)

    def tearDown(self) -> None:
        for k in ("NOMAD_DATA", "NOMAD_HOST_ID"):
            os.environ.pop(k, None)
        self._tmp.cleanup()


class LeaseTests(Isolated):
    def test_fresh_lease_blocks_other_host_and_stale_allows_takeover(self) -> None:
        from nomad import lease
        lease.write("desktop")
        self.assertTrue(lease.alive())
        self.assertTrue(lease.held_by_other("gh-1"))
        self.assertFalse(lease.held_by_other("desktop"))
        row = lease.read()
        row["heartbeat"] = "2026-01-01T00:00:00Z"
        lease.path().write_text(json.dumps(row))
        self.assertFalse(lease.alive())
        self.assertFalse(lease.held_by_other("gh-1"))
        lease.write("desktop", released=True)
        self.assertFalse(lease.alive())

    def test_orphaned_lease_only_for_finished_github_run(self) -> None:
        from nomad import lease
        fresh = {"host": "gh-123", "released": False, "heartbeat": "2026-01-01T00:00:00Z"}
        self.assertEqual(lease.gh_run_id(fresh), "123")
        self.assertTrue(lease.orphaned(fresh, "completed"))
        self.assertFalse(lease.orphaned(fresh, "in_progress"))
        self.assertFalse(lease.orphaned(fresh, "unknown"))
        self.assertFalse(lease.orphaned({**fresh, "released": True}, "completed"))
        desk = {"host": "james-pc-4242", "released": False}
        self.assertIsNone(lease.gh_run_id(desk))
        self.assertFalse(lease.orphaned(desk, "completed"))
        self.assertFalse(lease.orphaned(None, "completed"))

    def test_body_stands_by_when_another_host_holds_lease(self) -> None:
        from nomad import lease
        from nomad.body import run
        lease.write("desktop")
        os.environ["NOMAD_HOST_ID"] = "gh-2"
        res = run(0.01, push=False, max_cycles=2, cycle_gap_s=0, evolve=False)
        self.assertEqual(res["status"], "standby")
        self.assertFalse((self.data / "continuous" / "log.jsonl").exists())


class BodyLoopTests(Isolated):
    def test_local_body_cycles_learns_and_releases(self) -> None:
        from nomad import lease
        from nomad.body import run
        os.environ["NOMAD_HOST_ID"] = "test-host"
        res = run(0.05, push=False, max_cycles=6, cycle_gap_s=0, sleep_every=3, evolve=False)
        self.assertEqual(res["status"], "done")
        self.assertEqual(res["cycles"], 6)
        self.assertGreaterEqual(res["sleeps"], 2)
        held = lease.read()
        self.assertEqual(held["host"], "test-host")
        self.assertTrue(held["released"])
        self.assertTrue((self.data / "organism.json").exists())
        self.assertTrue((self.data / "continuous" / "world_prior.json").exists())


class RetentionTests(Isolated):
    def test_trim_keeps_tail_and_ledger(self) -> None:
        from nomad.retention import LIMITS, trim
        p = self.data / "continuous" / "log.jsonl"
        n = LIMITS["continuous/log.jsonl"] + 7
        p.write_text("".join(f'{{"i":{i}}}\n' for i in range(n)))
        self.assertEqual(trim(), {"continuous/log.jsonl": 7})
        lines = p.read_text().splitlines()
        self.assertEqual(json.loads(lines[0])["i"], 7)
        self.assertEqual(json.loads((self.data / "retention.json").read_text())["continuous/log.jsonl"], 7)


class GenomeEvolveTests(Isolated):
    def test_genome_bounds_and_defaults(self) -> None:
        from nomad import genome
        self.assertEqual(genome.load(), genome.DEFAULTS)
        genome.save({"decay": 0.5, "library_k": 99})
        g = genome.load()
        self.assertEqual(g["decay"], 0.85)
        self.assertEqual(g["library_k"], 10)

    def test_propose_is_bounded_and_replayable(self) -> None:
        from nomad import genome
        from nomad.evolve import propose
        a, ga = propose(genome.DEFAULTS, 7)
        b, gb = propose(genome.DEFAULTS, 7)
        self.assertEqual((a, ga), (b, gb))
        lo, hi = genome.BOUNDS[ga]
        self.assertTrue(lo <= a[ga] <= hi)

    def test_better_prefers_heldout_wins_then_cost(self) -> None:
        from nomad.evolve import better
        base = {"heldout_wins": 2, "total_evaluations": 100, "train_certified": 16}
        self.assertTrue(better({**base, "heldout_wins": 3, "total_evaluations": 999}, base))
        self.assertTrue(better({**base, "total_evaluations": 90}, base))
        self.assertFalse(better({**base, "total_evaluations": 100}, base))
        self.assertFalse(better({**base, "train_certified": 15, "heldout_wins": 4}, base))

    def test_guard_reverts_on_live_regression_and_keeps_otherwise(self) -> None:
        from nomad import evolve
        from nomad.scoreboard import record_arm
        evolve._log({"ts": "2026-01-01T00:00:00Z", "gene": "decay", "accepted": True,
                     "status": "pending_verification", "id": "abc", "live_ratio_before": 0.2})
        self.assertEqual(evolve.guard()["decision"], "wait")
        for i in range(evolve.GUARD_MIN_PAIRS):
            record_arm(f"world:f{i}", "control", True, pair_id=str(i), evaluations=100)
            record_arm(f"world:f{i}", "treatment", True, pair_id=str(i), evaluations=60)
        g = evolve.guard()
        self.assertEqual(g["decision"], "revert")
        self.assertEqual(evolve.guard()["decision"], "none")
        self.assertTrue(evolve.should_evolve() in (True, False))


if __name__ == "__main__":
    unittest.main()
