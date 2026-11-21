"""Organism health report and heartbeat event log."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


class OrganismTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.data = Path(self._tmp.name)
        os.environ["NOMAD_DATA"] = str(self.data)
        for d in ("weights", "continuous", "society"):
            (self.data / d).mkdir(parents=True)

    def tearDown(self) -> None:
        os.environ.pop("NOMAD_DATA", None)
        os.environ.pop("NOMAD_LEARNER", None)
        self._tmp.cleanup()

    def test_status_after_one_full_cycle(self) -> None:
        from nomad.continuous import pair, sleep
        from nomad.organism import status
        pair()
        sleep(arm="treatment")
        r = status()
        self.assertTrue((self.data / "organism.json").exists())
        self.assertIsNotNone(r["sense"]["last_pair"])
        self.assertIsNotNone(r["sense"]["last_sleep"])
        self.assertGreaterEqual(r["remember"]["field_version"], 1)
        self.assertEqual(r["remember"]["queued"], 0)
        self.assertEqual(set(r["remember"]["world_heldout"]),
                         {"absdiff", "quartic_sum", "last_first_upper", "sum_minus_max"})
        self.assertGreaterEqual(r["act_verify"]["world_twin"]["groups"], 1)

    def test_heartbeat_gap_event(self) -> None:
        from nomad.organism import main
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):   # synthetic fixture event: keep it out of CI logs
            main(["event", "heartbeat_gap", "--minutes", "120", "--action", "redispatched_awake"])
        rows = [json.loads(l) for l in (self.data / "organism_events.jsonl").read_text().splitlines()]
        self.assertEqual(rows[-1]["kind"], "heartbeat_gap")
        self.assertEqual(rows[-1]["minutes"], 120.0)
        status = json.loads((self.data / "organism.json").read_text())
        self.assertEqual(status["heartbeat"]["recent_events"][-1]["action"], "redispatched_awake")


if __name__ == "__main__":
    unittest.main()
