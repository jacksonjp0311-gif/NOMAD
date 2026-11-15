"""Prior adaptive failure evidence cannot be rewritten by a later experiment."""
import unittest
from unittest.mock import patch
from scripts import verify_lineage_v18 as lineage


class TemporalLineageTests(unittest.TestCase):
    def test_original_adaptive_evidence_and_mechanism_remain_bound(self):
        report=lineage.verify()['adaptive_3ffd467_evidence']
        self.assertEqual(report['status'],'PASS')
        self.assertTrue(report['includes_original_controller_study_audits_and_reports'])
        self.assertGreater(report['unchanged_files'],303)

    def test_rehashed_original_manifest_cannot_be_resealed(self):
        original=lineage.hash_file;target=lineage.ROOT/'results/RELEASE_MANIFEST_ADAPTIVE_V018.json'
        with patch.object(lineage,'hash_file',side_effect=lambda p:'0'*64 if p==target else original(p)):
            with self.assertRaisesRegex(ValueError,'original 3ffd467 ADAPTIVE seal differs'):lineage.verify()

    def test_old_negative_outcome_controller_report_and_provenance_are_immutable(self):
        for name in ('results/ADAPTIVE_MECHANISMS_V018.json','nomad/adaptive.py',
                     'docs/ADAPTIVE_REPORT_V018.md',
                     'experiments/development/adaptive_sources/w2n-74/original/subject.py'):
            original=lineage.hash_file;target=lineage.ROOT/name
            with self.subTest(name=name),patch.object(lineage,'hash_file',side_effect=lambda p:'0'*64 if p==target else original(p)):
                with self.assertRaisesRegex(ValueError,'frozen 3ffd467 ADAPTIVE evidence differs'):lineage.verify()


if __name__=='__main__':unittest.main()
