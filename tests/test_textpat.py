"""TEXT_ABSTRACT: reusable string templates from certified text chains (docs/TEXTPAT.md)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nomad import invent as I  # noqa: E402
from nomad import textpat as TP  # noqa: E402
from nomad.world import WorldPrior, run  # noqa: E402

W = ["Hello", "cat", "Zoom"]
SEP = [":", ":", ":"]
ROWS = [{"w": w, "n": n, "k": 2} for w, n in zip(W, ["Ann", "Bo", "Cy"])]


def V(n):
    return ["var", n]


def cat(*xs):
    t = xs[-1]
    for x in reversed(xs[:-1]):
        t = ["concat", x, t]
    return t


class TextpatTests(unittest.TestCase):
    def test_default_off_and_on_switch(self) -> None:
        old = os.environ.pop("NOMAD_TEXT_ABSTRACT", None)
        try:
            self.assertFalse(TP.enabled())
            os.environ["NOMAD_TEXT_ABSTRACT"] = "on"
            self.assertTrue(TP.enabled())
            os.environ["NOMAD_TEXT_ABSTRACT"] = "off"
            self.assertFalse(TP.enabled())
        finally:
            os.environ.pop("NOMAD_TEXT_ABSTRACT", None)
            if old is not None:
                os.environ["NOMAD_TEXT_ABSTRACT"] = old

    def test_chain_tree_detects_concat_and_wrappers(self) -> None:
        self.assertTrue(TP._is_chain_tree(cat(V("w"), V("n"))))
        self.assertTrue(TP._is_chain_tree(["upper", cat(V("w"), V("n"))]))
        self.assertFalse(TP._is_chain_tree(["upper", V("w")]))
        self.assertFalse(TP._is_chain_tree(["itos", ["strlen", V("w")]]))

    def test_abstract_vars_and_lgg_make_templates(self) -> None:
        p = WorldPrior()
        t1 = cat(["upper", V("a")], V("s"), ["lower", V("b")])
        t2 = cat(["lower", V("a")], V("s"), ["upper", V("b")])
        remember(p, "W1", t1, [("a", "str"), ("s", "str"), ("b", "str")])
        remember(p, "W2", t2, [("a", "str"), ("s", "str"), ("b", "str")])
        pats = TP.templates(p)
        self.assertTrue(pats)
        # LGG of the two chains is concat(h0, concat(h1, h2)) -- three string holes
        spines = [I._render(t.tree) for t in pats]
        self.assertTrue(any("concat" in s for s in spines))
        # every template has only holes / operators, no residual vars
        for t in pats:
            self.assertTrue(all(x[0] != "var" for x in I._subtrees(t.tree) if I._is_leaf(x)))
            self.assertTrue(1 <= len(t.args) <= TP.TEXTPAT_MAX_HOLES)

    def test_empty_field_has_no_templates(self) -> None:
        self.assertEqual(TP.templates(WorldPrior()), [])
        self.assertEqual(TP.templates(None), [])

    def test_shuffled_rewires_concat_order(self) -> None:
        p = WorldPrior()
        remember(p, "W1", cat(["upper", V("a")], V("s"), V("b")),
                 [("a", "str"), ("s", "str"), ("b", "str")])
        remember(p, "W2", cat(["lower", V("a")], V("s"), V("b")),
                 [("a", "str"), ("s", "str"), ("b", "str")])
        raw = TP.templates(p)
        self.assertTrue(raw)
        sh = TP.templates(TP.shuffled(p, 1))
        self.assertEqual(len(sh), len(raw))
        # rewiring changes at least one body (concat is not commutative)
        self.assertTrue(any(a.tree != b.tree for a, b in zip(raw, sh)))
        # original prior is untouched
        self.assertEqual([t.tree for t in TP.templates(p)], [t.tree for t in raw])

    def test_free_eval_assembles_from_pool_and_variants(self) -> None:
        rows = [{"w": w, "s": ":", "k": 2} for w in W]
        goal = tuple(w.upper() + ":" + str(2) for w in W)
        up = ["upper", V("w")]
        memo = {
            json_key(V("w")): tuple(r["w"] for r in rows),
            json_key(V("s")): tuple(":" for _ in rows),
            json_key(V("k")): tuple(2 for _ in rows),
        }
        tree = cat(up, V("s"), ["itos", V("k")])
        got = TP.free_eval(tree, rows, memo, {"upper", "lower", "itos", "concat"})
        self.assertEqual(got, goal)
        # without upper in the pool or the opset, it should fail
        self.assertIsNone(TP.free_eval(tree, rows, memo, {"itos", "concat"}))

    def test_length_filter_and_instances(self) -> None:
        # a 3-part template instantiated on matching rows
        body = cat(["hole", 0], ["hole", 1], ["itos", ["hole", 2]])
        t = TP.Template("Ttest", json_loads(body), ("str", "str", "int"), 2, "ex")
        class T:
            out = "str"
            inputs = (("w", "str"), ("s", "str"), ("k", "int"))
        inst = TP.instances([t], T())
        self.assertTrue(inst)
        row = {"w": "Hi", "s": "|", "k": 3}
        # some bindings repeat a string input (w+w+itos(k)); every instance has a defined length
        self.assertTrue(all(TP.pred_len(tr, row) is not None for tr in inst))
        tree = cat(V("w"), V("s"), ["itos", V("k")])
        self.assertEqual(TP.pred_len(tree, row), 4)
        self.assertTrue(TP.length_matches(tree, [row], ["Hi|3"]))
        self.assertFalse(TP.length_matches(tree, [row], ["x"]))

    def test_free_eval_first_and_itos_strlen(self) -> None:
        rows = [{"w": w, "s": ":"} for w in W]
        goal = tuple(w[0] + ":" + str(len(w)) for w in W)
        memo = {json_key(V("w")): tuple(r["w"] for r in rows),
                json_key(V("s")): tuple(":" for _ in rows)}
        tree = cat(["first", V("w")], V("s"), ["itos", ["strlen", V("w")]])
        got = TP.free_eval(tree, rows, memo, {"first", "itos", "concat", "strlen"})
        self.assertEqual(got, goal)

    def test_catalogue_truth_matches_tree(self) -> None:
        import random
        from nomad import textpat_tasks as XT
        for f in XT.CATALOGUE + XT.TRAIN_CATALOGUE:
            draw = XT.draw_rows if f in XT.CATALOGUE else XT.draw_train_rows
            rows = draw(f, random.Random(f"test:{f.family}"))
            self.assertEqual(len(rows), 11, f.family)

    def test_sealed_suite_hash(self) -> None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import textpat_suite as XS
        suite, easy, hard = XS.load(XS.OUT, check=True)
        self.assertEqual((len(easy), len(hard)), (2, 22))
        self.assertEqual(suite["seed"], 20270117)

    def test_input_names_are_new(self) -> None:
        from nomad import textpat_tasks as XT
        sealed = {n for f in XT.CATALOGUE for n in f.inputs}
        train = {n for f in XT.TRAIN_CATALOGUE for n in f.inputs}
        self.assertEqual(sealed, {"va", "vb", "vk", "vj", "vs", "vt"})
        self.assertEqual(train, {"ua", "ub", "uk", "uj", "us", "ut"})
        self.assertFalse(sealed & train)

    def test_prepare_length_filter_keeps_a_matching_binding(self) -> None:
        p = WorldPrior()
        remember(p, "W1", cat(V("ua"), V("us"), V("ub"), V("ut"), ["itos", V("uk")]),
                 [("ua", "str"), ("us", "str"), ("ub", "str"), ("ut", "str"), ("uk", "int")])
        remember(p, "W2", cat(V("ua"), V("us"), V("ub"), V("ut"), ["itos", ["strlen", V("ua")]]),
                 [("ua", "str"), ("us", "str"), ("ub", "str"), ("ut", "str"), ("uk", "int")])
        class T:
            out = "str"
            inputs = (("va", "str"), ("vb", "str"), ("vs", "str"), ("vt", "str"), ("vk", "int"))
            public = [({"va": "Hi", "vb": "Bo", "vs": "|", "vt": "#", "vk": 3}, "Hi|Bo#3")]
        inst = TP.prepare(p, T())
        self.assertTrue(inst)
        self.assertTrue(any(TP.free_eval(tr, [r for r,_ in T.public],
                                         TP.memo_from({}, [], [r for r,_ in T.public], T.inputs),
                                         {"itos", "concat"}) == ("Hi|Bo#3",) for tr in inst))


def remember(p, name, tree, inputs):
    p.programs[name] = tree
    p.programs_sig[name] = [list(i) if not isinstance(i, list) else i for i in inputs]
    p.programs_uses[name] = 1.0


def json_key(t):
    import json
    return json.dumps(t)


def json_loads(t):
    import json
    return json.loads(json.dumps(t))


if __name__ == "__main__":
    unittest.main()
