import copy
import unittest
from unittest.mock import patch

from nomad.adaptive import AdaptiveController, AdaptiveConfig, digest


class AdaptiveTests(unittest.TestCase):
    def test_cold_and_public_planning_are_lazy(self):
        with patch('nomad.adaptive.load_native',side_effect=AssertionError('not selected')):
            model=AdaptiveController()
            row=model.decide({'candidate_count':64,'memory_records':0})
            self.assertEqual(row['mechanism'],'frequency')
            for i in range(16):
                model.predict(i%2);model.observe(i%2,i%2)
            self.assertEqual(model.telemetry['native_builds'],0)

    def test_future_labels_and_invalid_budget_refused(self):
        model=AdaptiveController()
        for state in ({'family':'lag3'},{'hidden_outcome':1},{'public_failures':True}):
            with self.assertRaises(ValueError):model.decide(state)
        with self.assertRaises(ValueError):model.decide(remaining_budget={'steps':float('inf')})
        self.assertEqual(model.decide(remaining_budget={'steps':0})['mechanism'],'abstain')

    def test_pending_public_observation_and_snapshot_are_strict(self):
        model=AdaptiveController();model.predict(0)
        with self.assertRaises(RuntimeError):model.predict(1)
        with self.assertRaises(RuntimeError):model.observe(1,0)
        with self.assertRaises(RuntimeError):model.snapshot()
        with self.assertRaises(RuntimeError):model.peek_probabilities()
        model.observe(0,1)
        changed=model.snapshot();changed['payload']['history'][0][1]=0
        with self.assertRaises(ValueError):AdaptiveController.load(changed)

    def test_measured_cost_does_not_silently_retune_frozen_cost(self):
        low=AdaptiveController();high=AdaptiveController()
        low.record_verified('temporal',.8,.001,'a',independently_verified=True)
        high.record_verified('temporal',.8,100,'a',independently_verified=True)
        self.assertEqual(low.decide()['scores'],high.decide()['scores'])
        self.assertEqual(low.selected,'temporal')

    def test_duplicate_contradictory_and_unverified_evidence(self):
        model=AdaptiveController()
        self.assertFalse(model.record_verified('native',.5,.1,'x'))
        self.assertTrue(model.record_verified('native',.5,.1,'x',independently_verified=True))
        self.assertFalse(model.record_verified('native',.5,.1,'x',independently_verified=True))
        with self.assertRaises(ValueError):model.record_verified('native',-.5,.1,'x',independently_verified=True)
        self.assertEqual(len(model.gains['native']),1)

    def test_history_ablation_never_loads_expensive_predictor(self):
        model=AdaptiveController(AdaptiveConfig(use_history=False))
        for i in range(64):model.ingest_public(i%2,i%3==0 and 1 or 0)
        model.record_verified('native',1,.1,'good',independently_verified=True)
        with patch('nomad.adaptive.load_native',side_effect=AssertionError('history-disabled')):
            self.assertEqual(model.decide()['mechanism'],'frequency')
        with self.assertRaises(ValueError):model.peek_probabilities('native')

    def test_actual_temporal_lazy_catchup_and_restart(self):
        model=AdaptiveController()
        for i in range(37):model.ingest_public(i%2,(i//2)%2)
        first=model.peek_probabilities('temporal')
        self.assertEqual(model.telemetry['catchup_observations'],37)
        saved=model.snapshot();restored=AdaptiveController.load(saved)
        self.assertEqual(restored.snapshot(),saved)
        debt=restored.decide()['scores']['temporal']
        self.assertEqual(debt['catchup_observations'],37)
        self.assertTrue(debt['requires_reconstruction'])
        self.assertGreater(debt['estimated_setup_seconds'],0)
        self.assertEqual(restored.peek_probabilities('temporal'),first)
        self.assertEqual(restored.telemetry['catchup_observations'],37)
        self.assertEqual(restored.decide()['scores'],model.decide()['scores'])

    def test_exploration_is_bounded_and_deterministic(self):
        model=AdaptiveController(AdaptiveConfig(use_structure=False))
        for i in range(64):model.ingest_public(i%2,(i//2)%2)
        rows=[model.decide() for _ in range(17)]
        selected=[row['decision_index'] for row in rows if row['exploration']]
        self.assertEqual(selected,[0,4,8,12,16])
        clone=AdaptiveController.load(model.snapshot())
        self.assertEqual(clone.decide(),model.decide())

    def test_memory_reset_removes_utility_not_public_prefix(self):
        model=AdaptiveController(AdaptiveConfig(use_memory=False))
        model.record_verified('native',1,.1,'x',independently_verified=True)
        model.ingest_public(0,1)
        self.assertEqual(model.decide()['scores']['native']['observations'],0)
        self.assertEqual(model.history,[(0,1)])


if __name__=='__main__':unittest.main()
