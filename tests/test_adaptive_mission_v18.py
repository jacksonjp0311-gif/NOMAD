"""Public-only adaptive mission contracts, not native containment qualification.

The worker double interprets only explicitly authored fixtures from the earlier
test module. Actual controller, AST/GENESIS and memory code run on the host.
"""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad import platform_mission as mission
from nomad.adaptive import AdaptiveConfig, AdaptiveController
from nomad.mission_runtime import InjectedInterruption, MissionHold, canonical, digest
from tests.test_frontier_function_mission_v18 import fixture, controlled_execution, POLICY


def initialize(base, *, config=None, memory=None, epoch=0, marker=None, final_wrong=False, **options):
    source,public,challenge,final=fixture(base)
    if marker is not None:
        with (source/'lower.py').open('a') as handle: handle.write('\ndef marker():\n    return '+str(marker)+'\n')
    if final_wrong: final[0]['expected']=9999
    root=base/'mission'
    goal=mission.initialize_functions(root,source,goal_text='explicit trusted computation fixture',
        public=public,challenge=challenge,final=final,policy=POLICY,memory_root=memory,capture_epoch=epoch,
        computation_controller=config or AdaptiveConfig(),**options)
    return root,goal


def rehash(rows):
    previous='0'*64
    for row in rows:
        row['prev']=previous
        row['sha256']=digest(canonical({k:v for k,v in row.items() if k!='sha256'}))
        previous=row['sha256']


class AdaptiveMissionTests(unittest.TestCase):
    def test_cold_choice_avoids_native_synthesis_and_retrieval(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch('nomad.adaptive.load_native',side_effect=AssertionError('unnecessary native work')),\
                 patch('nomad.genesis.synthesize',side_effect=AssertionError('unnecessary synthesis')),\
                 patch.object(mission.EvidenceMemory,'recall',side_effect=AssertionError('unnecessary recall')):
                root,goal=initialize(Path(temporary))
                self.assertEqual(goal['computation']['decision']['mechanism'],'frequency')
                self.assertEqual(goal['analysis']['genesis'],[])
                self.assertLessEqual(goal['analysis']['generated_candidates_checked'],64)
                with patch.object(mission,'run_isolated',side_effect=controlled_execution): result=mission.run(root)
                self.assertEqual(result['status'],'completed')
                self.assertEqual(result['baseline_probes_recorded'],1)
                self.assertEqual(result['computation']['ranking'],'frequency')

    def test_fixed_native_profile_reaches_original_model_and_genesis(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,goal=initialize(Path(temporary),config=AdaptiveConfig(adaptive_selection=False))
            self.assertEqual(goal['computation']['decision']['mechanism'],'native')
            self.assertGreater(sum(r['candidates_evaluated'] for r in goal['analysis']['genesis']),0)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution),self.assertRaises(InjectedInterruption):
                mission.run(root,interrupt_at='after_proposal')
            rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
            diagnosis=next(r['data'] for r in rows if r['kind']=='F_DIAGNOSIS')
            self.assertEqual(diagnosis['ranking']['mechanism'],'native')
            self.assertEqual(diagnosis['telemetry']['native_builds'],1)

    def test_abstention_is_durable_without_any_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,goal=initialize(Path(temporary),config=AdaptiveConfig(cost_seconds={k:10.0 for k in ('frequency','temporal','native')}))
            self.assertEqual(goal['analysis']['proposals'],[])
            with patch.object(mission,'run_isolated',side_effect=AssertionError('abstention must not dispatch')):
                for action in (mission.run,mission.inspect,mission.recover,mission.run):
                    result=action(root)
                    self.assertEqual(result['status'],'abstained')
                    self.assertEqual(result['dispatches'],0)
                    self.assertEqual(result['witness_observations'],0)
            self.assertFalse((root/'learning.json').exists())

    def test_runtime_choice_and_forecast_resume_without_repeating_work(self):
        for boundary in ('after_control','after_proposal','after_memory'):
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as temporary:
                root,goal=initialize(Path(temporary))
                with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                    with self.assertRaises(InjectedInterruption): mission.run(root,interrupt_at=boundary)
                    if boundary=='after_proposal':
                        with patch.object(AdaptiveController,'peek_probabilities',side_effect=AssertionError('repeated forecast')):
                            result=mission.run(root)
                    else: result=mission.run(root)
                self.assertEqual(result['status'],'completed')
                rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
                self.assertEqual(sum(r['kind']=='F_CONTROL' for r in rows),1)
                self.assertEqual(sum(r['kind']=='F_DIAGNOSIS' for r in rows),1)
                self.assertEqual(len(mission._function_memory(root/'mnemonic',epoch=0)['records']),1)

    def test_external_controller_state_is_not_an_authorized_prior(self):
        controller=AdaptiveController(); controller.ingest_public(0,1)
        with tempfile.TemporaryDirectory() as temporary,self.assertRaisesRegex(ValueError,'configuration only'):
            initialize(Path(temporary),config=controller)

    def test_distinct_accepted_sources_admit_public_trace_without_hidden_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); memory=base/'memory'
            for number in range(3):
                folder=base/str(number);folder.mkdir()
                root,_=initialize(folder,memory=memory,epoch=number,marker=20+number)
                with patch.object(mission,'run_isolated',side_effect=controlled_execution): mission.run(root)
            models=mission._function_memory(memory,epoch=2)
            self.assertEqual(models['eligible_tasks'],3)
            active=mission.read_function_computation_controller(memory,now_epoch=2)
            self.assertEqual(len(active.verified_ids),3)
            self.assertGreaterEqual(len(active.history),3)
            self.assertEqual(mission.read_function_computation_controller(memory,now_epoch=9).history,[])
            self.assertEqual(mission.read_function_computation_controller(memory,now_epoch=2,
                config=AdaptiveConfig(use_memory=False)).history,[])
            for record in models['records']:
                trace=record['computation_evidence']['public_trace']
                operations=[r['data']['operation'] for r in trace if r['kind']=='F_OBSERVED']
                self.assertTrue(all(op.startswith(('probe:','search:')) for op in operations))
                self.assertNotIn('challenge',record['origin'])
                self.assertNotIn('final',record['origin'])

    def test_failed_final_admits_no_computation_benefit(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); memory=base/'memory'
            root,_=initialize(base,memory=memory,final_wrong=True)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                self.assertEqual(mission.run(root)['status'],'rejected')
            self.assertFalse(memory.exists())

    def test_rehashed_public_utility_and_cost_mutation_refused(self):
        for field in ('public_log_gain','cost'):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temporary:
                root,_=initialize(Path(temporary))
                with patch.object(mission,'run_isolated',side_effect=controlled_execution): mission.run(root)
                path=root/'mnemonic'/'events.jsonl'
                rows=mission.Journal(path,mission.FUNCTION_MEMORY_ID).read()
                evidence=rows[1]['data']['computation_evidence']
                if field=='public_log_gain': evidence[field]+=.5
                else: evidence[field]['wall_seconds']+=1
                rehash(rows); path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
                with self.assertRaises(MissionHold): mission.read_function_computation_controller(path.parent)

    def test_private_expected_values_do_not_change_public_allocation(self):
        outcomes=[]
        with tempfile.TemporaryDirectory() as temporary:
            for number,wrong in enumerate((False,True)):
                base=Path(temporary)/str(number);base.mkdir()
                root,goal=initialize(base,final_wrong=wrong)
                outcomes.append((goal['computation']['controller_after'],goal['analysis']['candidate_inventory_sha256']))
        self.assertEqual(outcomes[0],outcomes[1])


if __name__=='__main__': unittest.main()
