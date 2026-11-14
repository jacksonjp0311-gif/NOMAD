"""New-arm protocol software checks; every mock is explicitly not efficacy."""
import copy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import experiment_frontier_v18 as experiment
from tests.test_experiment_qualification_v18 import corpus as original_corpus, IMAGE


def corpus():
    value = original_corpus(); value['schema'] = experiment.SCHEMA+'.corpus'; return value


def plan():
    payload = {'schema':experiment.SCHEMA+'.plan','protocol':experiment.protocol(),'corpus':corpus(),
        'source_sha256':experiment.code_identity(),'image':IMAGE,
        'qualification_sha256':'a'*64,'recovery_sha256':'b'*64}
    return {'payload':payload,'sha256':experiment.shared.digest(payload)}


class FrontierExperimentTests(unittest.TestCase):
    def test_new_user_arms_do_not_rewrite_the_old_protocol(self):
        original = copy.deepcopy(experiment.shared.protocol())
        design = experiment.protocol()
        self.assertEqual(design['arms']['A'], {'adaptive_enabled':False,'ranker_mode':'cold'})
        self.assertEqual(design['arms']['B'], {'adaptive_enabled':False,'ranker_mode':'frequency'})
        self.assertEqual(design['arms']['C'], {'adaptive_enabled':False,'ranker_mode':'native'})
        self.assertEqual(design['arms']['D'], {'adaptive_enabled':True,'ranker_mode':'native'})
        self.assertEqual(experiment.shared.protocol(), original)

    def test_no_corpus_never_opens_hidden_results_or_dispatches(self):
        with tempfile.TemporaryDirectory() as td, patch.object(experiment,'trial') as trial, \
                patch.object(experiment.shared,'_private_contract') as hidden:
            report = experiment.run(None,Path(td),None,None,Path(td)/'receipt.json')
            self.assertEqual(report['execution'],'NOT_RUN')
            self.assertFalse(report['private_contracts_opened'])
            trial.assert_not_called(); hidden.assert_not_called()

    def test_metadata_reuse_refuses_overlap_and_newly_exposed_sources(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(experiment.audit(corpus(),Path(td),inspect_public=False)['private_contracts_opened'])
            value=corpus(); value['tasks'][2]['repository']='https://github.com/keon/algorithms'
            value['tasks'][2]['issue_url']='https://github.com/keon/algorithms/issues/99999'
            with self.assertRaises(ValueError): experiment.audit(value,Path(td),inspect_public=False)

    def test_missing_aggregate_compute_qualification_holds_even_before_native_dispatch(self):
        with tempfile.TemporaryDirectory() as td, patch.object(experiment,'docker_preflight') as docker, \
                patch.object(experiment.shared,'_private_contract') as hidden:
            result=experiment.preflight(plan(),Path(td),None,None)
            self.assertEqual(result['execution'],'NOT_RUN')
            self.assertIn('controller-plus-worker',' '.join(result['reasons']))
            docker.assert_not_called(); hidden.assert_not_called()

    def test_function_recovery_requires_its_own_bound_native_case_semantics(self):
        from scripts import qualify_function_recovery_frontier_v18 as recovery
        from scripts.qualify_isolation_v18 import qualification_host_identity
        policy=asdict(experiment.shared.execution_policy(IMAGE)); sources=recovery.source_identity()
        record={'schema':recovery.SCHEMA,'status':'PASS','isolated_mission_recovery':'PASS','backend':'docker',
            'adapter_scopes':[experiment.ADAPTER],'image':IMAGE,'policy':policy,
            'policy_sha256':experiment.shared.digest(policy),
            'host_identity_sha256':experiment.shared.digest(qualification_host_identity()),
            'source_stable':True,'source_sha256_before':sources,'source_sha256_after':sources,
            'evidence_inventory_complete':True,
            'protected_host_sentinel_unchanged':True,'original_source_unchanged':True,
            'isolation_receipt_sha256':'a'*64,'cases':[]}
        for name in recovery.required_cases():
            row={'case':name,'status':'PASS','result':{'passed':True}}
            if name.startswith('tampered-'): row.update(refused=True,dispatched=False)
            if name=='final_rejection_restores_source':
                row.update(restored_original=True,no_learning_admitted=True); row['result']['status']='rejected'
            if name=='two_file_partial_patch_recovery':
                row['actual_mixed_two_file_snapshot_observed']=True
                row['reference_control']={'passed':True,'changed_files':2}
            if name=='owner_hard_death_with_live_container':
                row['death']={key:True for key in ('observed_live_container_before_owner_death',
                    'cleanup_confirmed_after_owner_death','held_before_cleanup')}
            record['cases'].append(row)
        def seal(value): value['receipt_sha256']=experiment.shared.digest({k:v for k,v in value.items() if k!='receipt_sha256'})
        seal(record)
        # This in-memory fixture tests validation shape, not actual qualification.
        experiment.function_recovery_binding(record,IMAGE,'a'*64)
        changed=copy.deepcopy(record); changed.pop('evidence_inventory_complete'); seal(changed)
        with self.assertRaises(ValueError): experiment.function_recovery_binding(changed,IMAGE,'a'*64)
        changed=copy.deepcopy(record); changed['schema']='nomad.platform-recovery-qualification.v18'; seal(changed)
        with self.assertRaises(ValueError): experiment.function_recovery_binding(changed,IMAGE,'a'*64)
        changed=copy.deepcopy(record)
        next(row for row in changed['cases'] if row['case']=='owner_hard_death_with_live_container')['death']['held_before_cleanup']=False
        seal(changed)
        with self.assertRaises(ValueError): experiment.function_recovery_binding(changed,IMAGE,'a'*64)

    def test_design_only_and_changed_protocol_cannot_be_executed(self):
        with tempfile.TemporaryDirectory() as td:
            design=experiment.freeze_design(Path(td)/'design.json')
            with self.assertRaises(ValueError): experiment.validate(design)
            changed=plan(); changed['payload']['protocol']['arms']['D']['ranker_mode']='frequency'
            changed['sha256']=experiment.shared.digest(changed['payload'])
            with self.assertRaises(ValueError): experiment.validate(changed)

    def test_matched_schedule_clones_training_before_every_evaluation(self):
        calls=[]
        def fake(task,root,destination,memory,settings,image):
            if task['split']=='training': memory.mkdir(exist_ok=True); (memory/'unit').write_text('training')
            else:
                self.assertEqual((memory/'unit').read_text(),'training'); (memory/'unit').write_text('do-not-reuse-evaluation')
            calls.append((task['split'],settings))
            return {'task_id':task['id'],'repository':experiment.shared._repository(task['repository']),
                'source_sha256':task['source_sha256'],'public_spec_sha256':task['public_spec_sha256'],
                'status':'rejected','accepted':False,'candidate_inventory_sha256':'c'*64,
                'candidate_evaluations':1,'isolated_executions':3}
        with tempfile.TemporaryDirectory() as td, patch.object(experiment,'preflight',return_value={'status':'PASS'}), \
                patch.object(experiment,'audit',return_value={}),patch.object(experiment,'trial',side_effect=fake):
            result=experiment.run(plan(),Path(td),None,None,Path(td)/'mock-only.json')
            self.assertEqual(result['execution'],'COMPLETED')
            self.assertEqual(result['repository_advantage'],'NOT_ESTABLISHED')
            self.assertEqual(len([x for x in calls if x[0]=='evaluation']),24*3*4)

    def test_changed_inventory_or_unmatched_arms_refuse_assessment(self):
        rows=[{'seed':experiment.SEEDS[0],'task_id':'fixture','arm':arm,'repository':'unit/repo',
            'source_sha256':'a','public_spec_sha256':'b','candidate_inventory_sha256':'c','accepted':False}
            for arm in experiment.ARMS]
        with self.assertRaises(ValueError): experiment.assess(rows[:-1])
        rows[-1]['candidate_inventory_sha256']='changed'
        with self.assertRaises(ValueError): experiment.assess(rows)

    def test_trial_uses_function_controller_with_explicit_authored_execution_double(self):
        from tests.test_frontier_function_mission_v18 import fixture,controlled_execution
        from nomad import platform_mission
        from nomad.isolation import snapshot_source
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source,public,challenge,final=fixture(root)
            public_path=root/'public.json'; private_path=root/'private.json'
            experiment.shared.write_new(public_path,{'goal_text':'Restore declared clamp behavior','public':public})
            experiment.shared.write_new(private_path,{'challenge':challenge,'final':final})
            snapshot=snapshot_source(source,root/'identity',experiment.shared.execution_policy(IMAGE))
            task={'id':'unit-authored','repository':'https://github.com/unit/fixture','source':'source',
                'source_sha256':snapshot.digest,'public_spec':'public.json','private_contract':'private.json',
                'public_spec_sha256':experiment.shared.file_hash(public_path),
                'private_contract_sha256':experiment.shared.file_hash(private_path)}
            with patch.object(platform_mission,'run_isolated',side_effect=controlled_execution):
                row=experiment.trial(task,root,root/'mission',root/'memory',experiment.ARMS['D'],IMAGE)
            self.assertTrue(row['accepted'])
            self.assertTrue(row['public_passed'])
            self.assertFalse(row['independent_contract_rejected'])
            self.assertGreater(row['isolated_executions'],1)


if __name__=='__main__': unittest.main()
