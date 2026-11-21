"""INFLECT: morphology / expression rule blocks (docs/INFLECT.md)."""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nomad import inflect as X  # noqa: E402
from nomad import invent as I  # noqa: E402
from nomad import world as W  # noqa: E402


def R(tree, **row):
    return W.run(tree, row)


class _Env:
    def __init__(self, **kw):
        self.kw, self.old = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = os.environ.get(k)
            os.environ[k] = v

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class OpTests(unittest.TestCase):
    def test_predicates_and_helpers(self) -> None:
        w = ["var", "w"]
        for word, want in (("box", 1), ("church", 1), ("dish", 1), ("bus", 1), ("cat", 0), ("fly", 0)):
            self.assertEqual(R(["sib", w], w=word), want, word)
        for word, want in (("city", 1), ("baby", 1), ("day", 0), ("y", 0), ("box", 0)):
            self.assertEqual(R(["cy", w], w=word), want, word)
        self.assertEqual(R(["ve", w], w="make"), 1)
        self.assertEqual(R(["ens", w], w="bus"), 1)
        self.assertEqual(R(["init", w], w="city"), "cit")
        self.assertEqual(R(["init", w], w=""), "")
        for word, want in (("stop", "p"), ("plan", "n"), ("hug", "g"), ("open", ""), ("visit", ""), ("fix", ""),
                           ("play", ""), ("walk", ""), ("need", ""), ("at", ""), ("snow", "")):
            self.assertEqual(R(["gem", w], w=word), want, word)
        n = ["var", "n"]
        self.assertEqual([R(["one", n], n=k) for k in (0, 1, 2)], [0, 1, 0])
        self.assertEqual(R(["sel", ["one", n], w, ["upper", w]], n=1, w="ab"), "ab")
        self.assertEqual(R(["sel", ["one", n], w, ["upper", w]], n=3, w="ab"), "AB")

    def test_truth_matches_reference_trees(self) -> None:
        for f in X.CATALOGUE:
            rows = X.draw_rows(f, random.Random(f"t:{f.family}"))
            self.assertEqual(len(rows), 11, f.family)
            for r, ans in rows:
                self.assertEqual(W.run(f.tree, r), ans, f.family)
                self.assertEqual(f.truth(*(r[n] for n in f.inputs)), ans, f.family)

    def test_python_rules(self) -> None:
        self.assertEqual([X.py_plural(w) for w in ("box", "city", "day", "cat", "church")],
                         ["boxes", "cities", "days", "cats", "churches"])
        self.assertEqual([X.py_past(w) for w in ("walk", "bake", "stop", "carry", "play", "open")],
                         ["walked", "baked", "stopped", "carried", "played", "opened"])
        self.assertEqual([X.py_ing(w) for w in ("make", "stop", "walk", "carry")],
                         ["making", "stopping", "walking", "carrying"])
        self.assertEqual((X.py_poss("box"), X.py_poss("boxes")), ("box's", "boxes'"))
        self.assertEqual((X.py_count(1, "city"), X.py_count(3, "city")), ("1 city", "3 cities"))

    def test_word_lists_disjoint(self) -> None:
        train = set(X.flat(X.TRAIN_NOUNS)) | set(X.flat(X.TRAIN_VERBS))
        sealed = set(X.flat(X.SEALED_NOUNS)) | set(X.flat(X.SEALED_VERBS))
        self.assertFalse(train & sealed, train & sealed)

    def test_train_tasks_certify_with_reference_trees(self) -> None:
        self.assertEqual(len(X.train_tasks()), len(X.TRAIN_FAMILIES))


class SwitchTests(unittest.TestCase):
    def test_default_off_and_collapse(self) -> None:
        task = X.train_tasks()[0]
        with _Env(NOMAD_BRIDGE="on"):
            os.environ.pop("NOMAD_INFLECT", None)
            self.assertFalse(W.inflect_enabled())
            self.assertEqual(W.opset_of(task), W.OPSETS["bridge"])
            os.environ["NOMAD_INFLECT"] = "on"
            self.assertTrue(W.inflect_enabled())
            self.assertIn("sel", W.opset_of(task))
            os.environ["NOMAD_INFLECT"] = "off"
            self.assertNotIn("sel", W.opset_of(task))
        self.assertNotIn("sel", W.OPSETS["bridge"])
        for name in ("init", "sib", "cy", "ve", "ens", "gem", "one", "sel"):
            self.assertNotIn(name, W.OPSETS["text"] + W.OPSETS["bridge"])

    def test_affix_score_only_for_inflect(self) -> None:
        self.assertEqual(W.affix_score(("s", "es"), ("cats", "boxes")), (0, 2, 0))
        self.assertEqual(W.affix_score(("x", "es"), ("cats", "boxes")), (0, 1, 0))


class SelTests(unittest.TestCase):
    def test_sel_complete_builds_a_selector(self) -> None:
        w = ["var", "w"]
        words = ("box", "cat", "bus", "dog")
        seg = ("es", "s", "es", "s")
        preds = [(["sib", w], tuple(int(x.endswith(("s", "x"))) for x in words)),
                 (["cy", w], (0, 0, 0, 0))]
        branches = [(["var", "a"], ("s",) * 4), (["var", "b"], ("es",) * 4), (["var", "c"], ("x",) * 4)]
        out = list(I.sel_complete(seg, preds, branches))
        self.assertEqual(out[0], ["sel", ["sib", w], ["var", "b"], ["var", "a"]])
        # a segment no pair of branches covers yields nothing
        self.assertEqual(list(I.sel_complete(("q",) * 4, preds, branches)), [])

    def test_text_chain_without_selpool_unchanged(self) -> None:
        goal = ("a:b", "c:d")
        parts = [(["var", "x"], ("a", "c"), False), (["var", "y"], (":", ":"), False), (["var", "z"], ("b", "d"), False)]
        self.assertEqual(list(I.text_chain(goal, parts)), [["concat", ["var", "x"], ["concat", ["var", "y"], ["var", "z"]]]])

    def test_end_to_end_plural_with_bank_blocks(self) -> None:
        """A field taught the stem rule and the suffix rule completes a word class it never saw."""
        import copy
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import science_probe as SP
        from nomad import variation as V
        with _Env(NOMAD_BRIDGE="on", NOMAD_INFLECT="on"):
            p, vs = W.WorldPrior(), V.VariationState()
            SP.train_more(p, vs, X.train_tasks())
            f = [f for f in X.CATALOGUE if f.family == "q_plural_full"][0]
            rows = X.draw_rows(f, random.Random("e2e"))
            task = X.to_task({"task_id": "e2e", "family": f.family, "inputs": list(f.inputs), "out": f.out,
                              "rows": [[r, a] for r, a in rows]})
            ev, _ = W.evaluate(task, prior=p, variation=vs, casesplit=True, max_eval=10000)
            self.assertTrue(ev.certified, ev)
            cold, _ = W.evaluate(task, prior=None, max_eval=10000)
            self.assertFalse(cold.certified)
        # the same field, switch off: the inflect opset is the bridge world, so the rule blocks are never searched
        with _Env(NOMAD_BRIDGE="on", NOMAD_INFLECT="off"):
            self.assertNotIn("sel", W.opset_of(task))


if __name__ == "__main__":
    unittest.main()
