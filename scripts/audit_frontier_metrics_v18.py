"""Independent arithmetic audit of frozen forecast traces; imports no learner."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(plan_path, result_path):
    plan = json.loads(plan_path.read_bytes())
    result = json.loads(result_path.read_bytes())
    encoded = json.dumps(plan['payload'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if hashlib.sha256(encoded).hexdigest() != plan['sha256'] or result['plan_sha256'] != plan['sha256']:
        raise ValueError('plan/result identity mismatch')
    design = plan['payload']['design']
    expected = {(f, s) for f in design['families'] for s in design['evaluation_seeds']}
    measured = {}
    forecasts = 0
    for stream in result['streams']:
        key = stream['family'], stream['seed']
        if key not in expected or key in measured:
            raise ValueError('missing, duplicate or unregistered stream')
        trace = stream['trace']
        if len(trace) != design['steps'] or [r['step'] for r in trace] != list(range(design['steps'])):
            raise ValueError('incomplete temporal trace')
        measured[key] = {}
        for mode in design['modes']:
            losses, squared = [], []
            for row in trace:
                p, y = row['probabilities'][mode], row['outcome']
                if type(y) is not int or y not in (0, 1) or not 0 < p < 1 or not math.isfinite(p):
                    raise ValueError('invalid Bernoulli trace')
                if row['step'] >= design['unscored_prefix']:
                    losses.append(-math.log(p if y else 1-p))
                    squared.append((p-y)**2)
            values = {'mean_logloss': fmean(losses), 'brier': fmean(squared)}
            for name, value in values.items():
                if not math.isclose(value, stream['metrics'][mode][name], rel_tol=0, abs_tol=1e-12):
                    raise ValueError('stored metric differs from raw forecasts')
            measured[key][mode] = values
            forecasts += len(losses)
    if set(measured) != expected:
        raise ValueError('unregistered stream inventory')
    for family in design['families']:
        for mode in design['modes']:
            for metric in ('mean_logloss', 'brier'):
                mean = fmean(v[mode][metric] for (f, _), v in measured.items() if f == family)
                if not math.isclose(mean, result['assessment']['means'][family][mode][metric], abs_tol=1e-12):
                    raise ValueError('aggregate differs from independent stream arithmetic')
    contrasts = []
    for family, proposed, control in design['primary_contrasts']:
        delta = [v[proposed]['mean_logloss']-v[control]['mean_logloss']
                 for (f, _), v in measured.items() if f == family]
        wins = sum(d < -1e-12 for d in delta)
        losses = sum(d > 1e-12 for d in delta)
        n = wins+losses
        p = sum(math.comb(n, k) for k in range(wins, n+1))/2**n if n else 1.0
        contrasts.append({'family': family, 'proposed': proposed, 'control': control,
                          'wins': wins, 'losses': losses, 'p_one_sided': p})
    prior = True
    for index, row in enumerate(sorted(contrasts, key=lambda c: c['p_one_sided'])):
        row['holm_threshold'] = .05/(len(contrasts)-index)
        row['significant'] = prior and row['p_one_sided'] <= row['holm_threshold']
        prior = row['significant']
    for actual, stored in zip(contrasts, result['assessment']['registered_contrasts'], strict=True):
        if any(stored[key] != value for key, value in actual.items()):
            raise ValueError('registered contrast or Holm decision differs')
    return {'schema': 'nomad.frontier-independent-arithmetic.v18', 'status': 'PASS',
            'plan_file_sha256': sha(plan_path), 'result_file_sha256': sha(result_path),
            'auditor_sha256': sha(Path(__file__)), 'independent_streams': len(measured),
            'scored_model_forecasts_checked': forecasts, 'contrasts': contrasts,
            'scope': 'recomputed trace arithmetic, aggregation and multiplicity; not independent task outcomes or proof of execution order',
            'coding_advantage': 'NOT_ESTABLISHED'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT/'experiments/PLAN_FRONTIER_BITWORK_MECHANISMS_V018.json')
    parser.add_argument('--result', type=Path, default=ROOT/'results/FRONTIER_BITWORK_MECHANISMS_V018.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('preserve existing evidence; choose a new output')
    record = audit(args.plan, args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps(record))
