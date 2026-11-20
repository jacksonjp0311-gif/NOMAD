import copy
import importlib.util
import json
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "feed" / "nomad_feed_check.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("nomad_feed_check", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StandaloneFeedCheckTests(unittest.TestCase):
    """The stdlib-only consumer checker must agree with NOMAD without importing it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.chk = _load_checker()
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
        from nomad import feed
        cls.feed = feed
        feed.publish(p)
        feed.publish(p)
        cls.packet = json.loads((feed.feed_root() / "latest.json").read_text())
        cls.manifest = feed.load_manifest()

    @classmethod
    def tearDownClass(cls) -> None:
        for k, v in cls._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_checker_does_not_import_nomad(self) -> None:
        src = CHECKER.read_text()
        imports = [l.strip() for l in src.splitlines() if l.startswith(("import ", "from "))]
        self.assertTrue(imports)
        for line in imports:
            self.assertNotIn("nomad", line)
            self.assertIn(line.split()[1].split(".")[0], {"hashlib", "json", "sys"})

    def test_agrees_with_nomad_on_published_packet(self) -> None:
        out = self.chk.check(self.packet, self.manifest)
        self.assertTrue(out["ok"], out["failures"])
        self.assertTrue(self.feed.verify(self.packet)["ok"])
        self.assertFalse(out["witness_reattested"])

    def test_rejects_tampering(self) -> None:
        def rehash(p):
            p["packet_sha256"] = self.chk.packet_hash(p)
            return p

        p = copy.deepcopy(self.packet)
        p["scores"]["note"] = "edited"
        self.assertIn("packet_sha256", self.chk.check(p)["failures"])

        p = copy.deepcopy(self.packet)
        row = p["evidence"][0]["task"]["final"][0]
        row[1] = row[1] + 1 if isinstance(row[1], int) else ("x" + row[1] if isinstance(row[1], str) else row[1] + [1])
        tid = p["evidence"][0]["task"]["task_id"]
        self.assertIn("evidence:%s:rows" % tid, self.chk.check(rehash(p))["failures"])

        p = copy.deepcopy(self.packet)
        p["blocks"][0]["certified_in"] = ["no-such-task"]
        self.assertIn("block:%s:no_certified_use" % p["blocks"][0]["block_id"], self.chk.check(rehash(p))["failures"])

        p = rehash(copy.deepcopy(self.packet))
        self.assertIn("manifest:not_in_chain", self.chk.check(p, {"packets": []})["failures"])

    def test_op_table_matches_nomad_world(self) -> None:
        from nomad import world
        self.assertEqual(set(self.chk.OPS), set(world.OPS))
        for name, op in world.OPS.items():
            self.assertEqual(tuple(self.chk.OPS[name][0]), op.args, name)
            self.assertEqual(self.chk.OPS[name][1], op.out, name)
        rng = random.Random(7)
        gen = {
            "int": lambda: rng.choice([0, 1, -1, 2, 3, rng.randint(-50, 50), rng.randint(-10**6, 10**6)]),
            "str": lambda: "".join(rng.choice("aBz Q9") for _ in range(rng.randint(0, 40))),
            "list": lambda: tuple(rng.randint(-20, 20) for _ in range(rng.randint(0, 6))),
        }
        for name, op in world.OPS.items():
            for _ in range(300):
                kids = [gen[t]() for t in op.args]
                row = {"v%d" % i: v for i, v in enumerate(kids)}
                tree = [name] + [["var", "v%d" % i] for i in range(len(kids))]
                try:
                    want = world.run(tree, row)
                except world.Invalid:
                    want = "INVALID"
                try:
                    got = self.chk.run(tree, row)
                except self.chk.Invalid:
                    got = "INVALID"
                self.assertEqual(got, want, (name, kids))

    def test_cli_exit_codes(self) -> None:
        import subprocess
        import sys
        latest = self.feed.feed_root() / "latest.json"
        man = self.feed.feed_root() / "manifest.json"
        ok = subprocess.run([sys.executable, str(CHECKER), str(latest), "--manifest", str(man)],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        bad = subprocess.run([sys.executable, str(CHECKER), str(Path(self.tmp) / "missing.json")],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
