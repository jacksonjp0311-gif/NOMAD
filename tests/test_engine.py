import unittest

from nomad.benchmarks import make_task
from nomad.engine import NomadEngine
from nomad.operators import FAMILIES


class EngineTests(unittest.TestCase):
    def test_solves_each_family(self):
        engine = NomadEngine(fixed_order=FAMILIES, learn=False)
        for i, family in enumerate(FAMILIES):
            hidden = make_task(family, i, 100 + i)
            result = engine.solve(hidden.public)
            self.assertTrue(result.solved, family)
            self.assertEqual(result.operator_family, family)

    def test_max_attempts_abstains(self):
        hidden = make_task("negate", 0, 5)
        engine = NomadEngine(fixed_order=FAMILIES, learn=False)
        result = engine.solve(hidden.public, max_attempts=1)
        self.assertFalse(result.solved)


if __name__ == "__main__":
    unittest.main()

class NoHiddenMetadataLeakTests(unittest.TestCase):
    def test_family_label_does_not_change_solution(self):
        from nomad.model import CodeTask
        hidden = make_task("constant", 3, 818)
        engine = NomadEngine(fixed_order=FAMILIES, learn=False)
        a = engine.solve(hidden.public)
        disguised = CodeTask(hidden.public.task_id, hidden.public.source, hidden.public.examples, family="negate")
        b = engine.solve(disguised)
        self.assertEqual((a.solved, a.source, a.attempts), (b.solved, b.source, b.attempts))
