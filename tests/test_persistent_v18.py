import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from nomad.adaptive import make_predictor, probability
from nomad.persistent import (PersistentConfig, PersistentController, StateRefused,
    canonical, digest, predictor_restore, predictor_snapshot, prefix_digest,
    read_checkpoint, write_checkpoint, deterministic_state_hash)


def reseal(document):
    document['sha256'] = digest(document['payload'])
    return document


def stream(n=512):
    """A fixed public contract fixture, never an experiment evaluation seed."""
    rng = random.Random(918721)
    history = []
    for t in range(n):
        action = rng.randrange(2)
        y = (action if t < 170 else (1-action if t < 340 else (history[-3][1] ^ action)))
        if rng.random() < .12: y ^= 1
        history.append((action,y))
    return history


class PredictorCodecContracts(unittest.TestCase):
    def test_actual_512_forecasts_equal_across_periodic_restoration(self):
        rows = stream()
        for name in ('frequency','temporal','native'):
            with self.subTest(name=name):
                original, restored = make_predictor(name), make_predictor(name)
                for index,(a,y) in enumerate(rows):
                    self.assertEqual(probability(original,a),probability(restored,a))
                    original.observe(a,y); restored.observe(a,y)
                    if index+1 in (64,256,512):
                        identity = prefix_digest(rows[:index+1])
                        document = predictor_snapshot(restored,name,prefix_sha256=identity)
                        restored = predictor_restore(json.loads(canonical(document)),name,expected_prefix_sha256=identity)
                self.assertEqual(probability(original,1),probability(restored,1))

    def test_promoted_lag_state_restores_in_fresh_python_process(self):
        rng = random.Random(9981); model = make_predictor('native'); rows=[]
        for t in range(256):
            a=rng.randrange(2); y=a^(rows[-3][0] if len(rows)>=3 else 0)
            probability(model,a); model.observe(a,y); rows.append((a,y))
        self.assertIsNotNone(model.lags)
        self.assertTrue(model.lags.promotions)
        identity = prefix_digest(rows)
        document = predictor_snapshot(model,'native',prefix_sha256=identity)
        expected=[]
        for t in range(32):
            a=t%2; y=a^rows[-3][0]
            expected.append(probability(model,a)); model.observe(a,y); rows.append((a,y))
        code = """import json,sys
from nomad.persistent import predictor_restore,read_checkpoint
from nomad.adaptive import probability
m=predictor_restore(read_checkpoint(sys.argv[1]),'native',expected_prefix_sha256=sys.argv[2])
h=[(a,y) for a,y,_ in m.history]; result=[]
for t in range(32):
 a=t%2; y=a^h[-3][0]
 result.append(probability(m,a));m.observe(a,y);h.append((a,y))
print(json.dumps(result,allow_nan=False))
"""
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'state.json'; write_checkpoint(path,document)
            result=subprocess.run([sys.executable,'-B','-c',code,str(path),identity],
                cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),expected)

    def test_pending_native_and_temporal_states_are_refused(self):
        for name in ('native','temporal'):
            model = make_predictor(name); probability(model,0)
            with self.assertRaises(StateRefused): predictor_snapshot(model,name)

    def test_model_prefix_is_not_merely_a_relabelable_header(self):
        for name in ('native','temporal'):
            model = make_predictor(name)
            probability(model,0); model.observe(0,1)
            with self.assertRaises(StateRefused): predictor_snapshot(model,name,prefix_sha256=prefix_digest([(1,0)]))
            doc = predictor_snapshot(model,name,prefix_sha256=prefix_digest([(0,1)]))
            doc['payload']['prefix_sha256'] = prefix_digest([(1,0)]); reseal(doc)
            with self.assertRaises(StateRefused): predictor_restore(doc,name,expected_prefix_sha256=prefix_digest([(1,0)]))

    def test_rehashed_unknown_type_fields_configuration_and_versions_refused(self):
        original = predictor_snapshot(make_predictor('native'),'native')
        mutations = (
            lambda p:p['state'].__setitem__('t','subprocess.Popen'),
            lambda p:p['state']['fields'].__setitem__('execute','bad'),
            lambda p:p['state']['fields'].__setitem__('threshold',.7),
            lambda p:p['state'].__setitem__('version',True),
            lambda p:p.__setitem__('state_version',True),
            lambda p:p['runtime'].__setitem__('python_version',[0,0,0]),
            lambda p:p['source_sha256'].__setitem__('nomad/persistent.py','0'*64),
        )
        for mutate in mutations:
            doc = copy.deepcopy(original); mutate(doc['payload']); reseal(doc)
            with self.assertRaises(StateRefused): predictor_restore(doc,'native')

    def test_expiry_and_policy_mismatch(self):
        doc = predictor_snapshot(make_predictor('frequency'),'frequency',epoch=2,policy_sha256='1'*64)
        for kwargs in ({'expected_epoch':1,'expected_policy_sha256':'1'*64},
                       {'expected_epoch':35,'expected_policy_sha256':'1'*64},
                       {'expected_epoch':2,'expected_policy_sha256':'2'*64}):
            with self.assertRaises(StateRefused): predictor_restore(doc,'frequency',**kwargs)


