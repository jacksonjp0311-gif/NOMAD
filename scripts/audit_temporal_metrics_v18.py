"""Independent retained-trace arithmetic for Temporal Ascension.

Imports no experiment, learner, native engine or state codec. This verifies
receipt consistency under the frozen external source/plan anchor; it cannot
authenticate a hostile replacement of every anchor or prove forecast order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='nomad.temporal-ascension.v18'
FAMILIES=('stationary','temporal','delayed','shift','sparse_noisy','misleading','unseen_structure','irreducible')
MODES=('frequency','temporal','native','original','persistent','no_detector','no_delayed','cold','fullwarm')
SEEDS=tuple(range(18186101,18186109))
STEPS=512
PREFIX=64


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    if path.stat().st_size>160_000_000: raise ValueError('audit input exceeds bounded retained-receipt size')
    def reject_constant(value): raise ValueError('nonfinite JSON constant: '+value)
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError('duplicate JSON key: '+key)
            result[key]=value
        return result
    value=json.loads(path.read_bytes(),parse_constant=reject_constant,object_pairs_hook=unique)
    if not isinstance(value,dict): raise ValueError('audit receipt must be an object')
    return value


def equal(actual,expected,label='receipt'):
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or set(actual)!=set(expected): raise ValueError('dictionary inventory differs: '+label)
        for key,value in expected.items(): equal(actual[key],value,label+'.'+str(key))
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected): raise ValueError('sequence inventory differs: '+label)
        for number,value in enumerate(expected): equal(actual[number],value,label+'.'+str(number))
    elif type(expected) in (int,float):
        if type(actual) not in (int,float) or not math.isfinite(actual) or not math.isclose(actual,expected,abs_tol=1e-11,rel_tol=0):
            raise ValueError('arithmetic differs: '+label)
    elif type(actual) is not type(expected) or actual!=expected: raise ValueError('value differs: '+label)


def nonnegative(value,label):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError('invalid finite measured cost: '+label)
    return value


def metrics(trace):
    if (not isinstance(trace,list) or len(trace)!=STEPS
            or any(type(row.get('step')) is not int or row['step']!=number for number,row in enumerate(trace))):
        raise ValueError('incomplete ordered prequential trace')
    for row in trace:
        if (type(row.get('action')) is not int or row['action'] not in (0,1)
                or type(row.get('outcome')) is not int or row['outcome'] not in (0,1)
                or type(row.get('p')) not in (int,float) or not math.isfinite(row['p']) or not 0<row['p']<1
                or row.get('mechanism') not in ('frequency','temporal','native','abstain')):
            raise ValueError('invalid Bernoulli forecast or public observation')
    scored=trace[PREFIX:]
    bins=[[] for _ in range(10)]
    for row in scored: bins[min(9,int(row['p']*10))].append(row)
    return {'mean_logloss':statistics.fmean(-math.log(r['p'] if r['outcome'] else 1-r['p']) for r in scored),
            'brier':statistics.fmean((r['p']-r['outcome'])**2 for r in scored),
            'ece10':sum(abs(sum(r['p']-r['outcome'] for r in bucket)) for bucket in bins)/len(scored),
            'scored_forecasts':len(scored)}


def sign_test(values):
    wins=sum(v < -1e-12 for v in values); losses=sum(v > 1e-12 for v in values); size=wins+losses
    return {'wins':wins,'losses':losses,'ties':len(values)-size,
            'p_one_sided':sum(math.comb(size,k) for k in range(wins,size+1))/2**size if size else 1.0}


def interval(values,seed):
    rng=random.Random(seed)
    means=sorted(statistics.fmean(rng.choices(values,k=len(values))) for _ in range(4000))
    return [means[99],means[3899]]


def paired_assessment(measured,*,bootstrap_seed):
    """Eight seed units; family/task repeats never inflate the unit count."""
    means={family:{mode:statistics.fmean(measured[family,seed,mode]['metrics']['mean_logloss'] for seed in SEEDS)
                   for mode in MODES} for family in FAMILIES}
    blocks={str(seed):{mode:{'loss':statistics.fmean(measured[family,seed,mode]['metrics']['mean_logloss'] for family in FAMILIES),
                            'cpu':statistics.fmean(measured[family,seed,mode]['cpu'] for family in FAMILIES)}
                      for mode in MODES} for seed in SEEDS}
    comparisons={}; tests=[]
    for control in ('native','temporal','frequency','original','no_detector','no_delayed','cold','fullwarm'):
        loss=[blocks[str(seed)]['persistent']['loss']-blocks[str(seed)][control]['loss'] for seed in SEEDS]
        cpu=[blocks[str(seed)]['persistent']['cpu']-blocks[str(seed)][control]['cpu'] for seed in SEEDS]
        objective=[quality+2.0*cost/STEPS for quality,cost in zip(loss,cpu)]
        comparisons[control]={'paired_loss':loss,'paired_cpu':cpu,
            'paired_objective':objective,'mean_loss_difference':statistics.fmean(loss),
            'mean_cpu_difference':statistics.fmean(cpu),'mean_objective_difference':statistics.fmean(objective),
            'loss_interval95_descriptive':interval(loss,bootstrap_seed),
            'cpu_interval95_descriptive':interval(cpu,bootstrap_seed),
            'objective_interval95_descriptive':interval(objective,bootstrap_seed)}
        if control in ('native','temporal'):
            for metric,values in [('objective',objective),('margin_quality',[value-.02 for value in loss])]+(
                    [('cpu',cpu)] if control=='native' else []):
                tests.append({'control':control,'metric':metric,**sign_test(values)})
    continuing=True
    for index,row in enumerate(sorted(tests,key=lambda entry:entry['p_one_sided'])):
        row['holm_threshold']=.05/(len(tests)-index)
        row['significant']=continuing and row['p_one_sided']<=row['holm_threshold']
        continuing=row['significant']
    return {'family_means':means,'seed_blocks':blocks,'comparisons':comparisons,
            'five_primary_tests':tests,'registered_success':all(row['significant'] for row in tests),
            'unit':'eight independent seed blocks; families and observations are not independent replicates'}


def detector_metrics(family,alarms):
    if (not isinstance(alarms,list) or any(type(value) is not int or not 1<=value<=STEPS for value in alarms)
            or alarms!=sorted(set(alarms))):
        raise ValueError('invalid ordered unique detector alarm prefixes')
    changes=[171,341] if family in ('shift','misleading') else []
    unmatched=list(alarms); delays=[]
    for change in changes:
        matches=[alarm for alarm in unmatched if change<=alarm<=min(STEPS,change+96)]
        alarm=matches[0] if matches else None
        delays.append(alarm-change if alarm is not None else None)
        if alarm is not None: unmatched.remove(alarm)
    return {'known_change_boundaries':changes,'detection_window':96,'delays':delays,
            'detected_changes':sum(value is not None for value in delays),'false_alarms':len(unmatched),
            'alarm_prefixes':alarms,
            'interpretation':'distribution changes only; dependence-screen decisions are not change alarms'}


def registered_schedule():
    randomizer=random.Random(18186931)
    groups=[(family,seed) for seed in SEEDS for family in FAMILIES]
    randomizer.shuffle(groups); result=[]
    for family,seed in groups:
        modes=list(MODES);randomizer.shuffle(modes)
        result.extend((family,seed,mode) for mode in modes)
    return result


def expected_config(design,mode):
    if mode in MODES[:3]: return None
    if mode=='original': return design['original_controller_config']
    result=dict(design['controller_config'])
    result.update({'no_detector':{'detector_enabled':False},'no_delayed':{'delayed_credit':False},
                   'cold':{'state_policy':'cold'},'fullwarm':{'state_policy':'fullwarm'}}.get(mode,{}))
    return result


def trace_alarms(row):
    if row['mode'] in MODES[:4]: return []
    config=row['config']
    if type(config['detector_enabled']) is not bool: raise ValueError('detector flag must be boolean')
    if not config['detector_enabled']: return []
    width,cooldown=config['detector_window'],config['detector_cooldown'];threshold=config['detector_threshold']
    if (type(width) is not int or not 1<=width<=2048 or type(cooldown) is not int or not 1<=cooldown<=2048
            or type(threshold) not in (int,float) or not math.isfinite(threshold) or not .001<=threshold<=4):
        raise ValueError('invalid registered detector parameters')
    losses=[];last=-cooldown;alarms=[]
    for prefix,event in enumerate(row['trace'],1):
        probability=min(1-1e-9,max(1e-9,event['p']))
        losses.append(min(4.0,max(0.0,-math.log(probability if event['outcome'] else 1-probability))))
        losses=losses[-2*width:]
        if len(losses)<2*width or prefix-last<cooldown: continue
        before=sum(losses[:width])/width;after=sum(losses[width:])/width
        if abs(after-before)>=threshold: alarms.append(prefix);last=prefix
    return alarms


def validate_design(design):
    fixed={'schema':SCHEMA+'.design','modes':list(MODES),'families':list(FAMILIES),
           'development_seeds':[18186001,18186002],'evaluation_seeds':list(SEEDS),
           'development_excludes':['unseen_structure'],'steps':STEPS,'unscored_prefix':PREFIX,
           'restart_after_observations':[256],'schedule_seed':18186931}
    for key,value in fixed.items(): equal(design[key],value,'registered design.'+key)
    for key,value in {'quality_margin_nats':.02,'primary_tests':5,'alpha':.05,
                      'objective':'mean logloss + 2 * total Job-plus-supervisor CPU / 512'}.items():
        equal(design['metrics'][key],value,'registered metric.'+key)
    for key,value in {'samples':4000,'seed':18186999,'indices':[99,3899]}.items():
        equal(design['metrics']['bootstrap'][key],value,'registered bootstrap.'+key)
    for key,value in {'wall_seconds':60,'job_memory_mib':512,'job_processes':4,'hard_cpu_seconds':None}.items():
        equal(design['budgets'][key],value,'registered budget.'+key)
    if not isinstance(design['controller_config'],dict) or design['controller_config'].get('state_policy')!='selectivewarm':
        raise ValueError('primary persistent arm must retain registered selective-warm policy')
    choice=design['development_choice']
    if choice['profiles'][choice['selected_profile']]!=design['controller_config']:
        raise ValueError('primary configuration differs from development nomination')


def validate_decisions(row,design):
    trace,decisions,mode=row['trace'],row['decisions'],row['mode']
    if not isinstance(decisions,list) or len(decisions)>STEPS: raise ValueError('decision record budget exceeded')
    if mode in MODES[:3]:
        if decisions or any(event['mechanism']!=mode for event in trace): raise ValueError('fixed predictor mode changed')
        return []
    if not decisions: raise ValueError('controller decisions missing')
    previous=-1
    for index,decision in enumerate(decisions):
        prefix=decision['observed_prefix']
        if (type(prefix) is not int or not previous<prefix<STEPS
                or type(decision['decision_index']) is not int or decision['decision_index']!=index
                or decision['mechanism'] not in ('frequency','temporal','native','abstain')):
            raise ValueError('controller decision index or observed prefix invalid')
        if index==0 and prefix!=0: raise ValueError('initial forecast has no prior decision')
        stop=decisions[index+1]['observed_prefix'] if index+1<len(decisions) else STEPS
        if any(event['mechanism']!=decision['mechanism'] for event in trace[prefix:stop]):
            raise ValueError('forecast mechanism differs from the prior public decision')
        previous=prefix
    if mode=='original':
        size=design['original_controller_config']['block_size']
        equal([d['observed_prefix'] for d in decisions],list(range(0,STEPS,size)),'original block decisions')
    alarms=trace_alarms(row)
    for decision in decisions:
        if decision.get('change_alarm',False) is not (decision['observed_prefix'] in alarms):
            raise ValueError('decision alarm differs from prior observed loss detector')
    return alarms


def validate_trial(row,design,platform):
    if row['status']!='COMPLETED' or row['split']!='evaluation' or row['source_stable'] is not True:
        raise ValueError('incomplete or source-unstable worker')
    equal(row['config'],expected_config(design,row['mode']),'actual arm configuration')
    quality=metrics(row['trace']);equal(row['metrics'],quality,'worker quality metrics')
    inputs=[[event['action'],event['outcome']] for event in row['trace']]
    if row['input_sha256']!=digest(inputs): raise ValueError('public input identity differs from trace')
    receipt=row['process_receipt']; native=receipt['native_job_metrics']
    raw={key:value for key,value in row.items() if key not in ('cost','process_receipt')}
    transport=(json.dumps(raw,sort_keys=True,allow_nan=False)+('\r\n' if platform=='win32' else '\n')).encode()
    if len(transport)>4_000_000: raise ValueError('worker transport exceeds registered byte ceiling')
    if hashlib.sha256(transport).hexdigest()!=receipt['output_sha256']:
        raise ValueError('retained worker JSON differs from its transport receipt')
    if (type(receipt['returncode']) is not int or receipt['returncode']!=0 or receipt['timed_out'] is not False
            or receipt['truncated'] is not False or receipt['cleanup']!='windows-job-empty-confirmed'
            or native['available'] is not True):
        raise ValueError('unqualified process completion or missing Job accounting')
    job=nonnegative(native['cpu_user_s'],'Job user CPU')+nonnegative(native['cpu_kernel_s'],'Job kernel CPU')
    cost=row['cost']; supervisor=nonnegative(cost['supervisor_cpu_seconds'],'supervisor CPU')
    equal(cost['whole_job_cpu_seconds'],job,'whole Job CPU')
    equal(cost['total_cpu_seconds'],job+supervisor,'disjoint Job plus supervisor CPU')
    nonnegative(cost['whole_wall_seconds'],'whole trial wall')
    nonnegative(native['peak_job_memory_counter_bytes'],'Job high-water counter')
    equal(cost['native_peak_counter_bytes'],native['peak_job_memory_counter_bytes'],'Job high-water counter')
    if cost['strict_peak_qualification']!='HOLD': raise ValueError('strict simultaneous peak qualification overstated')
    alarms=validate_decisions(row,design)
    equal(row['detector_metrics'],detector_metrics(row['family'],alarms),'evaluator-only detector metrics')
    equal(row['switches'],sum(a['mechanism']!=b['mechanism'] for a,b in zip(row['trace'],row['trace'][1:])),'mechanism switches')
    checkpoints=row['checkpoints']
    if not isinstance(checkpoints,list) or [c['observed_prefix'] for c in checkpoints]!=[256]:
        raise ValueError('registered direct-state restart inventory changed')
    for checkpoint in checkpoints:
        if (type(checkpoint['state_bytes']) is not int or not 1<=checkpoint['state_bytes']<=16*1024*1024
                or not isinstance(checkpoint['state_sha256'],str) or len(checkpoint['state_sha256'])!=64
                or any(c not in '0123456789abcdef' for c in checkpoint['state_sha256'])):
            raise ValueError('invalid retained state size or identity')
        nonnegative(checkpoint['cpu_seconds'],'checkpoint CPU');nonnegative(checkpoint['wall_seconds'],'checkpoint wall')
        method=('canonical JSON, fsync partial, atomic replace; original history/logical restart with lazy learner reconstruction'
                if row['mode']=='original' else 'canonical JSON, fsync partial, atomic replace, parsed direct-state restoration')
        equal(checkpoint['method'],method,'registered checkpoint restoration method')
        if (not isinstance(checkpoint['deterministic_state_sha256'],str) or len(checkpoint['deterministic_state_sha256'])!=64
                or any(c not in '0123456789abcdef' for c in checkpoint['deterministic_state_sha256'])):
            raise ValueError('deterministic state identity missing')
    for key in ('final_state_sha256','final_storage_sha256'):
        if not isinstance(row[key],str) or len(row[key])!=64 or any(c not in '0123456789abcdef' for c in row[key]):
            raise ValueError('final state/storage identity missing')
    if type(row['final_state_bytes']) is not int or not 1<=row['final_state_bytes']<=16*1024*1024:
        raise ValueError('final state byte budget invalid')
    stages=row['worker_cost']
    for name,value in stages.items(): nonnegative(value,'worker stage '+name)
    for suffix in ('cpu_seconds','wall_seconds'):
        equal(stages['checkpoint_subset_'+suffix],sum(c[suffix] for c in checkpoints),'checkpoint subset '+suffix)
        if stages['checkpoint_subset_'+suffix]>stages['loop_inclusive_'+suffix]+1e-9:
            raise ValueError('checkpoint subset exceeds inclusive loop')
        allocated=sum(stages[name+'_'+suffix] for name in ('initialization','loop_inclusive','final_state'))
        if allocated>stages['algorithm_inclusive_'+suffix]+1e-9:
            raise ValueError('disjoint worker stages exceed algorithm interval')
    if stages['algorithm_inclusive_cpu_seconds']>job+1e-7:
        raise ValueError('worker algorithm CPU exceeds encompassing Job CPU')
    if stages['algorithm_inclusive_wall_seconds']>cost['whole_wall_seconds']+1e-7:
        raise ValueError('worker algorithm wall exceeds encompassing trial interval')
    return {'metrics':quality,'cpu':job+supervisor,'job_cpu':job,'supervisor_cpu':supervisor,
            'inputs':inputs,'decisions':len(row['decisions']),'checkpoints':len(checkpoints)}


def audit_records(plan,result,started,*,started_sha256,root):
    payload=plan['payload'];design=payload['design']
    if (set(plan)!={'payload','sha256'} or payload['schema']!=SCHEMA+'.plan'
            or result['schema']!=SCHEMA+'.result' or started['schema']!=SCHEMA+'.started'
            or plan['sha256']!=digest(payload) or result['plan_sha256']!=plan['sha256']
            or started['plan_sha256']!=plan['sha256'] or result['started_receipt_sha256']!=started_sha256):
        raise ValueError('plan/result/start identity or schema mismatch')
    validate_design(design)
    if (payload['evaluation_outcomes_generated'] is not False or started['evaluation_outcomes_generated'] is not False
            or started['split']!='evaluation' or result['split']!='evaluation' or result['status']!='COMPLETED'
            or result['source_stable'] is not True or result['cpu_coverage']!='complete for attempted process trees'
            or payload['platform']!='win32'):
        raise ValueError('complete prospective Windows process-tree study required')
    equal(result['config'],design['controller_config'],'frozen primary configuration')
    required={'nomad/persistent.py','nomad/adaptive.py','nomad/native_bitwork.py','nomad/supervised.py','nomad/windows_job.py',
              'scripts/experiment_temporal_v18.py','scripts/experiment_adaptive_v18.py',
              'scripts/audit_temporal_metrics_v18.py','scripts/verify_temporal_replay_v18.py',
              'vendor/BGR-v1.4.0-runtime/MANIFEST.sha256','experiments/PLAN_ADAPTIVE_MECHANISMS_V018.json'}
    sources=payload['source_sha256']
    if set(sources)!=required: raise ValueError('source commitment inventory changed')
    for mapping in (result['source_sha256_before'],result['source_sha256_after'],started['source_sha256']):
        equal(mapping,sources,'frozen source identity')
    root=Path(root).resolve()
    for name,checksum in sources.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or file_hash(path)!=checksum: raise ValueError('current source differs: '+name)
    expected=registered_schedule()
    actual=[(r['family'],r['seed'],r['mode']) for r in result['trials']]
    if actual!=expected: raise ValueError('registered ordered inventory incomplete, duplicated or reordered')
    observed={};inputs={};job=supervisor=0.0;decisions=checkpoints=0
    for row in result['trials']:
        key=row['family'],row['seed'],row['mode'];value=validate_trial(row,design,payload['platform'])
        if inputs.setdefault(key[:2],value['inputs'])!=value['inputs']: raise ValueError('arms received unmatched public observations')
        observed[key]=value;job+=value['job_cpu'];supervisor+=value['supervisor_cpu']
        decisions+=value['decisions'];checkpoints+=value['checkpoints']
    outer=nonnegative(result['harness_cpu_seconds'],'whole harness CPU')
    nonnegative(result['harness_wall_seconds'],'whole harness wall')
    if outer+1e-9<supervisor: raise ValueError('allocated supervisors exceed encompassing harness CPU')
    equal(result['whole_study_cpu_seconds'],outer+job,'whole study disjoint CPU')
    equal(result['unallocated_harness_cpu_seconds'],max(0.0,outer-supervisor),'unallocated harness CPU')
    assessment=paired_assessment(observed,bootstrap_seed=design['metrics']['bootstrap']['seed'])
    equal(result['assessment'],assessment,'paired independent assessment')
    return {'schema':'nomad.temporal-independent-arithmetic.v18','status':'PASS','complete_trials':len(observed),
            'seed_blocks':len(SEEDS),'forecasts_checked':len(observed)*STEPS,
            'scored_forecasts_checked':len(observed)*(STEPS-PREFIX),'decisions_checked':decisions,
            'restarts_checked':checkpoints,'total_cpu_arithmetic_seconds':outer+job,'assessment':assessment,
            'scope':'independent retained-trace arithmetic, transport/source bindings, matched inputs, stage subsets, complete Job-plus-supervisor CPU and paired inference; not independent outcome authorship or proof of forecast execution order',
            'strict_peak_qualification':'HOLD','coding_advantage':'NOT_ESTABLISHED','cross_repository_transfer':'NOT_ESTABLISHED'}


def audit(plan_path,result_path):
    plan_path,result_path=Path(plan_path),Path(result_path)
    started_path=result_path.with_name(result_path.stem+'.STARTED.json')
    report=audit_records(read(plan_path),read(result_path),read(started_path),
                         started_sha256=file_hash(started_path),root=ROOT)
    return {**report,'plan_file_sha256':file_hash(plan_path),'result_file_sha256':file_hash(result_path),
            'auditor_sha256':file_hash(Path(__file__))}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args(argv)
    if args.output.exists(): raise FileExistsError('preserve prior audit receipts')
    report=audit(args.plan,args.result);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({key:report[key] for key in ('status','complete_trials','forecasts_checked','scored_forecasts_checked')}))


if __name__=='__main__': main()
