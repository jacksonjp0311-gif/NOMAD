import json
import tempfile
import unittest
from pathlib import Path

from nomad.benchmarks import dataset
from nomad.engine import NomadEngine
from nomad.learner import ContextualOperatorLearner
from nomad.ledger import EvidenceLedger
from nomad.simulation import train
from nomad.store import load_learner, save_learner


class StoreLedgerTests(unittest.TestCase):
    def test_save_load_roundtrip(self):
        learner = ContextualOperatorLearner(contextual=True)
        train(learner, dataset(7, 2, skew=True))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "skills.json"
            save_learner(learner, path)
            restored = load_learner(path)
            self.assertEqual(learner.snapshot(), restored.snapshot())

    def test_hash_chain(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = EvidenceLedger(Path(td) / "ledger.jsonl")
            engine = NomadEngine(ledger=ledger, learn=True)
            engine.solve(dataset(3, 1, skew=False)[0].public)
            self.assertTrue(ledger.verify())
            p = ledger.path
            lines = p.read_text().splitlines()
            self.assertTrue(lines)
            row = json.loads(lines[0])
            row["event"]["attempts"] = int(row["event"]["attempts"]) + 1
            lines[0] = json.dumps(row, sort_keys=True)
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.assertFalse(ledger.verify())


if __name__ == "__main__":
    unittest.main()