class PersistentControllerContracts(unittest.TestCase):
    def test_full_warm_real_states_continue_512_steps_without_replay(self):
        original = PersistentController(); restored = PersistentController()
        rows = stream()
        for index,(a,y) in enumerate(rows):
            self.assertEqual(original.predict(a),restored.predict(a))
            original.observe(a,y); restored.observe(a,y)
            if index+1 in (256,512):
                doc = restored.snapshot()
                restored = PersistentController.load(doc,expected_epoch=0,
                    expected_prefix_sha256=prefix_digest(rows[:index+1]),expected_config=original.config)
        self.assertEqual(original.decisions,restored.decisions)
        self.assertEqual(original.alarms,restored.alarms)
        self.assertEqual(restored.telemetry['catchup_observations'],0)
        self.assertEqual(restored.telemetry['active_forecasts'],512)
        self.assertEqual(restored.telemetry['inactive_forecasts'],1024)
        self.assertEqual(restored.telemetry['inactive_updates'],1024)

    def test_delayed_credit_has_no_unmatured_or_future_gain(self):
        model = PersistentController(PersistentConfig(credit_horizon=8,commitment=4,detector_window=2))
        model.gains['native'] = [[i,.5] for i in range(8)]
        model.history = [(0,0)]*7
        self.assertEqual(model._credit('native')['samples'],0)
        model.history.append((0,0))
        self.assertEqual(model._credit('native')['samples'],8)
        self.assertAlmostEqual(model._credit('native')['gain'],.5)
        model.config = replace(model.config,delayed_credit=False)
        model.history = model.history[:7]
        self.assertEqual(model._credit('native')['samples'],7)

    def test_selective_catches_up_and_explicit_memory_pressure_evicts(self):
        model = PersistentController(PersistentConfig(state_policy='selectivewarm',commitment=4,credit_horizon=8,detector_window=2,detector_enabled=False))
        for a,y in stream(16): model.ingest_public(a,y)
        self.assertGreater(model.telemetry['catchup_observations'],0)
        self.assertGreater(len(model.models),1)
        self.assertEqual(model.trim_resident(1),1)
        with self.assertRaises(StateRefused): model.peek_probabilities('native')
        model.trim_resident(2)
        old = model.telemetry['catchup_observations']; model.peek_probabilities('native')
        self.assertEqual(model.telemetry['catchup_observations']-old,16)
        self.assertEqual(model.evictions[-1]['reason'],'memory_pressure')

    def test_abstention_does_not_run_expensive_warm_learners(self):
        model = PersistentController()
        self.assertEqual(model.decide(remaining_budget={'steps':0})['mechanism'],'abstain')
        self.assertEqual(model.predict(0),.5); model.observe(0,1)
        self.assertEqual(set(model.models),{'frequency'})
        self.assertEqual(model.telemetry['inactive_forecasts'],1)

    def test_resident_cap_survives_future_fullwarm_predictions(self):
        model = PersistentController()
        for a,y in stream(3): model.ingest_public(a,y)
        model.trim_resident(1)
        for a,y in stream(8): model.ingest_public(a,y)
        self.assertEqual(set(model.models),{'frequency'})
        self.assertEqual(model.selected,'frequency')
        restored = PersistentController.load(model.snapshot())
        self.assertEqual(restored.residency_limit,1)

    def test_cold_policy_evicts_switched_learner(self):
        model = PersistentController(PersistentConfig(state_policy='cold',commitment=4,credit_horizon=8,detector_window=2,detector_enabled=False))
        for a,y in stream(13): model.ingest_public(a,y)
        self.assertGreaterEqual(model.telemetry['cold_evictions'],1)
        self.assertLessEqual(len(model.models),2)

    def test_delayed_exploration_commits_until_credit_release_and_charges_it(self):
        config=PersistentConfig(state_policy='selectivewarm',commitment=4,credit_horizon=8,detector_window=2,detector_enabled=False)
        model=PersistentController(config)
        for a,y in stream(9): model.ingest_public(a,y)
        decision=model.decisions[-1]
        self.assertEqual(decision['mechanism'],'native')
        self.assertEqual(decision['observed_prefix'],8)
        self.assertEqual(decision['committed_until'],16)
        self.assertEqual(decision['estimated_horizon_steps']['native'],8)
        # Native starts absent and must replay eight rows, then perform eight
        # new forecasts rather than charging only the four-step base interval.
        self.assertAlmostEqual(decision['estimated_cost_seconds']['native'],
            config.setup_seconds['native']+16*config.cost_seconds['native']+8*config.cost_seconds['frequency'])
        short=PersistentController(config)
        for a,y in stream(8): short.ingest_public(a,y)
        row=short.decide(remaining_budget={'steps':2})
        self.assertEqual(row['committed_until'],10)

    def test_decision_and_eviction_exhaustion_do_not_mutate_policy(self):
        model=PersistentController(PersistentConfig(state_policy='cold',commitment=4,credit_horizon=8,detector_window=2,detector_enabled=False))
        for a,y in stream(5): model.ingest_public(a,y)
        self.assertEqual(model.selected,'temporal')
        model.evictions=[{'at':0,'mechanism':'native','reason':'memory_pressure'} for _ in range(512)]
        before=(model.selected,list(model.explored),set(model.models),len(model.decisions))
        with self.assertRaises(ValueError): model.decide(available_actions=('frequency',))
        self.assertEqual(before,(model.selected,list(model.explored),set(model.models),len(model.decisions)))
        model.decisions=[{} for _ in range(512)]
        with self.assertRaises(ValueError): model.decide()
        self.assertEqual(model.selected,'temporal')

    def test_detector_and_ablation_are_public_only(self):
        config = PersistentConfig(detector_window=2,detector_cooldown=4,detector_threshold=.3)
        model = PersistentController(config)
        for loss in (0.,0.,1.,1.):
            model.history.append((0,0)); model._detect(loss)
        self.assertEqual(model.alarms[0]['at'],4)
        self.assertEqual(model.credit_start,4)
        disabled = PersistentController(replace(config,detector_enabled=False))
        for loss in (0.,0.,1.,1.):
            disabled.history.append((0,0)); disabled._detect(loss)
        self.assertEqual(disabled.alarms,[])

    def test_settled_peek_and_once_only_observation(self):
        model = PersistentController(PersistentConfig(state_policy='selectivewarm'))
        self.assertEqual(model.peek_probabilities(),(.5,.5))
        self.assertIsNone(model.pending)
        model.predict(0)
        with self.assertRaises(RuntimeError): model.snapshot()
        with self.assertRaises(RuntimeError): model.peek_probabilities()
        model.observe(0,1)
        with self.assertRaises(RuntimeError): model.observe(0,1)
        model.snapshot()

    def test_verified_duplicate_contradiction_and_no_manufactured_stream_credit(self):
        model = PersistentController()
        self.assertFalse(model.record_verified('native',1.,.1,'receipt'))
        self.assertTrue(model.record_verified('native',1.,.1,'receipt',independently_verified=True))
        self.assertFalse(model.record_verified('native',1.,.1,'receipt',independently_verified=True))
        with self.assertRaises(ValueError): model.record_verified('native',.2,.1,'receipt',independently_verified=True)
        self.assertEqual(model.gains['native'],[])

    def test_expired_and_wrong_prefix_recover_cold_explicitly(self):
        model = PersistentController(PersistentConfig(state_policy='selectivewarm'))
        model.ingest_public(0,1); doc = model.snapshot()
        for kwargs in ({'expected_epoch':33},{'expected_prefix_sha256':'0'*64}):
            restored,receipt = PersistentController.restore_or_cold(doc,model.config,**kwargs)
            self.assertEqual(receipt['status'],'COLD_FALLBACK')
            self.assertEqual(restored.history,[])
            self.assertEqual(restored.models['frequency'].counts,[[1,1],[1,1]])

    def test_prefix_counts_and_typed_gain_corruption_refused(self):
        model = PersistentController(PersistentConfig(state_policy='selectivewarm'))
        model.ingest_public(0,1); original = model.snapshot()
        doc = copy.deepcopy(original); doc['payload']['gains']['native']=[[0,.1],[0,.1]]; reseal(doc)
        with self.assertRaises(StateRefused): PersistentController.load(doc)
        doc = copy.deepcopy(original); doc['payload']['history']=[[1,0]]; doc['payload']['prefix_sha256']=prefix_digest([[1,0]]); reseal(doc)
        with self.assertRaises(StateRefused): PersistentController.load(doc)

    def test_native_counter_and_cache_shape_refused_before_forecast(self):
        original=predictor_snapshot(make_predictor('native'),'native')
        doc=copy.deepcopy(original)
        doc['payload']['state']['fields']['telemetry']['v']=[]; reseal(doc)
        with self.assertRaises(StateRefused): predictor_restore(doc,'native')
        doc=copy.deepcopy(original)
        synth=doc['payload']['state']['fields']['base']['fields']['discovered']['fields']
        synth['_exact_terms']={'t':'tuple','v':[1]}; reseal(doc)
        with self.assertRaises(StateRefused): predictor_restore(doc,'native')

    def test_storage_budget_and_deterministic_hash_excludes_clocks(self):
        model = PersistentController(PersistentConfig(state_policy='selectivewarm'))
        doc = model.snapshot(); changed = copy.deepcopy(doc)
        changed['payload']['telemetry']['decision_cpu_seconds'] += 10; reseal(changed)
        self.assertEqual(deterministic_state_hash(doc),deterministic_state_hash(changed))
        small = PersistentController(PersistentConfig(max_state_bytes=1024))
        with self.assertRaises(StateRefused): small.snapshot()


