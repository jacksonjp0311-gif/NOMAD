import tempfile
import unittest
from pathlib import Path

from nomad.ledger import EvidenceLedger
from nomad.skills import SkillRegistry


class SkillRegistryTests(unittest.TestCase):
    def test_external_challenges_promote_then_counterexample_contests(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = EvidenceLedger(Path(td) / "ledger.jsonl")
            registry = SkillRegistry(ledger=ledger)
            seq = ("variable", "constant")
            for i in range(3):
                record = registry.record_challenge(
                    signature=7,
                    sequence=seq,
                    task_id=f"task-{i}",
                    challenge_passed=True,
                    evaluator="independent-test",
                )
            self.assertEqual(record.status, "promoted")
            record = registry.record_challenge(
                signature=7,
                sequence=seq,
                task_id="counterexample",
                challenge_passed=False,
                evaluator="independent-test",
            )
            self.assertEqual(record.status, "contested")
            self.assertTrue(ledger.verify())
            path = Path(td) / "skills.json"
            registry.save(path)
            restored = SkillRegistry.load(path)
            self.assertEqual(restored.snapshot(), registry.snapshot())

    def test_search_cannot_self_promote(self):
        registry = SkillRegistry()
        self.assertEqual(registry.promoted(), [])


if __name__ == "__main__":
    unittest.main()
