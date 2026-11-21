"""GRAPH (docs/GRAPH.md): per-block co-occurrence graph learned from verified
receipts; persists and decays; off by default; an empty graph proposes
nothing (empty field and cold control identical on and off)."""
import json
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from nomad import world as W  # noqa: E402
from nomad.world import WorldPrior, evaluate, make_task, synthesize  # noqa: E402


def _vsq():
    rng = random.Random(5)

    def rows(n):
        out = []
        for _ in range(n):
            u, a, d = rng.randint(-9, 12), rng.randint(-5, 6), rng.randint(1, 12)
            out.append(({"u": u, "a": a, "d": d}, u * u + 2 * a * d))
        return out
    return make_task("t-vsq", "graph_vsq", "int", {"u": "int", "a": "int", "d": "int"}, "int",
                     rows(5), rows(3), rows(3))


class _Receipt:
    supported = True

    def verify_checksum(self):
        return True


TREE = ["add", ["mul", ["var", "x"], ["var", "y"]], ["mul", ["var", "x"], ["add", ["var", "y"], ["const", 1]]]]


class Graph(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("NOMAD_GRAPH", None)

    def test_default_off(self):
        self.assertFalse(W.graph_enabled())

    def test_nodes_edges_learned_persisted_decayed(self):
        p = WorldPrior()
        p.add_witnessed(TREE, _Receipt(), family="g", opset=W.OPSETS["int"], inputs=[["x", "int"], ["y", "int"]])
        a = W.graph_key(["mul", ["var", "x"], ["var", "y"]])
        b = W.graph_key(["mul", ["var", "x"], ["add", ["var", "y"], ["const", 1]]])
        self.assertIn(a, p.graph_nodes)
        self.assertIn(W.graph_edge(a, b), p.graph_edges)   # disjoint siblings co-occur
        # renaming does not change a node
        self.assertEqual(a, W.graph_key(["mul", ["var", "q"], ["var", "r"]]))
        back = WorldPrior.from_snapshot(json.loads(json.dumps(p.snapshot())))
        self.assertEqual((back.graph_nodes, back.graph_edges), (p.graph_nodes, p.graph_edges))
        old = WorldPrior.from_snapshot({k: v for k, v in p.snapshot().items() if not k.startswith("graph")})
        self.assertEqual(old.graph_edges, {})
        p.decay(0.5)
        self.assertTrue(all(v <= 0.5 for v in p.graph_edges.values()))
        p.decay(0.001)
        self.assertEqual(p.graph_edges, {})   # pruned

    def test_unverified_receipt_learns_nothing(self):
        p = WorldPrior()

        class Bad(_Receipt):
            supported = False
        with self.assertRaises(ValueError):
            p.add_witnessed(TREE, Bad(), family="g", opset=W.OPSETS["int"], inputs=[["x", "int"], ["y", "int"]])
        self.assertEqual((p.graph_nodes, p.graph_edges), ({}, {}))

    def test_empty_graph_proposes_nothing_and_controls_identical(self):
        task = _vsq()
        self.assertEqual(W.graph_pairs(WorldPrior(), [], (1, 2, 3), {}), [])
        res = {}
        for mode in ("off", "on"):
            os.environ["NOMAD_GRAPH"] = mode
            e = synthesize(task, prior=WorldPrior(), max_eval=10000)
            c = synthesize(task, max_eval=10000)
            res[mode] = ((e.tree, e.evaluations, e.via), (c.tree, c.evaluations, c.via))
        self.assertEqual(res["off"], res["on"])

    def test_graph_pairs_only_along_edges(self):
        p = WorldPrior()
        p.add_witnessed(TREE, _Receipt(), family="g", opset=W.OPSETS["int"], inputs=[["x", "int"], ["y", "int"]])
        goal = (10, 20, 30)
        ranked = [((0, -1, 0), "A", ["mul", ["var", "u"], ["var", "a"]], (1, 2, 3)),
                  ((0, -1, 0), "B", ["mul", ["var", "u"], ["add", ["var", "a"], ["const", 1]]], (2, 4, 6)),
                  ((0, -1, 0), "C", ["sub", ["var", "u"], ["var", "a"]], (5, 5, 5))]
        pairs = W.graph_pairs(p, ranked, goal, {})
        self.assertTrue(pairs)
        names = {frozenset((x[1], y[1])) for x, y in pairs}
        self.assertNotIn(frozenset(("C",)), names)
        self.assertTrue(all("C" not in n for n in names))
        import graph_judge as GJ
        q = GJ.rewired(p, 0)
        self.assertEqual(sorted(q.graph_nodes), sorted(p.graph_nodes))
        self.assertEqual(len(q.graph_edges), len(p.graph_edges))

    def test_on_respects_budget(self):
        task = _vsq()
        p = WorldPrior()
        p.add_witnessed(TREE, _Receipt(), family="g", opset=W.OPSETS["int"], inputs=[["x", "int"], ["y", "int"]])
        os.environ["NOMAD_GRAPH"] = "on"
        r = synthesize(task, prior=p, max_eval=10000)
        self.assertLessEqual(r.evaluations, 10000)


if __name__ == "__main__":
    unittest.main()
