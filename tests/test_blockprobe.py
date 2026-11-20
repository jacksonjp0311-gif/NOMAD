"""BLOCKPROBE: learned blocks tried before stage 1 finishes; off switch; cheap tasks untouched."""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import science_suite as SS  # noqa: E402
from nomad import world as W  # noqa: E402
from nomad.world import WorldPrior, evaluate, synthesize  # noqa: E402


def _prior_with(task, blocks):
    p = WorldPrior()
    sig = [list(i) for i in task.inputs]
    for i, b in enumerate(blocks):
        p.library[f"Lt{i}"] = b
        p.library_sig[f"Lt{i}"] = sig
        p.library_uses[f"Lt{i}"] = 1.0
    return p


class BlockProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suite, _, hard = SS.load()
        cls.task = next(t for t in hard if t.family == "sci_d_rest")   # a*t^2/2, cold misses @10k

    def tearDown(self):
        os.environ.pop("NOMAD_BLOCKPROBE", None)

    def test_probe_finds_block_program_and_witness_certifies(self):
        p = _prior_with(self.task, [["mul", ["var", "a"], ["var", "t"]]])
        ev, _ = evaluate(self.task, prior=p, max_eval=10000, casesplit=False)
        self.assertTrue(ev.certified)
        self.assertEqual(ev.via, "blockprobe")
        self.assertLessEqual(ev.evaluations, 10000)
        cold, _ = evaluate(self.task, max_eval=10000)
        self.assertFalse(cold.certified)

    def test_off_switch_restores_previous_path(self):
        p = _prior_with(self.task, [["mul", ["var", "a"], ["var", "t"]]])
        os.environ["NOMAD_BLOCKPROBE"] = "off"
        s = synthesize(self.task, prior=p, max_eval=10000, casesplit=False)
        self.assertIsNone(s.tree)
        self.assertEqual(s.evaluations, 10000)

    def test_task_solved_before_trigger_is_untouched(self):
        from nomad.world_tasks import by_family
        t = by_family("pick_gt")                       # cold: 3,283 evaluations at size 6
        p = _prior_with(t, [["sub", ["var", "x"], ["var", "y"]]])
        cold = synthesize(t, max_eval=10000)
        self.assertLess(cold.evaluations, W.BLOCKPROBE_TRIGGER * 10000)
        on = synthesize(t, prior=p, max_eval=10000, casesplit=False)
        os.environ["NOMAD_BLOCKPROBE"] = "off"
        off = synthesize(t, prior=p, max_eval=10000, casesplit=False)
        self.assertEqual((on.evaluations, on.tree), (off.evaluations, off.tree))
        self.assertNotEqual(on.via, "blockprobe")

    def test_no_library_no_probe(self):
        s = synthesize(self.task, prior=WorldPrior(), max_eval=10000, casesplit=False)
        self.assertIsNone(s.tree)
        self.assertNotEqual(s.via, "blockprobe")

    def test_science_probe_inputs_cover_suite_signatures(self):
        from nomad.variation import PROBES, sig_key
        suite, easy, hard = SS.load()
        for t in easy + hard:
            self.assertIn(sig_key(t.inputs), PROBES)


if __name__ == "__main__":
    unittest.main()
