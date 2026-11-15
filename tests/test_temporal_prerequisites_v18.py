"""Read-only refresh contracts; no native boundary or unfamiliar code execution."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from scripts import refresh_temporal_prerequisites_v18 as refresh


class TemporalPrerequisiteTests(unittest.TestCase):
    def test_timestamp_differential_uses_both_clocks(self):
        self.assertFalse(refresh.select_recent(SimpleNamespace(st_mtime=1,st_ctime=2),3))
        self.assertTrue(refresh.select_recent(SimpleNamespace(st_mtime=1,st_ctime=3),3))
        self.assertTrue(refresh.select_recent(SimpleNamespace(st_mtime=3,st_ctime=1),3))

    def test_corpus_leads_cannot_become_qualified_unseen_tasks(self):
        report=refresh.corpus_gap()
        self.assertEqual(report['existing_development_bundles'],3)
        self.assertEqual(report['exact_projection_parse_only_supported'],2)
        self.assertEqual(report['unseen_evaluation_tasks'],0)
        self.assertEqual(report['qualified_training_repositories'],0)
        self.assertFalse(report['private_contracts_opened'])
        self.assertEqual(report['status'],'HOLD')
        self.assertEqual(report['receipt_sha256'],refresh.sha(refresh.canonical({k:v for k,v in report.items() if k!='receipt_sha256'})))

    def test_receipt_writer_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'receipt.json';refresh.write_new(path,{'status':'HOLD'})
            original=path.read_bytes()
            with self.assertRaises(FileExistsError):refresh.write_new(path,{'status':'PASS'})
            self.assertEqual(path.read_bytes(),original)


if __name__=='__main__':unittest.main()
