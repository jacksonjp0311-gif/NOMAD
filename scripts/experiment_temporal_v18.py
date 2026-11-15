"""Prospective persistent-computation experiment on trusted binary streams.

No unfamiliar code runs here. Source, development choice, costs, seeds, scoring,
restart schedule and paired inference are frozen before evaluation generation.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nomad.adaptive import AdaptiveConfig, AdaptiveController, canonical, digest, make_predictor, probability
from nomad.native_bitwork import verified_runtime_identity
from nomad.supervised import run_supervised
from scripts.experiment_adaptive_v18 import process_memory

SCHEMA = 'nomad.temporal-ascension.v18'
MODES = ('frequency', 'temporal', 'native', 'original', 'persistent',
         'no_detector', 'no_delayed', 'cold', 'fullwarm')
FAMILIES = ('stationary', 'temporal', 'delayed', 'shift', 'sparse_noisy',
            'misleading', 'unseen_structure', 'irreducible')
DEVELOPMENT_SEEDS = (18186001, 18186002)
EVALUATION_SEEDS = tuple(range(18186101, 18186109))
STEPS, PREFIX = 512, 64
RESTART_AT = (256,)
SCHEDULE_SEED, BOOTSTRAP_SEED = 18186931, 18186999


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_bytes())
def write_new(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, separators=(',', ':'), allow_nan=False)
        stream.write('\n')


def source_identity():
    names = ('nomad/persistent.py', 'nomad/adaptive.py', 'nomad/native_bitwork.py',
             'nomad/supervised.py', 'nomad/windows_job.py',
             'scripts/experiment_temporal_v18.py', 'scripts/experiment_adaptive_v18.py',
             'scripts/audit_temporal_metrics_v18.py','scripts/verify_temporal_replay_v18.py',
             'vendor/BGR-v1.4.0-runtime/MANIFEST.sha256',
             'experiments/PLAN_ADAPTIVE_MECHANISMS_V018.json')
    return {name: sha(ROOT/name) for name in names}


def original_config():
    return AdaptiveConfig(**read(ROOT/'experiments/PLAN_ADAPTIVE_MECHANISMS_V018.json')['payload']['design']['controller_config'])


def generated_outcome(family, action, history, draw):
    """Evaluator-only rules. Models receive only action and previous outcomes."""
    t = len(history)
    previous = lambda lag, bit: history[-lag][bit] if len(history) >= lag else 0
    if family == 'irreducible': chance = .5
    elif family == 'stationary': chance = (.13, .32)[action]
    elif family == 'sparse_noisy': chance = (.06, .29)[action]
    elif family == 'shift':
        chance = ((.12, .31) if t < 171 else (.82, .62) if t < 341 else (.18, .36))[action]
    elif family == 'misleading' and 171 <= t < 341: chance = (.13, .32)[action]
    else:
        if family in ('temporal', 'misleading'): bit = previous(1, 1)
        elif family == 'delayed': bit = previous(3, 0)
        elif family == 'unseen_structure':
            bit = previous(2, 1) ^ (previous(4, 0) & previous(6, 1))
        else: raise ValueError('unregistered generator')
        chance = .92 if action ^ bit else .08
    return int(draw < chance)


def metrics(trace):
    if len(trace) != STEPS: raise ValueError('incomplete stream')
    scored = trace[PREFIX:]; bins = [[] for _ in range(10)]
    for row in scored: bins[min(9, int(row['p']*10))].append(row)
    return {'mean_logloss': statistics.fmean(-math.log(r['p'] if r['outcome'] else 1-r['p']) for r in scored),
            'brier': statistics.fmean((r['p']-r['outcome'])**2 for r in scored),
            'ece10': sum(abs(sum(r['p']-r['outcome'] for r in b)) for b in bins)/len(scored),
            'scored_forecasts': len(scored)}


def detector_metrics(family, alarms):
    boundaries = [171, 341] if family in ('shift', 'misleading') else []
    remaining = list(alarms); delays = []
    for boundary in boundaries:
        matches = [a for a in remaining if boundary <= a <= min(STEPS, boundary+96)]
        found = min(matches) if matches else None
        delays.append(None if found is None else found-boundary)
        if found is not None: remaining.remove(found)
    return {'known_change_boundaries': boundaries, 'detection_window': 96,
            'delays': delays, 'detected_changes': sum(d is not None for d in delays),
            'false_alarms': len(remaining), 'alarm_prefixes': list(alarms),
            'interpretation': 'distribution changes only; dependence-screen decisions are not change alarms'}


def schedule(split, modes=MODES):
    seeds = DEVELOPMENT_SEEDS if split == 'development' else EVALUATION_SEEDS
    families = [f for f in FAMILIES if split != 'development' or f != 'unseen_structure']
    rng = random.Random(SCHEDULE_SEED)
    groups = [(f, s) for s in seeds for f in families]; rng.shuffle(groups)
    result = []
    for f, s in groups:
        selected = list(modes); rng.shuffle(selected)
        result.extend((f, s, m) for m in selected)
    return result


def sign_test(values):
    wins, losses = sum(v < -1e-12 for v in values), sum(v > 1e-12 for v in values)
    n = wins+losses
    return {'wins': wins, 'losses': losses, 'ties': len(values)-n,
            'p_one_sided': sum(math.comb(n, j) for j in range(wins, n+1))/2**n if n else 1.0}


def interval(values):
    rng = random.Random(BOOTSTRAP_SEED)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(4000))
    return [means[99], means[3899]]


def assess(rows):
    expected = {(f,s,m) for f in FAMILIES for s in EVALUATION_SEEDS for m in MODES}
    indexed = {(r['family'],r['seed'],r['mode']):r for r in rows}
    if len(rows) != len(expected) or set(indexed) != expected or any(r['status'] != 'COMPLETED' for r in rows):
        raise ValueError('complete registered paired inventory required')
    for f in FAMILIES:
        for s in EVALUATION_SEEDS:
            if len({indexed[f,s,m]['input_sha256'] for m in MODES}) != 1:
                raise ValueError('unmatched arm observations')
    blocks = {str(s): {m: {'loss': statistics.fmean(indexed[f,s,m]['metrics']['mean_logloss'] for f in FAMILIES),
                          'cpu': statistics.fmean(indexed[f,s,m]['cost']['total_cpu_seconds'] for f in FAMILIES)}
                      for m in MODES} for s in EVALUATION_SEEDS}
    comparisons, tests = {}, []
    for control in ('native', 'temporal', 'frequency', 'original', 'no_detector', 'no_delayed', 'cold', 'fullwarm'):
        loss = [blocks[str(s)]['persistent']['loss']-blocks[str(s)][control]['loss'] for s in EVALUATION_SEEDS]
        cpu = [blocks[str(s)]['persistent']['cpu']-blocks[str(s)][control]['cpu'] for s in EVALUATION_SEEDS]
        objective = [q+2*c/STEPS for q,c in zip(loss,cpu)]
        comparisons[control] = {'paired_loss':loss, 'paired_cpu':cpu, 'paired_objective':objective,
            'mean_loss_difference':statistics.fmean(loss), 'mean_cpu_difference':statistics.fmean(cpu),
            'mean_objective_difference':statistics.fmean(objective),
            'loss_interval95_descriptive':interval(loss), 'cpu_interval95_descriptive':interval(cpu),
            'objective_interval95_descriptive':interval(objective)}
        if control in ('native','temporal'):
            contrasts = [('objective', objective), ('margin_quality', [v-.02 for v in loss])]
            if control == 'native': contrasts.append(('cpu',cpu))
            for name, values in contrasts: tests.append({'control':control,'metric':name,**sign_test(values)})
    accepting = True
    for i,row in enumerate(sorted(tests,key=lambda r:r['p_one_sided'])):
        row['holm_threshold'] = .05/(len(tests)-i)
        row['significant'] = accepting and row['p_one_sided'] <= row['holm_threshold']
        accepting = row['significant']
    return {'seed_blocks':blocks, 'comparisons':comparisons, 'five_primary_tests':tests,
            'registered_success':all(t['significant'] for t in tests),
            'unit':'eight independent seed blocks; families and observations are not independent replicates',
            'family_means':{f:{m:statistics.fmean(indexed[f,s,m]['metrics']['mean_logloss'] for s in EVALUATION_SEEDS)
                              for m in MODES} for f in FAMILIES}}


def specification(config, development_choice):
    return {'schema':SCHEMA+'.design', 'modes':list(MODES), 'families':list(FAMILIES),
        'development_seeds':list(DEVELOPMENT_SEEDS), 'evaluation_seeds':list(EVALUATION_SEEDS),
        'development_excludes':['unseen_structure'], 'steps':STEPS, 'unscored_prefix':PREFIX,
        'restart_after_observations':list(RESTART_AT), 'controller_config':config,
        'state_policies':{'persistent':'selectivewarm, retain inactive state and replay only missing prefix on demand',
                          'cold':'discard switched-away expensive state and reconstruct on return',
                          'fullwarm':'update all three every observation; extra paid forecasts also supply credit'},
        'state_comparison_limit':'fullwarm changes both maintenance and available paid prediction credit; not a pure storage-only ablation',
        'original_controller_config':asdict(original_config()), 'development_choice':development_choice,
        'information':'identical current action and past outcomes only; seed/family/change times/future outcomes evaluator-only',
        'generator':{'source_bound':True, 'known_changes':{'shift':[171,341],'misleading':[171,341]},
                     'heldout_only_structure':'a XOR y[t-2] XOR (a[t-4] AND y[t-6]), noise .08',
                     'draw_order':'predict before outcome RNG draw; two independent uniform draws per step',
                     'within_seed_families':'common random numbers; family outcomes correlated, seed block is inference unit'},
        'budgets':{'wall_seconds':60,'job_memory_mib':512,'job_processes':4,'hard_cpu_seconds':None,
                   'cpu_note':'whole Job CPU measured; equal wall/memory/process limits, not equal consumed work'},
        'schedule_seed':SCHEDULE_SEED,
        'metrics':{'objective':'mean logloss + 2 * total Job-plus-supervisor CPU / 512',
                   'quality_margin_nats':.02,'primary_tests':5,'alpha':.05,
                   'tests':'E-C objective, quality margin, CPU; E-B objective, quality margin',
                   'multiplicity':'Holm five one-sided exact paired seed-block sign tests; ties abs<=1e-12 omitted',
                   'success':'all five pass; shifted-margin sign inference is not a proof of mean noninferiority',
                   'bootstrap':{'samples':4000,'seed':BOOTSTRAP_SEED,'indices':[99,3899],'role':'descriptive paired mean intervals'},
                   'detector':'first alarm within96 observations perknownchange; other alarms false; nochange times sent tolearner'},
        'failure_rule':'preserve every attempt; missing/failed trial forbids complete paired assessment',
        'scope':'trusted synthetic mechanisms; no authentic coding, persistent repository transfer or strict peak-memory claim'}


def profile_configs():
    from nomad.persistent import PersistentConfig
    baseline = PersistentConfig(state_policy='selectivewarm')
    return {'standard':baseline,
            'long':replace(baseline,commitment=96,credit_horizon=192),
            'short':replace(baseline,commitment=32,credit_horizon=64,detector_window=16,detector_threshold=.25)}


def mode_config(config, mode):
    from nomad.persistent import PersistentConfig
    value = PersistentConfig(**config)
    flags = {'no_detector':{'detector_enabled':False}, 'no_delayed':{'delayed_credit':False},
             'cold':{'state_policy':'cold'}, 'fullwarm':{'state_policy':'fullwarm'}}
    return replace(value, **flags.get(mode, {}))


def worker(request):
    from nomad.persistent import PersistentController, predictor_snapshot, predictor_restore, deterministic_state_hash
    split, family, seed, mode = (request[k] for k in ('split','family','seed','mode'))
    if split == 'evaluation':
        plan = validate(request['plan']); config = plan['design']['controller_config']
        allowed, modes = EVALUATION_SEEDS, MODES
    elif split == 'development':
        config = request['controller_config']; allowed = DEVELOPMENT_SEEDS
        modes = (*MODES[:4], *('candidate_'+name for name in profile_configs()))
        if family == 'unseen_structure': raise ValueError('heldout-only generator prohibited during development')
    else: raise ValueError('unknown split')
    if family not in FAMILIES or seed not in allowed or mode not in modes:
        raise ValueError('unregistered worker request')
    before = source_identity(); started, cpu = time.perf_counter(), time.process_time()
    if mode in MODES[:3]: model = make_predictor(mode)
    elif mode == 'original': model = AdaptiveController(original_config())
    else: model = PersistentController(mode_config(config, mode))
    initialization_wall, initialization_cpu = time.perf_counter()-started, time.process_time()-cpu
    rng = random.Random(seed); history, trace, checkpoints, telemetry_segments = [], [], [], []
    fixed_cost = {'inference_wall_seconds':0.,'inference_cpu_seconds':0.,
                  'incremental_update_wall_seconds':0.,'incremental_update_cpu_seconds':0.}
    checkpoint_wall = checkpoint_cpu = 0.0
    loop_wall, loop_cpu = time.perf_counter(), time.process_time()
    for step in range(STEPS):
        action = int(rng.random() < (.09 if family == 'sparse_noisy' else .5))
        prediction_wall,prediction_cpu = time.perf_counter(),time.process_time()
        p = probability(model, action)
        if mode in MODES[:3]:
            fixed_cost['inference_wall_seconds'] += time.perf_counter()-prediction_wall
            fixed_cost['inference_cpu_seconds'] += time.process_time()-prediction_cpu
        # The outcome draw and rule occur strictly after the forecast.
        outcome = generated_outcome(family, action, history, rng.random())
        mechanism = model.selected if hasattr(model,'selected') else mode
        update_wall,update_cpu = time.perf_counter(),time.process_time()
        model.observe(action, outcome)
        if mode in MODES[:3]:
            fixed_cost['incremental_update_wall_seconds'] += time.perf_counter()-update_wall
            fixed_cost['incremental_update_cpu_seconds'] += time.process_time()-update_cpu
        history.append((action,outcome))
        trace.append({'step':step,'action':action,'outcome':outcome,'p':p,'mechanism':mechanism})
        if step+1 in RESTART_AT:
            telemetry_segments.append({'observed_prefix':step+1,
                'telemetry':json.loads(canonical(model.telemetry if hasattr(model,'telemetry') else fixed_cost))})
            wall, timing = time.perf_counter(), time.process_time()
            if mode in MODES[:3]: state = predictor_snapshot(model,mode,prefix_sha256=digest(history))
            else: state = model.snapshot()
            state_bytes = canonical(state)
            with tempfile.TemporaryDirectory(prefix='nomad-temporal-state-') as temp:
                target, partial = Path(temp)/'state.json', Path(temp)/'state.pending'
                with partial.open('xb') as handle:
                    handle.write(state_bytes); handle.flush(); os.fsync(handle.fileno())
                os.replace(partial,target)
                restored = json.loads(target.read_bytes())
                if mode in MODES[:3]:
                    model = predictor_restore(restored,mode,expected_prefix_sha256=digest(history))
                elif mode == 'original': model = AdaptiveController.load(restored)
                else:
                    model = PersistentController.load(restored,expected_epoch=0,
                        expected_prefix_sha256=digest(history),expected_config=mode_config(config,mode))
            duration, cpu_duration = time.perf_counter()-wall, time.process_time()-timing
            checkpoint_wall += duration; checkpoint_cpu += cpu_duration
            checkpoints.append({'observed_prefix':step+1,'state_sha256':hashlib.sha256(state_bytes).hexdigest(),
                'deterministic_state_sha256':deterministic_state_hash(state) if mode not in MODES[:4] else digest(state),
                'state_bytes':len(state_bytes),'wall_seconds':duration,'cpu_seconds':cpu_duration,
                'method':('canonical JSON, fsync partial, atomic replace; original history/logical restart with lazy learner reconstruction'
                          if mode=='original' else 'canonical JSON, fsync partial, atomic replace, parsed direct-state restoration')})
    loop_wall, loop_cpu = time.perf_counter()-loop_wall, time.process_time()-loop_cpu
    wall, timing = time.perf_counter(), time.process_time()
    if mode in MODES[:3]: state = predictor_snapshot(model,mode,prefix_sha256=digest(history))
    else: state = model.snapshot()
    final_bytes = canonical(state)
    final_state_wall, final_state_cpu = time.perf_counter()-wall, time.process_time()-timing
    decisions = model.decisions if hasattr(model,'decisions') else []
    alarms = [d['at'] for d in getattr(model,'alarms',[])]
    result = {'split':split,'family':family,'seed':seed,'mode':mode,'status':'COMPLETED',
        'config':asdict(mode_config(config,mode)) if mode not in MODES[:4] else asdict(original_config()) if mode=='original' else None,
        'input_sha256':digest(history),
        'trace':trace,'metrics':metrics(trace),'decisions':decisions,
        'switches':sum(a['mechanism']!=b['mechanism'] for a,b in zip(trace,trace[1:])),
        'detector_metrics':detector_metrics(family,alarms), 'checkpoints':checkpoints,
        'final_state_sha256':deterministic_state_hash(state) if mode not in MODES[:4] else digest(state),
        'final_storage_sha256':hashlib.sha256(final_bytes).hexdigest(),'final_state_bytes':len(final_bytes),
        'telemetry':model.telemetry if hasattr(model,'telemetry') else {},
        'telemetry_segments':telemetry_segments,'fixed_predictor_cost':fixed_cost,
        'worker_memory':process_memory(),'source_stable':source_identity()==before,
        'worker_cost':{'initialization_wall_seconds':initialization_wall,'initialization_cpu_seconds':initialization_cpu,
            'loop_inclusive_wall_seconds':loop_wall,'loop_inclusive_cpu_seconds':loop_cpu,
            'checkpoint_subset_wall_seconds':checkpoint_wall,'checkpoint_subset_cpu_seconds':checkpoint_cpu,
            'final_state_wall_seconds':final_state_wall,'final_state_cpu_seconds':final_state_cpu,
            'algorithm_inclusive_wall_seconds':time.perf_counter()-started,
            'algorithm_inclusive_cpu_seconds':time.process_time()-cpu},
        'cost_scope':'loop includes checkpoints and all inactive updates; stage subsets must not be summed with inclusive totals'}
    if not result['source_stable']: raise ValueError('worker source changed')
    return result


def execute(request):
    if os.name != 'nt': raise RuntimeError('registered total process accounting requires Windows Job supervision')
    wall, cpu = time.perf_counter(), time.process_time()
    with tempfile.TemporaryDirectory(prefix='nomad-temporal-worker-') as temp:
        path = Path(temp)/'request.json'; write_new(path,request)
        result = run_supervised([sys.executable,'-B',str(Path(__file__).resolve()),'worker','--request',str(path)],
            cwd=ROOT,timeout_s=60,max_output_bytes=4_000_000,windows_memory_mib=512,windows_max_processes=4)
        accounting = result.metrics or {}
        try:
            row = json.loads(result.output)
            if row.get('status') != 'COMPLETED': raise ValueError('incomplete worker')
        except (ValueError,TypeError,AttributeError):
            row = {k:request[k] for k in ('split','family','seed','mode')}
            row.update(status='FAILED',output_excerpt=result.output[:4000].decode('utf-8','replace'))
        job_cpu = accounting.get('cpu_user_s',0)+accounting.get('cpu_kernel_s',0) if accounting.get('available') else None
        row['process_receipt'] = {'returncode':result.returncode,'timed_out':result.timed_out,
            'truncated':result.truncated,'output_sha256':result.output_sha256,
            'cleanup':result.cleanup,'native_job_metrics':accounting}
        if result.returncode or result.timed_out or result.truncated or job_cpu is None or result.cleanup != 'windows-job-empty-confirmed':
            row['status'] = 'FAILED'
    outer = time.process_time()-cpu
    row['cost'] = {'whole_job_cpu_seconds':job_cpu,'supervisor_cpu_seconds':outer,
        'total_cpu_seconds':None if job_cpu is None else job_cpu+outer,'whole_wall_seconds':time.perf_counter()-wall,
        'native_peak_counter_bytes':accounting.get('peak_job_memory_counter_bytes'),
        'strict_peak_qualification':'HOLD','coverage':'worker Job subtree plus supervisor; parent peak separate'}
    return row


def development_choice(rows):
    configs = profile_configs()
    expected = {(f,s,m) for f,s,m in schedule('development',(*MODES[:4],*('candidate_'+n for n in configs)))}
    if len(rows)!=len(expected) or {(r['family'],r['seed'],r['mode']) for r in rows}!=expected or any(r['status']!='COMPLETED' for r in rows):
        raise ValueError('complete development inventory required')
    scores = {name:statistics.fmean(r['metrics']['mean_logloss']+2*r['cost']['total_cpu_seconds']/STEPS
                for r in rows if r['mode']=='candidate_'+name) for name in configs}
    winner = min(configs,key=lambda name:(scores[name],list(configs).index(name)))
    return {'selected_profile':winner,'profile_mean_objectives':scores,
            'selection_rule':'minimum mean development logloss +2totalCPU/512; deterministic declared profile order breaks ties',
            'profiles':{name:asdict(value) for name,value in configs.items()}}


def validate_development(development):
    data = read(development)
    if (data.get('schema')!=SCHEMA+'.development' or data.get('status')!='COMPLETED'
            or data.get('source_sha256_before')!=source_identity() or data.get('source_sha256_after')!=source_identity()
            or not data.get('source_stable')): raise ValueError('current-source complete development required')
    choice = development_choice(data['trials'])
    if data.get('development_choice') != choice: raise ValueError('development selection differs')
    inputs={}
    for row in data['trials']:
        raw = {k:v for k,v in row.items() if k not in ('cost','process_receipt')}
        if hashlib.sha256((json.dumps(raw,sort_keys=True,allow_nan=False)+os.linesep).encode()).hexdigest() != row['process_receipt']['output_sha256']:
            raise ValueError('development transport changed')
        if row['metrics']!=metrics(row['trace']): raise ValueError('development scoring changed')
        process,cost=row['process_receipt'],row['cost']; native=process['native_job_metrics']
        if (process['returncode']!=0 or process['timed_out'] is not False or process['truncated'] is not False
                or process['cleanup']!='windows-job-empty-confirmed' or native.get('available') is not True
                or row.get('source_stable') is not True or row.get('split')!='development'):
            raise ValueError('development worker completion changed')
        for value in (native['cpu_user_s'],native['cpu_kernel_s'],cost['supervisor_cpu_seconds'],
                      cost['whole_wall_seconds'],cost['total_cpu_seconds']):
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                raise ValueError('invalid development cost')
        job=native['cpu_user_s']+native['cpu_kernel_s']
        if cost['whole_job_cpu_seconds']!=job or cost['total_cpu_seconds']!=job+cost['supervisor_cpu_seconds']:
            raise ValueError('development whole-process cost differs')
        history=[(r['action'],r['outcome']) for r in row['trace']]
        if row['input_sha256']!=digest(history) or inputs.setdefault((row['family'],row['seed']),history)!=history:
            raise ValueError('development inputs differ')
        expected=(asdict(profile_configs()[row['mode'].removeprefix('candidate_')]) if row['mode'].startswith('candidate_')
                  else asdict(original_config()) if row['mode']=='original' else None)
        if row['config']!=expected: raise ValueError('development configuration changed')
    return data,choice


def freeze(output, development):
    data,choice=validate_development(development)
    config = asdict(profile_configs()[choice['selected_profile']])
    payload = {'schema':SCHEMA+'.plan','design':specification(config,choice),
        'source_sha256':source_identity(),'native_identity':verified_runtime_identity(),
        'python':sys.version,'platform':sys.platform,'development_sha256':sha(development),
        'development_path':str(development),'evaluation_outcomes_generated':False,
        'observed_at_utc':datetime.now(timezone.utc).isoformat()}
    result = {'payload':payload,'sha256':digest(payload)}; write_new(output,result); return result


def validate(document):
    p = document.get('payload')
    if (not isinstance(p,dict) or document.get('sha256')!=digest(p) or p.get('schema')!=SCHEMA+'.plan'
            or p.get('source_sha256')!=source_identity() or p.get('native_identity')!=verified_runtime_identity()
            or p.get('python')!=sys.version or p.get('platform')!=sys.platform
            or p.get('evaluation_outcomes_generated') is not False):
        raise ValueError('registered source/runtime/plan differs')
    if p['design']!=specification(p['design']['controller_config'],p['design']['development_choice']):
        raise ValueError('registered design changed')
    choice=p['design']['development_choice']; profiles={n:asdict(c) for n,c in profile_configs().items()}
    if (choice.get('profiles')!=profiles or choice.get('selected_profile') not in profiles
            or p['design']['controller_config']!=profiles[choice['selected_profile']]):
        raise ValueError('frozen configuration is not the declared development choice')
    if set(DEVELOPMENT_SEEDS)&set(EVALUATION_SEEDS): raise ValueError('split overlap')
    return p


def run(output, document=None):
    split = 'evaluation' if document else 'development'
    if document: config = validate(document)['design']['controller_config']; modes=MODES
    else:
        config = asdict(profile_configs()['standard'])
        modes = (*MODES[:4],*('candidate_'+name for name in profile_configs()))
    output = Path(output)
    if output.exists(): raise FileExistsError('preserve all temporal attempts')
    started = output.with_name(output.stem+'.STARTED.json')
    write_new(started,{'schema':SCHEMA+'.started','split':split,'plan_sha256':document['sha256'] if document else None,
        'source_sha256':source_identity(),'evaluation_outcomes_generated':False,
        'observed_at_utc':datetime.now(timezone.utc).isoformat()})
    report = {'schema':SCHEMA+('.result' if document else '.development'),'status':'STARTED','split':split,
        'plan_sha256':document['sha256'] if document else None,'started_receipt_sha256':sha(started),
        'source_sha256_before':source_identity(),'config':config,'trials':[],
        'observed_at_utc':datetime.now(timezone.utc).isoformat(),'parent_memory_before':process_memory(),
        'scope':'trusted mechanisms only','coding_advantage':'NOT_ESTABLISHED','cross_repository_transfer':'NOT_ESTABLISHED'}
    wall,cpu = time.perf_counter(),time.process_time()
    try:
        for family,seed,mode in schedule(split,modes):
            if source_identity()!=report['source_sha256_before']:
                raise ValueError('source changed before next registered trial')
            request = {'split':split,'family':family,'seed':seed,'mode':mode,'controller_config':config}
            if mode.startswith('candidate_'): request['controller_config']=asdict(profile_configs()[mode.removeprefix('candidate_')])
            if document: request['plan']=document
            attempt_wall,attempt_cpu = time.perf_counter(),time.process_time()
            try: row=execute(request)
            except BaseException as error:
                observed=time.process_time()-attempt_cpu
                row={k:request[k] for k in ('split','family','seed','mode')}
                row.update(status='FAILED',reason=type(error).__name__+': '+str(error),
                    cost={'whole_job_cpu_seconds':None,'supervisor_cpu_seconds':observed,
                          'total_cpu_seconds':None,'whole_wall_seconds':time.perf_counter()-attempt_wall})
            report['trials'].append(row)
            print(json.dumps({'split':split,'trial':len(report['trials']),'family':family,'mode':mode,'status':row['status']}),flush=True)
            if row['status']!='COMPLETED': raise RuntimeError('failed attempt retained; paired assessment refused')
        if source_identity()!=report['source_sha256_before']: raise ValueError('source changed during run')
        if document: report['assessment']=assess(report['trials'])
        else: report['development_choice']=development_choice(report['trials'])
        report['status']='COMPLETED'
    except BaseException as error:
        report['status']='INTERRUPTED_HOLD'; report['reason']=type(error).__name__+': '+str(error)
    report['harness_wall_seconds']=time.perf_counter()-wall
    report['harness_cpu_seconds']=time.process_time()-cpu
    allocated=sum(r['cost']['supervisor_cpu_seconds'] for r in report['trials'])
    jobs=[r['cost']['whole_job_cpu_seconds'] for r in report['trials']]
    report['unallocated_harness_cpu_seconds']=max(0.,report['harness_cpu_seconds']-allocated)
    report['whole_study_cpu_seconds']=report['harness_cpu_seconds']+sum(jobs) if all(v is not None for v in jobs) else None
    report['cpu_coverage']='complete for attempted process trees' if all(v is not None for v in jobs) else 'INCOMPLETE'
    report['parent_memory_after']=process_memory()
    report['cost_scope']='includes worker startup, verification, all active/inactive computation, snapshots, restore and transport; final parent JSON write excluded'
    report['source_sha256_after']=source_identity()
    report['source_stable']=report['source_sha256_before']==report['source_sha256_after']
    if not report['source_stable']: report['status']='INTERRUPTED_HOLD'
    write_new(output,report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='action',required=True)
    child=sub.add_parser('worker'); child.add_argument('--request',type=Path,required=True)
    child=sub.add_parser('develop'); child.add_argument('--output',type=Path,required=True)
    child=sub.add_parser('freeze'); child.add_argument('--development',type=Path,required=True); child.add_argument('--output',type=Path,required=True)
    child=sub.add_parser('run'); child.add_argument('--plan',type=Path,required=True); child.add_argument('--output',type=Path,required=True)
    child.add_argument('--confirm-preregistered-evaluation',action='store_true',required=True)
    args=parser.parse_args()
    if args.action=='worker': print(json.dumps(worker(read(args.request)),sort_keys=True,allow_nan=False)); return 0
    if args.action=='freeze': result=freeze(args.output,args.development)
    elif args.action=='develop': result=run(args.output)
    else: result=run(args.output,read(args.plan))
    print(json.dumps({'status':result.get('status','FROZEN'),'sha256':result.get('sha256')}))
    return 0 if result.get('status','COMPLETED')=='COMPLETED' else 3


if __name__=='__main__': raise SystemExit(main())
