"""TEXT (docs/TEXT.md): string / language held-out domain, the `text` opset,
the `rest` block, SPLICE off by default, and the frozen TEXT suite."""
import json
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import text_suite as XS  # noqa: E402
from nomad import science as S  # noqa: E402
from nomad import text as X  # noqa: E402
from nomad import transfer as T  # noqa: E402
from nomad import transfer2 as T2  # noqa: E402
from nomad.world import OPSETS, certify, run, splice_enabled  # noqa: E402
from nomad.world_tasks import all_training  # noqa: E402

SHA = "08a826a38fab20dca5897edaf732db84a68a43ace4ec67386e796ad26cb64a02"


class TextDomain(unittest.TestCase):
    def test_opsets(self):
        self.assertEqual(OPSETS["str"], ("upper", "lower", "srev", "concat", "first", "last", "strlen", "add", "sub"))
        self.assertIn("rest", OPSETS["text"])
        self.assertEqual(run(["rest", ["var", "w"]], {"w": "nomad"}), "omad")
        self.assertEqual(run(["rest", ["var", "w"]], {"w": ""}), "")

    def test_names_disjoint(self):
        train = {n for t in all_training() for n, _ in t.inputs} | {n for f in S.CATALOGUE for n in f.inputs}
        other = {n for f in T.CATALOGUE + T2.CATALOGUE for n in f.inputs}
        mine = {n for f in X.CATALOGUE for n in f.inputs}
        self.assertFalse(mine & train)
        self.assertFalse(mine & other)
        self.assertEqual(len(X.BY_FAMILY), len(X.CATALOGUE))

    def test_rows_exact_and_deterministic(self):
        for f in X.CATALOGUE:
            a = X.draw_rows(f, random.Random(f"7:{f.family}"))
            self.assertEqual(a, X.draw_rows(f, random.Random(f"7:{f.family}")))
            for r, ans in a:
                self.assertEqual(f.truth(*(r[n] for n in f.inputs)), ans)
                self.assertEqual(run(f.tree, r), ans)

    def test_splice_off_by_default(self):
        old = os.environ.pop("NOMAD_SPLICE", None)
        try:
            self.assertFalse(splice_enabled())
        finally:
            if old is not None:
                os.environ["NOMAD_SPLICE"] = old


class FrozenTextSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = json.loads(XS.OUT.read_text())

    def test_hash(self):
        self.assertEqual(XS.suite_hash(self.suite), SHA)
        self.assertEqual(XS.HASH.read_text().split()[0], SHA)

    def test_sections(self):
        s = self.suite
        self.assertEqual(len(s["hard"]), 24)
        self.assertEqual(len(s["easy"]) + len(s["hard"]) + len(s["stats"]["lookup_dropped"]), len(X.CATALOGUE))
        self.assertTrue(all(not e["cold_certified"] for e in s["hard"]))

    def test_reference_certifies(self):
        _, _, hard = XS.load()
        for e, t in zip(self.suite["hard"], hard):
            r, pub, fin = certify(t, e["tree"])
            self.assertTrue(r.supported and pub and fin, e["family"])


if __name__ == "__main__":
    unittest.main()
