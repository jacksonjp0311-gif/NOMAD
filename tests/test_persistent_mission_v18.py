"""Persistent mission contracts with explicit trusted fixture worker doubles.

Real controller/parser/memory code runs; these are not Docker qualifications.
"""
from dataclasses import asdict,replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad import platform_mission as mission
from nomad.persistent import PersistentConfig,PersistentController
from nomad.mission_runtime import InjectedInterruption,MissionHold,canonical,digest
from tests.test_frontier_function_mission_v18 import fixture,controlled_execution,POLICY
from tests.test_adaptive_mission_v18 import rehash


CONFIG=PersistentConfig(state_policy='selectivewarm',commitment=1,credit_horizon=2,
    detector_window=2,detector_cooldown=4,detector_threshold=4.)


def initialize(base,*,memory=None,epoch=0,marker=None,config=None,wrong=False,**options):
    source,public,challenge,final=fixture(base,two=options.pop('two',False))
    if options.pop('late',False):
        path=source/'lower.py';path.write_bytes(path.read_bytes().replace(b'value < limit',b'value == limit'))
        for row in public+challenge+final:row['expected']=max(row['args'])
    if marker is not None:
        path=source/'lower.py';path.write_bytes(path.read_bytes()+('\ndef marker():\n    return '+str(marker)+'\n').encode())
    if wrong:final[0]['expected']=9999
    root=base/'mission'
    goal=mission.initialize_functions(root,source,goal_text='trusted persistent contract fixture',
        public=public,challenge=challenge,final=final,policy=POLICY,memory_root=memory,capture_epoch=epoch,
        persistent_controller=config or CONFIG,**options)
    return root,goal


