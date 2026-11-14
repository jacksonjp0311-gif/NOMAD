import unittest

from nomad.python_benchmarks import make_python_task
from nomad.python_operators import generate_python_candidates
from nomad.python_search import ResonanceSearchEngine
from nomad.resonance import P_PARSE_ERROR, R_NAME_ERROR, R_ZERO_DIVISION, encode_resonance
from nomad.resonance_learner import ResonanceOperatorLearner
from nomad.simulation_v3 import _challenge


class ResonanceTests(unittest.TestCase):
    def test_parser_and_runtime_are_distinct_senses(self):
        syntax = make_python_task("syntax", 0, 1).public
        name = make_python_task("identifier", 0, 2).public
        s1 = encode_resonance(syntax)
        s2 = encode_resonance(name)
        self.assertTrue(s1.parser_bits & P_PARSE_ERROR)
        self.assertTrue(s2.runtime_bits & R_NAME_ERROR)
        self.assertNotEqual(s1.fusion_signature, s2.fusion_signature)

    def test_zero_division_channel(self):
        task = make_python_task("zero_guard", 0, 3).public
        state = encode_resonance(task)
        self.assertTrue(state.runtime_bits & R_ZERO_DIVISION)

    def test_operator_generation_repairs_syntax_and_guard(self):
        syntax = make_python_task("syntax", 0, 4).public
        zero = make_python_task("zero_guard", 0, 5).public
        self.assertTrue(generate_python_candidates(syntax.source)["syntax"])
        self.assertTrue(generate_python_candidates(zero.source)["zero_guard"])

    def test_reverberation_solves_unseen_compound(self):
        hidden = make_python_task("syntax+binary", 2, 99, compound=True)
        engine = ResonanceSearchEngine(ResonanceOperatorLearner(), mode="fusion")
        result = engine.solve(hidden.public, max_depth=4, max_expansions=180)
        self.assertTrue(result.solved)
        self.assertTrue(_challenge(hidden, result.source))
        self.assertGreaterEqual(len(result.lineage), 2)

    def test_hierarchical_learner_can_use_error_channel(self):
        learner = ResonanceOperatorLearner()
        hidden = make_python_task("identifier", 0, 8)
        state = encode_resonance(hidden.public)
        for _ in range(4):
            learner.update_state(state, "identifier", True)
            learner.update_state(state, "binary_operator", False)
        self.assertEqual(learner.rank_state(state)[0], "identifier")


if __name__ == "__main__":
    unittest.main()
