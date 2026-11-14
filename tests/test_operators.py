import unittest

from nomad.operators import generate_candidates


class OperatorTests(unittest.TestCase):
    def test_generates_families(self):
        c = generate_candidates("x + 2")
        self.assertTrue(c["root_operator"])
        self.assertTrue(c["constant"])
        self.assertTrue(c["variable"])
        self.assertTrue(c["negate"])

    def test_no_duplicate_sources(self):
        c = generate_candidates("x + y")
        sources = [x.source for xs in c.values() for x in xs]
        self.assertEqual(len(sources), len(set(sources)))


if __name__ == "__main__":
    unittest.main()
