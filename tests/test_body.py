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


class GateTests(Isolated):
    """Nov 21 2026 restart storm: standby runs each queued a successor."""

    def setUp(self) -> None:
        super().setUp()
        self.out = self.data / "gh_output"
        self.out.write_text("")
        os.environ["GITHUB_OUTPUT"] = str(self.out)
        os.environ["NOMAD_HOST_ID"] = "gh-200"

    def tearDown(self) -> None:
        os.environ.pop("GITHUB_OUTPUT", None)
        super().tearDown()

    def _outputs(self) -> dict:
        return dict(l.split("=", 1) for l in self.out.read_text().splitlines() if "=" in l)

    def test_standby_when_live_holder_and_no_successor(self) -> None:
        from nomad import lease
        from nomad.body import gate, run
        lease.write("gh-100")  # fresh, unreleased, 0 cycles
        for status in (None, "in_progress", "queued", "unknown"):
            self.out.write_text("")
            g = gate(holder_status=status)
            self.assertTrue(g["standby"], status)
            self.assertEqual(self._outputs()["standby"], "yes")
        res = run(0.01, push=False, max_cycles=2, cycle_gap_s=0, evolve=False, holder_status="in_progress")
        self.assertEqual(res["status"], "standby")
        self.assertEqual(self._outputs().get("successor"), "no")
        self.assertEqual(lease.read()["host"], "gh-100")

    def test_workflow_queues_successor_only_after_gate_says_no(self) -> None:
        wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "nomad-body.yml").read_text()
        gate_at = wf.index("python -m nomad.body gate")
        queue_at = wf.index("name: Queue successor first")
        live_at = wf.index("name: Live")
        self.assertLess(gate_at, queue_at)
        self.assertLess(queue_at, live_at)
        queue_step = wf[queue_at:live_at]
        self.assertIn("steps.gate.outputs.standby == 'no'", queue_step)
        self.assertIn("--holder-status", wf[live_at:])

    def test_stale_lease_is_taken_over(self) -> None:
        from nomad import lease
        from nomad.body import gate, run
        lease.write("gh-100", cycles=0)
        row = lease.read()
        row["heartbeat"] = "2026-01-01T00:00:00Z"
        lease.path().write_text(json.dumps(row))
        g = gate(holder_status="in_progress")  # stale wins even if the run looks alive
        self.assertFalse(g["standby"])
        self.assertEqual(self._outputs()["standby"], "no")
        res = run(0.01, push=False, max_cycles=1, cycle_gap_s=0, evolve=False)
        self.assertEqual(res["status"], "done")
        self.assertEqual(lease.read()["host"], "gh-200")

    def test_orphaned_fresh_lease_is_taken_over_only_for_completed_gh_run(self) -> None:
        from nomad import lease
        from nomad.body import gate, run
        lease.write("gh-100", cycles=0)  # cancelled run left a fresh lease
        self.assertFalse(gate(holder_status="completed")["standby"])
        res = run(0.01, push=False, max_cycles=1, cycle_gap_s=0, evolve=False, holder_status="completed")
        self.assertEqual(res["status"], "done")
        self.assertEqual(lease.read()["host"], "gh-200")
        lease.write("james-pc-1")  # non-GitHub hosts are judged by heartbeat only
        self.assertTrue(gate(holder_status="completed")["standby"])

    def test_gate_cli_empty_status_means_unknown(self) -> None:
        from nomad import lease
        from nomad.body import main
        lease.write("gh-100")
        self.assertEqual(main(["gate", "--holder-status", ""]), 0)
        self.assertEqual(self._outputs()["standby"], "yes")


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


class EvolveStepDispatchTests(Isolated):
    """body.evolve_step routing after the guard, with the slow organs mocked (the revert drill
    covers the real guard -> git revert -> push path; selfedit/evolve have their own tests)."""

    def _run(self, *, guard, se_should, ev_should, push=True):
        from unittest import mock
        from nomad import body, evolve, hostgit, selfedit
        se_res = {"accepted": True, "reason": None, "gene": "inv_k", "id": "se1",
                  "before": {"inv_k": 4}, "after": {"inv_k": 6},
                  "dev_before": {"certified": 1}, "dev_after": {"certified": 2}, "sandbox_clean": True}
        ev_res = {"accepted": True, "gene": "decay", "id": "ev1", "before": {}, "after": {}}
        with mock.patch.object(evolve, "guard", return_value=guard), \
             mock.patch.object(selfedit, "should", return_value=se_should), \
             mock.patch.object(selfedit, "attempt", return_value=se_res) as se_att, \
             mock.patch.object(evolve, "should_evolve", return_value=ev_should), \
             mock.patch.object(evolve, "evolve", return_value=ev_res) as ev_att, \
             mock.patch.object(hostgit, "commit") as commit, \
             mock.patch.object(hostgit, "find_commit", return_value="deadbeef00") as find, \
             mock.patch.object(hostgit, "revert", return_value=True) as rev:
            out = body.evolve_step(push=push)
        return out, se_att, ev_att, commit, find, rev

    def test_due_selfedit_runs_instead_of_evolve_and_commits_genome(self) -> None:
        out, se, ev, commit, _, _ = self._run(guard={"decision": "none"}, se_should=True, ev_should=True)
        se.assert_called_once()
        ev.assert_not_called()
        self.assertTrue(out["selfedit"]["accepted"])
        msgs = [c.args[0] for c in commit.call_args_list]
        self.assertTrue(any(m.startswith("nomad-evolve-log: selfedit inv_k accepted=True") for m in msgs), msgs)
        self.assertTrue(any(m.startswith("nomad-evolve: se1 selfedit inv_k 4 -> 6") for m in msgs), msgs)

    def test_evolve_runs_when_selfedit_not_due(self) -> None:
        out, se, ev, commit, _, _ = self._run(guard={"decision": "none"}, se_should=False, ev_should=True)
        se.assert_not_called()
        ev.assert_called_once()
        msgs = [c.args[0] for c in commit.call_args_list]
        self.assertTrue(any(m.startswith("nomad-evolve: ev1 decay") for m in msgs), msgs)

    def test_revert_decision_reverts_then_nothing_due_means_no_mutation(self) -> None:
        out, se, ev, commit, find, rev = self._run(guard={"decision": "revert", "id": "g1"},
                                                    se_should=False, ev_should=False)
        find.assert_called_once_with("^nomad-evolve: g1")
        rev.assert_called_once()
        self.assertIn("nomad-revert: g1", rev.call_args.args[1])
        se.assert_not_called(); ev.assert_not_called()
        self.assertNotIn("selfedit", out); self.assertNotIn("evolve", out)

    def test_no_push_never_touches_git(self) -> None:
        out, se, ev, commit, find, rev = self._run(guard={"decision": "keep", "id": "g2"},
                                                    se_should=True, ev_should=False, push=False)
        se.assert_called_once()
        commit.assert_not_called(); rev.assert_not_called()


if __name__ == "__main__":
    unittest.main()
