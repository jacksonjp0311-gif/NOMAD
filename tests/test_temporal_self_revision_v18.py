"""Data-only artifact contracts; positive validator doubles are disclosed."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad.mission_runtime import canonical,digest
from nomad.recursion import prepare_computation_experiment
from scripts import experiment_temporal_v18 as temporal


def fixture(base,winner='long'):
    profiles={name:asdict(value) for name,value in temporal.profile_configs().items()}
    scores={name:.5 if name==winner else .6 for name in profiles}
    choice={'selected_profile':winner,'profile_mean_objectives':scores,'profiles':profiles,
        'selection_rule':'minimum mean development logloss +2totalCPU/512; deterministic declared profile order breaks ties'}
    rows=[{'mode':'candidate_'+name,'metrics':{'mean_logloss':scores[name]-.01},
           'cost':{'total_cpu_seconds':2.56}} for name in profiles]
    data={'schema':temporal.SCHEMA+'.development','status':'COMPLETED','trials':rows,'development_choice':choice}
    path=base/'development.json';path.write_bytes(canonical(data));return path,data,choice


class TemporalSelfRevisionTests(unittest.TestCase):
    def test_data_only_candidate_retains_baseline_and_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);path,data,choice=fixture(base);output=base/'proposal'
            with patch.object(temporal,'validate_development',return_value=(data,choice)),\
                 patch('nomad.persistent.PersistentController',side_effect=AssertionError('candidate must not run')):
                report=prepare_computation_experiment(output,path)
            self.assertEqual(report['status'],'DEVELOPMENT_NOMINATION_ONLY')
            self.assertTrue(report['development_objective_improved']);self.assertFalse(report['heldout_read'])
            self.assertFalse(report['candidate_code_executed']);self.assertFalse(report['authoritative_source_replaced'])
            self.assertFalse(report['candidate_eligible_for_independent_test'])
            self.assertEqual(report['self_improvement_advantage'],'NOT_ESTABLISHED')
            self.assertEqual((output/'baseline/config.json').read_bytes(),(output/'rollback/config.json').read_bytes())
            for name,checksum in report['files_sha256'].items():self.assertEqual(digest((output/name).read_bytes()),checksum)
            self.assertEqual(json.loads((output/'protocol.json').read_bytes()),report)

    def test_standard_winner_makes_no_improvement_or_eligibility_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);path,data,choice=fixture(base,'standard')
            with patch.object(temporal,'validate_development',return_value=(data,choice)):
                report=prepare_computation_experiment(base/'proposal',path,future_plan_sha256='a'*64)
            self.assertEqual(report['status'],'BASELINE_RETAINED')
            self.assertFalse(report['development_objective_improved'])
            self.assertFalse(report['candidate_eligible_for_independent_test'])
            self.assertEqual(report['baseline_config'],report['candidate_config'])

    def test_future_digest_does_not_grant_acceptance_and_existing_artifact_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);path,data,choice=fixture(base);output=base/'proposal'
            with patch.object(temporal,'validate_development',return_value=(data,choice)):
                report=prepare_computation_experiment(output,path,future_plan_sha256='b'*64)
                self.assertEqual(report['independent_acceptance']['status'],'HOLD')
                original=(output/'protocol.json').read_bytes()
                with self.assertRaises(FileExistsError):prepare_computation_experiment(output,path)
                self.assertEqual((output/'protocol.json').read_bytes(),original)

    def test_incomplete_or_stale_report_refused_by_real_validator(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);path,_,_=fixture(base)
            with self.assertRaises(ValueError):prepare_computation_experiment(base/'proposal',path)
            self.assertFalse((base/'proposal').exists())

    def test_duplicate_keys_nonfinite_values_and_bad_future_digest_refused(self):
        for raw in (b'{"schema":1,"schema":2}',b'{"value":NaN}'):
            with tempfile.TemporaryDirectory() as temporary:
                base=Path(temporary);path=base/'development.json';path.write_bytes(raw)
                with self.assertRaises(ValueError):prepare_computation_experiment(base/'proposal',path)
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);path,_,_=fixture(base)
            with self.assertRaises(ValueError):prepare_computation_experiment(base/'proposal',path,future_plan_sha256='not-a-hash')


if __name__=='__main__':unittest.main()
