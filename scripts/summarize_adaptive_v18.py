"""Descriptive summaries from frozen observations; never tunes a predictor."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics


def summarize(path):
    result=json.loads(path.read_bytes())
    if result['status']!='COMPLETED': raise ValueError('complete retained experiment required')
    groups={m:[t for t in result['trials'] if t['mode']==m] for m in sorted({t['mode'] for t in result['trials']})}
    rows={}
    for mode,trials in groups.items():
        rows[mode]={key:statistics.mean(t['metrics'][key] for t in trials) for key in ('mean_logloss','brier','ece10')}
        rows[mode].update({key:statistics.mean(t['cost'][key] for t in trials)
            for key in ('total_cpu_seconds','whole_wall_seconds','whole_job_cpu_seconds','supervisor_cpu_seconds')})
        rows[mode].update(trials=len(trials),
            max_reported_job_peak_bytes=max(t['cost']['native_peak_counter_bytes'] for t in trials),
            max_worker_peak_working_set_bytes=max(t['worker_memory']['peak_working_set_bytes'] for t in trials),
            mean_worker_algorithm_cpu_seconds=statistics.mean(t['worker_cost']['algorithm_cpu_seconds'] for t in trials),
            selected_forecasts=dict(collections.Counter(e['mechanism'] for t in trials for e in t['trace'])),
            mean_telemetry={k:statistics.mean(t['telemetry'][k] for t in trials) for k in trials[0]['telemetry']})
    families={f:{m:statistics.mean(t['metrics']['mean_logloss'] for t in groups[m] if t['family']==f)
                   for m in ('frequency','native','temporal','adaptive')}
              for f in result['assessment']['family_quality_means_descriptive']}
    selections={f:dict(collections.Counter(e['mechanism'] for t in groups['adaptive'] if t['family']==f for e in t['trace'])) for f in families}
    return {'schema':'nomad.adaptive-descriptive-summary.v18','scope':'posthoc descriptive summaries; no policy change or new confirmatory test',
        'result_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'modes':rows,'family_logloss':families,
        'adaptive_forecast_mechanisms_by_family':selections,
        'adaptive_cpu_percent_less_than_native':100*(1-rows['adaptive']['total_cpu_seconds']/rows['native']['total_cpu_seconds']),
        'primary_wall_seconds':result['harness_wall_seconds'],'primary_total_cpu_seconds':result['whole_study_cpu_seconds'],
        'parent_memory_after':result['parent_memory_after'],
        'memory_scope':'reported worker Job/working-set and parent peaks separately; not additive or strict simultaneous peak',
        'all_registered_joint_comparisons_passed':all(c['registered_quality_cost_criterion_passed'] for c in result['assessment']['comparisons'].values()),
        'coding_transfer':'NOT_ESTABLISHED'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError('preserve existing summary')
    report=summarize(args.result)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'modes':len(report['modes']),'registered_joint_success':report['all_registered_joint_comparisons_passed']}))


if __name__=='__main__': main()
