"""Frozen trusted-stream adaptive computation study, never repository efficacy."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.adaptive import AdaptiveConfig, AdaptiveController, canonical, digest, make_predictor, probability
from nomad.native_bitwork import verified_runtime_identity
from nomad.supervised import run_supervised

SCHEMA='nomad.adaptive-mechanism-study.v18'
FAMILIES=('stationary','temporal','delayed','shift','sparse_noisy','misleading','unseen_structure','irreducible')
MODES=('frequency','native','temporal','adaptive','no_history','no_structure','no_memory','no_selection')
DEVELOPMENT_SEEDS=(18185001,)
EVALUATION_SEEDS=tuple(range(18185101,18185109))
STEPS=128
PREFIX=32


def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(value,handle,sort_keys=True,indent=2,allow_nan=False);handle.write('\n')


def read(path):return json.loads(Path(path).read_bytes())


def process_memory():
    """Process-local native high-water counters, never sum-of-process peaks."""
    if os.name!='nt':return {'available':False,'scope':'Windows process counter unavailable'}
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in
            ('peak_ws','ws','peak_paged_pool','paged_pool','peak_nonpaged_pool','nonpaged_pool','commit','peak_commit')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);api=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    api.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
    api.GetProcessMemoryInfo.restype=wintypes.BOOL
    value=Counters();value.cb=ctypes.sizeof(value)
    ok=bool(api.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(value),ctypes.sizeof(value)))
    return {'available':ok,'peak_working_set_bytes':value.peak_ws if ok else None,
        'reported_peak_commit_bytes':value.peak_commit if ok else None,'winerror':0 if ok else ctypes.get_last_error(),
        'scope':'this process lifetime; excludes other processes; peaks are not contemporaneous or additive',
        'strict_commit_peak_qualification':'HOLD'}


def source_identity():
    return {name:file_hash(ROOT/name) for name in ('nomad/adaptive.py','nomad/native_bitwork.py',
        'nomad/supervised.py','nomad/windows_job.py','scripts/experiment_adaptive_v18.py',
        'vendor/BGR-v1.4.0-runtime/MANIFEST.sha256')}


def specification(config):
    return {'schema':SCHEMA+'.design','modes':list(MODES),'families':list(FAMILIES),
        'development_seeds':list(DEVELOPMENT_SEEDS),'evaluation_seeds':list(EVALUATION_SEEDS),
        'development_excludes':['unseen_structure'],'steps':STEPS,'unscored_prefix':PREFIX,
        'controller_config':asdict(config),
        'generator':{'actions':'one RNG.random per step; probability1 .08 for sparse_noisy, .5 otherwise',
            'outcome_draw':'one RNG.random drawn only AFTER this arm forecasts',
            'stationary':[.1,.3],'temporal':'a XOR previous y, flip .075',
            'delayed':'a XOR action at lag3, flip .075','shift':'[.1,.3] before64, [.8,.6] thereafter',
            'sparse_noisy':[.07,.35],'misleading':'temporal rule before64; stationary [.1,.3] thereafter',
            'unseen_structure':'a XOR (outcome at lag2 AND action at lag5), flip .075',
            'irreducible':.5,'missing_history_bit':0},
        'information':'predictor receives current binary action and previously observed binary outcomes only; never family/seed/future',
        'ablations':{'no_history':'frequency only; chronological history unavailable to screening or expensive models',
            'no_structure':'screen disabled; bounded exploration continues without structural ordering',
            'no_memory':'selector utility history reset at decisions; native predictive history retained, not MNEMONIC ablation',
            'no_selection':'fixed native choice with controller bookkeeping; no adaptive strategy selection'},
        'cost_calibration':'fixed development initialization wall and full-loop wall per observation; realized whole-process CPU is evaluated separately',
        'budgets':{'per_trial_wall_seconds':30,'windows_job_memory_mib':512,'windows_job_max_processes':4,
            'observations':STEPS,'maximum_decisions':256,'maximum_retained_history':config.max_history,
            'hard_cpu_seconds':None,'hard_cpu_limit_note':'CPU measured; equal wall and Job memory/process ceilings, no independent CPU-time kill limit'},
        'schedule':{'order':'seed-family groups, shuffled with independent registered schedule seed; modes shuffled within every group',
                    'schedule_seed':18185931},
        'metrics':{'primary_quality':'mean natural-log loss after prefix','brier':'mean (p-y)^2 after prefix',
            'ece':'10 fixed equal-width bins, left-closed/right-open except final includes1; weighted absolute calibration error',
            'objective':'mean_logloss + cost_weight * (whole_job_cpu_seconds + supervisor_cpu_seconds) / 128',
            'objective_cost_weight':config.cost_weight,'quality_margin_nats':.02,
            'unit':'eight independent seed blocks; average eight family streams within each seed',
            'primary_controls':['native','frequency','temporal'],
            'primary_tests':['objective difference <0','logloss difference minus .02 <0','whole CPU difference <0'],
            'multiplicity':'Holm correction across nine one-sided paired exact sign tests, alpha .05; ties <=1e-12 omitted',
            'meaning':'directional seed-block evidence; shifted-margin sign criterion is not mean-equivalence proof',
            'bootstrap':{'paired_seed':18185999,'samples':4000,'percentiles':[2.5,97.5],'purpose':'descriptive paired seed-block mean interval, not extra independent evidence'}},
        'failure_rule':'retain every attempted trial and cost; any missing/failed arm prevents complete paired efficacy assessment',
        'limits':['trusted generated binary streams only; no coding/transfer/energy/GPU claim',
            'unseen structure excludes development outcomes, but its generator is designed and known',
            'reported native Job peak is a high-water counter, potentially including attempted charges; strict committed peak remains HOLD',
            'cost estimates and uncertainty proxies do not establish optimal allocation or causal benefit']}


def calibrated_config(calibration):
    if (calibration.get('schema')!=SCHEMA+'.development' or calibration.get('status')!='COMPLETED'
            or calibration.get('source_sha256_before')!=source_identity()
            or calibration.get('source_sha256_after')!=source_identity()
            or calibration.get('source_stable') is not True
            or calibration.get('config')!=asdict(AdaptiveConfig())):
        raise ValueError('complete current-source development calibration required')
    rows=calibration.get('trials',[])
    expected=set(schedule('development'))
    if len(rows)!=len(expected) or {(r.get('family'),r.get('seed'),r.get('mode')) for r in rows}!=expected:
        raise ValueError('incomplete, repeated or heldout-contaminated development inventory')
    for row in rows:
        receipt=row.get('process_receipt',{});cost=row.get('cost',{})
        if (row.get('split')!='development' or row.get('status')!='COMPLETED'
                or receipt.get('returncode')!=0 or receipt.get('timed_out') is not False
                or receipt.get('truncated') is not False or receipt.get('cleanup')!='windows-job-empty-confirmed'
                or cost.get('total_cpu_seconds') is None or cost['total_cpu_seconds']<0
                or row.get('metrics')!=metrics(row.get('trace',[]))
                or row.get('input_sha256')!=digest([(r['action'],r['outcome']) for r in row['trace']])):
            raise ValueError('development outcome/cost receipt incomplete or changed')
        raw={k:v for k,v in row.items() if k not in ('process_receipt','cost')}
        if receipt.get('output_sha256')!=hashlib.sha256((json.dumps(raw,sort_keys=True,allow_nan=False)+os.linesep).encode()).hexdigest():
            raise ValueError('development worker output differs from retained transport hash')
    costs={m:statistics.mean(r['worker_cost']['loop_wall_seconds']/STEPS for r in rows if r['mode']==m) for m in ('frequency','temporal','native')}
    setups={m:statistics.mean(r['worker_cost']['initialization_wall_seconds'] for r in rows if r['mode']==m) for m in ('frequency','temporal','native')}
    config=replace(AdaptiveConfig(),cost_seconds=costs,setup_seconds=setups);config.validate()
    if calibration.get('suggested_controller_config')!=asdict(config):raise ValueError('calibration cost summary changed')
    return config


def freeze(output,calibration_path):
    calibration=read(calibration_path);config=calibrated_config(calibration)
    payload={'schema':SCHEMA+'.plan','design':specification(config),'source_sha256':source_identity(),
        'native_identity':verified_runtime_identity(),'python':sys.version,'platform':sys.platform,
        'calibration_sha256':file_hash(calibration_path),'calibration_path':str(calibration_path),
        'evaluation_outcomes_generated':False,'observed_at_utc':datetime.now(timezone.utc).isoformat()}
    document={'payload':payload,'sha256':digest(payload)};write_new(output,document);return document


def validate(document):
    p=document.get('payload')
    if not isinstance(p,dict) or document.get('sha256')!=digest(p) or p.get('schema')!=SCHEMA+'.plan':
        raise ValueError('invalid frozen adaptive plan')
    config=AdaptiveConfig(**p['design']['controller_config']);config.validate()
    if (p['design']!=specification(config) or p['source_sha256']!=source_identity()
            or p['native_identity']!=verified_runtime_identity() or p['python']!=sys.version
            or p['platform']!=sys.platform or p['evaluation_outcomes_generated'] is not False):
        raise ValueError('adaptive source/runtime/design changed after freeze')
    return p


def generated_outcome(family,action,history,draw):
    previous=lambda lag,bit:history[-lag][bit] if len(history)>=lag else 0
    if family=='irreducible':return int(draw<.5)
    if family in ('stationary','shift','sparse_noisy') or (family=='misleading' and len(history)>=64):
        probs=([.07,.35] if family=='sparse_noisy' else [.8,.6] if family=='shift' and len(history)>=64 else [.1,.3])
        return int(draw<probs[action])
    if family in ('temporal','misleading'):bit=previous(1,1)
    elif family=='delayed':bit=previous(3,0)
    elif family=='unseen_structure':bit=previous(2,1)&previous(5,0)
    else:raise ValueError('unregistered generator')
    return action^bit^int(draw<.075)


def metrics(trace):
    scored=trace[PREFIX:]
    if len(scored)!=STEPS-PREFIX:raise ValueError('incomplete scored trace')
    losses=[-math.log(row['p'] if row['outcome'] else 1-row['p']) for row in scored]
    bins=[[] for _ in range(10)]
    for row in scored:bins[min(9,int(row['p']*10))].append(row)
    ece=sum(abs(sum(r['p']-r['outcome'] for r in bucket)) for bucket in bins)/len(scored)
    return {'mean_logloss':statistics.mean(losses),'brier':statistics.mean((r['p']-r['outcome'])**2 for r in scored),
            'ece10':ece,'scored_forecasts':len(scored)}


def worker(request):
    split=request['split'];seed=request['seed'];family=request['family'];mode=request['mode']
    if split=='evaluation':
        plan=validate(request['plan']);config=AdaptiveConfig(**plan['design']['controller_config'])
        allowed=EVALUATION_SEEDS
    elif split=='development':
        config=AdaptiveConfig(**request['controller_config']);config.validate();allowed=DEVELOPMENT_SEEDS
        if family=='unseen_structure':raise ValueError('heldout-only structure cannot generate development outcomes')
    else:raise ValueError('unregistered split')
    if seed not in allowed or family not in FAMILIES or mode not in MODES:raise ValueError('unregistered worker trial')
    start,cpustart=time.perf_counter(),time.process_time()
    if mode in ('frequency','native','temporal'):model=make_predictor(mode)
    else:
        flags={'no_history':{'use_history':False},'no_structure':{'use_structure':False},
               'no_memory':{'use_memory':False},'no_selection':{'adaptive_selection':False}}
        model=AdaptiveController(replace(config,**flags.get(mode,{})))
    init_wall,init_cpu=time.perf_counter()-start,time.process_time()-cpustart
    wall,cpu=time.perf_counter(),time.process_time()
    rng=random.Random(seed);history=[];trace=[]
    for step in range(STEPS):
        action=int(rng.random()<(.08 if family=='sparse_noisy' else .5))
        p=probability(model,action)
        # No future outcome draw or generator rule reaches the predictor.
        outcome=generated_outcome(family,action,history,rng.random())
        selected=model.selected if isinstance(model,AdaptiveController) else mode
        model.observe(action,outcome)
        history.append((action,outcome));trace.append({'step':step,'action':action,'outcome':outcome,'p':p,'mechanism':selected})
    loop_wall,loop_cpu=time.perf_counter()-wall,time.process_time()-cpu
    state=model.snapshot() if hasattr(model,'snapshot') else {'counts':model.counts}
    result={'split':split,'family':family,'seed':seed,'mode':mode,'status':'COMPLETED','input_sha256':digest(history),
        'trace':trace,'metrics':metrics(trace),'decisions':model.decisions if isinstance(model,AdaptiveController) else [],
        'final_state_sha256':digest(state),'telemetry':model.telemetry if isinstance(model,AdaptiveController) else {},
        'worker_memory':process_memory(),
        'worker_cost':{'initialization_wall_seconds':init_wall,'initialization_cpu_seconds':init_cpu,
            'loop_wall_seconds':loop_wall,'loop_cpu_seconds':loop_cpu,
            'algorithm_wall_seconds':time.perf_counter()-start,'algorithm_cpu_seconds':time.process_time()-cpustart}}
    return result


def execute(request):
    if os.name!='nt':raise RuntimeError('registered whole-process study requires native Windows Job accounting')
    wall,cpu=time.perf_counter(),time.process_time();result=None
    with tempfile.TemporaryDirectory(prefix='nomad-adaptive-worker-') as temp:
        path=Path(temp)/'request.json';write_new(path,request)
        process=run_supervised([sys.executable,'-B',str(Path(__file__).resolve()),'worker','--request',str(path)],
            cwd=ROOT,timeout_s=30,max_output_bytes=2_000_000,windows_memory_mib=512,windows_max_processes=4)
        accounting=process.metrics or {}
        try:
            result=json.loads(process.output)
            if not isinstance(result,dict) or result.get('status')!='COMPLETED':raise ValueError('worker incomplete')
        except (ValueError,TypeError):
            result={key:request[key] for key in ('split','family','seed','mode')}
            result.update(status='FAILED',output_excerpt=process.output[:2000].decode('utf-8','replace'))
        jobcpu=accounting.get('cpu_user_s',0)+accounting.get('cpu_kernel_s',0) if accounting.get('available') else None
        result['process_receipt']={'returncode':process.returncode,'timed_out':process.timed_out,
            'truncated':process.truncated,'output_sha256':process.output_sha256,'cleanup':process.cleanup,
            'native_job_metrics':accounting}
        if process.returncode or process.timed_out or process.truncated or jobcpu is None or process.cleanup!='windows-job-empty-confirmed':
            result['status']='FAILED'
    supervisor_cpu=time.process_time()-cpu
    result['cost']={'whole_job_cpu_seconds':jobcpu,'supervisor_cpu_seconds':supervisor_cpu,
        'total_cpu_seconds':jobcpu+supervisor_cpu if jobcpu is not None else None,
        'whole_wall_seconds':time.perf_counter()-wall,
        'native_peak_counter_bytes':accounting.get('peak_job_memory_counter_bytes'),
        'peak_counter_scope':accounting.get('peak_counter_scope'),'memory_coverage':'worker Job subtree; excludes parent supervisor',
        'strict_peak_qualification':'HOLD'}
    return result


def schedule(split):
    seeds=DEVELOPMENT_SEEDS if split=='development' else EVALUATION_SEEDS
    families=tuple(f for f in FAMILIES if split!='development' or f!='unseen_structure')
    rng=random.Random(18185931);groups=[(f,s) for s in seeds for f in families];rng.shuffle(groups)
    rows=[]
    for family,seed in groups:
        modes=list(MODES);rng.shuffle(modes)
        rows.extend((family,seed,mode) for mode in modes)
    return rows


def sign_test(values):
    wins=sum(v < -1e-12 for v in values);losses=sum(v > 1e-12 for v in values);n=wins+losses
    return {'wins':wins,'losses':losses,'ties':len(values)-n,
            'p_one_sided':sum(math.comb(n,j) for j in range(wins,n+1))/2**n if n else 1.0}


def interval(values,seed):
    rng=random.Random(seed);means=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(4000))
    return [means[99],means[3899]]


def assess(rows,config):
    expected={(f,s,m) for f in FAMILIES for s in EVALUATION_SEEDS for m in MODES}
    actual={(r['family'],r['seed'],r['mode']) for r in rows}
    if actual!=expected or len(rows)!=len(expected) or any(r['status']!='COMPLETED' for r in rows):
        raise ValueError('all attempted and registered trials required; failed trials cannot be discarded')
    indexed={(r['family'],r['seed'],r['mode']):r for r in rows}
    for family in FAMILIES:
        for seed in EVALUATION_SEEDS:
            if len({indexed[(family,seed,m)]['input_sha256'] for m in MODES})!=1:raise ValueError('arms received unmatched stream inputs')
    means={f:{m:{key:statistics.mean(indexed[(f,s,m)]['metrics'][key] for s in EVALUATION_SEEDS)
                for key in ('mean_logloss','brier','ece10')} for m in MODES} for f in FAMILIES}
    blocks={s:{m:{'loss':statistics.mean(indexed[(f,s,m)]['metrics']['mean_logloss'] for f in FAMILIES),
                   'cpu':statistics.mean(indexed[(f,s,m)]['cost']['total_cpu_seconds'] for f in FAMILIES)}
                for m in MODES} for s in EVALUATION_SEEDS}
    contrasts=[];comparisons={}
    for control in ('native','frequency','temporal'):
        loss=[blocks[s]['adaptive']['loss']-blocks[s][control]['loss'] for s in EVALUATION_SEEDS]
        cpu=[blocks[s]['adaptive']['cpu']-blocks[s][control]['cpu'] for s in EVALUATION_SEEDS]
        objective=[q+config.cost_weight*c/STEPS for q,c in zip(loss,cpu)]
        comparisons[control]={'paired_seed_logloss_differences':loss,'paired_seed_cpu_differences':cpu,
            'paired_seed_objective_differences':objective,'mean_logloss_difference':statistics.mean(loss),
            'mean_cpu_difference':statistics.mean(cpu),'mean_objective_difference':statistics.mean(objective),
            'descriptive_logloss_mean_interval95':interval(loss,18185999),
            'descriptive_cpu_mean_interval95':interval(cpu,18185999),
            'descriptive_objective_mean_interval95':interval(objective,18185999)}
        for metric,values in (('objective',objective),('margin_shifted_quality',[v-.02 for v in loss]),('whole_cpu',cpu)):
            contrasts.append({'control':control,'metric':metric,**sign_test(values)})
    rejecting=True
    for i,row in enumerate(sorted(contrasts,key=lambda r:r['p_one_sided'])):
        row['holm_threshold']=.05/(len(contrasts)-i)
        row['significant']=rejecting and row['p_one_sided']<=row['holm_threshold'];rejecting=row['significant']
    for control in comparisons:
        tests={r['metric']:r['significant'] for r in contrasts if r['control']==control}
        comparisons[control]['registered_quality_cost_criterion_passed']=all(tests.values())
    return {'family_quality_means_descriptive':means,'paired_seed_blocks':blocks,'comparisons':comparisons,
        'nine_registered_sign_tests':contrasts,'unit':'8 independent seed blocks, not 64 independent family streams',
        'coding_advantage':'NOT_ESTABLISHED','transfer_advantage':'NOT_ESTABLISHED'}


def run(output,*,document=None):
    split='evaluation' if document else 'development'
    if document:payload=validate(document);config=AdaptiveConfig(**payload['design']['controller_config'])
    else:config=AdaptiveConfig()
    output=Path(output)
    if output.exists():raise FileExistsError('preserve all prior adaptive attempts')
    started=output.with_name(output.stem+'.STARTED.json')
    write_new(started,{'schema':SCHEMA+'.started','split':split,'plan_sha256':document['sha256'] if document else None,
        'source_sha256':source_identity(),'evaluation_outcomes_generated':False,
        'observed_at_utc':datetime.now(timezone.utc).isoformat()})
    report={'schema':SCHEMA+('.result' if document else '.development'),'status':'STARTED','split':split,
        'plan_sha256':document['sha256'] if document else None,'started_receipt_sha256':file_hash(started),
        'source_sha256_before':source_identity(),'config':asdict(config),'trials':[],
        'scope':'trusted generated streams only; no repository code','coding_advantage':'NOT_ESTABLISHED',
        'api_cost_usd':0,'energy_joules':None,'strict_peak_qualification':'HOLD',
        'observed_at_utc':datetime.now(timezone.utc).isoformat(),'parent_memory_before':process_memory()}
    wall,cpu=time.perf_counter(),time.process_time()
    try:
        for family,seed,mode in schedule(split):
            request={'split':split,'family':family,'seed':seed,'mode':mode,'controller_config':asdict(config)}
            if document:request['plan']=document
            attempt_wall,attempt_cpu=time.perf_counter(),time.process_time()
            try:row=execute(request)
            except BaseException as error:
                observed_cpu=time.process_time()-attempt_cpu
                row={k:request[k] for k in ('split','family','seed','mode')}
                row.update(status='FAILED',reason=type(error).__name__+': '+str(error),
                    cost={'whole_job_cpu_seconds':None,'supervisor_cpu_seconds':observed_cpu,
                        'total_cpu_seconds':None,'whole_wall_seconds':time.perf_counter()-attempt_wall,
                        'coverage':'worker execution/accounting unknown; measured supervisor CPU is a lower bound'})
            report['trials'].append(row)
            print(json.dumps({'split':split,'trial':len(report['trials']),'family':family,'mode':mode,'status':row['status']}),flush=True)
            if row['status']!='COMPLETED':raise RuntimeError('failed trial retained; complete efficacy assessment refused')
        if source_identity()!=report['source_sha256_before']:raise ValueError('source changed during registered run')
        if document:report['assessment']=assess(report['trials'],config)
        else:
            costs={m:statistics.mean(r['worker_cost']['loop_wall_seconds']/STEPS for r in report['trials'] if r['mode']==m) for m in ('frequency','temporal','native')}
            setups={m:statistics.mean(r['worker_cost']['initialization_wall_seconds'] for r in report['trials'] if r['mode']==m) for m in ('frequency','temporal','native')}
            report['suggested_controller_config']=asdict(replace(config,cost_seconds=costs,setup_seconds=setups))
            report['calibration_rule']='arithmetic mean development baseline full-loop wall/128 and initialization wall; no heldout quality selection'
        report['status']='COMPLETED'
    except BaseException as error:
        report['status']='INTERRUPTED_HOLD';report['reason']=type(error).__name__+': '+str(error)
    report['harness_wall_seconds']=time.perf_counter()-wall
    report['harness_cpu_seconds']=time.process_time()-cpu
    allocated=sum(r['cost']['supervisor_cpu_seconds'] for r in report['trials'])
    report['unallocated_harness_cpu_seconds']=max(0.,report['harness_cpu_seconds']-allocated)
    known_jobs=[r['cost']['whole_job_cpu_seconds'] for r in report['trials']]
    report['measured_study_cpu_lower_bound_seconds']=report['harness_cpu_seconds']+sum(v for v in known_jobs if v is not None)
    report['whole_study_cpu_seconds']=report['measured_study_cpu_lower_bound_seconds'] if all(v is not None for v in known_jobs) else None
    report['cpu_coverage']='complete for attempted process trees' if all(v is not None for v in known_jobs) else 'INCOMPLETE_UNKNOWN_WORKER_COST'
    report['parent_memory_after']=process_memory()
    report['memory_aggregation']='parent lifetime peak and worker Job peaks reported separately; no sum or strict simultaneous whole-study peak'
    report['cost_scope']='per-trial Job subtree plus supervisor; unallocated orchestration/analysis CPU reported separately; final JSON serialization excluded'
    try:report['source_sha256_after']=source_identity()
    except OSError as error:report['source_sha256_after']={'error':str(error)}
    report['source_stable']=report['source_sha256_before']==report['source_sha256_after']
    if not report['source_stable']:report['status']='INTERRUPTED_HOLD'
    write_new(output,report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    child=sub.add_parser('worker');child.add_argument('--request',type=Path,required=True)
    child=sub.add_parser('develop');child.add_argument('--output',type=Path,required=True)
    child=sub.add_parser('freeze');child.add_argument('--calibration',type=Path,required=True);child.add_argument('--output',type=Path,required=True)
    child=sub.add_parser('run');child.add_argument('--plan',type=Path,required=True);child.add_argument('--output',type=Path,required=True)
    child.add_argument('--confirm-preregistered-evaluation',action='store_true',required=True)
    args=parser.parse_args(argv)
    if args.action=='worker':print(json.dumps(worker(read(args.request)),sort_keys=True,allow_nan=False));return 0
    if args.action=='freeze':result=freeze(args.output,args.calibration)
    elif args.action=='develop':result=run(args.output)
    else:result=run(args.output,document=read(args.plan))
    print(json.dumps({'status':result.get('status','FROZEN'),'sha256':result.get('sha256')}))
    return 0 if result.get('status','COMPLETED')=='COMPLETED' else 3


if __name__=='__main__':raise SystemExit(main())
