"""Posthoc data-only temporal diagnostics; no learner or experiment imports.

Reads an already completed frozen evaluation. It neither generates outcomes,
changes policies, estimates new significance tests, nor changes acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

MODES = ('frequency','temporal','native','original','persistent','no_detector',
         'no_delayed','cold','fullwarm')
FAMILIES = ('stationary','temporal','delayed','shift','sparse_noisy','misleading',
            'unseen_structure','irreducible')
SEEDS = tuple(range(18186101,18186109))
CONTROLLERS = ('persistent','no_detector','no_delayed','cold','fullwarm')
STEPS, PREFIX = 512, 64
STAGES = ('build','catchup','active','inactive','decision','detector','bookkeeping',
          'serialization','restoration')


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def loss(event): return -math.log(event['p'] if event['outcome'] else 1-event['p'])


def quality(trace):
    selected=trace[PREFIX:]; bins=[[] for _ in range(10)]
    for event in selected: bins[min(9,int(event['p']*10))].append(event)
    return {'mean_logloss':statistics.fmean(loss(e) for e in selected),
        'brier':statistics.fmean((e['p']-e['outcome'])**2 for e in selected),
        'ece10':sum(abs(sum(e['p']-e['outcome'] for e in b)) for b in bins)/len(selected)}


def episodes(trace):
    result=[]
    for event in trace:
        if not result or result[-1]['mechanism']!=event['mechanism']:
            result.append({'mechanism':event['mechanism'],'start':event['step'],
                           'end_exclusive':event['step']+1,'forecasts':1})
        else:
            result[-1]['end_exclusive']=event['step']+1
            result[-1]['forecasts']+=1
    return result


def paired_difference(left,right):
    lq,rq=quality(left['trace']),quality(right['trace'])
    fields={key:lq[key]-rq[key] for key in lq}
    fields.update({key:left['cost'][key]-right['cost'][key]
        for key in ('total_cpu_seconds','whole_wall_seconds')})
    fields.update({key:left['telemetry'][key]-right['telemetry'][key]
        for key in ('catchup_observations','inactive_forecasts','cold_evictions')})
    fields['mean_objective_difference']=fields['mean_logloss']+2*fields['total_cpu_seconds']/STEPS
    return fields


def match_forecasts(rows,index):
    """Compare recorded forecasts, not a new learner reconstruction."""
    output={}
    for mode in (*CONTROLLERS,'original'):
        counts=Counter(); max_difference=0.; mismatches=[]; scored_gap=Counter()
        for row in rows:
            if row['mode']!=mode: continue
            for event in row['trace']:
                selected=event['mechanism']
                if selected=='abstain':
                    counts['abstain']+=1
                    if event['p']!=.5: raise ValueError('nonneutral abstention')
                    continue
                control=index[(row['family'],row['seed'],selected)]['trace'][event['step']]
                if (event['action'],event['outcome'])!=(control['action'],control['outcome']):
                    raise ValueError('comparison does not share observed input prefix')
                counts[selected+'_comparisons']+=1
                difference=abs(event['p']-control['p']); max_difference=max(max_difference,difference)
                if difference==0: counts[selected+'_exact_matches']+=1
                else:
                    counts[selected+'_mismatches']+=1
                    if len(mismatches)<32:
                        mismatches.append({'family':row['family'],'seed':row['seed'],'step':event['step'],
                            'mechanism':selected,'controller_p':event['p'],'control_p':control['p']})
                if event['step']>=PREFIX:
                    scored_gap[selected]+=loss(event)-loss(control)
        output[mode]={'counts':dict(counts),'maximum_absolute_probability_difference':max_difference,
            'first_mismatches_up_to32':mismatches,'scored_logloss_difference_sum_by_selected_mechanism':dict(scored_gap),
            'status':'EXACT_RECORDED_FORECAST_MATCH' if max_difference==0 else 'DIFFERENCE_REQUIRES_REVIEW',
            'interpretation':('Recorded selected learners match independently executed fixed controls on the same full observed prefixes.'
                if max_difference==0 else 'A prediction difference is observed; this diagnostic does not infer its cause or excuse it as an algorithm change.')}
    return output


def episode_diagnostics(row):
    sequence=episodes(row['trace']); last_end={'native':0,'temporal':0}; detailed=[]
    inferred_catchup=0
    for episode in sequence:
        mechanism=episode['mechanism']
        if mechanism not in last_end: continue
        start,end=episode['start'],episode['end_exclusive']
        gap=start-last_end[mechanism]
        if row['config']['state_policy']=='cold': missed=start
        elif row['config']['state_policy']=='fullwarm': missed=0
        else: missed=gap
        inferred_catchup+=missed
        decisions=[d for d in row['decisions'] if start<=d['observed_prefix']<end and d['mechanism']==mechanism]
        next_decision=next((d for d in row['decisions'] if d['observed_prefix']>=end),None)
        ending_credit=(next_decision.get('credits',{}).get(mechanism) if next_decision else None)
        detailed.append({**episode,
            'activation':'first_selected_episode' if last_end[mechanism]==0 else 'reselected_episode',
            'observations_since_previous_selected_episode':gap,
            'policy_implied_catchup_observations':missed,
            'decision_records':[{'observed_prefix':d['observed_prefix'],'reason':d['reason'],
                'committed_until':d['committed_until'],'change_alarm':d.get('change_alarm',False),
                'estimated_horizon_steps':d.get('estimated_horizon_steps',{}).get(mechanism),
                'estimated_cost_seconds':d.get('estimated_cost_seconds',{}).get(mechanism),
                'mature_credit':d.get('credits',{}).get(mechanism)} for d in decisions],
            'ending_native_or_temporal_credit':ending_credit,
            'ended_at_observed_alarm':end in row['detector_metrics']['alarm_prefixes'],
            'ends_before_last_recorded_commitment':bool(decisions and end<decisions[-1]['committed_until']),
            'right_censored_at_stream_end':end==STEPS})
        last_end[mechanism]=end
    native=next((d for d in detailed if d['mechanism']=='native'),None)
    return {'family':row['family'],'seed':row['seed'],'mode':row['mode'],
        'state_policy':row['config']['state_policy'],'first_native_episode':native,
        'expensive_episodes':detailed,'actual_catchup_observations':row['telemetry']['catchup_observations'],
        'policy_implied_catchup_observations':inferred_catchup,
        'catchup_count_agrees_with_trace_and_policy':inferred_catchup==row['telemetry']['catchup_observations'],
        'scope':'Per-episode catchup is derived from recorded selection and policy; only cumulative catchup was instrumented. No per-episode measured CPU is invented.'}


def window(trace,begin,end):
    values=trace[begin:end]
    return {'begin':begin,'end_exclusive':end,'selected_forecasts':dict(Counter(v['mechanism'] for v in values)),
            'mean_logloss':statistics.fmean(loss(v) for v in values) if values else None}


def around_changes(row):
    output=[]
    for boundary in row['detector_metrics']['known_change_boundaries']:
        output.append({'boundary':boundary,
            'before32':window(row['trace'],max(0,boundary-32),boundary),
            'after32':window(row['trace'],boundary,min(STEPS,boundary+32)),
            'after96':window(row['trace'],boundary,min(STEPS,boundary+96)),
            'recorded_alarm_prefixes':[n for n in row['detector_metrics']['alarm_prefixes'] if boundary<=n<=min(STEPS,boundary+96)],
            'decisions_after96':[{'observed_prefix':d['observed_prefix'],'mechanism':d['mechanism'],
                'reason':d['reason'],'committed_until':d['committed_until']} for d in row['decisions']
                if boundary<=d['observed_prefix']<=min(STEPS,boundary+96)]})
    return {'family':row['family'],'seed':row['seed'],'mode':row['mode'],'changes':output}


def paid_work(rows):
    """Stage totals are diagnostics, never summed into an alternative CPU bill."""
    result={}
    counts=('catchup_observations','active_forecasts','inactive_forecasts','active_updates',
            'inactive_updates','cold_evictions','restores','cache_rebuilds_on_restore')
    for mode in ('persistent','cold','fullwarm'):
        current=[r for r in rows if r['mode']==mode]
        result[mode]={'trials':len(current),
            'state_policy':current[0]['config']['state_policy'],
            'operation_totals':{k:sum(r['telemetry'][k] for r in current) for k in counts},
            'stage_seconds':{stage:{kind:sum(r['telemetry'][stage+'_'+kind+'_seconds'] for r in current)
                for kind in ('cpu','wall')} for stage in STAGES},
            'whole_job_plus_supervisor_cpu_seconds':sum(r['cost']['total_cpu_seconds'] for r in current),
            'outer_checkpoint_cpu_seconds':sum(r['worker_cost']['checkpoint_subset_cpu_seconds'] for r in current),
            'outer_final_state_cpu_seconds':sum(r['worker_cost']['final_state_cpu_seconds'] for r in current),
            'logical_restores':sum(len(r['checkpoints']) for r in current),
            'selected_forecasts':dict(Counter(e['mechanism'] for r in current for e in r['trace'])),
            'scope':'Outer checkpoint/final-state totals overlap stage timers; no sum of these fields estimates total CPU. Whole Job plus supervisor is the charged total.'}
    return result


def diagnose(path):
    path=Path(path); raw=path.read_bytes(); data=json.loads(raw)
    if (data.get('schema')!='nomad.temporal-ascension.v18.result' or data.get('status')!='COMPLETED'
            or data.get('split')!='evaluation' or data.get('source_stable') is not True
            or data.get('source_sha256_before')!=data.get('source_sha256_after')):
        raise ValueError('completed source-stable frozen evaluation required')
    rows=data['trials']; index={(r['family'],r['seed'],r['mode']):r for r in rows}
    expected={(f,s,m) for f in FAMILIES for s in SEEDS for m in MODES}
    if len(rows)!=len(expected) or len(index)!=len(rows) or set(index)!=expected:
        raise ValueError('exact registered 576-trial inventory required')
    for row in rows:
        if row.get('status')!='COMPLETED' or row.get('source_stable') is not True or len(row['trace'])!=STEPS:
            raise ValueError('incomplete trial retained; posthoc complete-case interpretation refused')
        for step,event in enumerate(row['trace']):
            if event['step']!=step or type(event['action']) is not int or event['action'] not in (0,1) or type(event['outcome']) is not int or event['outcome'] not in (0,1):
                raise ValueError('trace chronology or binary domain')
            if type(event['p']) not in (int,float) or not math.isfinite(event['p']) or not 0<event['p']<1:
                raise ValueError('finite predictive probability required')
        history=[(e['action'],e['outcome']) for e in row['trace']]
        if digest(history)!=row['input_sha256']: raise ValueError('recorded input hash mismatch')
        reference=index[(row['family'],row['seed'],'native')]
        if history!=[(e['action'],e['outcome']) for e in reference['trace']]: raise ValueError('unmatched input stream')
        if any(abs(quality(row['trace'])[k]-row['metrics'][k])>1e-12 for k in ('mean_logloss','brier','ece10')):
            raise ValueError('recorded predictive score mismatch')
        for key in ('total_cpu_seconds','whole_wall_seconds'):
            if type(row['cost'][key]) not in (int,float) or not math.isfinite(row['cost'][key]) or row['cost'][key]<0:
                raise ValueError('missing or negative paid cost')
    comparisons={}
    for other,label in (('no_delayed','E_minus_G_delayed_credit'),('no_detector','E_minus_F_detector'),
                        ('cold','E_minus_H_state_retention'),('fullwarm','E_minus_I_inactive_work')):
        family_rows={}
        for family in FAMILIES:
            pairs=[]
            for seed in SEEDS:
                left,right=index[(family,seed,'persistent')],index[(family,seed,other)]
                difference=paired_difference(left,right)
                le,re=episodes(left['trace']),episodes(right['trace'])
                first=lambda seq:next((e for e in seq if e['mechanism']=='native'),None)
                a,b=first(le),first(re)
                divergent=next((x['step'] for x,y in zip(left['trace'],right['trace']) if x['mechanism']!=y['mechanism']),None)
                pairs.append({'seed':seed,'E_minus_comparator':difference,
                    'first_mechanism_divergence_step':divergent,
                    'E_first_native_episode':a,'comparator_first_native_episode':b,
                    'E_alarm_prefixes':left['detector_metrics']['alarm_prefixes'],
                    'comparator_alarm_prefixes':right['detector_metrics']['alarm_prefixes']})
            family_rows[family]={'paired_seed_differences':pairs,
                'mean_paired_differences':{k:statistics.fmean(p['E_minus_comparator'][k] for p in pairs)
                    for k in pairs[0]['E_minus_comparator']}}
        comparisons[label]={'comparator_mode':other,'by_family':family_rows,
            'interpretation':'Descriptive paired differences. Negative quality/cost values favor E. No new significance, causal identification, or acceptance rule.'}
    details=[episode_diagnostics(r) for r in rows if r['mode'] in ('persistent','cold','fullwarm')]
    return {'schema':'nomad.temporal-posthoc-diagnosis.v18','status':'COMPLETED_POSTHOC',
        'observed_at_utc':datetime.now(timezone.utc).isoformat(),
        'primary_result_sha256':hashlib.sha256(raw).hexdigest(),'plan_sha256':data['plan_sha256'],
        'diagnoser_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':'Pure-data descriptive analysis of frozen primary results; no learner execution, new outcomes, retuning, or new hypothesis tests.',
        'contrasts':comparisons,'matched_recorded_forecasts':match_forecasts(rows,index),
        'expensive_episode_diagnostics':details,
        'all_trace_implied_catchup_counts_match_observed':all(r['catchup_count_agrees_with_trace_and_policy'] for r in details),
        'choices_around_known_changes':[around_changes(r) for r in rows if r['mode'] in CONTROLLERS
            and r['detector_metrics']['known_change_boundaries']],
        'actual_paid_work_by_state_policy':paid_work(rows),
        'limits':[
            'Eight shared seed blocks are the independent units; family rows are correlated within seed.',
            'No additional inferential tests or confidence intervals are introduced by this diagnosis.',
            'Fullwarm changes paid inactive forecasts and available observed credit as well as state retention.',
            'No-delayed changes horizon release, the initial waiting rule, and the current credit window together.',
            'Selected-loss alarms can reflect mechanism switches, not only distribution changes.',
            'Per-episode CPU and per-mechanism catchup counters were not instrumented; derived counts are explicitly labeled.',
            'Fixed native controls ran independently on matched prefixes; this script compares retained probabilities and does not rerun native inference.',
            'Exact output matching does not establish coding advantage, cross-repository transfer, calibrated confidence, or energy efficiency.'],
        'parameters_retuned':False,'new_confirmatory_tests':0,
        'original_assessment_unchanged':data.get('assessment')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); report=diagnose(args.result)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as output:
        json.dump(report,output,sort_keys=True,indent=2,allow_nan=False); output.write('\n')
    print(json.dumps({'status':report['status'],
        'catchup_counts_match':report['all_trace_implied_catchup_counts_match_observed'],
        'forecast_matching':{m:r['status'] for m,r in report['matched_recorded_forecasts'].items()}},sort_keys=True))


if __name__=='__main__': main()
