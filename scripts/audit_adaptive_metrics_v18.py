"""Independent trace and cost arithmetic; no predictor or experiment imports."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'nomad.adaptive-mechanism-study.v18'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def read(path): return json.loads(path.read_bytes())

def equal(actual, expected, path='result'):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError('dictionary inventory mismatch: '+path)
        for key, value in expected.items(): equal(actual[key], value, path+'.'+str(key))
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError('sequence length mismatch: '+path)
        for i, value in enumerate(expected): equal(actual[i], value, path+'.'+str(i))
    elif type(expected) in (int, float):
        if type(actual) not in (int, float) or not math.isfinite(actual) or not math.isclose(actual, expected, abs_tol=1e-11, rel_tol=0):
            raise ValueError('arithmetic mismatch: '+path)
    elif actual != expected or type(actual) is not type(expected):
        raise ValueError('value mismatch: '+path)

def finite_nonnegative(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('invalid measured cost: '+label)
    return value

def bootstrap(values, count, seed):
    rng = random.Random(seed)
    ordered = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(count))
    # Registered 4000-sample nearest-rank percentile convention.
    return [ordered[99], ordered[3899]]

def signs(values):
    wins = sum(x < -1e-12 for x in values)
    losses = sum(x > 1e-12 for x in values)
    n = wins+losses
    return {'wins':wins, 'losses':losses, 'ties':len(values)-n,
            'p_one_sided': sum(math.comb(n, k) for k in range(wins,n+1))/2**n if n else 1.0}

def audit(plan_path, result_path):
    plan, result = read(plan_path), read(result_path)
    payload = plan['payload']; design = payload['design']
    if (payload.get('schema') != SCHEMA+'.plan' or result.get('schema') != SCHEMA+'.result'
            or design.get('schema') != SCHEMA+'.design'):
        raise ValueError('incorrect study schema')
    if plan['sha256'] != digest(payload) or result['plan_sha256'] != plan['sha256']:
        raise ValueError('plan/result commitment differs')
    if (result.get('status') != 'COMPLETED' or result.get('split') != 'evaluation'
            or result.get('source_stable') is not True
            or result.get('cpu_coverage') != 'complete for attempted process trees'):
        raise ValueError('incomplete trial set cannot establish a paired result')
    source = payload['source_sha256']
    if not {'nomad/adaptive.py','nomad/native_bitwork.py','nomad/supervised.py',
            'nomad/windows_job.py','scripts/experiment_adaptive_v18.py',
            'vendor/BGR-v1.4.0-runtime/MANIFEST.sha256'} <= set(source):
        raise ValueError('incomplete implementation commitment')
    if result['source_sha256_before'] != source or result['source_sha256_after'] != source:
        raise ValueError('source changed between registration and results')
    for name, expected in source.items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha(path) != expected:
            raise ValueError('current study source differs: '+name)
    started_path = result_path.with_name(result_path.stem+'.STARTED.json')
    started = read(started_path)
    if (started.get('schema') != SCHEMA+'.started' or started.get('split') != 'evaluation'
            or sha(started_path) != result['started_receipt_sha256'] or started['source_sha256'] != source
            or started['plan_sha256'] != plan['sha256'] or started['evaluation_outcomes_generated'] is not False):
        raise ValueError('missing or inconsistent pre-run commitment')
    equal(result['config'], design['controller_config'], 'registered controller config')
    families, seeds, modes = design['families'], design['evaluation_seeds'], design['modes']
    if len(seeds) != 8 or len(set(seeds)) != 8 or design['metrics']['bootstrap']['samples'] != 4000:
        raise ValueError('unsupported registered inference inventory')
    steps, prefix = design['steps'], design['unscored_prefix']
    inventory = {(f,s,m) for f in families for s in seeds for m in modes}
    measured, inputs = {}, {}
    cost_sum = job_sum = 0.0
    decisions = 0
    for row in result['trials']:
        key = row['family'], row['seed'], row['mode']
        if key not in inventory or key in measured or row['status'] != 'COMPLETED' or row['split'] != 'evaluation':
            raise ValueError('missing, duplicate, failed or unregistered trial')
        trace = row['trace']
        if len(trace) != steps or [r['step'] for r in trace] != list(range(steps)):
            raise ValueError('incomplete prequential trace')
        for event in trace:
            if (type(event['action']) is not int or event['action'] not in (0,1)
                    or type(event['outcome']) is not int or event['outcome'] not in (0,1)
                    or type(event['p']) not in (int,float) or not math.isfinite(event['p']) or not 0 < event['p'] < 1
                    or event['mechanism'] not in ('frequency','temporal','native','abstain')):
                raise ValueError('invalid Bernoulli observation or probability')
        history = [[r['action'],r['outcome']] for r in trace]
        if row['input_sha256'] != digest(history): raise ValueError('input digest differs from trace')
        group = key[:2]
        if inputs.setdefault(group,history) != history: raise ValueError('arms received different observations')
        scored = trace[prefix:]
        buckets = [[] for _ in range(10)]
        for event in scored: buckets[min(9,int(event['p']*10))].append(event)
        metrics = {'mean_logloss':statistics.fmean(-math.log(e['p'] if e['outcome'] else 1-e['p']) for e in scored),
                   'brier':statistics.fmean((e['p']-e['outcome'])**2 for e in scored),
                   'ece10':sum(abs(sum(e['p']-e['outcome'] for e in bucket)) for bucket in buckets)/len(scored),
                   'scored_forecasts':len(scored)}
        equal(row['metrics'], metrics, 'metrics.'+str(key))
        process = row['process_receipt']; native = process['native_job_metrics']
        raw_worker = {name:value for name,value in row.items() if name not in ('process_receipt','cost')}
        newline = '\r\n' if payload['platform'] == 'win32' else '\n'
        worker_bytes = (json.dumps(raw_worker,sort_keys=True,allow_nan=False)+newline).encode('utf-8')
        if hashlib.sha256(worker_bytes).hexdigest() != process['output_sha256']:
            raise ValueError('worker output differs from retained transport hash')
        if (process['returncode'] != 0 or process['timed_out'] or process['truncated']
                or process['cleanup'] != 'windows-job-empty-confirmed' or native.get('available') is not True):
            raise ValueError('unqualified trusted worker completion')
        job = finite_nonnegative(native['cpu_user_s'], 'job user') + finite_nonnegative(native['cpu_kernel_s'], 'job kernel')
        cost = row['cost']; supervisor = finite_nonnegative(cost['supervisor_cpu_seconds'], 'supervisor')
        equal(cost['whole_job_cpu_seconds'], job, 'Job CPU')
        equal(cost['total_cpu_seconds'], job+supervisor, 'total CPU')
        finite_nonnegative(cost['whole_wall_seconds'], 'wall')
        equal(cost['native_peak_counter_bytes'], native['peak_job_memory_counter_bytes'], 'Job reported peak')
        if cost['strict_peak_qualification'] != 'HOLD': raise ValueError('strict peak accounting overstated')
        for value in row['worker_cost'].values(): finite_nonnegative(value, 'worker stage')
        if row['mode'] in ('frequency','native','temporal'):
            if row['decisions'] or any(event['mechanism'] != row['mode'] for event in trace):
                raise ValueError('fixed mechanism or decision inventory changed')
        else:
            size = design['controller_config']['block_size']
            if len(row['decisions']) != math.ceil(steps/size): raise ValueError('controller decision inventory changed')
            for i, decision in enumerate(row['decisions']):
                if (decision['decision_index'] != i or decision['observed_prefix'] != i*size
                        or any(e['mechanism'] != decision['mechanism'] for e in trace[i*size:(i+1)*size])):
                    raise ValueError('decision prefix or selected mechanism differs from trace')
        decisions += len(row['decisions']); cost_sum += supervisor; job_sum += job
        measured[key] = {'metrics':metrics, 'cpu':job+supervisor}
    if set(measured) != inventory: raise ValueError('registered trial inventory incomplete')
    outer_cpu = finite_nonnegative(result['harness_cpu_seconds'], 'whole harness')
    finite_nonnegative(result['harness_wall_seconds'], 'whole harness wall')
    if outer_cpu+1e-10 < cost_sum: raise ValueError('allocated supervisor CPU exceeds whole harness CPU')
    equal(result['whole_study_cpu_seconds'], result['harness_cpu_seconds']+job_sum, 'study total CPU')
    equal(result['measured_study_cpu_lower_bound_seconds'], result['whole_study_cpu_seconds'], 'complete CPU lower bound')
    equal(result['unallocated_harness_cpu_seconds'], max(0.,result['harness_cpu_seconds']-cost_sum), 'unallocated CPU')
    means = {f:{m:{metric:statistics.fmean(measured[f,s,m]['metrics'][metric] for s in seeds)
                  for metric in ('mean_logloss','brier','ece10')} for m in modes} for f in families}
    blocks = {str(s):{m:{'loss':statistics.fmean(measured[f,s,m]['metrics']['mean_logloss'] for f in families),
                        'cpu':statistics.fmean(measured[f,s,m]['cpu'] for f in families)} for m in modes} for s in seeds}
    assessment = result['assessment']
    equal(assessment['family_quality_means_descriptive'],means,'family means')
    equal(assessment['paired_seed_blocks'],blocks,'paired seed blocks')
    contrasts, comparisons = [], {}
    config_weight = design['metrics']['objective_cost_weight']
    margin = design['metrics']['quality_margin_nats']
    bootstrap_seed = design['metrics']['bootstrap']['paired_seed']
    for control in design['metrics']['primary_controls']:
        delta = [blocks[str(s)]['adaptive']['loss']-blocks[str(s)][control]['loss'] for s in seeds]
        cpu = [blocks[str(s)]['adaptive']['cpu']-blocks[str(s)][control]['cpu'] for s in seeds]
        objective = [q+config_weight*c/steps for q,c in zip(delta,cpu)]
        comparisons[control] = {
            'paired_seed_logloss_differences':delta,'paired_seed_cpu_differences':cpu,'paired_seed_objective_differences':objective,
            'mean_logloss_difference':statistics.fmean(delta),'mean_cpu_difference':statistics.fmean(cpu),
            'mean_objective_difference':statistics.fmean(objective),
            'descriptive_logloss_mean_interval95':bootstrap(delta,4000,bootstrap_seed),
            'descriptive_cpu_mean_interval95':bootstrap(cpu,4000,bootstrap_seed),
            'descriptive_objective_mean_interval95':bootstrap(objective,4000,bootstrap_seed)}
        for metric, values in [('objective',objective),('margin_shifted_quality',[v-margin for v in delta]),('whole_cpu',cpu)]:
            contrasts.append({'control':control,'metric':metric,**signs(values)})
    continuation = True
    for i, row in enumerate(sorted(contrasts,key=lambda c:c['p_one_sided'])):
        row['holm_threshold'] = .05/(len(contrasts)-i)
        row['significant'] = continuation and row['p_one_sided'] <= row['holm_threshold']
        continuation = row['significant']
    for control in comparisons:
        comparisons[control]['registered_quality_cost_criterion_passed'] = all(r['significant'] for r in contrasts if r['control']==control)
    equal(assessment['nine_registered_sign_tests'],contrasts,'paired sign tests')
    equal(assessment['comparisons'],comparisons,'comparisons and intervals')
    return {'schema':'nomad.adaptive-independent-arithmetic.v18','status':'PASS',
            'plan_file_sha256':sha(plan_path),'result_file_sha256':sha(result_path),'auditor_sha256':sha(Path(__file__)),
            'complete_trials':len(measured),'seed_blocks':len(seeds),'forecasts_checked':len(measured)*steps,
            'scored_forecasts_checked':len(measured)*(steps-prefix),'decision_records_checked':decisions,
            'total_cpu_arithmetic_seconds':result['whole_study_cpu_seconds'],
            'registered_comparisons':comparisons,'registered_tests':contrasts,
            'scope':'independent trace, calibration metric, cost arithmetic, matched inputs, aggregation and paired inference; not independent outcome authorship or proof of forecast execution order',
            'strict_peak_qualification':'HOLD','coding_advantage':'NOT_ESTABLISHED','cross_repository_transfer':'NOT_ESTABLISHED'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError('preserve the existing audit receipt')
    report=audit(args.plan,args.result)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({key:report[key] for key in ('status','complete_trials','forecasts_checked','scored_forecasts_checked')}))

if __name__=='__main__': main()
