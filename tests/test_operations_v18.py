"""Operational contracts. Execution doubles are trusted fixtures, never containment."""
import contextlib
from dataclasses import replace
import io
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from nomad import platform_mission as mission
from nomad.platform_cli import main, _review
from nomad.persistent import PersistentController
from nomad.mission_runtime import InjectedInterruption, MissionHold
from tests.test_frontier_function_mission_v18 import fixture, controlled_execution, POLICY


def setup(base, mechanism='temporal', late=False, memory=None, wrong=False):
    source,public,challenge,final=fixture(base)
    if late:
        path=source/'lower.py'
        path.write_bytes(path.read_bytes().replace(b'value < limit',b'value == limit'))
        for row in public+challenge+final: row['expected']=max(row['args'])
    if wrong: final[0]['expected']=999
    root=base/'mission'
    goal=mission.initialize_functions(root,source,goal_text='trusted operating fixture',
        public=public,challenge=challenge,final=final,policy=POLICY,
        memory_root=memory,operating_mechanism=mechanism)
    return root,goal


class OperatingControllerTests(unittest.TestCase):
    def test_frozen_research_sources_and_results_remain_unchanged(self):
        root=Path(__file__).resolve().parents[1]
        baseline=json.loads((root/'results/BASELINE_OPERATIONS_V018.json').read_bytes())
        for name,expected in baseline['source_and_result_sha256'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),expected,name)

    def test_native_selection_is_live_and_detector_cannot_interrupt_it(self):
        controller=PersistentController(mission.operational_config())
        decision=mission._persistent_decide(controller,{}, {'steps':64,'max_cost_seconds':120.}, 'native')
        for i in range(64):
            controller.predict(i%2);controller.observe(i%2,int(i>=32))
        self.assertEqual(controller.selected,'native')
        self.assertEqual(type(controller.models['native']).__name__,'GovernedBitworkV14')
        self.assertEqual(len(controller.models['native'].history),64)
        self.assertEqual(controller.alarms,[])
        self.assertEqual(controller.next_decision,decision['committed_until'])

    def test_multiple_candidates_reuse_control_and_restart_exactly(self):
        signatures=[]
        for boundary in (None,'after_persistent_control','after_persistent_update'):
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as temporary:
                root,goal=setup(Path(temporary),late=True)
                with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                    if boundary:
                        with self.assertRaises(InjectedInterruption):mission.run(root,interrupt_at=boundary)
                    result=mission.run(root)
                self.assertEqual(result['status'],'completed')
                rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
                updates=[r for r in rows if r['kind']=='F_P_UPDATED']
                controls=[r for r in rows if r['kind']=='F_P_CONTROL']
                self.assertGreater(len(updates),1)
                self.assertEqual(len(controls),1)
                self.assertEqual(result['persistent']['mechanisms'],['temporal'])
                self.assertTrue(goal['analysis']['genesis'])
                signatures.append([(r['kind'],r['data'].get('candidate'),r['data'].get('p'))
                    for r in rows if r['kind'] in ('F_P_CONTROL','F_P_FORECAST','F_SELECTED')])
        self.assertEqual(signatures[0],signatures[1]);self.assertEqual(signatures[0],signatures[2])

    def test_verified_warm_state_restores_without_history_catchup(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root,goal=setup(base,mechanism='native',memory=base/'memory')
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                self.assertEqual(mission.run(root)['status'],'completed')
            state,cache=mission.read_function_persistent_controller(base/'memory',config=mission.operational_config(),operating_mechanism='native')
            self.assertEqual(cache['status'],'RESTORED')
            before=state.telemetry['catchup_observations']
            state.peek_probabilities('native')
            self.assertEqual(before,state.telemetry['catchup_observations'])
            self.assertTrue(state.models['native'].history)

    def test_failed_final_reverts_and_cannot_export_or_train(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root,goal=setup(base,memory=base/'memory',wrong=True)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                self.assertEqual(mission.run(root)['status'],'rejected')
            self.assertEqual(mission._manifest(root/'workspace'),goal['baseline'])
            self.assertFalse((base/'memory').exists())
            with self.assertRaises(MissionHold):_review(root,base/'export','accept')

    def test_cold_reconstruction_obeys_fixed_mechanism(self):
        history=[(i%2,(i//3)%2) for i in range(130)]
        with patch.object(mission,'_persistent_prefix',return_value=(history,[],[])):
            controller,cache=mission._persistent_from_memory(mission.operational_config(),{},0,'frequency')
        self.assertEqual(cache['status'],'REBUILT')
        self.assertEqual(set(controller.models),{'frequency'})
        self.assertEqual(controller.history,history)
        self.assertEqual({d['mechanism'] for d in controller.decisions},{'frequency'})

    def test_rechained_forecast_cannot_skip_an_expired_control(self):
        from tests.test_adaptive_mission_v18 import rehash
        config=replace(mission.operational_config(),commitment=1)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(mission,'operational_config',return_value=config):root,goal=setup(Path(temporary),late=True)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                with self.assertRaises(InjectedInterruption):mission.run(root,interrupt_at='after_persistent_update')
            rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
            checked=mission._validate_persistent_trace(goal,rows)
            state=checked['state'];control=checked['control']
            candidate=next(i for i in control['order'] if i!=checked['updated'][-1]['candidate'])
            action=int(mission._function_proposal(goal,candidate)['family']!='comparison')
            learner=mission._persistent_load(state,config,checked['history'],0)
            probability=learner.predict(action)  # Deliberately bypass the fixed-policy decision.
            rows.append({'seq':len(rows)+1,'prev':rows[-1]['sha256'],'mission_id':goal['mission_id'],
                'kind':'F_P_FORECAST','data':{'candidate':candidate,'action':action,'p':probability,
                    'mechanism':learner.selected,'state_before_sha256':mission.digest(mission.canonical(state))}})
            rehash(rows)
            with self.assertRaisesRegex(MissionHold,'current authorized control'):
                mission._validate_persistent_trace(goal,rows)


class OperatingCliTests(unittest.TestCase):
    def call(self, args):
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):code=main(args)
        return code,json.loads(output.getvalue())

    def test_inspection_requires_no_engine_and_never_imports_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);source,*_=fixture(base)
            code,result=self.call(['inspect-source','--source',str(source)])
            self.assertEqual(code,0);self.assertIn('bounded',result['interfaces']['lower.py'])
            self.assertFalse(result['executed_code'])
            (source/'evil.py').write_text('raise RuntimeError("must never execute")\n')
            code,result=self.call(['inspect-source','--source',str(source)])
            self.assertEqual(code,3);self.assertFalse(result['untrusted_host_fallback'])

    def test_default_temporal_and_review_patch_applies_to_exact_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);source,public,challenge,final=fixture(base)
            path=source/'lower.py';path.write_bytes(b'def bounded(value, limit):\n    return value - limit')
            for row in public+challenge+final:row['expected']=sum(row['args'])
            before=mission._manifest(source)
            contract=base/'contract.json'
            contract.write_text(json.dumps({'adapter':'python-functions-v1','goal_text':'trusted fixture',
                'public':public,'challenge':challenge,'final':final}))
            root=base/'mission'
            code,goal=self.call(['--image',POLICY.image,'init','--root',str(root),'--source',str(source),'--contract',str(contract)])
            self.assertEqual(code,0)
            self.assertEqual(goal['persistent']['decision']['mechanism'],'temporal')
            self.assertFalse(goal['persistent']['config']['detector_enabled'])
            self.assertTrue(any(r.get('origin')=='GENESIS' for r in goal['analysis']['proposals']))
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                code,result=self.call(['run','--root',str(root)])
            self.assertEqual(code,0)
            code,review=self.call(['review','--root',str(root)])
            self.assertEqual(code,0);self.assertTrue(review['witness']);self.assertTrue(review['final'])
            for decision in ('accept','reject'):
                code,report=self.call([decision,'--root',str(root),'--output',str(base/decision)])
                self.assertEqual(code,0);self.assertEqual(report['decision'],decision)
                self.assertFalse(report['source_application_performed'])
            self.assertEqual(mission._manifest(source),before)
            checked=subprocess.run(['git','apply','--check',str(base/'accept'/'proposed.patch')],cwd=source,capture_output=True)
            self.assertEqual(checked.returncode,0,checked.stderr)
            with self.assertRaises(FileExistsError):_review(root,base/'accept','accept')

    def test_repair_refuses_hold_before_initializing_or_dispatching(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);receipt=base/'hold.json';receipt.write_text('{"status":"HOLD"}')
            with patch.object(mission,'initialize_functions') as initialize,patch.object(mission,'run_isolated') as execute:
                code,result=self.call(['--image',POLICY.image,'repair','--root',str(base/'mission'),
                    '--source',str(base/'absent'),'--contract',str(base/'absent.json'),'--isolation-receipt',str(receipt)])
            self.assertEqual(code,3);initialize.assert_not_called();execute.assert_not_called()
            self.assertFalse((base/'mission').exists())

    def test_duplicate_contract_keys_are_refused(self):
        from nomad.platform_cli import _read_json
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'bad.json';path.write_text('{"goal_text":"a","goal_text":"b"}')
            with self.assertRaisesRegex(ValueError,'duplicate'):_read_json(path)

    def test_arithmetic_export_requires_current_terminal_evidence(self):
        from tests.test_platform_mission_v18 import fixture as arithmetic, passing_execution
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root,_=arithmetic(base)
            with patch.object(mission,'run_isolated',side_effect=passing_execution):mission.run(root)
            review=_review(root)
            self.assertTrue(review['witness']);self.assertTrue(review['final'])
            path=root/'workspace'/'solution.py';original=path.read_bytes()
            path.write_bytes((root/'baseline'/'solution.py').read_bytes())
            with self.assertRaises(MissionHold):_review(root)
            path.write_bytes(original)
            (root/'learning.json').unlink()
            with self.assertRaises(MissionHold):_review(root)


if __name__=='__main__':unittest.main()
