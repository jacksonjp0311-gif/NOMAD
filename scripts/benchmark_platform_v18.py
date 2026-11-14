"""Frozen, matched native-BGR controls on preserved public execution traces.

This does not execute third-party repositories. Its ranking metric concerns only
the already observed candidates in a truncated historical trace, not fresh
repair success or causal learning gain. Freeze the plan before measuring it.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nomad.native_bitwork import action_for_family, load_native, logloss, verified_runtime_identity

MODES = ('cold', 'frequency', 'native', 'shuffled')
STUDY = ROOT / 'results/FRONTIER_STUDY_V014.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze() -> dict:
    return {'schema': 'nomad.platform.bitwork-plan.v1', 'seed': 18018,
            'source_path': 'results/FRONTIER_STUDY_V014.json', 'source_sha256': sha(STUDY),
            'native_identity': verified_runtime_identity(), 'training_split': 'training',
            'evaluation_split': 'cold', 'modes': list(MODES), 'repeats': 3,
            'budget_per_task': 12, 'evaluation_updates': False,
            'shuffled_control': 'permute training outcome labels with fixed seed; retain action sequence',
            'authority': 'historical_public_trace_replay_only'}


def _working_set_bytes() -> int | None:
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
              'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
              'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    info = Counters(); info.cb = ctypes.sizeof(info)
    return int(info.WorkingSetSize) if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(info), info.cb) else None


def _arm(mode: str, train: list, evaluation: list, seed: int, budget: int) -> dict:
    factory = load_native() if mode in ('native', 'shuffled') else None
    tracemalloc.start()
    started, cpu = time.perf_counter(), time.process_time()
    model = factory() if factory else None
    counts = [[1, 1], [1, 1]]
    labels = [int(t['public_pass']) for t in train]
    if mode == 'shuffled':
        random.Random(seed).shuffle(labels)
    for row, observed in zip(train, labels):
        action = action_for_family(row['edit_family'])
        if model is not None:
            model.predict(action)
            model.observe(action, observed)
        counts[action][observed] += 1
    if mode == 'cold': probabilities = (0.5, 0.5)
    elif model is not None: probabilities = tuple(float(copy.deepcopy(model).predict(a)) for a in (0, 1))
    else: probabilities = tuple(c[1] / sum(c) for c in counts)
    rows = []; losses = []; briers = []
    for task in evaluation:
        trace = task['trace']
        ordered = sorted(range(len(trace)), key=lambda i: (-probabilities[action_for_family(trace[i]['edit_family'])], i))
        for event in trace:
            p = probabilities[action_for_family(event['edit_family'])]; y = int(event['public_pass'])
            losses.append(logloss(p, y)); briers.append((p-y)**2)
        first = next((i for i, j in enumerate(ordered, 1) if trace[j]['public_pass']), None)
        rows.append({'task_id': task['id'], 'observed_candidates': len(trace),
                     'ordered_original_indices': ordered, 'first_public_pass_rank': first,
                     'public_pass_within_budget': first is not None and first <= budget,
                     'archived_witness_supported': task.get('witness', {}).get('supported'),
                     'fresh_repository_execution': False})
    wall = time.perf_counter() - started; cpu = time.process_time() - cpu
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    ranks = [row['first_public_pass_rank'] for row in rows if row['first_public_pass_rank'] is not None]
    return {'mode': mode, 'action_probabilities': probabilities,
            'mean_logloss': sum(losses)/len(losses), 'mean_brier': sum(briers)/len(briers),
            'public_events': len(losses), 'public_success_tasks': len(ranks),
            'mean_observed_public_success_rank': sum(ranks)/len(ranks) if ranks else None,
            'tasks': rows, 'wall_seconds': wall, 'cpu_seconds': cpu,
            'python_peak_allocated_bytes': peak, 'process_working_set_bytes_after': _working_set_bytes()}


def run(plan: dict) -> dict:
    if plan != freeze():
        raise ValueError('plan, input bytes, or preserved runtime differs from the frozen benchmark')
    data = json.loads(STUDY.read_text(encoding='utf-8'))
    train = [event for task in data['training'] for event in task['trace']]
    evaluation = data['cold']
    arms = {mode: [_arm(mode, train, evaluation, plan['seed'], plan['budget_per_task'])
                   for _ in range(plan['repeats'])] for mode in MODES}
    metrics = {}
    for mode, runs in arms.items():
        first = runs[0]
        metrics[mode] = {k: first[k] for k in ('action_probabilities', 'mean_logloss', 'mean_brier',
                        'public_events', 'public_success_tasks', 'mean_observed_public_success_rank', 'tasks')}
        metrics[mode].update({'mean_wall_seconds': sum(r['wall_seconds'] for r in runs)/len(runs),
                             'mean_cpu_seconds': sum(r['cpu_seconds'] for r in runs)/len(runs),
                             'max_python_peak_allocated_bytes': max(r['python_peak_allocated_bytes'] for r in runs),
                             'timing_repeats': [{k: r[k] for k in ('wall_seconds', 'cpu_seconds',
                                 'python_peak_allocated_bytes', 'process_working_set_bytes_after')} for r in runs]})
    return {'schema': 'nomad.platform.bitwork-benchmark.v1', 'plan': plan,
            'environment': {'python': sys.version, 'platform': platform.platform(), 'machine': platform.machine()},
            'training_tasks': len(data['training']), 'training_public_events': len(train),
            'evaluation_tasks': len(evaluation), 'metrics': metrics,
            'cost': {'cloud_calls': 0, 'api_cost_usd': 0, 'energy_joules': None,
                     'electricity_cost_usd': None, 'gpu_used': False,
                     'memory_scope': 'tracemalloc per arm; Windows working set sampled after arm, not isolated peak RSS'},
            'native_beats_frequency_logloss': metrics['native']['mean_logloss'] < metrics['frequency']['mean_logloss'],
            'external_repair_advantage': 'NOT_ESTABLISHED', 'learning_gate': 'HOLD',
            'limitations': ['Historical outcomes were already available before this new adapter was designed.',
                'Frozen historical replay is not a prospective heldout experiment.',
                'Candidate pools stop at prior policy outcomes and omit unexecuted repairs.',
                'Public pass ranking does not imply WITNESS or final correctness.',
                'The Catalogue false-positive remains a permanent independent-contract regression.',
                'No statistical significance, GPU, energy, or fresh repository repair claim is made.']}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, default=ROOT/'experiments/PLAN_BITWORK_V018.json')
    parser.add_argument('--output', type=Path, default=ROOT/'results/BITWORK_V018.json')
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    if args.freeze:
        if args.plan.exists(): raise ValueError('will not overwrite an existing frozen plan')
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.write_text(json.dumps(freeze(), indent=2, sort_keys=True)+'\n', encoding='utf-8')
        print(json.dumps({'plan': str(args.plan), 'sha256': sha(args.plan)}))
        return 0
    result = run(json.loads(args.plan.read_text(encoding='utf-8')))
    if args.output.exists(): raise ValueError('will not overwrite a previous benchmark result')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'learning_gate': result['learning_gate'],
                      'native_beats_frequency_logloss': result['native_beats_frequency_logloss'],
                      'metrics': {k: {field: v[field] for field in ('mean_logloss', 'mean_observed_public_success_rank',
                          'mean_wall_seconds', 'mean_cpu_seconds', 'max_python_peak_allocated_bytes')} for k, v in result['metrics'].items()}}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
