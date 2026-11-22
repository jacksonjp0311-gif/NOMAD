import unittest
from nomad import cert


class CertTests(unittest.TestCase):
    def test_default_off(self):
        self.assertFalse(cert.enabled())

    def test_rows_deterministic_and_not_evidence(self):
        inputs = (("x", "int"), ("y", "int"))
        ev = [({"x": 3 * i + 1, "y": 7}, 3 * i + 2) for i in range(10)]
        a, b = cert.rows(inputs, ev), cert.rows(inputs, ev)
        self.assertEqual(a, b)
        seen = {(r["x"], r["y"]) for r, _ in ev}
        self.assertTrue(all((r["x"], r["y"]) not in seen for r in a))

    def test_bound_veto(self):
        inputs = (("x", "int"),)
        ev = [({"x": 3 * i + i % 3}, 3 * i + i % 3 + 1) for i in range(1, 12)]
        self.assertEqual(cert.check(["add", ["var", "x"], ["const", 1]], inputs, ev)["verdict"] != "veto", True)
        self.assertEqual(cert.check(["mul", ["var", "x"], ["const", 5]], inputs, ev)["verdict"], "veto")


if __name__ == "__main__":
    unittest.main()
