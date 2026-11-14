"""Qualifier preconditions and controlled contracts; never a native PASS."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad import platform_mission as mission
from nomad.isolation import SandboxPolicy
from nomad.mission_runtime import InjectedInterruption, MissionHold
from scripts import qualify_function_recovery_frontier_v18 as qualifier
from tests.test_frontier_function_mission_v18 import controlled_execution


class FunctionRecoveryQualifierTests(unittest.TestCase):
    def test_missing_native_prerequisites_hold_before_fixture_creation(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(qualifier,'_fixture',side_effect=AssertionError('fixture created')):
            path=Path(temporary)/'new-evidence'
            result=qualifier.qualify(evidence_root=path)
            self.assertEqual(result['status'],'HOLD'); self.assertEqual(result['cases'],[])
            self.assertFalse(path.exists()); self.assertTrue(result['source_stable'])
            self.assertEqual(result['receipt_sha256'],qualifier.canonical_digest({k:v for k,v in result.items() if k!='receipt_sha256'}))

    def test_hold_native_receipt_cannot_authorize_a_function_mission(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(qualifier,'_fixture',side_effect=AssertionError('fixture created')):
            base=Path(temporary); receipt=base/'hold.json'
            receipt.write_text(json.dumps({'schema':'nomad.native-isolation-qualification.v18','status':'HOLD'}))
            result=qualifier.qualify('python@sha256:'+'a'*64,receipt,base/'new-evidence')
            self.assertEqual(result['status'],'HOLD'); self.assertEqual(result['cases'],[])
            self.assertFalse((base/'new-evidence').exists())

    def test_owner_observation_exception_still_recovers_recorded_dispatch(self):
        with patch.object(qualifier,'_hard_death_once',side_effect=OSError('controlled inspect failure')), \
             patch.object(mission,'recover',return_value={}) as recovery:
            with self.assertRaisesRegex(OSError,'controlled inspect failure'):
                qualifier._hard_death(Path('fixture'),Path('base'))
            recovery.assert_called_once_with(Path('fixture'))

    def test_source_drift_cannot_promote_hold_or_demote_fail(self):
        for status,wanted in (('PASS','HOLD'),('FAIL','FAIL')):
            with self.subTest(status=status), patch.object(qualifier,'source_identity',return_value={'new':'1'*64}):
                result=qualifier._seal({'status':status,'source_sha256_before':{'old':'0'*64},'reason':None})
                self.assertEqual(result['status'],wanted); self.assertFalse(result['source_stable'])

    def test_actual_two_file_partial_checkpoint_contract_with_explicit_execution_double(self):
        policy=SandboxPolicy(image='python@sha256:'+'a'*64,**qualifier.POLICY)
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            reference=qualifier._fixture(base/'reference',policy,two=True)
            interrupted=qualifier._fixture(base/'interrupted',policy,two=True)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                mission.run(reference); reference_result=qualifier._control(reference)
                self.assertTrue(reference_result['passed']); self.assertEqual(reference_result['changed_files'],2)
                with self.assertRaises(InjectedInterruption):
                    mission.run(interrupted,interrupt_at='after_multifile_patch_write')
                pending=qualifier._rows(interrupted)[-1]['data']
                current=mission._manifest(interrupted/'workspace')
                self.assertNotEqual(current,pending['before']); self.assertNotEqual(current,pending['after'])
                mission.run(interrupted); result=qualifier._control(interrupted,reference_result)
                self.assertTrue(result['passed']); self.assertTrue(result['matches_reference'])

    def test_equivalence_ignores_suite_wall_time_but_keeps_api_observations(self):
        policy=SandboxPolicy(image='python@sha256:'+'a'*64,**qualifier.POLICY)
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); controls=[]
            for number in (1,2):
                root=qualifier._fixture(base/str(number),policy)
                def execution(source,**kwargs):
                    result=controlled_execution(source,**kwargs)
                    if kwargs['command']==mission.COMMAND: result['output_sha256']=str(number)*64
                    return result
                with patch.object(mission,'run_isolated',side_effect=execution):
                    mission.run(root); controls.append(qualifier._control(root,controls[0] if controls else None))
            self.assertTrue(controls[1]['matches_reference']); self.assertTrue(controls[1]['passed'])


if __name__=='__main__': unittest.main()
