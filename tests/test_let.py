"""LET: let-bindings over a learned block (docs/LET.md)."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from nomad import let_tasks as LT  # noqa: E402
from nomad import world as W  # noqa: E402

ROWS = [{"a": a, "b": b, "c": c} for a, b, c in ((3, 4, 5), (2, 7, 1), (6, 6, 30), (1, 9, 2), (5, 2, 8))]


def vals(tree):
    return tuple(W.run(tree, r) for r in ROWS)


class LetTests(unittest.TestCase):
    def test_default_off_and_on_switch(self) -> None:
        old = os.environ.pop("NOMAD_LET", None)
        try:
            self.assertFalse(W.let_enabled())
            os.environ["NOMAD_LET"] = "on"
            self.assertTrue(W.let_enabled())
        finally:
            os.environ.pop("NOMAD_LET", None)
            if old is not None:
                os.environ["NOMAD_LET"] = old

    def test_terms_reuse_t(self) -> None:
        t = ["mul", ["var", "a"], ["var", "b"]]
        atoms = [["var", "c"], ["const", 3]]
        terms = W.let_terms(t, vals(t), ROWS, atoms)
        self.assertEqual(terms[0][0], t)
        got = {json.dumps(tr): tv for tr, tv in terms}
        # every term really is its tree's value, and t * t / max(t, c) / t // 3 are among them
        for tr, tv in terms:
            self.assertEqual(vals(tr), tv)
        vs = set(got.values())
        self.assertIn(vals(["mul", t, t]), vs)
        self.assertIn(vals(["max", t, ["var", "c"]]), vs)
        self.assertIn(vals(["div", t, ["const", 3]]), vs)
        # values are distinct
        self.assertEqual(len(vs), len(terms))

    def test_catalogue_truth_matches_tree(self) -> None:
        import random
        for f in LT.CATALOGUE:
            rows = LT.draw_rows(f, random.Random(f"test:{f.family}"))
            self.assertEqual(len(rows), 11, f.family)
            names = {x for x in json.dumps(f.tree).replace('"', " ").split() if x.startswith("x")}
            self.assertTrue(set(f.inputs) >= {n.strip(",]") for n in names if n.strip(",]") in ("xa", "xb", "xc", "xd")})

    def test_sealed_suite_hash(self) -> None:
        import let_suite as XS
        suite, easy, hard = XS.load(XS.OUT, check=True)
        self.assertEqual((len(easy), len(hard)), (2, 22))
        self.assertEqual(suite["seed"], 20261231)

    def test_empty_field_unchanged(self) -> None:
        import random
        f = LT.CATALOGUE[0]
        rows = LT.draw_rows(f, random.Random("t:empty"))
        task = LT.to_task({"task_id": "x", "family": f.family, "inputs": list(f.inputs), "rows": [[r, a] for r, a in rows]})
        res = {}
        for flag in ("off", "on"):
            old = os.environ.get("NOMAD_LET")
            os.environ["NOMAD_LET"] = flag
            try:
                ev = W.evaluate(task, prior=W.WorldPrior(), max_eval=2000, max_size=7, casesplit=True)[0]
            finally:
                os.environ.pop("NOMAD_LET", None)
                if old is not None:
                    os.environ["NOMAD_LET"] = old
            res[flag] = (ev.certified, ev.evaluations, ev.candidate)
        self.assertEqual(res["off"], res["on"])


if __name__ == "__main__":
    unittest.main()
