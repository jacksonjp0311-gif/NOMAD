"""BRIDGE (docs/BRIDGE.md): int <-> str bridge operators, domain, and the off switch."""
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from nomad import bridge as B  # noqa: E402
from nomad import text as T  # noqa: E402
from nomad import world as W  # noqa: E402


class _Env:
    def __init__(self, **kv):
        self.kv, self.old = kv, {}

    def __enter__(self):
        for k, v in self.kv.items():
            self.old[k] = os.environ.get(k)
            os.environ[k] = v

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def R(tree, **row):
    return W.run(tree, row)


class BridgeOps(unittest.TestCase):
    def test_semantics(self):
        s = ["var", "s"]
        i = ["var", "i"]
        self.assertEqual(R(["at", s, i], s="nomad", i=2), "m")
        self.assertEqual(R(["take", s, i], s="nomad", i=2), "no")
        self.assertEqual(R(["take", s, i], s="nomad", i=0), "")
        self.assertEqual(R(["take", s, i], s="nomad", i=9), "nomad")
        self.assertEqual(R(["drop", s, i], s="nomad", i=2), "mad")
        self.assertEqual(R(["srep", s, i], s="ab", i=3), "ababab")
        self.assertEqual(R(["itos", i], i=407), "407")
        self.assertEqual(R(["itos", i], i=0), "0")

    def test_partial(self):
        s, i = ["var", "s"], ["var", "i"]
        for t, row in ((["at", s, i], dict(s="abc", i=3)), (["at", s, i], dict(s="abc", i=-1)),
                       (["take", s, i], dict(s="abc", i=-1)), (["drop", s, i], dict(s="abc", i=-2)),
                       (["srep", s, i], dict(s="abc", i=-1)), (["srep", s, i], dict(s="abc", i=10 ** 6)),
                       (["itos", i], dict(i=-5)), (["at", s, s], dict(s="abc", i=0))):
            with self.assertRaises(W.Invalid):
                W.run(t, row)

    def test_opsets_unchanged_and_switch(self):
        self.assertNotIn("at", W.OPSETS["str"])
        self.assertNotIn("at", W.OPSETS["text"])
        self.assertEqual(W.OPSETS["text"][-1], "div")
        t = B.train_tasks()[0]
        with _Env(NOMAD_BRIDGE="off"):
            self.assertFalse(W.bridge_enabled())
            self.assertEqual(W.opset_of(t), W.OPSETS["text"])
        with _Env(NOMAD_BRIDGE="on"):
            self.assertTrue(W.bridge_enabled())
            self.assertEqual(W.opset_of(t), W.OPSETS["bridge"])
        os.environ.pop("NOMAD_BRIDGE", None)
        self.assertTrue(W.bridge_enabled(), "default is on (flipped after the sealed judge, docs/BRIDGE.md)")
        # non-bridge tasks never see a different opset
        from nomad.world_tasks import all_training
        for x in all_training():
            self.assertEqual(W.opset_of(x), W.OPSETS[x.opset])


class BridgeDomain(unittest.TestCase):
    def test_trees_match_truth(self):
        for f in B.CATALOGUE + B.DEV_CATALOGUE:
            rows = B.draw_rows(f, random.Random(f"t:{f.family}"))
            self.assertEqual(len(rows), 11)
            for r, a in rows:
                self.assertEqual(W.run(f.tree, r), a, f.family)
            self.assertTrue(set(W.ops_used(f.tree)) & {"at", "take", "drop", "srep", "itos", "strlen"}, f.family)

    def test_names_disjoint(self):
        names = set(B.TYPES)
        self.assertFalse(names & set(T.TYPES))
        self.assertFalse(names & {"s", "xs", "x", "y"})
        fams = [f.family for f in B.CATALOGUE + B.DEV_CATALOGUE]
        self.assertEqual(len(fams), len(set(fams)))
        self.assertFalse(set(fams) & set(B.TRAIN_FAMILIES))

    def test_training_tasks_valid(self):
        ts = B.train_tasks()
        self.assertEqual(len(ts), len(B.TRAIN_FAMILIES))
        for t in ts:
            self.assertEqual(t.opset, "bridge")

    def test_sealed_suite_frozen(self):
        import bridge_suite as BS
        suite, easy, hard = BS.load()
        self.assertGreaterEqual(len(hard), 12)
        self.assertFalse({e["family"] for e in suite["hard"]} & set(B.TRAIN_FAMILIES))
        self.assertFalse(suite["trained_on_by_any_arm"])


class BridgeLearning(unittest.TestCase):
    def test_memory_certifies_what_empty_cannot(self):
        """A field that certified the rotate block (bridge on) certifies a rotate+upper task the empty field does not."""
        from nomad import variation as V
        import science_probe as SP
        with _Env(NOMAD_BRIDGE="on", NOMAD_PORT="on"):
            p, vs = W.WorldPrior(), V.VariationState()
            tr = {t.family: t for t in B.train_tasks()}
            SP.train_more(p, vs, [tr["br_take"], tr["br_drop"], tr["br_rotate"]], rounds=1)
            task = B.to_task(_entry("b_rot_upper"))
            e = W.evaluate(task, prior=W.WorldPrior(), max_eval=10000, max_size=7)[0]
            f = W.evaluate(task, prior=p, variation=vs, max_eval=10000, max_size=7)[0]
            c = W.evaluate(task, prior=None, max_eval=10000, max_size=7)[0]
            self.assertTrue(f.certified)
            self.assertFalse(e.certified)
            self.assertFalse(c.certified)
            self.assertEqual(f.via, "port:probe")


def _entry(family):
    f = B.BY_FAMILY[family]
    rows = B.draw_rows(f, random.Random(f"e:{family}"))
    return {"task_id": "t", "family": family, "inputs": list(f.inputs), "out": f.out, "rows": [[r, a] for r, a in rows]}


if __name__ == "__main__":
    unittest.main()
