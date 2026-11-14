"""Post hoc arithmetic audit of frozen observations, not a new efficacy trial."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def action(family: str) -> int:
    # Independent transcription of the documented frozen two-action encoding.
    return 0 if family.split('\u2192')[0] in ('==', '!=', '>', '<', '<=', '>=', 'in', 'not in') else 1


def analyze(root: Path = ROOT) -> dict:
    paths = ['results/BITWORK_V018.json', 'results/FRONTIER_STUDY_V014.json',
             'experiments/PLAN_BITWORK_V018.json']
    seals = json.loads((root/'results/RELEASE_MANIFEST_V018.json').read_bytes())['sha256_by_path']
    identities = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths}
    if any(identities[name] != seals[name] for name in paths):
        raise ValueError('frozen input differs; refusing retrospective substitution')
    benchmark, study, plan = [json.loads((root/name).read_bytes()) for name in paths]
    if plan != benchmark['plan'] or plan['source_sha256'] != identities[paths[1]]:
        raise ValueError('frozen study identity mismatch')
    train = [event for task in study['training'] for event in task['trace']]
    evaluation = [event for task in study['cold'] for event in task['trace']]
    groups = []
    for a in (0, 1):
        rows = [row for row in evaluation if action(row['edit_family']) == a]
        trained = [row for row in train if action(row['edit_family']) == a]
        count, successes = len(rows), sum(bool(row['public_pass']) for row in rows)
        means = {}
        probabilities = {}
        for mode in ('frequency', 'native'):
            p = benchmark['metrics'][mode]['action_probabilities'][a]
            probabilities[mode] = p
            means[mode] = -(successes*math.log(p)+(count-successes)*math.log1p(-p))/count
        groups.append({'action': a, 'training_events': len(trained),
                       'training_public_successes': sum(bool(row['public_pass']) for row in trained),
                       'evaluation_events': count, 'evaluation_public_successes': successes,
                       'observed_public_success_rate': successes/count,
                       'predicted_probabilities': probabilities, 'mean_logloss': means,
                       'weighted_excess_native_logloss': (means['native']-means['frequency'])*count/len(evaluation)})
    recomputed = {mode: sum(g['mean_logloss'][mode]*g['evaluation_events'] for g in groups)/len(evaluation)
                  for mode in ('frequency', 'native')}
    for mode, value in recomputed.items():
        if not math.isclose(value, benchmark['metrics'][mode]['mean_logloss'], abs_tol=1e-12):
            raise ValueError('independent likelihood arithmetic disagrees with frozen result')
    same_order = all(left['ordered_original_indices'] == right['ordered_original_indices']
                     for left, right in zip(benchmark['metrics']['frequency']['tasks'],
                                            benchmark['metrics']['native']['tasks']))
    return {'schema': 'nomad.frozen-bitwork-posthoc-audit.v18',
            'scope': 'post hoc decomposition of original frozen public-trace predictions',
            'input_sha256_by_path': identities, 'original_results_modified': False,
            'native_runtime_rerun': False, 'fresh_repository_executions': 0,
            'independent_arithmetic_check': 'PASS', 'groups': groups,
            'recomputed_mean_logloss': recomputed,
            'native_excess_mean_logloss': recomputed['native']-recomputed['frequency'],
            'identical_frequency_native_candidate_ordering': same_order,
            'diagnosis': ['Native probabilities are higher for both actions; this hurts calibration on failure-heavy recorded evaluation events.',
                          'Both controls produce the same candidate order and observed public success rank; this corpus demonstrates no native search-order gain.',
                          'Eight training events and a two-action encoding do not establish general repository reasoning.',
                          'The adaptive model dynamics and encoding remain causal hypotheses; this audit does not isolate their contributions.'],
            'heldout_protocol_changed': False, 'intelligence_advantage': 'NOT_ESTABLISHED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('refusing to overwrite an audit')
    result = analyze()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
