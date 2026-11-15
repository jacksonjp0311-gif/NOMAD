"""Descriptive decomposition of retained temporal study; no learner execution."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


def summarize(path):
    source=Path(path); data=json.loads(source.read_bytes())
    if data.get('status')!='COMPLETED': raise ValueError('complete evidence required')
    modes=sorted({row['mode'] for row in data['trials']}); result={}
    for mode in modes:
        rows=[r for r in data['trials'] if r['mode']==mode]
        selected=Counter(e['mechanism'] for r in rows for e in r['trace'])
        result[mode]={'trials':len(rows),
            **{key:statistics.fmean(r['metrics'][key] for r in rows) for key in ('mean_logloss','brier','ece10')},
            'mean_total_cpu_seconds':statistics.fmean(r['cost']['total_cpu_seconds'] for r in rows),
            'mean_wall_seconds':statistics.fmean(r['cost']['whole_wall_seconds'] for r in rows),
            'max_worker_working_set_bytes':max(r['worker_memory']['peak_working_set_bytes'] for r in rows),
            'max_job_peak_counter_bytes':max(r['cost']['native_peak_counter_bytes'] for r in rows),
            'mean_state_bytes':statistics.fmean(r['final_state_bytes'] for r in rows),
            'max_state_bytes':max(r['final_state_bytes'] for r in rows),
            'mean_switches':statistics.fmean(r['switches'] for r in rows),
            'selected_forecasts':dict(selected),
            'mean_checkpoint_cpu_seconds':statistics.fmean(sum(c['cpu_seconds'] for c in r['checkpoints']) for r in rows),
            'mean_checkpoint_wall_seconds':statistics.fmean(sum(c['wall_seconds'] for c in r['checkpoints']) for r in rows),
            'mean_final_state_cpu_seconds':statistics.fmean(r['worker_cost']['final_state_cpu_seconds'] for r in rows),
            'mean_final_state_wall_seconds':statistics.fmean(r['worker_cost']['final_state_wall_seconds'] for r in rows),
            'mean_telemetry':{k:statistics.fmean(r['telemetry'].get(k,0) for r in rows)
                              for k in sorted({k for r in rows for k in r['telemetry']})},
            'detector':{f:{'alarms':sum(len(r['detector_metrics']['alarm_prefixes']) for r in rows if r['family']==f),
                'false_alarms':sum(r['detector_metrics']['false_alarms'] for r in rows if r['family']==f),
                'known_changes':sum(len(r['detector_metrics']['known_change_boundaries']) for r in rows if r['family']==f),
                'detected':sum(r['detector_metrics']['detected_changes'] for r in rows if r['family']==f),
                'detected_delays':[v for r in rows if r['family']==f for v in r['detector_metrics']['delays'] if v is not None]}
                for f in sorted({r['family'] for r in rows})}}
    return {'schema':'nomad.temporal-descriptive-summary.v18','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'status':'DESCRIPTIVE_COMPLETE','modes':result,'assessment':data.get('assessment'),
        'whole_study_cpu_seconds':data['whole_study_cpu_seconds'],'whole_study_wall_seconds':data['harness_wall_seconds'],
        'parent_memory':data['parent_memory_after'],
        'limits':'stage timers overlap inclusive totals; original adaptive telemetry resets on restore, see retained telemetry_segments; no summed peak memory, causal ablation, energy, coding or transfer claim'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    if args.output.exists(): raise FileExistsError('preserve summary')
    report=summarize(args.result); args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as out:
        json.dump(report,out,sort_keys=True,indent=2); out.write('\n')
    print(json.dumps({'status':report['status'],'modes':{m:{k:v for k,v in row.items()
        if k in ('mean_logloss','mean_total_cpu_seconds','mean_wall_seconds')} for m,row in report['modes'].items()}}))
