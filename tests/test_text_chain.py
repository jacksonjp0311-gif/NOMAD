"""TEXT_CHAIN: multi-part concat chains on string goals (docs/TEXT_CHAIN.md)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nomad import invent as I  # noqa: E402
from nomad.world import run  # noqa: E402

W = ["hello", "Was", "cat"]
ROWS = [{"w": w, "q": "_", "k": 2} for w in W]


def V(n):
    return ["var", n]


def vals(tree):
    return tuple(run(tree, r) for r in ROWS)


class TextChainTests(unittest.TestCase):
    def test_default_off(self) -> None:
        old = os.environ.pop("NOMAD_TEXT_CHAIN", None)
        try:
            self.assertFalse(I.chain_enabled())
            os.environ["NOMAD_TEXT_CHAIN"] = "on"
            self.assertTrue(I.chain_enabled())
        finally:
            os.environ.pop("NOMAD_TEXT_CHAIN", None)
            if old is not None:
                os.environ["NOMAD_TEXT_CHAIN"] = old

    def test_three_part_chain_by_peeling(self) -> None:
        last, first, q = ["last", V("w")], ["first", V("w")], V("q")
        goal = tuple(w[-1] + "_" + w[0] for w in W)
        pool = [(t, vals(t)) for t in (last, q, first)]
        parts = I.chain_parts(goal, pool, [], [], ("upper", "lower"))
        got = list(I.text_chain(goal, parts))
        self.assertTrue(got)
        self.assertEqual(vals(got[0]), goal)
        self.assertEqual(sum(1 for _ in str(got[0]).split("concat")) - 1, 2)   # two concats: three parts

    def test_case_and_itos_variants(self) -> None:
        goal = tuple(w.upper() + "_" + str(len(w)) for w in W)
        pool = [(V("w"), vals(V("w"))), (V("q"), ("_",) * 3)]
        ints = [(["strlen", V("w")], vals(["strlen", V("w")]))]
        parts = I.chain_parts(goal, pool, [], ints, ("upper", "lower", "itos"))
        got = list(I.text_chain(goal, parts))
        self.assertTrue(got)
        self.assertEqual(vals(got[0]), goal)
        # without upper / itos in the opset nothing fits
        self.assertEqual(list(I.text_chain(goal, I.chain_parts(goal, pool, [], ints, ()))), [])

    def test_parts_are_proper_substrings_and_two_part_left_to_anchors(self) -> None:
        goal = tuple(w + "_" for w in W)
        pool = [(V("w"), vals(V("w"))), (V("q"), ("_",) * 3), (["concat", V("w"), V("q")], goal)]
        parts = I.chain_parts(goal, pool, [], [], ())
        self.assertNotIn(goal, [e[1] for e in parts])          # the whole goal is never a part
        self.assertEqual(list(I.text_chain(goal, parts)), [])  # two parts: INVENT_TEXT's anchors, not here

    def test_node_cap(self) -> None:
        goal = tuple(w[-1] + "_" + w[0] for w in W)
        pool = [(t, vals(t)) for t in (["last", V("w")], V("q"), ["first", V("w")])]
        parts = I.chain_parts(goal, pool, [], [], ())
        self.assertEqual(list(I.text_chain(goal, parts, max_nodes=1)), [])

    def test_learned_flag(self) -> None:
        goal = tuple(w[-1] + "_" + w[0] for w in W)
        last, first, q = ["last", V("w")], ["first", V("w")], V("q")
        parts = I.chain_parts(goal, [(t, vals(t)) for t in (last, q)], [(first, vals(first))], [], ())
        self.assertEqual([e[2] for e in parts if e[0] == first], [True])
        dup = I.chain_parts(goal, [(t, vals(t)) for t in (last, q, first)], [(first, vals(first))], [], ())
        self.assertFalse(any(e[2] for e in dup))   # a learned block adds nothing the pool already holds


if __name__ == "__main__":
    unittest.main()
