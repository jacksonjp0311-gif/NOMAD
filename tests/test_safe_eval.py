import unittest

from nomad.safe_eval import UnsafeExpression, evaluate


class SafeEvalTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(evaluate("x * 2 + y", {"x": 3, "y": 4}), 10)

    def test_rejects_call(self):
        with self.assertRaises(UnsafeExpression):
            evaluate("__import__('os')", {"x": 1, "y": 2})


if __name__ == "__main__":
    unittest.main()