class StateFileContracts(unittest.TestCase):
    def test_atomic_failure_keeps_previous_and_partial_and_duplicate_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'state.json'
            doc = PersistentController(PersistentConfig(state_policy='selectivewarm')).snapshot()
            write_checkpoint(path,doc)
            with patch('nomad.persistent.os.replace',side_effect=OSError('public fixture failure')):
                with self.assertRaises(OSError): write_checkpoint(path,{'new':True})
            self.assertEqual(read_checkpoint(path),doc)
            path.write_text('{"payload":',encoding='utf-8')
            with self.assertRaises(StateRefused): read_checkpoint(path)
            path.write_text('{"x":1,"x":2}',encoding='utf-8')
            with self.assertRaises(StateRefused): read_checkpoint(path)
            path.write_text('{"x":NaN}',encoding='utf-8')
            with self.assertRaises(StateRefused): read_checkpoint(path)

    @unittest.skipUnless(os.name == 'nt','native Windows junction contract')
    def test_windows_junction_ancestor_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); target=root/'target'; target.mkdir(); junction=root/'junction'
            process = subprocess.run(['cmd','/c','mklink','/J',str(junction),str(target)],capture_output=True,text=True)
            if process.returncode: self.skipTest('host cannot create controlled junction')
            try:
                (target/'state.json').write_text('{}',encoding='utf-8')
                with self.assertRaises(StateRefused): read_checkpoint(junction/'state.json')
                with self.assertRaises(StateRefused): write_checkpoint(junction/'new.json',{})
            finally:
                # Remove only the junction itself, never recurse through it.
                junction.rmdir()


if __name__ == '__main__': unittest.main()
