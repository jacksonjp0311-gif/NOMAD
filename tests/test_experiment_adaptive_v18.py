from dataclasses import asdict
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import experiment_adaptive_v18 as study


def request(mode='frequency',family='stationary'):
    return {'split':'development','seed':study.DEVELOPMENT_SEEDS[0],'family':family,'mode':mode,
            'controller_config':asdict(study.AdaptiveConfig())}


class AdaptiveExperimentTests(unittest.TestCase):
    def test_every_prediction_precedes_generator_outcome(self):
        class Observer:
            counts=[[1,1],[1,1]]
            pending=False
            def predict(self,action):
                self.assert_clear();self.pending=True;return .5
            def assert_clear(self):
                if self.pending:raise AssertionError('prediction overlap')
            def observe(self,action,outcome):
                if not self.pending:raise AssertionError('observation without forecast')
                self.pending=False
        model=Observer();actual=study.generated_outcome
        def outcome(*args):
            self.assertTrue(model.pending);return actual(*args)
        with patch.object(study,'make_predictor',return_value=model),patch.object(study,'generated_outcome',outcome):
            row=study.worker(request())
        self.assertEqual(len(row['trace']),128);self.assertEqual(row['metrics']['scored_forecasts'],96)

    def test_unseen_structure_and_eval_seed_never_enter_development(self):
        with patch.object(study,'generated_outcome') as generated,patch.object(study,'make_predictor') as models:
            with self.assertRaises(ValueError):study.worker(request(family='unseen_structure'))
            row=request();row['seed']=study.EVALUATION_SEEDS[0]
            with self.assertRaises(ValueError):study.worker(row)
            generated.assert_not_called();models.assert_not_called()

    def test_frozen_plan_and_source_required_before_evaluation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);calibration=base/'calibration.json'
            study.write_new(calibration,{'schema':study.SCHEMA+'.development','status':'COMPLETED',
                'suggested_controller_config':asdict(study.AdaptiveConfig())})
            with patch.object(study,'calibrated_config',return_value=study.AdaptiveConfig()):
                plan=study.freeze(base/'plan.json',calibration);study.validate(plan)
                with self.assertRaises(FileExistsError):study.freeze(base/'plan.json',calibration)
            with patch.object(study,'source_identity',return_value={'changed':'x'}):
                with self.assertRaises(ValueError):study.validate(plan)
            row=request();row.update(split='evaluation',seed=study.EVALUATION_SEEDS[0],plan={})
            with patch.object(study,'generated_outcome') as generated:
                with self.assertRaises(ValueError):study.worker(row)
                generated.assert_not_called()

    def test_fixed_metrics_and_counterbalanced_registered_schedule(self):
        rows=[{'p':.5,'outcome':i%2} for i in range(128)]
        result=study.metrics(rows)
        self.assertAlmostEqual(result['mean_logloss'],math.log(2));self.assertEqual(result['brier'],.25)
        self.assertEqual(result['ece10'],0)
        scheduled=study.schedule('evaluation')
        self.assertEqual(scheduled,study.schedule('evaluation'));self.assertEqual(len(scheduled),512)
        self.assertEqual(len(set(scheduled)),512)
        self.assertNotEqual([r[2] for r in scheduled[:8]],[r[2] for r in scheduled[8:16]])
        self.assertNotIn('unseen_structure',{r[0] for r in study.schedule('development')})

    def test_failed_trial_is_retained_and_not_assessed(self):
        failed={'split':'development','family':'stationary','seed':study.DEVELOPMENT_SEEDS[0],
            'mode':'frequency','status':'FAILED','cost':{'supervisor_cpu_seconds':.01,'whole_job_cpu_seconds':.02}}
        with tempfile.TemporaryDirectory() as temporary,patch.object(study,'execute',return_value=failed):
            row=study.run(Path(temporary)/'failed.json')
            self.assertEqual(row['status'],'INTERRUPTED_HOLD');self.assertEqual(row['trials'],[failed])
            self.assertNotIn('assessment',row);self.assertNotIn('suggested_controller_config',row)
            with self.assertRaises(ValueError):study.assess([failed],study.AdaptiveConfig())

    def test_calibration_refuses_status_only_and_incomplete_source_bound_receipt(self):
        partial={'schema':study.SCHEMA+'.development','status':'COMPLETED',
                 'suggested_controller_config':asdict(study.AdaptiveConfig())}
        with self.assertRaises(ValueError):study.calibrated_config(partial)
        partial.update(source_sha256_before=study.source_identity(),source_sha256_after=study.source_identity(),
                       source_stable=True,config=asdict(study.AdaptiveConfig()),trials=[])
        with self.assertRaises(ValueError):study.calibrated_config(partial)

    def test_raised_worker_failure_retains_attempt_and_unknown_cost(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(study,'execute',side_effect=OSError('controlled launch failure')):
            row=study.run(Path(temporary)/'failed.json')
            self.assertEqual(len(row['trials']),1);self.assertEqual(row['trials'][0]['status'],'FAILED')
            self.assertIsNone(row['trials'][0]['cost']['whole_job_cpu_seconds'])
            self.assertIsNone(row['whole_study_cpu_seconds'])
            self.assertEqual(row['cpu_coverage'],'INCOMPLETE_UNKNOWN_WORKER_COST')

    def test_native_selection_disabled_is_original_native_prediction(self):
        # Only the declared development stream is generated by this contract test.
        native=study.worker(request('native'));fixed=study.worker(request('no_selection'))
        self.assertEqual([r['p'] for r in native['trace']],[r['p'] for r in fixed['trace']])
        self.assertEqual(native['input_sha256'],fixed['input_sha256'])
        self.assertGreater(fixed['telemetry']['native_forecasts'],0)


if __name__=='__main__':unittest.main()
