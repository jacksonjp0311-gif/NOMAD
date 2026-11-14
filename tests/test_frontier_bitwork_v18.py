"""Trusted mechanism protocol checks; development seeds are not evaluation."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad.platform_bitwork import NativeDecisionRanker
from scripts import frontier_bitwork_v18 as study


class FrontierBitworkTests(unittest.TestCase):
    def test_function_call_scope_cannot_import_other_task_semantics(self):
        ranker = NativeDecisionRanker('frequency', action_schema='python-call-relational-vs-other')
        self.assertEqual(ranker._action('comparison'), 0)
        self.assertEqual(ranker._action('binary_operator'), 1)
        for foreign in ('GENESIS', '==→!=', 'arbitrary_family'):
            with self.assertRaises(ValueError): ranker._action(foreign)
        self.assertEqual(NativeDecisionRanker.load(ranker.snapshot()).action_schema,
                         'python-call-relational-vs-other')

    def test_freezing_never_generates_an_outcome_and_is_immutable(self):
        with tempfile.TemporaryDirectory() as td, patch.object(study, 'outcome') as generator:
            path = Path(td)/'plan.json'
            document = study.freeze(path)
            study.validate(document)
            self.assertFalse(document['payload']['evaluation_outcomes_generated'])
            generator.assert_not_called()
            with self.assertRaises(FileExistsError): study.freeze(path)

    def test_changed_design_or_source_refuses_evaluation(self):
        with tempfile.TemporaryDirectory() as td:
            document = study.freeze(Path(td)/'plan.json')
            altered = copy.deepcopy(document)
            altered['payload']['design']['generator']['flip_probability'] = 0
            altered['sha256'] = study.digest(altered['payload'])
            with self.assertRaises(ValueError): study.validate(altered)
            with patch.object(study, 'source_identity', return_value={}):
                with self.assertRaises(ValueError): study.validate(document)
        with self.assertRaises(ValueError):
            study.stream(study.EVALUATION_SEEDS[0], 'stationary', study.specification())

    def test_all_forecasts_precede_each_generated_outcome(self):
        order = []
        class Observed:
            def predict(self, action): order.append('predict'); return 0.5
            def observe(self, action, y): order.append('observe')
            def snapshot(self): return {}
        design = study.specification(); design['steps'] = 4; design['unscored_prefix'] = 1
        original = study.outcome
        def observed(*args): order.append('generate'); return original(*args)
        with patch.object(study, 'models', return_value={name: Observed() for name in study.MODES}), \
                patch.object(study, 'outcome', side_effect=observed):
            row = study.stream(study.DEVELOPMENT_SEEDS[0], 'lag3', design, development=True)
        self.assertEqual(order, (['predict']*7+['generate']+['observe']*7)*4)
        self.assertEqual(row['metrics']['native']['scored_forecasts'], 3)

    def test_real_native_predict_observe_on_development_stream(self):
        design = study.specification(); design['steps'] = 12; design['unscored_prefix'] = 4
        row = study.stream(study.DEVELOPMENT_SEEDS[0], 'boolean_history', design, development=True)
        self.assertEqual(len(row['trace']), 12)
        self.assertEqual(row['native_snapshot']['steps'], 12)
        self.assertFalse(row['native_snapshot']['lag_search_active'])
        self.assertTrue(all(0 < p < 1 for event in row['trace'] for p in event['probabilities'].values()))

    def test_frozen_negative_forecast_has_exact_computational_decomposition(self):
        report = study.diagnose()
        self.assertEqual(report['training_events'], 8)
        self.assertFalse(report['lag_discovery_could_contribute'])
        self.assertEqual(report['first_original_lag_checkpoint'], 24)
        self.assertEqual(report['interventions']['native']['action_probabilities'],
                         report['interventions']['native_no_lag']['action_probabilities'])
        for row in report['decomposition']:
            self.assertAlmostEqual(row['frequency']+sum(row['additive_probability_contributions'].values()),
                                   row['reconstructed_native'], places=12)


if __name__ == '__main__': unittest.main()
