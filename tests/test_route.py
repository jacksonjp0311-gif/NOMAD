"""ROUTE (docs/ROUTE.md): learned routing table over the portable bank.
Learns only from verified receipts, persists, decays; off by default; with no
evidence (empty field, unknown SENSE key) the search is exactly main's; the
cold control never reads the table."""
import json
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad import world as W  # noqa: E402
from nomad.world import WorldPrior, evaluate, make_task, synthesize, task_route_key  # noqa: E402

PTS = [(2, 5), (7, 3), (4, 4), (9, 2), (10, 1), (11, 6), (3, 10), (8, 8), (13, 4), (5, 12), (6, 1)]


def _task(name, fn, names=("a", "b")):
    rows = [({n: v for n, v in zip(names, pt)}, fn(*pt)) for pt in PTS]
    return make_task(f"t-{name}", name, "int", {n: "int" for n in names}, "int", rows[:5], rows[5:8], rows[8:])


def _vsq():
    rng = random.Random(5)

    def rows(n):
        out = []
        for _ in range(n):
            u, a, d = rng.randint(-9, 12), rng.randint(-5, 6), rng.randint(1, 12)
            out.append(({"u": u, "a": a, "d": d}, u * u + 2 * a * d))
        return out
    return make_task("t-vsq", "route_vsq", "int", {"u": "int", "a": "int", "d": "int"}, "int",
                     rows(5), rows(3), rows(3))


def _learn(p, task):
    ev, r = evaluate(task, prior=p)
    assert ev.certified
    p.add_witnessed(ev.tree, r, family=task.family, opset=W.OPSETS["int"], inputs=task.inputs,
                    sense_key=task_route_key(task))
    return ev


def _field():
    p = WorldPrior()
    two_ab = _task("route_2ab", lambda a, b: 2 * a * b)
    _learn(p, two_ab)
    _learn(p, two_ab)          # re-certified: its own block is reused
    _learn(p, _task("route_sq", lambda a, b: a * a + b, ("x", "y")))
    return p


class Route(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("NOMAD_ROUTE", None)

    def test_default_off(self):
        os.environ.pop("NOMAD_ROUTE", None)
        self.assertFalse(W.route_enabled())

    def test_table_learned_persisted_decayed(self):
        p = _field()
        self.assertTrue(p.route)
        self.assertTrue(p.library_src or p.programs_src)
        key = task_route_key(_task("route_2ab", lambda a, b: 2 * a * b))
        self.assertIn(key, p.route)
        self.assertTrue(any(s > 0 for s, _f in p.route[key].values()))
        back = WorldPrior.from_snapshot(json.loads(json.dumps(p.snapshot())))
        self.assertEqual(back.route, p.route)
        self.assertEqual((back.library_src, back.programs_src), (p.library_src, p.programs_src))
        old = WorldPrior.from_snapshot({k: v for k, v in p.snapshot().items()
                                        if k not in ("route", "library_src", "programs_src")})
        self.assertEqual(old.route, {})     # snapshots from before ROUTE still load
        p.decay(0.5)
        self.assertTrue(all(s <= back.route[k][g][0] * 0.5 + 1e-9 for k, t in p.route.items() for g, (s, _f) in t.items()))

    def test_no_sense_key_learns_nothing_and_unverified_rejected(self):
        p = WorldPrior()
        t = _task("route_2ab", lambda a, b: 2 * a * b)
        ev, r = evaluate(t, prior=p)
        p.add_witnessed(ev.tree, r, family=t.family, opset=W.OPSETS["int"], inputs=t.inputs)
        self.assertEqual(p.route, {})
        self.assertIsNone(p.relevance("anything/x", "prog", "W0"))

        class Bad:
            supported = False

            def verify_checksum(self):
                return False
        with self.assertRaises(ValueError):
            p.add_witnessed(ev.tree, Bad(), family=t.family, opset=W.OPSETS["int"], inputs=t.inputs, sense_key="k")
        self.assertEqual(p.route, {})

    def test_empty_field_and_cold_identical(self):
        task = _vsq()
        res = {}
        for mode in ("off", "on"):
            os.environ["NOMAD_ROUTE"] = mode
            e = synthesize(task, prior=WorldPrior(), max_eval=10000)
            c = synthesize(task, max_eval=10000)
            res[mode] = ((e.tree, e.evaluations, e.via), (c.tree, c.evaluations, c.via))
        self.assertEqual(res["off"], res["on"])

    def test_unknown_key_is_exactly_off(self):
        task = _vsq()
        p = _field()
        key = task_route_key(task)
        p.route.pop(key, None)       # no evidence for this task's SENSE key
        os.environ["NOMAD_ROUTE"] = "off"
        a = synthesize(task, prior=p, max_eval=10000)
        os.environ["NOMAD_ROUTE"] = "on"
        b = synthesize(task, prior=p, max_eval=10000)
        self.assertEqual((a.tree, a.evaluations, a.via), (b.tree, b.evaluations, b.via))

    def test_routed_bank_same_blocks(self):
        task = _vsq()
        p = _field()
        key = task_route_key(task)
        p.route.setdefault(key, {})["prog:" + str(next(iter(p.programs_src.values())))] = [5.0, 0.0]
        os.environ["NOMAD_ROUTE"] = "off"
        plain = W.port_bank(p, task)
        os.environ["NOMAD_ROUTE"] = "on"
        rel: dict = {}
        routed = W.port_bank(p, task, key, rel)
        self.assertEqual(sorted(map(json.dumps, plain)), sorted(map(json.dumps, routed)))  # order only
        self.assertTrue(rel)
        self.assertTrue(all(0.0 < v < 1.0 for v in rel.values()))
        res = synthesize(task, prior=p, max_eval=10000)
        self.assertLessEqual(res.evaluations, 10000)


if __name__ == "__main__":
    unittest.main()