class PersistentMissionTests(unittest.TestCase):
    observed_decision_effects=[]
    def test_real_public_updates_and_terminal_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,goal=initialize(Path(temporary))
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):result=mission.run(root)
            self.assertEqual(result['status'],'completed');self.assertGreater(result['persistent']['public_updates'],0)
            rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
            checked=mission._validate_persistent_trace(goal,rows)
            self.assertEqual(len(checked['history']),len(checked['public_search']))
            with patch.object(mission,'run_isolated',side_effect=AssertionError('duplicate dispatch')):
                self.assertEqual(mission.run(root)['status'],'completed')
            self.assertEqual(result['witness_observations'],1);self.assertEqual(result['final_observations'],1)

    def test_settled_state_restart_at_public_boundaries(self):
        decisions=[]
        for boundary in (None,'after_persistent_control','after_persistent_forecast','after_public','after_persistent_update','after_memory'):
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as temporary:
                root,goal=initialize(Path(temporary))
                with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                    if boundary:
                        with self.assertRaises(InjectedInterruption):mission.run(root,interrupt_at=boundary)
                    result=mission.run(root)
                self.assertEqual(result['status'],'completed')
                rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
                decisions.append([(r['kind'],r['data'].get('candidate'),r['data'].get('p'),r['data'].get('decision'))
                    for r in rows if r['kind'] in ('F_P_CONTROL','F_P_FORECAST','F_SELECTED')])
                self.assertEqual(sum(r['kind']=='F_P_UPDATED' for r in rows),result['persistent']['public_updates'])
        for decision in decisions[1:]:self.assertEqual(decision,decisions[0])

    def test_configuration_only_and_private_noninterference(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);values=[]
            for i,wrong in enumerate((False,True)):
                folder=base/str(i);folder.mkdir();root,goal=initialize(folder,wrong=wrong)
                values.append((mission._persistent_semantics(goal['persistent']['controller_after']),goal['analysis']['candidate_inventory_sha256']))
            self.assertEqual(values[0],values[1])
        with tempfile.TemporaryDirectory() as temporary,self.assertRaisesRegex(ValueError,'configuration only'):
            initialize(Path(temporary),config=PersistentController(CONFIG))

    def test_abstention_has_no_verifier_or_learning_authority(self):
        config=replace(CONFIG,commitment=2,cost_seconds={name:100. for name in ('frequency','temporal','native')})
        with tempfile.TemporaryDirectory() as temporary:
            root,_=initialize(Path(temporary),config=config)
            with patch.object(mission,'run_isolated',side_effect=AssertionError('abstained dispatch')):
                for call in (mission.run,mission.inspect,mission.recover):
                    result=call(root);self.assertEqual(result['status'],'abstained');self.assertEqual(result['witness_observations'],0)
            self.assertFalse((root/'learning.json').exists())

    def test_failed_final_does_not_admit_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);memory=base/'memory';root,_=initialize(base,memory=memory,wrong=True)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):self.assertEqual(mission.run(root)['status'],'rejected')
            self.assertFalse(memory.exists())

    def test_later_success_interrupted_before_update_selects_its_own_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,goal=initialize(Path(temporary),late=True);original=mission.Journal.append;interrupted=[]
            def append(journal,kind,data):
                value=original(journal,kind,data)
                if kind=='F_OBSERVED' and data['operation'].startswith('search:') and data['result']['supported'] and not interrupted:
                    previous=[r for r in journal.read() if r['kind']=='F_P_UPDATED']
                    self.assertTrue(previous,'the fixture must have an earlier failed, updated candidate')
                    interrupted.append(data['operation'].partition(':')[2]);raise InjectedInterruption('later_success')
                return value
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                with patch.object(mission.Journal,'append',append),self.assertRaises(InjectedInterruption):mission.run(root)
                result=mission.run(root)
            self.assertEqual(result['status'],'completed')
            self.assertEqual(mission.resolved_goal(root)['candidate']['id'],interrupted[0])

    def test_distinct_accepted_prefix_restores_native_state_and_expires(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);memory=base/'memory';allocations=[];mechanisms=[]
            for number in range(3):
                folder=base/str(number);folder.mkdir();root,goal=initialize(folder,memory=memory,epoch=number,marker=20+number)
                allocations.append(goal['persistent'])
                with patch.object(mission,'run_isolated',side_effect=controlled_execution):result=mission.run(root)
                self.assertEqual(result['status'],'completed');mechanisms.extend(result['persistent']['mechanisms'])
                self.observed_decision_effects.append({'task':number,'initial_mechanism':goal['persistent']['decision']['mechanism'],
                    'memory_cache':goal['persistent']['memory_cache']['status'],'proposal_cap':goal['persistent']['max_candidates'],
                    'probe_cap':goal['probe_budget'],'actual_probes':result['baseline_probes_recorded'],
                    'genesis_cap':goal['persistent']['genesis_max_eval'],
                    'genesis_evaluations':sum(r['candidates_evaluated'] for r in goal['analysis']['genesis']),
                    'ast_checks':goal['analysis']['generated_candidates_checked'],'public_updates':result['persistent']['public_updates'],
                    'runtime_mechanisms':result['persistent']['mechanisms'],'status':result['status']})
            self.assertEqual(allocations[1]['memory_cache']['status'],'RESTORED')
            self.assertIn('native',mechanisms+[a['decision']['mechanism'] for a in allocations])
            self.assertTrue(any(a['genesis_max_eval']>0 for a in allocations))
            active,cache=mission.read_function_persistent_controller(memory,config=CONFIG,now_epoch=2)
            self.assertEqual(cache['status'],'RESTORED');self.assertIn('native',active.models)
            self.assertTrue(active.models['native'].history)
            cold,expired=mission.read_function_persistent_controller(memory,config=CONFIG,now_epoch=9)
            self.assertEqual(cold.history,[]);self.assertEqual(expired['status'],'COLD')
            changed,metadata=mission.read_function_persistent_controller(memory,config=replace(CONFIG,cost_weight=3.),now_epoch=2)
            self.assertEqual(metadata['status'],'REBUILT');self.assertEqual(changed.history,active.history)

    def test_rehashed_diagnosis_recall_forecast_and_private_training_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,goal=initialize(Path(temporary))
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):mission.run(root)
            path=root/'events.jsonl';original=path.read_bytes();rows=mission.Journal(path,goal['mission_id']).read()
            for mutation in ('posterior','recall','forecast','duplicate_update'):
                with self.subTest(mutation=mutation):
                    altered=json.loads(json.dumps(rows))
                    if mutation=='posterior':next(r['data'] for r in altered if r['kind']=='F_DIAGNOSIS')['posterior']['lower.py']=.125
                    elif mutation=='recall':next(r['data'] for r in altered if r['kind']=='F_P_CONTROL')['mnemonic_recall']={'invented':{'outcome':'impact'}}
                    elif mutation=='forecast':next(r['data'] for r in altered if r['kind']=='F_P_FORECAST')['p']=.123
                    else:
                        index=next(i for i,r in enumerate(altered) if r['kind']=='F_P_UPDATED');altered.insert(index+1,dict(altered[index]))
                    for i,row in enumerate(altered,1):row['seq']=i
                    rehash(altered);path.write_bytes(b''.join(canonical(r)+b'\n' for r in altered))
                    with self.assertRaises(MissionHold):mission.inspect(root)
                    path.write_bytes(original)
            memory=root/'mnemonic'/'events.jsonl';saved=mission.Journal(memory,mission.FUNCTION_MEMORY_ID).read()
            trace=saved[1]['data']['persistent_evidence']['public_trace']
            row=json.loads(json.dumps(trace[-2]));row['kind']='F_FINAL';row['data']={'supported':True};trace.insert(-1,row)
            for i,row in enumerate(trace,1):row['seq']=i
            rehash(trace);rehash(saved);memory.write_bytes(b''.join(canonical(r)+b'\n' for r in saved))
            with self.assertRaises(MissionHold):mission.read_function_persistent_controller(memory.parent,config=CONFIG)

    def test_ambiguous_search_requires_confirmed_cleanup_before_once_only_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,goal=initialize(Path(temporary));original=mission.Journal.append;interrupted=[]
            def append(journal,kind,data):
                value=original(journal,kind,data)
                if kind=='F_DISPATCHED' and data['operation'].startswith('search:') and not interrupted:
                    interrupted.append(data);raise InjectedInterruption('search_dispatch')
                return value
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                with patch.object(mission.Journal,'append',append),self.assertRaises(InjectedInterruption):mission.run(root)
                before=(root/'events.jsonl').read_bytes()
                with self.assertRaises(MissionHold):mission.run(root)
                with patch('nomad.isolation.cleanup_isolated',return_value=False),self.assertRaises(MissionHold):mission.recover(root)
                self.assertEqual((root/'events.jsonl').read_bytes(),before)
                with patch('nomad.isolation.cleanup_isolated',return_value=True):mission.recover(root)
                result=mission.run(root)
            self.assertEqual(result['status'],'completed')
            rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
            self.assertEqual(sum(r['kind']=='F_RECOVERED' for r in rows),1)
            forecasts=[r for r in rows if r['kind']=='F_P_FORECAST']
            updates=[r for r in rows if r['kind']=='F_P_UPDATED']
            self.assertEqual(len(forecasts),len(updates))
            self.assertEqual(len({r['data']['candidate'] for r in updates}),len(updates))


class PersistentRepositoryDesignTests(unittest.TestCase):
    def test_design_is_separate_source_bound_and_never_runs_or_invents_corpus(self):
        from scripts import experiment_repository_temporal_v18 as protocol
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with patch.object(mission,'initialize_functions',side_effect=AssertionError('design cannot dispatch')):
                document=protocol.freeze_design(root/'design.json')
                result=protocol.refusal(document,root/'refusal.json')
            self.assertEqual(document['payload']['protocol']['additional_arm']['label'],'F')
            self.assertIsNone(document['payload']['protocol']['corpus']['private_contract_sha256'])
            self.assertEqual(result['execution'],'NOT_RUN');self.assertEqual(result['trials'],[])
            self.assertFalse(result['private_contracts_opened'])
            original=(root/'refusal.json').read_bytes()
            with self.assertRaises(FileExistsError):protocol.refusal(document,root/'refusal.json')
            self.assertEqual((root/'refusal.json').read_bytes(),original)


if __name__=='__main__':unittest.main()
