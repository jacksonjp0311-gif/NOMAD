"""Read-only decomposition of frozen whole-worker cost evidence."""
from pathlib import Path
import hashlib
import json
import statistics


def summarize(source):
    data = json.loads(source.read_bytes())
    assert data['status'] == 'COMPLETED' and data['source_stable']
    assert len(data['trials']) == 576
    means = {}
    for mode in sorted({row['mode'] for row in data['trials']}):
        rows = [row for row in data['trials'] if row['mode'] == mode]
        def averages(key):
            keys = sorted({name for row in rows for name in row.get(key, {})
                           if type(row[key][name]) in (int, float)})
            return {name: statistics.fmean(row.get(key, {}).get(name, 0) for row in rows) for name in keys}
        means[mode] = {
            'trials': len(rows), 'whole_worker': averages('cost'),
            'worker_scopes': averages('worker_cost'),
            'controller_stage_scopes': averages('telemetry'),
            'fixed_predictor_scopes': averages('fixed_predictor_cost'),
            'mean_state_storage_bytes': statistics.fmean(row['final_state_bytes'] for row in rows),
            'maximum_state_storage_bytes': max(row['final_state_bytes'] for row in rows),
            'maximum_worker_working_set_bytes': max(row['worker_memory']['peak_working_set_bytes'] for row in rows),
            'maximum_job_peak_counter_bytes': max(row['cost']['native_peak_counter_bytes'] for row in rows),
        }
    report = {
        'schema': 'nomad.temporal-cost-accounting.v18', 'status': 'DESCRIPTIVE_COMPLETE',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'modes': means,
        'whole_study_cpu_seconds': data['whole_study_cpu_seconds'],
        'harness_cpu_seconds': data['harness_cpu_seconds'],
        'unallocated_harness_cpu_seconds': data['unallocated_harness_cpu_seconds'],
        'whole_study_wall_seconds': data['harness_wall_seconds'],
        'parent_memory_before': data['parent_memory_before'],
        'parent_memory_after': data['parent_memory_after'],
        'scope': {
            'primary_cost': 'Job user+kernel CPU plus supervisor CPU; includes inactive learner work, allocation, eviction, startup, source checks, transport and checkpoint I/O',
            'nested_scopes': 'worker loop includes checkpoint; controller scopes are diagnostics within whole worker, never additive to it',
            'original_controller': 'telemetry resets on restore; original telemetry_segments retain both segments, final telemetry alone is incomplete',
            'allocator_attribution': 'allocation and deallocation are included in process totals, not separately traced or attributed to each object',
            'eviction_attribution': 'event counts retained; no independent eviction-only stopwatch',
            'serialization': 'surrounding checkpoint includes encode, publication, parse and restore; inner serialization scope is a subset',
            'memory': 'process working-set and Job peak counters are separate nonadditive measures; strict committed-memory peak remains HOLD',
            'cpu_ceiling': 'equal 60-second wall/512MiB/four-process Jobs; CPU measured without a separate hard CPU-time kill limit',
            'outside_timer': 'final parent result JSON encoding/publication excluded from study timer',
            'unmeasured': 'energy, GPU and monetary costs',
        },
    }
    return report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('preserve accounting evidence')
    report=summarize(args.result)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as output:
        json.dump(report,output,sort_keys=True,indent=2);output.write('\n')
    print(json.dumps({'status':report['status'],'whole_study_cpu_seconds':report['whole_study_cpu_seconds']}))
