"""Preserve original FRONTIER failures, outcomes and their executable study."""
import unittest
from unittest.mock import patch

from scripts import verify_lineage_v18 as lineage


class AdaptiveLineageTests(unittest.TestCase):
    def test_original_frontier_evidence_and_mechanism_code_are_bound(self):
        evidence = lineage.verify()['frontier_993395f_evidence']
        self.assertEqual(evidence['status'], 'PASS')
        self.assertTrue(evidence['includes_original_mechanism_code'])

    def test_changed_historical_negative_result_is_not_resealed(self):
        original = lineage.hash_file
        target = lineage.ROOT/'results/FRONTIER_BITWORK_DIAGNOSIS_V018.json'
        with patch.object(lineage, 'hash_file', side_effect=lambda p: '0'*64 if p == target else original(p)):
            with self.assertRaisesRegex(ValueError, '993395f FRONTIER evidence differs'):
                lineage.verify()

    def test_changed_frozen_generator_is_not_relabelled_original(self):
        original = lineage.hash_file
        target = lineage.ROOT/'scripts/frontier_bitwork_v18.py'
        with patch.object(lineage, 'hash_file', side_effect=lambda p: '0'*64 if p == target else original(p)):
            with self.assertRaisesRegex(ValueError, '993395f FRONTIER evidence differs'):
                lineage.verify()
