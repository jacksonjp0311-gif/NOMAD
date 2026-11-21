"""MERGE (docs/MERGE.md): probe-equivalent portable-bank blocks are one idea.
Off by default; with the switch on the bank is main's element for element,
duplicates are not re-evaluated (their values are copied), lookups that
already missed are not repeated, and only the evaluations saved fund the
merged anchors. An empty field and the cold control are untouched."""
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad import world as W  # noqa: E402
from nomad.world import WorldPrior, evaluate, make_task  # noqa: E402


def _task(seed=5, f=lambda a, b: a * b + 2 * a):
    rng = random.Random(seed)

    def rows(n):
        out = []
        for _ in range(n):
            a, b = rng.randint(1, 20), rng.randint(1, 20)
            out.append(({"a": a, "b": b}, f(a, b)))
        return out
    return make_task("t-merge", "merge_ab", "int", {"a": "int", "b": "int"}, "int", rows(5), rows(3), rows(3))


def _prior() -> WorldPrior:
    """Blocks with equivalent pairs: x*y and y*x, x+x and 2*x, x and x*1."""
    p = WorldPrior()
    blocks = {
        "L1": (["mul", ["var", "x"], ["var", "y"]], [["x", "int"], ["y", "int"]]),
        "L2": (["mul", ["var", "y"], ["var", "x"]], [["x", "int"], ["y", "int"]]),
        "L3": (["add", ["var", "x"], ["var", "x"]], [["x", "int"]]),
        "L4": (["mul", ["const", 2], ["var", "x"]], [["x", "int"]]),
        "L5": (["sub", ["var", "x"], ["const", 1]], [["x", "int"]]),
        "L6": (["max", ["var", "x"], ["const", 3]], [["x", "int"]]),
    }
    for i, (n, (t, sig)) in enumerate(blocks.items()):
        p.library[n] = t
        p.library_sig[n] = sig
        p.library_uses[n] = float(10 - i)
    return p


class Merge(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("NOMAD_MERGE", None)

    def bank(self, p, on, task=None):
        os.environ["NOMAD_MERGE"] = "on" if on else "off"
        return W.port_bank(p, task or _task())

    def test_default_off(self):
        os.environ.pop("NOMAD_MERGE", None)
        self.assertFalse(W.merge_enabled())
        self.assertFalse(getattr(self.bank(_prior(), False), "merged", False))

    def test_bank_is_mains_element_for_element(self):
        p = _prior()
        off, on = self.bank(p, False), self.bank(p, True)
        self.assertTrue(on.merged)
        self.assertEqual(list(on), list(off))

    def test_duplicates_are_probe_equivalent_and_point_back(self):
        p = _prior()
        on = self.bank(p, True)
        rows = W._probe_rows(_task().inputs)
        self.assertTrue(on.dup_of)
        for i, j in on.dup_of.items():
            self.assertLess(j, i)
            self.assertEqual(W.probe_fingerprint(on[i][1], rows), W.probe_fingerprint(on[j][1], rows))
        # x+x and 2*x are one idea; x-1 and max(x,3) are not duplicates of anything
        fps = [W.probe_fingerprint(t, rows) for _n, t in on]
        self.assertEqual(len(set(fps)), len(on) - len(on.dup_of))

    def test_probe_rows_are_fixed_and_task_free(self):
        a = W._probe_rows((("a", "int"), ("b", "int")))
        b = W._probe_rows((("a", "int"), ("b", "int")))
        self.assertEqual(a, b)
        self.assertEqual(len(a), W.MERGE_PROBES)
        t1, t2 = _task(1), _task(2)
        self.assertEqual(W._probe_rows(t1.inputs), W._probe_rows(t2.inputs))

    def test_empty_field_and_cold_identical(self):
        t = _task()
        for prior in (None, WorldPrior()):
            res = []
            for on in (False, True):
                os.environ["NOMAD_MERGE"] = "on" if on else "off"
                ev = evaluate(t, prior=prior, max_eval=3000, casesplit=True)[0]
                res.append((ev.certified, ev.evaluations, ev.via))
            self.assertEqual(res[0], res[1])

    def test_on_never_costs_more_on_this_field(self):
        p = _prior()
        for seed, f in ((5, lambda a, b: a * b + 2 * a), (6, lambda a, b: 2 * a * b - a), (7, lambda a, b: a * a + b)):
            t = _task(seed, f)
            res = {}
            for on in (False, True):
                os.environ["NOMAD_MERGE"] = "on" if on else "off"
                ev = evaluate(t, prior=p, max_eval=4000, casesplit=True)[0]
                res[on] = (ev.certified, ev.evaluations)
            self.assertGreaterEqual(res[True][0], res[False][0])
            if res[False][0]:
                self.assertLessEqual(res[True][1], res[False][1])

    def test_route_or_cut_reordering_leaves_mains_bank(self):
        p = _prior()
        os.environ["NOMAD_MERGE"] = "on"
        os.environ["NOMAD_ROUTE_CUT"] = "on"
        p.route["k"] = {"lib:x": [1.0, 0.0]}
        try:
            b = W.port_bank(p, _task(), None, None, "k")
            self.assertFalse(getattr(b, "merged", False))
        finally:
            os.environ.pop("NOMAD_ROUTE_CUT", None)

    def test_merge_ranked_keeps_first_of_each_value_class(self):
        r = [((5, 0, 0), "a", ["var", "a"], (1, 2)), ((4, 0, 0), "b", ["var", "b"], (1, 2)),
             ((3, 0, 0), "c", ["var", "c"], (3, 4))]
        self.assertEqual([z[1] for z in W.merge_ranked(r)], ["a", "c"])


def json_key(t):
    import json
    return json.dumps(t)


if __name__ == "__main__":
    unittest.main()
