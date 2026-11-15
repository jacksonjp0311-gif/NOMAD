"""Prospective design, evaluator separation and incomplete-evidence contracts."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import experiment_temporal_v18 as study


class TemporalExperimentTests(unittest.TestCase):
    def test_new_seed_inventory_and_long_matched_schedule(self):
        prior=set(range(18185101,18185109))|{18185001}
        self.assertFalse(prior & set(study.EVALUATION_SEEDS))
        self.assertFalse(set(study.DEVELOPMENT_SEEDS)&set(study.EVALUATION_SEEDS))
        rows=study.schedule('evaluation')
        self.assertEqual(len(rows),576)
        self.assertEqual(len(set(rows)),576)
        self.assertEqual(study.RESTART_AT,(256,))
        self.assertEqual(len(study.schedule('development')),126)
        self.assertNotIn('unseen_structure',{f for f,s,m in study.schedule('development')})

    def test_metrics_have_exact_scored_prefix_and_calibration(self):
        trace=[{'p':.5,'outcome':i%2} for i in range(512)]
        result=study.metrics(trace)
        self.assertAlmostEqual(result['mean_logloss'],math.log(2))
        self.assertEqual(result['brier'],.25)
        self.assertEqual(result['ece10'],0.)
        self.assertEqual(result['scored_forecasts'],448)
        with self.assertRaises(ValueError): study.metrics(trace[:-1])

    def test_change_matching_is_evaluator_only_and_counts_extra_alarms(self):
        value=study.detector_metrics('shift',[100,180,185,450])
        self.assertEqual(value['delays'],[9,None])
        self.assertEqual(value['false_alarms'],3)
        self.assertEqual(study.detector_metrics('stationary',[100])['false_alarms'],1)

    def test_incomplete_inventory_cannot_have_primary_result(self):
        with self.assertRaises(ValueError): study.assess([])

    def test_receipts_cannot_overwrite_prior_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'receipt.json'
            study.write_new(path,{'status':'failed'})
            with self.assertRaises(FileExistsError): study.write_new(path,{'status':'passed'})
            self.assertEqual(study.read(path),{'status':'failed'})

    def test_old_comparator_configuration_is_preserved(self):
        value=study.original_config()
        self.assertEqual(value.block_size,16)
        self.assertEqual(value.max_history,512)

    def test_heldout_worker_requires_frozen_plan_before_generating(self):
        with patch.object(study,'validate',side_effect=ValueError('unfrozen')):
            with self.assertRaises(ValueError):
                study.worker({'split':'evaluation','family':'stationary','seed':18186101,
                              'mode':'frequency','plan':{}})

    def test_exact_seed_block_sign_inference(self):
        self.assertEqual(study.sign_test([-1]*8)['p_one_sided'],1/256)
        self.assertEqual(study.sign_test([0]*8)['p_one_sided'],1.)


if __name__=='__main__': unittest.main()
