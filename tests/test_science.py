"""SCIENCE generator: determinism, exact ground truth, verifier, tags, frozen files."""
import hashlib
import json
import random
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import science_suite as SS  # noqa: E402
from nomad import science as S  # noqa: E402
from nomad.world import certify, run  # noqa: E402
from nomad.world_tasks import domain_of  # noqa: E402

DEEP_SHA = "da3ae9bf3a984afb1584153f2fe6044c94d955037086c73ae036049537966fbd"


class ScienceGenerator(unittest.TestCase):
    def test_catalogue_well_formed(self):
        fams = [f.family for f in S.CATALOGUE]
        self.assertEqual(len(fams), len(set(fams)))
        for f in S.CATALOGUE:
            self.assertIn(f.kind, S.KINDS)
            self.assertEqual(set(f.ranges), set(f.inputs))

    def test_rows_deterministic_and_exact(self):
        for f in S.CATALOGUE:
            a = S.draw_rows(f, random.Random(f"7:{f.family}"))
            b = S.draw_rows(f, random.Random(f"7:{f.family}"))
            self.assertEqual(a, b)
            self.assertEqual(len(a), S.N_PUBLIC + S.N_CHALLENGE + S.N_FINAL)
            self.assertEqual(len({tuple(r[k] for k in f.inputs) for r, _ in a}), len(a))
            for r, ans in a:
                q = Fraction(f.truth(*(r[n] for n in f.inputs)))
                self.assertEqual(q.denominator, 1)
                self.assertEqual(int(q), ans)
                self.assertEqual(run(f.tree, r), ans)

    def test_non_integer_row_refused(self):
        f = S.BY_FAMILY["sci_d_rest"]       # a*t^2/2 with a*t^2 odd
        self.assertIsNone(S.exact_answer(f, {"u": 0, "a": 1, "t": 3}))
        self.assertEqual(S.exact_answer(f, {"u": 0, "a": 2, "t": 3}), 9)
        g = S.BY_FAMILY["sci_dist_m"]       # 1 km/h for 1 s is 5/18 m
        self.assertIsNone(S.exact_answer(g, {"v": 1, "t": 1, "k": 1000, "c": 3600}))

    def test_tags(self):
        self.assertEqual(S.science_tag("sci_vsq"), {"domain": "science", "kind": "kinematics"})
        self.assertIsNone(S.science_tag("max_pair"))
        self.assertEqual(domain_of("sci_water_g"), "science")
        self.assertEqual(domain_of("max_pair"), "mathematics")
        self.assertIsNone(domain_of("absdiff"))


class FrozenScienceSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite, cls.easy, cls.hard = SS.load()

    def test_hash_matches(self):
        want = SS.HASH.read_text().split()[0]
        self.assertEqual(SS.suite_hash(self.suite), want)

    def test_deep_suite_untouched(self):
        raw = json.loads((ROOT / "data" / "deep" / "deep_suite.json").read_text())
        h = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(h, DEEP_SHA)

    def test_every_row_verified(self):
        for e in self.suite["easy"] + self.suite["hard"]:
            f = S.BY_FAMILY[e["family"]]
            self.assertEqual(e["domain"], "science")
            self.assertEqual(e["kind"], f.kind)
            self.assertEqual(e["tree"], f.tree)
            for r, ans in e["rows"]:
                self.assertEqual(S.exact_answer(f, r), ans)

    def test_reference_certifies_and_wrong_tree_rejected(self):
        for e, t in zip(self.suite["easy"] + self.suite["hard"], self.easy + self.hard):
            rec, pub, fin = certify(t, e["tree"])
            self.assertTrue(rec is not None and rec.supported and pub and fin, e["family"])
            rec2, pub2, fin2 = certify(t, ["add", e["tree"], ["const", 1]])
            self.assertFalse(rec2 is not None and rec2.supported and fin2, e["family"])

    def test_tiers_match_cold_record(self):
        self.assertTrue(all(e["cold_certified"] for e in self.suite["easy"]))
        self.assertTrue(all(not e["cold_certified"] for e in self.suite["hard"]))
        self.assertGreaterEqual(len(self.hard), 10)
        self.assertEqual({e["kind"] for e in self.suite["hard"]}, set(S.KINDS))

    def test_sense_classifies_every_suite_task_as_science(self):
        from nomad import sense as SN
        for e, t in zip(self.suite["easy"] + self.suite["hard"], self.easy + self.hard):
            r = SN.sense(t)
            self.assertEqual((r["domain"], r["kind"], r["source"]), ("science", e["kind"], "tag"), e["family"])
            self.assertEqual(SN.lead_ops(r), ())   # SENSE does not aim science tasks

    def test_regeneration_is_identical(self):
        self.assertEqual(SS.suite_hash(SS.generate(self.suite["seed"])), SS.suite_hash(self.suite))


if __name__ == "__main__":
    unittest.main()
