"""TRANSFER domain + frozen suite: determinism, exact truth, disjoint names, frozen hash."""
import json
import random
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import transfer_suite as TS  # noqa: E402
from nomad import science as S  # noqa: E402
from nomad import transfer as T  # noqa: E402
from nomad.world import certify, run  # noqa: E402
from nomad.world_tasks import all_training, domain_of  # noqa: E402

SHA = "f27adf3cbe3dbec76b7904c5311de6cc46e453ba1426706281f895e0104e872c"


class TransferDomain(unittest.TestCase):
    def test_catalogue_well_formed(self):
        fams = [f.family for f in T.CATALOGUE]
        self.assertEqual(len(fams), len(set(fams)))
        for f in T.CATALOGUE:
            dom, kind = f.kind.split(":")
            self.assertIn(kind, T.KINDS[dom])
            self.assertEqual(set(f.ranges), set(f.inputs))

    def test_names_disjoint_from_training(self):
        train = {n for t in all_training() for n, _ in t.inputs} | {n for f in S.CATALOGUE for n in f.inputs}
        mine = {n for f in T.CATALOGUE for n in f.inputs}
        self.assertFalse(train & mine)
        self.assertFalse(set(T.BY_FAMILY) & set(S.BY_FAMILY))
        for fam in T.BY_FAMILY:
            self.assertIsNone(domain_of(fam))

    def test_rows_exact(self):
        for f in T.CATALOGUE:
            a = T.draw_rows(f, random.Random(f"7:{f.family}"))
            self.assertEqual(a, T.draw_rows(f, random.Random(f"7:{f.family}")))
            for r, ans in a:
                q = Fraction(f.truth(*(r[n] for n in f.inputs)))
                self.assertEqual(q.denominator, 1)
                self.assertEqual(int(q), ans)
                self.assertEqual(run(f.tree, r), ans)

    def test_guards(self):
        self.assertIsNone(T.exact_answer(T.BY_FAMILY["fin_breakeven"], {"S": 5, "K": 9, "N": 1, "X": 8}))
        self.assertIsNone(T.exact_answer(T.BY_FAMILY["geo_trap_diff"], {"B": 2, "T": 6, "Z": 4}))


class FrozenTransferSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = json.loads(TS.OUT.read_text())

    def test_hash(self):
        self.assertEqual(TS.suite_hash(self.suite), SHA)
        self.assertEqual(TS.HASH.read_text().split()[0], SHA)

    def test_sections(self):
        s = self.suite
        self.assertEqual(len(s["hard"]), 20)
        self.assertEqual(len(s["easy"]) + len(s["hard"]) + len(s["stats"]["lookup_dropped"]), len(T.CATALOGUE))
        self.assertTrue(all(not e["cold_certified"] for e in s["hard"]))
        self.assertTrue(all(e["cold_certified"] for e in s["easy"]))

    def test_reference_certifies_and_wrong_rejected(self):
        _, _, hard = TS.load()
        for e, t in zip(self.suite["hard"], hard):
            r, pub, fin = certify(t, e["tree"])
            self.assertTrue(r.supported and pub and fin, e["family"])
            r2, pub2, fin2 = certify(t, ["add", e["tree"], ["const", 1]])
            self.assertFalse(r2 is not None and r2.supported and fin2)
            n = len(t.public) + len(t.challenge) + len(t.final)
            self.assertEqual(n, 11)


if __name__ == "__main__":
    unittest.main()
