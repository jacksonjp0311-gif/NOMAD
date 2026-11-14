import unittest
from nomad.causal_skills import CausalSkillRegistry
from nomad.witness import Witness

class CausalSkillTests(unittest.TestCase):
    def _receipt(self, witness, task, tx, supported):
        candidate = (1.0, 2.0) if supported else (9.0, 9.0)
        return witness.attest(
            task_id=task, transmission_id=tx, world_epoch=0,
            current_public=(0.0, 0.0), target_public=(1.0, 2.0), candidate_public=candidate,
            current_challenge=(0.0, 0.0), target_challenge=(1.0, 2.0), candidate_challenge=candidate,
        )

    def test_learns_counterexample_bounded_precondition(self):
        w = Witness("test-w")
        r = CausalSkillRegistry(min_support=3, max_terms=2)
        for i in range(4):
            receipt = self._receipt(w, f"p{i}", f"txp{i}", True)
            self.assertTrue(r.ingest(witness=w, receipt=receipt, context={"ast_add", "error_above"}, family="binary", task_id=f"p{i}", transmission_id=f"txp{i}", world_epoch=0))
        neg = self._receipt(w, "n0", "txn0", False)
        r.ingest(witness=w, receipt=neg, context={"ast_add", "error_below"}, family="binary", task_id="n0", transmission_id="txn0", world_epoch=0)
        skill = r.promoted()[0]
        self.assertIn("error_above", skill.preconditions)
        self.assertTrue(skill.applies({"ast_add", "error_above"}))
        self.assertFalse(skill.applies({"ast_add", "error_below"}))

    def test_invalid_receipt_cannot_train(self):
        w = Witness("test-w")
        r = CausalSkillRegistry(min_support=1)
        receipt = self._receipt(w, "task", "tx", True)
        self.assertFalse(r.ingest(witness=w, receipt=receipt, context={"x"}, family="f", task_id="task", transmission_id="wrong", world_epoch=0))
        self.assertEqual([], r.observations)

if __name__ == "__main__": unittest.main()
