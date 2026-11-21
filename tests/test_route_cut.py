"""ROUTE_CUT (docs/ROUTE_CUT.md): when the portable bank overflows PORT_SCAN,
keep main's first CUT_HEAD instances and fill the rest in learned ROUTE
relevance order. Off by default; a bank within PORT_SCAN, a key without
evidence, and an empty field are exactly main's."""
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad import world as W  # noqa: E402
from nomad.world import WorldPrior, evaluate, make_task  # noqa: E402

KEY = "k/s"


def _task():
    rng = random.Random(3)

    def rows(n):
        out = []
        for _ in range(n):
            a, b = rng.randint(1, 20), rng.randint(1, 20)
            out.append(({"a": a, "b": b}, a * b + a))
        return out
    return make_task("t-cut", "cut_ab", "int", {"a": "int", "b": "int"}, "int", rows(5), rows(3), rows(3))


def _prior(n: int) -> WorldPrior:
    """n distinct one-variable library blocks; the least-used half come from source 'good'."""
    p = WorldPrior()
    for i in range(n):
        name = f"L{i:04d}"
        p.library[name] = ["add", ["mul", ["var", "x"], ["const", i + 2]], ["const", 3]]
        p.library_sig[name] = [["x", "int"]]
        p.library_uses[name] = float(n - i)
        p.library_src[name] = "good" if i >= n // 2 else "bad"
    p.route[KEY] = {"lib:good": [50.0, 0.0], "lib:bad": [0.0, 50.0]}
    return p


class RouteCut(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("NOMAD_ROUTE_CUT", None)

    def bank(self, p, on, key=KEY):
        os.environ["NOMAD_ROUTE_CUT"] = "on" if on else "off"
        return W.port_bank(p, _task(), None, None, key)

    def test_default_off(self):
        os.environ.pop("NOMAD_ROUTE_CUT", None)
        self.assertFalse(W.route_cut_enabled())

    def test_overflow_keeps_head_and_routes_tail(self):
        p = _prior(600)   # 2 renamings each (a, b): 1,200 instances > PORT_SCAN
        off, on = self.bank(p, False), self.bank(p, True)
        self.assertEqual(len(off), W.PORT_SCAN)
        self.assertEqual(len(on), W.PORT_SCAN)
        self.assertEqual(on[:W.CUT_HEAD], off[:W.CUT_HEAD])
        names_off = {json_key(t) for _n, t in off}
        tail = [t for _n, t in on[W.CUT_HEAD:]]
        self.assertTrue(all(json_key(t) not in names_off for t in tail))
        consts = [t[1][2][1] - 2 for t in tail]
        self.assertTrue(all(c >= 300 for c in consts))   # tail entries all from the learned 'good' source

    def test_within_cut_is_main(self):
        p = _prior(100)   # 200 instances < PORT_SCAN
        self.assertEqual(self.bank(p, True), self.bank(p, False))

    def test_no_evidence_is_main(self):
        p = _prior(600)
        self.assertEqual(self.bank(p, True, key="other/key"), self.bank(p, False))
        self.assertEqual(self.bank(p, True, key=None), self.bank(p, False))

    def test_empty_field_and_cold_identical(self):
        t = _task()
        for prior in (None, WorldPrior()):
            os.environ["NOMAD_ROUTE_CUT"] = "off"
            a = evaluate(t, prior=prior, max_eval=3000)[0]
            os.environ["NOMAD_ROUTE_CUT"] = "on"
            b = evaluate(t, prior=prior, max_eval=3000)[0]
            self.assertEqual((a.certified, a.evaluations, a.via), (b.certified, b.evaluations, b.via))


def json_key(t):
    import json
    return json.dumps(t)


if __name__ == "__main__":
    unittest.main()
