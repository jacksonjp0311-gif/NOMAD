"""Preregistered trusted binary-stream mechanism study; never repair efficacy.

The original vendored predictor is imported through its verified bridge. Every
model predicts before the next generated outcome. No downloaded code executes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nomad.native_bitwork import load_native, verified_runtime_identity, action_for_family

SCHEMA = 'nomad.frontier-bitwork-mechanisms.v18'
MODES = ('cold', 'frequency', 'native', 'native_no_lag', 'guarded_no_growth',
         'temporal', 'temporal_static')
EVALUATION_SEEDS = tuple(range(18180301, 18180309))
DEVELOPMENT_SEEDS = (18180101, 18180102)
FAMILIES = ('stationary', 'boolean_history', 'lag3', 'switch')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def source_identity():
    return {name: file_hash(ROOT/name) for name in
            ('scripts/frontier_bitwork_v18.py', 'nomad/native_bitwork.py',
             'vendor/BGR-v1.4.0-runtime/MANIFEST.sha256')}


def specification():
    return {'schema': SCHEMA+'.design', 'modes': list(MODES),
        'development_seeds': list(DEVELOPMENT_SEEDS), 'evaluation_seeds': list(EVALUATION_SEEDS),
        'families': list(FAMILIES), 'steps': 128, 'unscored_prefix': 32,
        'generator': {'actions': 'independent uniform binary random.Random(seed)',
            'stationary_probabilities': [0.1, 0.3], 'switch_probabilities': [0.8, 0.6],
            'switch_at': 64, 'flip_probability': 0.075, 'missing_history_bit': 0,
            'boolean_history': 'current_action XOR previous_observed_outcome',
            'lag3': 'current_action XOR action_three_steps_ago',
            'rng_schedule': 'one randrange(2), then one random() per step'},
        'information': 'same observed prefix and current action; no family/seed/future outcomes supplied to predictors',
        'updates': 'all models observe every outcome after all forecasts, including scored prequential segment',
        'parameters': {'native': 'unchanged GovernedBitworkV14 defaults',
            'native_no_lag': 'GovernedBitworkV14(checkpoints=())',
            'guarded_no_growth': 'ExactCompiledGuardedLearner(growth=False), no outer lag learner',
            'temporal': 'original GrammarEnsemble() defaults, without induced grammar or lag discovery',
            'temporal_static': 'original GrammarEnsemble(orders=(0,),retentions=(1.0,),share=0.0)',
            'frequency': 'action-conditional Beta(1,1) posterior mean', 'cold': 'constant 0.5'},
        'primary_contrasts': [
            ['stationary', 'frequency', 'native'],
            ['boolean_history', 'native_no_lag', 'frequency'],
            ['lag3', 'native', 'native_no_lag'],
            ['switch', 'temporal', 'frequency']],
        'primary_metric': 'mean scored prequential natural-log loss per independent seed stream',
        'test': 'one-sided exact paired sign test; lower log loss wins; Holm correction across four contrasts, alpha0.05',
        'secondary': ['Brier score', 'all paired module contrasts descriptive', 'native activation and promotion telemetry',
                      'per-model trusted controller wall and CPU time', 'whole-study Python allocation peak'],
        'budgets': {'observations_per_model_stream': 128, 'model_wall_seconds_per_stream': 60,
                    'equal_observation_budget': True, 'equal_operation_count': False,
                    'controller_hard_memory_cap': None},
        'limits': ['Designed synthetic distributions, not independently authored repository tasks.',
                   'Eight seeds per distribution are limited power; a negative result is retained.',
                   'No retuning or model selection from this evaluation; parameters are fixed original defaults.',
                   'No coding, autonomy, energy, GPU or economic advantage follows from these results.']}


def freeze(output):
    payload = {'schema': SCHEMA+'.plan', 'design': specification(), 'source_sha256': source_identity(),
               'native_identity': verified_runtime_identity(), 'evaluation_outcomes_generated': False,
               'python': sys.version, 'scope': 'trusted synthetic computational mechanism study'}
    document = {'payload': payload, 'sha256': digest(payload)}
    write_new(output, document)
    return document


def validate(document):
    payload = document.get('payload')
    if (not isinstance(payload, dict) or document.get('sha256') != digest(payload)
            or payload.get('schema') != SCHEMA+'.plan' or payload.get('design') != specification()
            or payload.get('source_sha256') != source_identity() or payload.get('python') != sys.version
            or payload.get('native_identity') != verified_runtime_identity()
            or payload.get('evaluation_outcomes_generated') is not False):
        raise ValueError('frozen study plan/code/runtime differs; do not reuse this evaluation')
    return payload


class CountPredictor:
    def __init__(self, cold=False):
        self.counts = [[1, 1], [1, 1]]
        self.cold = cold

    def predict(self, action):
        return 0.5 if self.cold else self.counts[action][1]/sum(self.counts[action])

    def observe(self, action, outcome):
        self.counts[action][outcome] += 1


def models():
    native = load_native()
    from bgr140.compiled import ExactCompiledGuardedLearner
    from bgr100.grammar import GrammarEnsemble
    return {'cold': CountPredictor(True), 'frequency': CountPredictor(),
            'native': native(), 'native_no_lag': native(checkpoints=()),
            'guarded_no_growth': ExactCompiledGuardedLearner(growth=False),
            'temporal': GrammarEnsemble(),
            'temporal_static': GrammarEnsemble(orders=(0,), retentions=(1.0,), share=0.0)}


def probability(model, action):
    value = model.predict(action)
    result = float(value.probability_one if hasattr(value, 'probability_one') else value)
    if not 0 < result < 1:
        raise ValueError('predictor returned an invalid probability')
    return result


def outcome(family, action, history, draw, design):
    """Generator-only rule. Predictors receive none of these arguments except action/history observations."""
    config = design['generator']
    if family in ('stationary', 'switch'):
        probabilities = config['switch_probabilities'] if family == 'switch' and len(history) >= config['switch_at'] else config['stationary_probabilities']
        return int(draw < probabilities[action])
    if family == 'boolean_history':
        bit = history[-1][1] if history else config['missing_history_bit']
    elif family == 'lag3':
        bit = history[-3][0] if len(history) >= 3 else config['missing_history_bit']
    else:
        raise ValueError('unknown frozen generator')
    return action ^ bit ^ int(draw < config['flip_probability'])


def loss(p, y):
    return -math.log(p if y else 1-p)


def stream(seed, family, design, *, development=False, preregistration=None):
    if not development:
        if preregistration is None or validate(preregistration)['design'] != design:
            raise ValueError('evaluation generation requires a valid frozen preregistration')
    allowed = DEVELOPMENT_SEEDS if development else EVALUATION_SEEDS
    if seed not in allowed or family not in FAMILIES:
        raise ValueError('unregistered stream or split')
    instances = models()
    costs = {name: {'wall_seconds': 0.0, 'cpu_seconds': 0.0} for name in MODES}
    history, trace = [], []
    rng = random.Random(seed)
    for step in range(design['steps']):
        action = rng.randrange(2)
        predictions = {}
        for name, model in instances.items():
            wall, cpu = time.perf_counter(), time.process_time()
            predictions[name] = probability(model, action)
            costs[name]['wall_seconds'] += time.perf_counter()-wall
            costs[name]['cpu_seconds'] += time.process_time()-cpu
        # Every forecast exists before the generator draws this outcome.
        observed = outcome(family, action, history, rng.random(), design)
        for name, model in instances.items():
            wall, cpu = time.perf_counter(), time.process_time()
            model.observe(action, observed)
            costs[name]['wall_seconds'] += time.perf_counter()-wall
            costs[name]['cpu_seconds'] += time.process_time()-cpu
            if costs[name]['wall_seconds'] > design['budgets']['model_wall_seconds_per_stream']:
                raise RuntimeError('registered per-model stream wall budget exhausted: '+name)
        history.append((action, observed))
        trace.append({'step': step, 'action': action, 'outcome': observed, 'probabilities': predictions})
    scored = trace[design['unscored_prefix']:]
    metrics = {name: {'mean_logloss': statistics.mean(loss(row['probabilities'][name], row['outcome']) for row in scored),
        'brier': statistics.mean((row['probabilities'][name]-row['outcome'])**2 for row in scored),
        'forecasts': len(trace), 'scored_forecasts': len(scored), **costs[name]} for name in MODES}
    snapshots = {name: model.snapshot() for name, model in instances.items() if hasattr(model, 'snapshot')}
    return {'seed': seed, 'family': family, 'metrics': metrics, 'trace': trace,
            'native_snapshot': snapshots['native'], 'model_snapshots': snapshots,
            'input_sha256': digest(history)}


def assess(rows, design):
    if {(row['family'], row['seed']) for row in rows} != {(f, s) for f in FAMILIES for s in EVALUATION_SEEDS} or len(rows) != len(FAMILIES)*len(EVALUATION_SEEDS):
        raise ValueError('missing or repeated independent stream')
    summary = {family: {mode: {key: statistics.mean(row['metrics'][mode][key] for row in rows if row['family'] == family)
        for key in ('mean_logloss', 'brier', 'wall_seconds', 'cpu_seconds')} for mode in MODES} for family in FAMILIES}
    contrasts = []
    for family, proposed, control in design['primary_contrasts']:
        differences = [row['metrics'][proposed]['mean_logloss']-row['metrics'][control]['mean_logloss'] for row in rows if row['family'] == family]
        wins = sum(d < -1e-12 for d in differences); losses = sum(d > 1e-12 for d in differences)
        n = wins+losses
        p = sum(math.comb(n, i) for i in range(wins, n+1))/2**n if n else 1.0
        contrasts.append({'family': family, 'proposed': proposed, 'control': control,
            'mean_proposed_minus_control_logloss': statistics.mean(differences), 'per_seed_differences': differences,
            'wins': wins, 'losses': losses, 'ties': len(differences)-n, 'p_one_sided': p})
    rejecting = True
    for index, row in enumerate(sorted(contrasts, key=lambda item: item['p_one_sided'])):
        row['holm_threshold'] = 0.05/(len(contrasts)-index)
        row['significant'] = rejecting and row['p_one_sided'] <= row['holm_threshold']
        rejecting = row['significant']
    return {'means': summary, 'registered_contrasts': contrasts,
            'interpretation': 'bounded synthetic mechanism evidence only', 'coding_advantage': 'NOT_ESTABLISHED'}


def run(document, output):
    payload = validate(document)
    output = Path(output)
    if output.exists():
        raise FileExistsError('never overwrite study results')
    started = output.with_name(output.stem+'.STARTED.json')
    write_new(started, {'schema': SCHEMA+'.started', 'plan_sha256': document['sha256'],
                        'evaluation_outcomes_generated': False, 'source_sha256': source_identity()})
    report = {'schema': SCHEMA+'.result', 'plan_sha256': document['sha256'],
        'started_receipt_sha256': file_hash(started), 'status': 'STARTED', 'streams': [],
        'scope': 'trusted computational streams, not repository repair',
        'cloud_calls': 0, 'energy_joules': None, 'gpu_measurement': None,
        'api_cost_usd': 0, 'coding_advantage': 'NOT_ESTABLISHED'}
    wall, cpu = time.perf_counter(), time.process_time()
    tracemalloc.start()
    try:
        for family in FAMILIES:
            for seed in EVALUATION_SEEDS:
                report['active_stream'] = {'family': family, 'seed': seed}
                row = stream(seed, family, payload['design'], preregistration=document)
                report['streams'].append(row)
                print(json.dumps({'family': family, 'seed': seed, 'completed_streams': len(report['streams'])}), flush=True)
        report['assessment'] = assess(report['streams'], payload['design'])
        if source_identity() != payload['source_sha256']:
            raise ValueError('study source changed during evaluation')
        verified_runtime_identity()
        report['status'] = 'COMPLETED'
        report.pop('active_stream', None)
    except Exception as error:
        report['status'] = 'INCOMPLETE_HOLD'
        report['reason'] = type(error).__name__+': '+str(error)
    finally:
        report['peak_python_allocated_bytes_all_models'] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    report['wall_seconds'] = time.perf_counter()-wall
    report['controller_cpu_seconds'] = time.process_time()-cpu
    report['cost_scope'] = 'per-model prediction+observation; whole-study wall/CPU includes orchestration, verified imports and tracemalloc, excludes final JSON serialization; no equal CPU-work claim'
    write_new(output, report)
    return report


def diagnose():
    """Posthoc computational interventions on already public frozen evidence."""
    study = json.loads((ROOT/'results/FRONTIER_STUDY_V014.json').read_bytes())
    frozen = json.loads((ROOT/'results/BITWORK_V018.json').read_bytes())
    if file_hash(ROOT/'results/FRONTIER_STUDY_V014.json') != frozen['plan']['source_sha256']:
        raise ValueError('historical study changed')
    instances = models()
    rows = [(action_for_family(event['edit_family']), int(event['public_pass'])) for task in study['training'] for event in task['trace']]
    for action, y in rows:
        for model in instances.values():
            probability(model, action); model.observe(action, y)
    native = instances['native']
    decomposition = []
    predictions = {mode: [probability(copy.deepcopy(model), a) for a in (0, 1)] for mode, model in instances.items()}
    for a in (0, 1):
        bank = copy.deepcopy(native.base.base).predict(a)
        grammar = probability(copy.deepcopy(native.base.discovered), a)
        frequency = predictions['frequency'][a]
        static = predictions['temporal_static'][a]
        wg = native.base.weight[1]
        temporal_terms = [{'expert': name, 'weight': weight, 'probability': p,
                          'weighted_lift_above_static': weight*(p-static)}
                         for name, weight, p in zip(bank.grammar_names, bank.grammar_weights, bank.expert_probabilities)]
        terms = {'KT_prior_minus_Laplace': static-frequency,
                 'temporal_expert_bank_minus_static': bank.probability_one-static,
                 'induced_grammar_mixture_lift': wg*(grammar-bank.probability_one)}
        reconstructed = frequency+sum(terms.values())
        expected = frozen['metrics']['native']['action_probabilities'][a]
        if not math.isclose(reconstructed, expected, abs_tol=1e-12) or not math.isclose(predictions['native'][a], expected, abs_tol=1e-12):
            raise ValueError('native decomposition does not reconstruct frozen forecast')
        decomposition.append({'action': a, 'frequency': frequency, 'static_KT': static,
            'expert_bank': bank.probability_one, 'induced_grammar': grammar,
            'grammar_mixture_weight': wg, 'additive_probability_contributions': terms,
            'temporal_experts': temporal_terms, 'reconstructed_native': reconstructed})
    evaluation = [(action_for_family(e['edit_family']), int(e['public_pass'])) for task in study['cold'] for e in task['trace']]
    return {'schema': SCHEMA+'.historical-mechanism-diagnosis', 'posthoc': True,
        'historical_results_modified': False, 'retuning_performed': False,
        'source_sha256': source_identity(), 'native_identity': verified_runtime_identity(),
        'input_sha256': {name: file_hash(ROOT/name) for name in ('results/BITWORK_V018.json', 'results/FRONTIER_STUDY_V014.json')},
        'native_snapshot': native.snapshot(), 'training_events': len(rows),
        'lag_discovery_could_contribute': native.lags is not None,
        'first_original_lag_checkpoint': min(native.checkpoints), 'decomposition': decomposition,
        'interventions': {mode: {'action_probabilities': p,
            'frozen_evaluation_logloss': statistics.mean(loss(p[a], y) for a, y in evaluation)} for mode, p in predictions.items()},
        'scope': 'exact computational attribution and module interventions for this observed prefix; no causal attribution to real repository repair',
        'coding_advantage': 'NOT_ESTABLISHED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('freeze', 'diagnose'):
        child = sub.add_parser(name); child.add_argument('--output', type=Path, required=True)
    child = sub.add_parser('run'); child.add_argument('--plan', type=Path, required=True); child.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == 'freeze':
        result = freeze(args.output); print(json.dumps({'plan_sha256': result['sha256']})); return 0
    if args.action == 'diagnose':
        result = diagnose(); write_new(args.output, result); print(json.dumps({'training_events': result['training_events'], 'lag_discovery_could_contribute': result['lag_discovery_could_contribute']})); return 0
    result = run(json.loads(args.plan.read_bytes()), args.output)
    print(json.dumps({'status': result['status'], 'streams': len(result['streams']), 'coding_advantage': 'NOT_ESTABLISHED'}))
    return 0 if result['status'] == 'COMPLETED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
