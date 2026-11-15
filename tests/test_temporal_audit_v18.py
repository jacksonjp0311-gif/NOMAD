"""Independent arithmetic and malformed-evidence tests; no native qualification."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from scripts import audit_temporal_metrics_v18 as audit


def constant_trace(probability=.75):
    return [{'step':i,'action':i%2,'outcome':1,'p':probability,'mechanism':'frequency'} for i in range(512)]


def bind_transport(row):
    raw={key:value for key,value in row.items() if key not in ('process_receipt','cost')}
    row['process_receipt']['output_sha256']=hashlib.sha256((json.dumps(raw,sort_keys=True,allow_nan=False)+'\r\n').encode()).hexdigest()


def design_fixture():
    config={'state_policy':'selectivewarm','detector_enabled':True,'delayed_credit':True,
            'detector_window':32,'detector_threshold':.35,'detector_cooldown':64}
    return {'schema':audit.SCHEMA+'.design','modes':list(audit.MODES),'families':list(audit.FAMILIES),
        'development_seeds':[18186001,18186002],'evaluation_seeds':list(audit.SEEDS),
        'development_excludes':['unseen_structure'],'steps':512,'unscored_prefix':64,
        'restart_after_observations':[256],'schedule_seed':18186931,'controller_config':config,
        'original_controller_config':{'block_size':16},
        'development_choice':{'selected_profile':'standard','profiles':{'standard':config}},
        'metrics':{'quality_margin_nats':.02,'primary_tests':5,'alpha':.05,
            'objective':'mean logloss + 2 * total Job-plus-supervisor CPU / 512',
            'bootstrap':{'samples':4000,'seed':18186999,'indices':[99,3899]}},
        'budgets':{'wall_seconds':60,'job_memory_mib':512,'job_processes':4,'hard_cpu_seconds':None}}


def trial_fixture(mode='persistent',family='stationary',seed=18186101):
    design=design_fixture();trace=constant_trace();mechanism=mode if mode in audit.MODES[:3] else 'frequency'
    for row in trace: row['mechanism']=mechanism
    prefixes=[] if mode in audit.MODES[:3] else list(range(0,512,16)) if mode=='original' else [0]
    decisions=[{'observed_prefix':prefix,'decision_index':i,'mechanism':mechanism,'change_alarm':False}
               for i,prefix in enumerate(prefixes)]
    row={'status':'COMPLETED','split':'evaluation','source_stable':True,'mode':mode,'family':family,'seed':seed,
        'config':audit.expected_config(design,mode),'trace':trace,'metrics':{'mean_logloss':-math.log(.75),'brier':.0625,'ece10':.25,'scored_forecasts':448},
        'input_sha256':audit.digest([[i%2,1] for i in range(512)]),'decisions':decisions,'switches':0,
        'detector_metrics':{'known_change_boundaries':[171,341] if family in ('shift','misleading') else [],
            'detection_window':96,'delays':[None,None] if family in ('shift','misleading') else [],
            'detected_changes':0,'false_alarms':0,'alarm_prefixes':[],
            'interpretation':'distribution changes only; dependence-screen decisions are not change alarms'},
        'checkpoints':[{'observed_prefix':256,'state_bytes':100,'state_sha256':'a'*64,'deterministic_state_sha256':'a'*64,
            'wall_seconds':.01,'cpu_seconds':.005,
            'method':'canonical JSON, fsync partial, atomic replace; original history/logical restart with lazy learner reconstruction'
                     if mode=='original' else 'canonical JSON, fsync partial, atomic replace, parsed direct-state restoration'}],
        'final_state_sha256':'a'*64,'final_storage_sha256':'a'*64,'final_state_bytes':100,
        'worker_cost':{'initialization_wall_seconds':.02,'initialization_cpu_seconds':.01,
            'loop_inclusive_wall_seconds':.08,'loop_inclusive_cpu_seconds':.04,
            'checkpoint_subset_wall_seconds':.01,'checkpoint_subset_cpu_seconds':.005,
            'final_state_wall_seconds':.002,'final_state_cpu_seconds':.001,
            'algorithm_inclusive_wall_seconds':.12,'algorithm_inclusive_cpu_seconds':.06},
        'process_receipt':{'returncode':0,'timed_out':False,'truncated':False,'cleanup':'windows-job-empty-confirmed',
            'native_job_metrics':{'available':True,'cpu_user_s':.2,'cpu_kernel_s':.1,'peak_job_memory_counter_bytes':1000000}},
        'cost':{'whole_job_cpu_seconds':.3,'supervisor_cpu_seconds':.01,'total_cpu_seconds':.31,'whole_wall_seconds':.2,
            'native_peak_counter_bytes':1000000,'strict_peak_qualification':'HOLD'}}
    bind_transport(row)
    return row


class TemporalArithmeticTests(unittest.TestCase):
    def test_known_bernoulli_arithmetic_and_prefix_exclusion(self):
        trace=constant_trace()
        for row in trace[:64]: row['p']=.001
        result=audit.metrics(trace)
        self.assertAlmostEqual(result['mean_logloss'],-math.log(.75))
        self.assertEqual(result['brier'],.0625)
        self.assertEqual(result['ece10'],.25)
        self.assertEqual(result['scored_forecasts'],448)

    def test_nonfinite_probability_boolean_outcome_and_missing_step_refused(self):
        for field,value in [('p',float('nan')),('p',0),('outcome',True),('step',True),('mechanism','unknown')]:
            with self.subTest(field=field,value=value):
                trace=constant_trace(); trace[0][field]=value
                with self.assertRaises(ValueError): audit.metrics(trace)
        with self.assertRaises(ValueError): audit.metrics(constant_trace()[:-1])

    def test_exact_sign_test_ties_and_five_primary_hypotheses(self):
        self.assertEqual(audit.sign_test([-1]*8),{'wins':8,'losses':0,'ties':0,'p_one_sided':1/256})
        self.assertEqual(audit.sign_test([0,1e-13,-1e-13])['p_one_sided'],1.0)
        rows={}
        for family in audit.FAMILIES:
            for seed in audit.SEEDS:
                for mode in audit.MODES:
                    loss,cpu={'persistent':(.49,.4),'native':(.6,1),'temporal':(.5,.2)}.get(mode,(.6,.5))
                    rows[family,seed,mode]={'metrics':{'mean_logloss':loss,'brier':.2,'ece10':.1},'cpu':cpu}
        result=audit.paired_assessment(rows,bootstrap_seed=18186999)
        tests=result['five_primary_tests']
        self.assertEqual(len(tests),5)
        self.assertEqual(sum(row['control']=='native' for row in tests),3)
        self.assertEqual(sum(row['control']=='temporal' for row in tests),2)
        self.assertEqual(len(result['seed_blocks']),8)
        self.assertTrue(all(row['significant'] for row in tests))
        self.assertTrue(result['registered_success'])
        self.assertGreater(result['comparisons']['temporal']['mean_cpu_difference'],0)
        self.assertAlmostEqual(result['comparisons']['native']['mean_objective_difference'],.49-.6+2*(.4-1)/512)

    def test_json_duplicate_keys_and_nonfinite_literals_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'receipt.json'
            for text in ('{"cpu":1,"cpu":2}','{"cpu":NaN}','[]'):
                path.write_bytes(text.encode())
                with self.assertRaises(ValueError): audit.read(path)


class TemporalReceiptTests(unittest.TestCase):
    def test_all_nine_arm_shapes_and_complete_cpu_scope(self):
        for mode in audit.MODES:
            with self.subTest(mode=mode):
                result=audit.validate_trial(trial_fixture(mode),design_fixture(),'win32')
                self.assertAlmostEqual(result['cpu'],.31)
                self.assertAlmostEqual(result['job_cpu'],.3)
                self.assertEqual(result['checkpoints'],1)

    def test_changed_trace_with_recomputed_metric_does_not_match_transport(self):
        row=trial_fixture();row['trace'][100]['p']=.6;row['metrics']=audit.metrics(row['trace'])
        with self.assertRaisesRegex(ValueError,'transport'): audit.validate_trial(row,design_fixture(),'win32')

    def test_unbound_outer_cpu_alteration_refused(self):
        row=trial_fixture();row['cost']['total_cpu_seconds']=.29
        with self.assertRaisesRegex(ValueError,'supervisor'): audit.validate_trial(row,design_fixture(),'win32')

    def test_rehashed_config_decision_checkpoint_and_detector_changes_refused(self):
        def config(row): row['config']['state_policy']='cold'
        def decision(row): row['decisions'][0]['observed_prefix']=100
        def checkpoint(row): row['checkpoints'][0]['observed_prefix']=255
        def detector(row): row['detector_metrics']['false_alarms']=1
        def subset(row): row['worker_cost']['checkpoint_subset_cpu_seconds']=.04
        for mutation in (config,decision,checkpoint,detector,subset):
            row=trial_fixture();mutation(row);bind_transport(row)
            with self.subTest(mutation=mutation.__name__),self.assertRaises(ValueError):
                audit.validate_trial(row,design_fixture(),'win32')

    def test_detector_recomputed_from_observed_losses_not_change_labels(self):
        row=trial_fixture();row['config'].update(detector_window=2,detector_threshold=.3,detector_cooldown=8)
        for i,event in enumerate(row['trace']): event['p']=.99 if i<4 else .1
        alarms=audit.trace_alarms(row)
        self.assertEqual(alarms[0],5)
        evaluation=audit.detector_metrics('stationary',alarms)
        self.assertEqual(evaluation['false_alarms'],len(alarms))
        self.assertEqual(evaluation['known_change_boundaries'],[])
        row['config']['detector_enabled']=False
        self.assertEqual(audit.trace_alarms(row),[])

    def test_missing_or_reordered_inventory_refused_before_arithmetic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            names=('nomad/persistent.py','nomad/adaptive.py','nomad/native_bitwork.py','nomad/supervised.py','nomad/windows_job.py',
                'scripts/experiment_temporal_v18.py','scripts/experiment_adaptive_v18.py',
                'scripts/audit_temporal_metrics_v18.py','scripts/verify_temporal_replay_v18.py',
                'vendor/BGR-v1.4.0-runtime/MANIFEST.sha256','experiments/PLAN_ADAPTIVE_MECHANISMS_V018.json')
            for name in names:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(name.encode())
            source={name:audit.file_hash(root/name) for name in names}
            payload={'schema':audit.SCHEMA+'.plan','design':design_fixture(),'evaluation_outcomes_generated':False,
                     'source_sha256':source,'platform':'win32'}
            plan={'payload':payload,'sha256':audit.digest(payload)}
            started={'schema':audit.SCHEMA+'.started','split':'evaluation','plan_sha256':plan['sha256'],
                     'evaluation_outcomes_generated':False,'source_sha256':source}
            result={'schema':audit.SCHEMA+'.result','status':'COMPLETED','split':'evaluation','plan_sha256':plan['sha256'],
                'started_receipt_sha256':'b'*64,'config':payload['design']['controller_config'],'source_stable':True,
                'source_sha256_before':source,'source_sha256_after':source,'cpu_coverage':'complete for attempted process trees','trials':[]}
            schedule=audit.registered_schedule()
            for inventory in (schedule[:-1],[schedule[1],schedule[0],*schedule[2:]]):
                result['trials']=[{'family':f,'seed':s,'mode':m} for f,s,m in inventory]
                with self.assertRaisesRegex(ValueError,'inventory'):
                    audit.audit_records(plan,result,started,started_sha256='b'*64,root=root)
            templates={mode:trial_fixture(mode) for mode in audit.MODES}
            trials=[];measured={}
            for family,seed,mode in schedule:
                row=dict(templates[mode]);row.update(family=family,seed=seed,
                    process_receipt=dict(templates[mode]['process_receipt']),detector_metrics=audit.detector_metrics(family,[]))
                bind_transport(row);trials.append(row)
                measured[family,seed,mode]={'metrics':row['metrics'],'cpu':.31}
            result.update(trials=trials,harness_cpu_seconds=.01*len(trials)+.5,harness_wall_seconds=200,
                unallocated_harness_cpu_seconds=.5,whole_study_cpu_seconds=.31*len(trials)+.5,
                assessment=audit.paired_assessment(measured,bootstrap_seed=18186999))
            verified=audit.audit_records(plan,result,started,started_sha256='b'*64,root=root)
            self.assertEqual(verified['complete_trials'],576)
            self.assertEqual(verified['forecasts_checked'],294912)
            self.assertEqual(verified['scored_forecasts_checked'],258048)
            self.assertFalse(verified['assessment']['registered_success'])
            altered={**result,'harness_cpu_seconds':-1}
            with self.assertRaisesRegex(ValueError,'finite measured cost'):
                audit.audit_records(plan,altered,started,started_sha256='b'*64,root=root)
            mismatch=dict(trials[0]);mismatch['trace']=copy.deepcopy(mismatch['trace'])
            mismatch['trace'][0]['action']=1-mismatch['trace'][0]['action']
            mismatch['input_sha256']=audit.digest([[r['action'],r['outcome']] for r in mismatch['trace']])
            mismatch['process_receipt']=dict(mismatch['process_receipt']);bind_transport(mismatch)
            altered={**result,'trials':[mismatch,*trials[1:]]}
            with self.assertRaisesRegex(ValueError,'unmatched'):
                audit.audit_records(plan,altered,started,started_sha256='b'*64,root=root)


if __name__=='__main__': unittest.main()
