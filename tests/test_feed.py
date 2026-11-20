import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


class FeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.mkdtemp()
        cls._env = {k: os.environ.get(k) for k in ("NOMAD_DATA", "NOMAD_FEED")}
        os.environ["NOMAD_DATA"] = cls.tmp
        os.environ.pop("NOMAD_FEED", None)
        from nomad.world import OPSETS, WorldPrior, evaluate
        from nomad.world_tasks import all_training
        p = WorldPrior()
        for t in all_training():
            ev, r = evaluate(t, prior=p)
            if ev.certified:
                p.add_witnessed(ev.tree, r, family=t.family, opset=OPSETS[t.opset], inputs=t.inputs)
        cls.prior = p
        from nomad import feed
        cls.feed = feed
        cls.res1 = feed.publish(p)
        cls.res2 = feed.publish(p)

    @classmethod
    def tearDownClass(cls) -> None:
        for k, v in cls._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _latest(self) -> dict:
        return json.loads((self.feed.feed_root() / "latest.json").read_text())

    def test_feed_lives_under_test_data_not_repo(self) -> None:
        self.assertEqual(self.feed.feed_root(), Path(self.tmp) / "feed")

    def test_publish_versions_and_chain(self) -> None:
        self.assertTrue(self.res1["published"])
        self.assertEqual(self.res2["feed_version"], 2)
        man = self.feed.load_manifest()
        self.assertEqual(man["latest"], 2)
        p = self._latest()
        self.assertEqual(p["prev_sha256"], man["packets"][0]["sha256"])
        self.assertEqual(p["packet_sha256"], self.feed.packet_hash(p))

    def test_only_certified_blocks_and_evidence(self) -> None:
        p = self._latest()
        self.assertTrue(p["evidence"])
        for e in p["evidence"]:
            self.assertEqual(e["receipt"]["verdict"], "supported")
            self.assertIn("evaluations", e["control"])
        for b in p["blocks"]:
            self.assertTrue(b["certified_in"])
        self.assertLessEqual(len(p["blocks"]), len(self.prior.library))

    def test_verify_passes_and_catches_tampering(self) -> None:
        p = self._latest()
        self.assertTrue(self.feed.verify(p)["ok"])
        bad = copy.deepcopy(p)
        bad["evidence"][0]["program"] = ["var", bad["evidence"][0]["task"]["inputs"][0][0]]
        bad["packet_sha256"] = self.feed.packet_hash(bad)  # attacker fixes the outer hash
        rep = self.feed.verify(bad)
        self.assertFalse(rep["ok"])
        rows = copy.deepcopy(p)
        rows["evidence"][0]["task"]["final"][0][1] = "tampered"
        rows["packet_sha256"] = self.feed.packet_hash(rows)
        self.assertFalse(self.feed.verify(rows)["ok"])
        outer = copy.deepcopy(p)
        outer["scores"]["note"] = "edited"
        self.assertIn("packet_sha256", self.feed.verify(outer)["failures"])

    def test_block_without_certified_use_is_rejected(self) -> None:
        p = copy.deepcopy(self._latest())
        if not p["blocks"]:
            self.skipTest("no blocks")
        p["blocks"][0]["certified_in"] = ["nope"]
        p["packet_sha256"] = self.feed.packet_hash(p)
        self.assertFalse(self.feed.verify(p)["ok"])

    def test_task_json_roundtrip(self) -> None:
        from nomad.world_tasks import all_training
        for t in all_training():
            self.assertEqual(self.feed.task_from_json(json.loads(json.dumps(self.feed.task_to_json(t)))), t)


if __name__ == "__main__":
    unittest.main()
