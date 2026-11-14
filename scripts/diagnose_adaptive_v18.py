"""Posthoc decomposition of frozen adaptive traces; no retuning or predictors."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import statistics


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def loss(row):return -math.log(row['p'] if row['outcome'] else 1-row['p'])


def diagnose(path):
    result=json.loads(path.read_bytes())
    if result.get('status')!='COMPLETED' or result.get('split')!='evaluation':raise ValueError('complete primary evaluation required')
    rows=result['trials'];index={(r['family'],r['seed'],r['mode']):r for r in rows}
    if len(index)!=len(rows):raise ValueError('duplicate trial')
    modes=sorted({r['mode'] for r in rows});families=sorted({r['family'] for r in rows})
    costs={}
    for mode in modes:
        selected=[r for r in rows if r['mode']==mode]
        costs[mode]={'trials':len(selected),**{key:statistics.mean(r['metrics'][key] for r in selected)
                     for key in ('mean_logloss','brier','ece10')},
            **{'mean_'+key:statistics.mean(r['cost'][key] for r in selected) for key in
               ('total_cpu_seconds','whole_job_cpu_seconds','supervisor_cpu_seconds','whole_wall_seconds','native_peak_counter_bytes')},
            'sum_total_cpu_seconds':sum(r['cost']['total_cpu_seconds'] for r in selected),
            **{'mean_'+key:statistics.mean(r['worker_cost'][key] for r in selected) for key in
               ('algorithm_cpu_seconds','algorithm_wall_seconds','initialization_wall_seconds','loop_wall_seconds')},
            'max_native_job_peak_counter_bytes':max(r['cost']['native_peak_counter_bytes'] for r in selected),
            'mean_worker_peak_working_set_bytes':statistics.mean(r['worker_memory']['peak_working_set_bytes'] for r in selected)}
    decomposition={name:{'scored_forecasts':0,'loss_difference_sum_vs_native':0.} for name in ('frequency','temporal','native','abstain')}
    matches=Counter();family_reports={};timed=Counter();allcounts=Counter()
    for family in families:
        selected=[r for r in rows if r['family']==family and r['mode']=='adaptive']
        counts=Counter();scored_counts=Counter();decision_counts=Counter();first_native=[];gain=0.
        for row in selected:
            native=index[(family,row['seed'],'native')]
            for key,value in row['telemetry'].items():timed[key]+=value
            for decision in row['decisions']:
                decision_counts[decision['reason']]+=1
                if decision['observed_prefix']>=32 and decision['diagnostic']['score']<=.015:
                    decision_counts['post_warmup_screen_at_or_below_threshold']+=1
            native_steps=[e['step'] for e in row['trace'] if e['mechanism']=='native']
            first_native.append({'seed':row['seed'],'first_native_step':min(native_steps) if native_steps else None,
                'native_observations_processed':max(native_steps)+1 if native_steps else 0})
            for event in row['trace']:
                name=event['mechanism'];counts[name]+=1;allcounts[name]+=1
                baseline=index[(family,row['seed'],name)]['trace'][event['step']] if name!='abstain' else None
                if baseline is not None:
                    if event['p']!=baseline['p'] or event['action']!=baseline['action'] or event['outcome']!=baseline['outcome']:
                        raise ValueError('lazy model differs from its matched full-prefix learner')
                    matches[name]+=1
                if event['step']>=32:
                    scored_counts[name]+=1
                    difference=loss(event)-loss(native['trace'][event['step']]);gain+=difference
                    decomposition[name]['scored_forecasts']+=1
                    decomposition[name]['loss_difference_sum_vs_native']+=difference
        n=sum(scored_counts.values())
        family_reports[family]={'selected_forecasts_all':dict(counts),'selected_forecasts_scored':dict(scored_counts),
            'decision_counts':dict(decision_counts),'native_activation':first_native,
            'mean_adaptive_minus_native_logloss':gain/n,
            'mean_adaptive_total_cpu_seconds':statistics.mean(r['cost']['total_cpu_seconds'] for r in selected)}
    total=sum(row['scored_forecasts'] for row in decomposition.values())
    for row in decomposition.values():
        row['contribution_to_overall_mean_loss_difference']=row['loss_difference_sum_vs_native']/total
        row['mean_loss_difference_when_selected']=row['loss_difference_sum_vs_native']/row['scored_forecasts'] if row['scored_forecasts'] else None
    return {'schema':'nomad.adaptive-posthoc-diagnosis.v18','status':'COMPLETED_POSTHOC',
        'observed_at_utc':datetime.now(timezone.utc).isoformat(),'primary_result_sha256':sha(path),'diagnoser_sha256':sha(Path(__file__)),
        'scope':'descriptive decomposition after heldout; no parameter changes or new confirmatory tests',
        'mean_quality_and_cost':costs,'adaptive_selection_by_family':family_reports,
        'adaptive_exact_matches_to_selected_original_learner':dict(matches),
        'adaptive_forecast_selection_counts':dict(allcounts),'adaptive_measured_telemetry_totals':dict(timed),
        'loss_gap_vs_native_decomposition':decomposition,'scored_adaptive_forecasts':total,
        'memory_scope':'no-memory ablation removes selector utility history only; no cross-repository MNEMONIC benefit established',
        'native_rebuild_note':'native_observations_processed counts public prefix through last selected native step; native internal lag replay is additional measured work',
        'memory_cost_note':'native Job/process high-water counters; parent lifetime peak separate, no contemporaneous sum or strict peak claim',
        'interpretation':'when a mechanism is selected, lazy forecasting exactly matches that existing full-prefix learner; the measured quality gap comes from mechanism choices, not approximate native inference',
        'coding_advantage':'NOT_ESTABLISHED','parameters_retuned':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--result',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=diagnose(args.result);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'status':report['status'],'scored_adaptive_forecasts':report['scored_adaptive_forecasts'],
                      'exact_matches':report['adaptive_exact_matches_to_selected_original_learner']}))


if __name__=='__main__':main()
