"""Bounded persistent computation over the unchanged frequency/temporal/BGR learners.

JSON checkpoints are local integrity records, not authenticated evidence. Only
the concrete classes below can be restored. No serialized code is evaluated.
Selection uses observed public losses and fixed costs; clocks are diagnostic.
"""
from __future__ import annotations

from collections import deque
import copy
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

from .adaptive import FrequencyPredictor, MECHANISMS, make_predictor, probability
from .native_bitwork import logloss, verified_runtime_identity

SCHEMA = 'nomad.persistent-controller.v18.1'
PREDICTOR_SCHEMA = 'nomad.persistent-predictor.v18.1'
MAX_BYTES = 16 * 1024 * 1024
MAX_HISTORY = 2048


class StateRefused(ValueError):
    """An untrusted or ineligible checkpoint must not acquire authority."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def prefix_digest(history):
    return digest([list(row) for row in history])


def source_identity():
    root = Path(__file__).resolve().parents[1]
    paths = ('nomad/persistent.py', 'nomad/adaptive.py', 'nomad/native_bitwork.py')
    return {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}


def _runtime_identity():
    return {**verified_runtime_identity(), 'python_version': list(sys.version_info[:3]),
            'python_implementation': sys.implementation.name,
            'python_cache_tag': sys.implementation.cache_tag}


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _integer(value, low=0, high=MAX_HISTORY):
    if type(value) is not int or not low <= value <= high:
        raise StateRefused('integer outside registered bound')
    return value


def _number(value, low=-1e12, high=1e12):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise StateRefused('finite number outside registered bound')
    return value


def _history(rows, width=2):
    if type(rows) is not list or len(rows) > MAX_HISTORY:
        raise StateRefused('history bound')
    for row in rows:
        if type(row) not in (list, tuple) or len(row) != width:
            raise StateRefused('history row shape')
        _integer(row[0], 0, 1); _integer(row[1], 0, 1)
        if width == 3: _number(row[2], 0, 1)


# Deliberately finite registry. Serialized names never become import targets.
_FIELDS = {
    'FrequencyPredictor': 'counts',
    'BackoffKT': 'backoff_strength evidence history order retention step tables',
    'GrammarEnsemble': 'cumulative_loss expert_cumulative_losses history last models prior share specs telemetry weights',
    'ExactCompiledGuardedLearner': 'base base_loss discovered history induced_loss last loss prior share telemetry weight',
    'GovernedBitworkV14': 'base checkpoints gate_events history lags last loss losses max_replay prior promote_gain public_certifications telemetry threshold weight',
    'ExactCompiledGrammarSynthesizer': '_approx_scores _epoch_lut _exact_scores _exact_terms _rank_cache atoms beam complexity contexts cost execution_cost expansions forgetting growth growth_every history mass0 mass1 max_depth max_pool max_size noise outputs pending pool proposals_tested telemetry tie_tolerance',
    'PackedLagFeatureLearner': 'awaiting_validation features forgetting history max_cache_entries max_terms min_history noise packed_cost pending programs promote_gain promotions proposal_period proposal_traces telemetry validation_fraction',
    'Expression': 'code depth operator signature size',
    'XorProgram': 'features phase',
}
_CONSTANTS = {
    'BackoffKT': {'backoff_strength': 2.0},
    'GrammarEnsemble': {'share': .025, 'specs': tuple((o, r) for o in (0, 1, 2, 3) for r in (1., .82))},
    'ExactCompiledGuardedLearner': {'prior': (.75, .25), 'share': .03},
    'GovernedBitworkV14': {'threshold': .66, 'checkpoints': frozenset((24, 30, 36, 48, 60)),
                         'max_replay': 100, 'promote_gain': .5, 'prior': (.8, .2), 'public_certifications': 0},
    'ExactCompiledGrammarSynthesizer': {'growth': True, 'beam': 20, 'max_pool': 105, 'growth_every': 5,
        'max_depth': 4, 'max_size': 13, 'forgetting': .975, 'noise': .075, 'complexity': .55, 'tie_tolerance': 1e-8},
    'PackedLagFeatureLearner': {'proposal_period': 12, 'min_history': 36, 'validation_fraction': .30,
        'promote_gain': .5, 'noise': .075, 'max_terms': 3, 'forgetting': .985, 'max_cache_entries': 4096},
}
_COUNTERS = {
    'GrammarEnsemble': {'telemetry': 'forecasts observations grammar_weight_updates backoff_context_reads abstained_public_certificates'},
    'ExactCompiledGuardedLearner': {'telemetry': 'forecasts observations hedge_updates public_certifications'},
    'GovernedBitworkV14': {'telemetry': 'monitor_evaluations lag_live_steps lag_replay_steps lag_activation fallback_due_budget public_certifications lag_trigger_reason'},
    'ExactCompiledGrammarSynthesizer': {
        'telemetry': 'forecasts observations candidate_scoring_calls candidate_signature_checks compositions_attempted unique_proposals structural_promotions high_confidence_public_certificates',
        'cost': 'lut_compilations compiled_candidate_evaluations near_tie_exact_evaluations forecast_exact_evaluations ranking_events compositions_attempted',
        'execution_cost': 'exact_score_requests exact_score_computations exact_score_cache_hits context_term_compilations ranking_score_reads peak_exact_cache_entries evidence_epochs'},
    'PackedLagFeatureLearner': {
        'telemetry': 'proposals_evaluated validation_program_evals prediction_program_evals public_certifications deferred_proposals deferred_rejections',
        'packed_cost': 'history_compilations historical_score_evaluations historical_score_cache_hits packed_validation_evaluations scalar_fallbacks peak_score_cache_entries'},
}


def _registry():
    # make_predictor verifies the original manifest before any vendor import.
    from .native_bitwork import load_native
    native = load_native()
    from bgr100.grammar import BackoffKT, GrammarEnsemble
    from bgr110.synthesis import Expression
    from bgr120.lag_discovery import XorProgram
    from bgr140.compiled import ExactCompiledGuardedLearner, ExactCompiledGrammarSynthesizer
    from bgr140.lag import PackedLagFeatureLearner
    return {c.__name__: c for c in (FrequencyPredictor, BackoffKT, GrammarEnsemble, Expression,
        XorProgram, ExactCompiledGuardedLearner, ExactCompiledGrammarSynthesizer, PackedLagFeatureLearner, native)}


def _validate_object(value, name):
    attrs = vars(value)
    expected = set(_FIELDS[name].split()) | ({'_packed_epoch'} if name == 'PackedLagFeatureLearner' else set())
    if set(attrs) != expected: raise StateRefused('unknown/missing concrete learner field')
    for key in ('last', 'pending'):
        if attrs.get(key) is not None: raise StateRefused('pending learner cannot be checkpointed')
    for key, expected_value in _CONSTANTS.get(name, {}).items():
        if attrs[key] != expected_value or type(attrs[key]) is not type(expected_value):
            raise StateRefused('unregistered learner configuration: ' + key)
    for field_name, keys in _COUNTERS.get(name,{}).items():
        counters = attrs[field_name]
        if type(counters) is not dict or set(counters) != set(keys.split()): raise StateRefused('native counter schema')
        for key,item in counters.items():
            if key == 'lag_trigger_reason':
                if item != 'rolling predictive surprise on compiled v1.1 base': raise StateRefused('native gate identity')
            else: _integer(item,0,10**12)
    for key in ('loss','base_loss','induced_loss','cumulative_loss'):
        if key in attrs: _number(attrs[key],0,1e12)
    if 'history' in attrs: _history(attrs['history'], 3 if name == 'GovernedBitworkV14' else 2)
    if name == 'FrequencyPredictor':
        if type(value.counts) is not list or len(value.counts) != 2: raise StateRefused('frequency counts')
        for row in value.counts:
            if type(row) is not list or len(row) != 2: raise StateRefused('frequency count row')
            for n in row: _integer(n, 1, MAX_HISTORY + 1)
    elif name == 'BackoffKT':
        _integer(value.order, 0, 3)
        if type(value.retention) is not float or value.retention not in (1., .82): raise StateRefused('retention')
        if value.step != len(value.history) or value.evidence != value.history: raise StateRefused('KT history mismatch')
        if type(value.tables) is not list or len(value.tables) != value.order + 1: raise StateRefused('KT tables')
        for level, table in enumerate(value.tables):
            if type(table) is not dict or len(table) > sum(2 ** (2 * k + 1) for k in range(level+1)): raise StateRefused('KT table bound')
            for key, row in table.items():
                if type(key) is not tuple or len(key) % 2 != 1 or len(key) > 2 * level + 1: raise StateRefused('KT context')
                for bit in key: _integer(bit, 0, 1)
                if type(row) is not tuple or len(row) != 3: raise StateRefused('KT count shape')
                _number(row[0], 0, MAX_HISTORY); _number(row[1], 0, MAX_HISTORY); _integer(row[2], 0, value.step)
    elif name == 'GrammarEnsemble':
        if len(value.models) != 8 or any(type(m).__name__ != 'BackoffKT' for m in value.models): raise StateRefused('expert bank')
        if any(m.history != value.history or (m.order, m.retention) != spec for m, spec in zip(value.models, value.specs)):
            raise StateRefused('expert prefix/config mismatch')
        for seq in (value.weights, value.prior):
            if len(seq) != 8 or abs(sum(seq)-1) > 1e-8 or any(x <= 0 for x in seq): raise StateRefused('expert mixture')
        if len(value.expert_cumulative_losses) != 8: raise StateRefused('expert losses')
        for loss in value.expert_cumulative_losses: _number(loss,0,1e12)
    elif name in ('GovernedBitworkV14', 'ExactCompiledGuardedLearner'):
        if len(value.weight) != 2 or abs(sum(value.weight)-1) > 1e-8 or any(x <= 0 for x in value.weight): raise StateRefused('mixture weights')
        if name == 'GovernedBitworkV14':
            if type(value.base).__name__ != 'ExactCompiledGuardedLearner' or type(value.lags).__name__ not in ('NoneType', 'PackedLagFeatureLearner'):
                raise StateRefused('native sublearner type')
            if value.base.history != [(a, y) for a, y, _ in value.history]: raise StateRefused('native base prefix')
            if value.lags is not None and value.lags.history != value.base.history: raise StateRefused('lag prefix')
            if not isinstance(value.losses, deque) or value.losses.maxlen != 24: raise StateRefused('surprise window')
            for loss in value.losses: _number(loss,0,100)
        elif type(value.base).__name__ != 'GrammarEnsemble' or type(value.discovered).__name__ != 'ExactCompiledGrammarSynthesizer' or value.base.history != value.history or value.discovered.history != value.history:
            raise StateRefused('guarded sublearner/prefix')
    elif name == 'ExactCompiledGrammarSynthesizer':
        if len(value.pool) > 117 or len(value.atoms) != 12: raise StateRefused('grammar pool')
        for pool in (value.pool, value.atoms):
            if type(pool) is not dict or any(type(v).__name__ != 'Expression' or k != v.signature for k, v in pool.items()): raise StateRefused('grammar signature')
        if len(value.contexts) != len(value.history) or value.outputs != [y for _, y in value.history]: raise StateRefused('grammar prefix')
        for c in value.contexts: _integer(c, 0, 31)
        for masses in (value.mass0, value.mass1):
            if len(masses) != 32: raise StateRefused('grammar mass shape')
            for mass in masses: _number(mass, 0, MAX_HISTORY)
        _integer(value.proposals_tested,0,10**12)
        for cache in (value._approx_scores,value._exact_scores):
            if type(cache) is not dict or len(cache)>8192: raise StateRefused('score cache bound')
            for key,score in cache.items():
                if type(key) is not tuple or len(key)!=2: raise StateRefused('score cache key')
                _integer(key[0],0,2**32-1); _integer(key[1],1,13); _number(score,-1e12,1e12)
        if value._rank_cache is not None and (type(value._rank_cache) is not list or len(value._rank_cache)>117 or any(type(e).__name__!='Expression' for e in value._rank_cache)):
            raise StateRefused('rank cache shape')
        if value._epoch_lut is not None:
            lut = value._epoch_lut
            if type(lut) is not tuple or len(lut)!=2 or type(lut[1]) is not list or len(lut[1])!=4: raise StateRefused('compiled lookup shape')
            _number(lut[0])
            for row in lut[1]:
                if type(row) is not list or len(row)!=256: raise StateRefused('compiled lookup row')
                for score in row: _number(score)
        if value._exact_terms is not None:
            if type(value._exact_terms) is not tuple or len(value._exact_terms)!=32: raise StateRefused('exact terms shape')
            for row in value._exact_terms:
                if type(row) is not tuple or len(row)!=2: raise StateRefused('exact terms row')
                for score in row: _number(score)
    elif name == 'Expression':
        _integer(value.signature, 0, 2**32-1); _integer(value.size, 1, 13); _integer(value.depth, 0, 4)
        if type(value.code) is not str or len(value.code) > 256 or value.operator not in ('atom','not','constant','xor','and','or'): raise StateRefused('expression domain')
    elif name == 'XorProgram':
        _integer(value.phase, 0, 1)
        features = ('action',) + tuple(f'{x}{i}' for i in range(1, 7) for x in ('y', 'a'))
        if type(value.features) is not tuple or len(value.features) > 3 or len(set(value.features)) != len(value.features) or any(f not in features for f in value.features): raise StateRefused('lag program')
    elif name == 'PackedLagFeatureLearner':
        allowed = ('action',) + tuple(f'{x}{i}' for i in range(1, 7) for x in ('y', 'a'))
        if len(set(value.features)) != len(value.features) or any(f not in allowed for f in value.features): raise StateRefused('lag features')
        if len(value.programs) > 1000 or any(type(p).__name__ != 'XorProgram' for p in value.programs): raise StateRefused('lag programs')
        if value.awaiting_validation is not None:
            row = value.awaiting_validation
            if type(row) is not tuple or len(row) != 4 or any(type(p).__name__ != 'XorProgram' for p in row[:2]): raise StateRefused('lag validation state')
            _integer(row[2], 0, len(value.history)); _number(row[3], -100, 100)


def _encode(value, registry, depth=0):
    if depth > 32: raise StateRefused('state nesting bound')
    if value is None or type(value) in (bool, str):
        if isinstance(value, str) and len(value) > 2048: raise StateRefused('string bound')
        return value
    if type(value) is int:
        if value.bit_length() > 4096: raise StateRefused('integer bit bound')
        return value
    if type(value) is float:
        if not math.isfinite(value): raise StateRefused('nonfinite native state')
        return value
    enc = lambda x: _encode(x, registry, depth + 1)
    if type(value) in (list, tuple, frozenset, deque):
        if len(value) > 8192: raise StateRefused('collection bound')
        seq = sorted(value) if type(value) is frozenset else value
        return {'t': type(value).__name__, 'v': [enc(x) for x in seq],
                **({'maxlen': value.maxlen} if type(value) is deque else {})}
    if type(value) is dict:
        if len(value) > 8192: raise StateRefused('map bound')
        return {'t': 'dict', 'v': [[enc(k), enc(v)] for k, v in value.items()]}
    name = type(value).__name__
    if name not in registry or type(value) is not registry[name]: raise StateRefused('unregistered concrete type')
    _validate_object(value, name)
    fields = {}
    for key in _FIELDS[name].split():
        item = getattr(value,key)
        if name == 'PackedLagFeatureLearner' and key == 'proposal_traces':
            item = copy.deepcopy(item)
            for row in item:
                if row.get('best_gain_nats_per_step') == -math.inf:
                    # The original runtime uses -inf when no candidate beat
                    # its training gate. This diagnostic is not a probability.
                    row['best_gain_nats_per_step'] = 'NO_FINITE_CANDIDATE'
        fields[key] = enc(item)
    return {'t': name, 'version': 1, 'fields': fields}


def _decode(value, registry, depth=0, counter=None):
    if counter is None: counter = [0]
    counter[0] += 1
    if counter[0] > 500000 or depth > 32: raise StateRefused('decoded allocation bound')
    if type(value) is not dict:
        if value is None or type(value) in (bool, str, int, float):
            return _encode(value, registry, depth)
        raise StateRefused('untagged collection')
    dec = lambda x: _decode(x, registry, depth + 1, counter)
    tag = value.get('t')
    if tag in ('list', 'tuple', 'frozenset', 'deque', 'dict'):
        if set(value) != ({'t', 'v', 'maxlen'} if tag == 'deque' else {'t', 'v'}) or type(value['v']) is not list or len(value['v']) > 8192: raise StateRefused('collection schema')
        rows = value['v']
        if tag == 'dict':
            result = {}
            for row in rows:
                if type(row) is not list or len(row) != 2: raise StateRefused('map entry')
                key, item = dec(row[0]), dec(row[1])
                if type(key) not in (str, int, tuple): raise StateRefused('map key type')
                if key in result: raise StateRefused('duplicate map key')
                result[key] = item
            return result
        seq = [dec(x) for x in rows]
        if tag == 'list': return seq
        if tag == 'tuple': return tuple(seq)
        if tag == 'frozenset':
            if len(set(seq)) != len(seq): raise StateRefused('duplicate set value')
            return frozenset(seq)
        _integer(value['maxlen'], 1, MAX_HISTORY)
        if len(seq) > value['maxlen']: raise StateRefused('deque truncation refused')
        return deque(seq, maxlen=value['maxlen'])
    if tag not in registry or set(value) != {'t', 'version', 'fields'} or type(value['version']) is not int or value['version'] != 1 or type(value['fields']) is not dict or set(value['fields']) != set(_FIELDS[tag].split()): raise StateRefused('concrete type/version/field schema')
    fields = {k: dec(v) for k, v in value['fields'].items()}
    if tag == 'PackedLagFeatureLearner':
        for row in fields['proposal_traces']:
            if row.get('best_gain_nats_per_step') == 'NO_FINITE_CANDIDATE':
                row['best_gain_nats_per_step'] = -math.inf
    cls = registry[tag]
    if tag in ('Expression', 'XorProgram'): result = cls(**fields)
    else:
        result = cls.__new__(cls)
        result.__dict__.update(fields)
    if tag == 'PackedLagFeatureLearner': result._packed_epoch = None
    _validate_object(result, tag)
    return result


def _envelope(payload):
    result = {'payload': payload, 'sha256': digest(payload)}
    if len(canonical(result)) > MAX_BYTES: raise StateRefused('checkpoint byte bound')
    return result


def _open(document, schema):
    if type(document) is not dict or set(document) != {'payload', 'sha256'} or len(canonical(document)) > MAX_BYTES:
        raise StateRefused('checkpoint envelope')
    payload = document['payload']
    if type(payload) is not dict or payload.get('schema') != schema or document['sha256'] != digest(payload): raise StateRefused('checkpoint checksum/schema')
    return payload


def predictor_snapshot(model, mechanism, *, epoch=0, prefix_sha256=None, policy_sha256=None):
    _integer(epoch, 0, 10**9)
    if mechanism not in MECHANISMS: raise StateRefused('mechanism')
    if prefix_sha256 is not None and not _hash(prefix_sha256): raise StateRefused('prefix digest')
    if policy_sha256 is not None and not _hash(policy_sha256): raise StateRefused('policy digest')
    registry = {'FrequencyPredictor': FrequencyPredictor} if mechanism == 'frequency' else _registry()
    name = {'frequency':'FrequencyPredictor','temporal':'GrammarEnsemble','native':'GovernedBitworkV14'}[mechanism]
    if type(model) is not registry[name]: raise StateRefused('mechanism type mismatch')
    if mechanism != 'frequency' and prefix_sha256 is not None:
        if prefix_digest([(a,y) for a,y,*_ in model.history]) != prefix_sha256:
            raise StateRefused('model history does not match supplied public prefix')
    return _envelope({'schema': PREDICTOR_SCHEMA, 'mechanism': mechanism, 'state_version': 1,
        'epoch': epoch, 'prefix_sha256': prefix_sha256, 'policy_sha256': policy_sha256,
        'source_sha256': source_identity(), 'runtime': _runtime_identity(),
        'state': _encode(model, registry), 'derived_cache_policy': 'packed_epoch_rebuild_on_next_forecast'})


def predictor_restore(document, mechanism, *, expected_epoch=0, expected_prefix_sha256=None,
                      expected_policy_sha256=None, ttl_epochs=32):
    try:
        p = _open(document, PREDICTOR_SCHEMA)
        fields = {'schema','mechanism','state_version','epoch','prefix_sha256','policy_sha256','source_sha256','runtime','state','derived_cache_policy'}
        if set(p) != fields or p['mechanism'] != mechanism or type(p['state_version']) is not int or p['state_version'] != 1: raise StateRefused('predictor identity')
        _integer(expected_epoch, 0, 10**9); _integer(ttl_epochs, 0, 10**9); _integer(p['epoch'], 0, 10**9)
        if not p['epoch'] <= expected_epoch <= p['epoch'] + ttl_epochs: raise StateRefused('expired/future state epoch')
        if p['source_sha256'] != source_identity() or p['runtime'] != _runtime_identity(): raise StateRefused('source/runtime mismatch')
        if p['prefix_sha256'] != expected_prefix_sha256 or p['policy_sha256'] != expected_policy_sha256: raise StateRefused('public prefix/policy mismatch')
        if p['derived_cache_policy'] != 'packed_epoch_rebuild_on_next_forecast': raise StateRefused('cache policy')
        registry = {'FrequencyPredictor': FrequencyPredictor} if mechanism == 'frequency' else _registry()
        result = _decode(p['state'], registry)
        expected = {'frequency':'FrequencyPredictor','temporal':'GrammarEnsemble','native':'GovernedBitworkV14'}[mechanism]
        if type(result) is not registry[expected]: raise StateRefused('restored type mismatch')
        if mechanism != 'frequency' and expected_prefix_sha256 is not None:
            if prefix_digest([(a,y) for a,y,*_ in result.history]) != expected_prefix_sha256:
                raise StateRefused('decoded model history does not match public prefix')
        return result
    except (TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
        raise StateRefused('malformed bounded predictor state') from exc


@dataclass
class PersistentConfig:
    state_policy: str = 'fullwarm'
    delayed_credit: bool = True
    detector_enabled: bool = True
    commitment: int = 64
    credit_horizon: int = 128
    gamma: float = .98
    detector_window: int = 32
    detector_threshold: float = .35
    detector_cooldown: int = 64
    switch_penalty: float = .01
    risk_weight: float = .10
    cost_weight: float = 2.
    max_history: int = 2048
    max_state_bytes: int = MAX_BYTES
    epoch: int = 0
    ttl_epochs: int = 32
    cost_seconds: dict = field(default_factory=lambda: {'frequency': .000002, 'temporal': .0001, 'native': .0015})
    setup_seconds: dict = field(default_factory=lambda: {'frequency': 0., 'temporal': .08, 'native': .08})

    def validate(self):
        if self.state_policy not in ('cold','fullwarm','selectivewarm'): raise ValueError('unregistered state policy')
        if type(self.delayed_credit) is not bool or type(self.detector_enabled) is not bool: raise ValueError('boolean ablation required')
        for key in ('commitment','credit_horizon','detector_window','detector_cooldown','max_history'):
            _integer(getattr(self,key), 1, MAX_HISTORY)
        if self.max_history < max(self.commitment, self.credit_horizon, 2*self.detector_window): raise ValueError('history budget smaller than registered window')
        _integer(self.epoch, 0, 10**9); _integer(self.ttl_epochs, 0, 10**9)
        _integer(self.max_state_bytes, 1024, MAX_BYTES)
        _number(self.gamma, .001, 1.); _number(self.detector_threshold, .001, 4.)
        for key in ('switch_penalty','risk_weight','cost_weight'): _number(getattr(self,key), 0, 100)
        for costs in (self.cost_seconds,self.setup_seconds):
            if type(costs) is not dict or set(costs) != set(MECHANISMS): raise ValueError('registered cost map required')
            for value in costs.values(): _number(value, 0, 120)


class PersistentController:
    """Three bounded live states; discounted public credit, no hidden labels."""
    def __init__(self, config=None):
        self.config = config or PersistentConfig(); self.config.validate()
        self.models = {'frequency': FrequencyPredictor()}; self.cursors = {'frequency': 0}
        self.residency_limit = 3
        self.history = []; self.gains = {name: [] for name in MECHANISMS}
        self.selected = 'frequency'; self.pending = None; self.decisions = []
        self.next_decision = 0; self.explored = []; self.verified_ids = {}
        self.detector_losses = []; self.alarms = []; self.last_alarm = -self.config.detector_cooldown
        self.credit_start = 0; self.evictions = []
        self.telemetry = {kind + suffix: 0. for kind in ('build','catchup','active','inactive','decision','detector','bookkeeping','serialization','restoration') for suffix in ('_wall_seconds','_cpu_seconds')}
        self.telemetry.update({name:0 for name in ('catchup_observations','active_forecasts','inactive_forecasts','active_updates','inactive_updates','switches','cold_evictions','restores','cache_rebuilds_on_restore','expired_states','cold_fallbacks')})

    def _timed(self, kind, call):
        wall, cpu = time.perf_counter(), time.process_time()
        try: return call()
        finally:
            self.telemetry[kind+'_wall_seconds'] += time.perf_counter()-wall
            self.telemetry[kind+'_cpu_seconds'] += time.process_time()-cpu

    @staticmethod
    def _binary(value): _integer(value, 0, 1)

    def _model(self, name):
        if name not in self.models:
            if self.residency_limit == 1 and name != 'frequency': raise StateRefused('resident learner budget exhausted')
            while len(self.models) >= self.residency_limit:
                choices = [n for n in self.models if n != 'frequency']
                if not choices: raise StateRefused('resident learner budget exhausted')
                self.evict(min(choices,key=lambda n:(self.cursors[n],n)))
            self.models[name] = self._timed('build', lambda: make_predictor(name)); self.cursors[name] = 0
        def catchup():
            model = self.models[name]
            while self.cursors[name] < len(self.history):
                a, y = self.history[self.cursors[name]]
                probability(model, a); model.observe(a, y)
                self.cursors[name] += 1; self.telemetry['catchup_observations'] += 1
            return model
        return self._timed('catchup', catchup)

    def _credit(self, name):
        now = len(self.history)
        # Outcomes after a horizon's start mature together. No future outcome
        # is imputed, and censored/inactive observations earn no gain.
        end = now if not self.config.delayed_credit else (now // self.config.credit_horizon) * self.config.credit_horizon
        width = self.config.credit_horizon if self.config.delayed_credit else min(16, self.config.credit_horizon)
        rows = [(t,g) for t,g in self.gains[name] if max(self.credit_start,end-width) <= t < end]
        weights = [self.config.gamma ** (end-1-t) for t,_ in rows]
        total = sum(weights)
        gain = sum(w*g for w,(_,g) in zip(weights,rows))/total if total else 0.
        effective = total*total/sum(w*w for w in weights) if weights else 0.
        risk = min(1., 1/math.sqrt(max(1.,effective)))
        return {'gain':gain,'samples':len(rows),'effective_samples':effective,'risk_proxy':risk,'mature_end':end}

    def decide(self, public_state=None, available_actions=MECHANISMS, remaining_budget=None):
        if self.pending is not None: raise RuntimeError('decision requires settled public prefix')
        def choose():
            if len(self.decisions) >= 512: raise ValueError('decision budget exhausted')
            state = public_state or {}; budget = remaining_budget or {}
            allowed = {'candidate_count','symbol_count','edge_count','memory_records','public_failures','public_observations'}
            if type(state) is not dict or set(state)-allowed: raise ValueError('public counts only')
            for value in state.values(): _integer(value,0,1000000)
            if type(budget) is not dict or set(budget)-{'steps','max_cost_seconds'}: raise ValueError('unregistered budget')
            steps = budget.get('steps',self.config.commitment); maximum = budget.get('max_cost_seconds',120.)
            _integer(steps,0,MAX_HISTORY); _number(maximum,0,3600)
            if type(available_actions) not in (tuple,list) or len(set(available_actions)) != len(available_actions) or any(n not in MECHANISMS for n in available_actions): raise ValueError('unregistered actions')
            old = self.selected; scores = {}; credits = {}; costs = {}; horizons = {}
            now = len(self.history)
            for name in available_actions:
                if self.residency_limit == 1 and name != 'frequency': continue
                credit = self._credit(name); credits[name] = credit
                deadline = min(self.config.max_history,now+steps)
                prospective_exploration = name in ('native','temporal') and name not in self.explored and now >= self.config.commitment
                if self.config.delayed_credit and prospective_exploration:
                    horizon = self.config.credit_horizon
                    deadline = min(self.config.max_history,((now+self.config.commitment+horizon-1)//horizon)*horizon)
                    if 'steps' in budget: deadline = min(deadline,now+steps)
                planned = max(0,deadline-now); horizons[name] = planned
                # Full-warm means all learners are updated, so its marginal
                # selected cost is equal. The realized whole policy cost is
                # still measured, never reduced to this scheduling estimate.
                names = MECHANISMS if self.config.state_policy == 'fullwarm' and self.residency_limit == 3 else tuple(dict.fromkeys(('frequency',name)))
                cost = sum(self.config.cost_seconds[n]*(planned+len(self.history)-self.cursors.get(n,0)) + (self.config.setup_seconds[n] if n not in self.models else 0.) for n in names)
                costs[name] = cost
                if planned and cost <= maximum:
                    scores[name] = credit['gain'] - self.config.risk_weight*credit['risk_proxy'] - self.config.cost_weight*cost/planned - (self.config.switch_penalty if name != old else 0.)
            reason = 'discounted_public_credit'
            if not scores: chosen = 'abstain'; reason = 'budget_exhausted'
            elif len(self.history) < self.config.commitment and 'frequency' in scores:
                chosen = 'frequency'; reason = 'initial_public_prefix'
            elif old in scores and len(self.history) < self.next_decision:
                chosen = old; reason = 'committed_interval'
            else:
                unexplored = [n for n in ('temporal','native') if n in scores and n not in self.explored]
                if unexplored:
                    chosen = unexplored[0]; reason = 'bounded_exploration'
                else: chosen = max(scores,key=lambda n:(scores[n],-MECHANISMS.index(n)))
            if chosen != old and self.config.state_policy == 'cold' and old in ('native','temporal') and old in self.models and len(self.evictions) >= 512:
                raise ValueError('eviction event budget')
            if reason == 'bounded_exploration': self.explored.append(chosen)
            if chosen != old:
                self.telemetry['switches'] += 1
                if self.config.state_policy == 'cold' and old in ('native','temporal') and old in self.models:
                    del self.models[old]; del self.cursors[old]
                    self.evictions.append({'at':len(self.history),'mechanism':old,'reason':'cold_switch'})
                    self.telemetry['cold_evictions'] += 1
            self.selected = chosen
            if reason != 'committed_interval':
                # Preserve a zero-budget abstention until the next registered
                # interval instead of immediately auto-deciding with defaults.
                self.next_decision = (now+max(1,min(self.config.commitment,self.config.max_history-now))
                    if chosen == 'abstain' else now+horizons[chosen])
            row = {'decision_index':len(self.decisions),'observed_prefix':len(self.history),'mechanism':chosen,
                'reason':reason,'scores':scores,'credits':credits,'estimated_cost_seconds':costs,'committed_until':self.next_decision,
                'estimated_horizon_steps':horizons,
                'change_alarm':bool(self.alarms and self.alarms[-1]['at'] == len(self.history))}
            self.decisions.append(row)
            return copy.deepcopy(row)
        return self._timed('decision',choose)

    def predict(self, action):
        self._binary(action)
        if self.pending is not None: raise RuntimeError('public outcome pending')
        if len(self.history) >= self.config.max_history: raise ValueError('history budget exhausted')
        if not self.decisions or len(self.history) >= self.next_decision: self.decide()
        names = (('frequency',) if self.selected == 'abstain' else MECHANISMS
                 if self.config.state_policy == 'fullwarm' and self.residency_limit == 3
                 else tuple(dict.fromkeys(('frequency',self.selected))))
        forecasts = {}
        for name in names:
            if name == 'abstain': continue
            model = self._model(name); kind = 'active' if name == self.selected else 'inactive'
            forecasts[name] = self._timed(kind,lambda:probability(model,action))
            self.telemetry[kind+'_forecasts'] += 1
        p = forecasts.get(self.selected,.5)
        self.pending = (action,p,forecasts)
        return p

    def _detect(self, loss):
        self.detector_losses.append(min(4.,max(0.,loss))); self.detector_losses = self.detector_losses[-2*self.config.detector_window:]
        n = len(self.history); width = self.config.detector_window
        if not self.config.detector_enabled or len(self.detector_losses) < 2*width or n-self.last_alarm < self.config.detector_cooldown: return
        before = sum(self.detector_losses[:width])/width; after = sum(self.detector_losses[width:])/width
        if abs(after-before) >= self.config.detector_threshold:
            self.alarms.append({'at':n,'before_mean':before,'after_mean':after,'difference':abs(after-before)})
            self.last_alarm = n; self.credit_start = n
            # Expire selection credit, not latent model evidence. Retained
            # models have their own original forgetting mechanisms.
            self.next_decision = n; self.explored = []

    def observe(self, action, outcome):
        self._binary(action); self._binary(outcome)
        if self.pending is None or self.pending[0] != action: raise RuntimeError('matching forecast required')
        _,p,forecasts = self.pending; t = len(self.history)
        for name in forecasts:
            kind = 'active' if name == self.selected else 'inactive'
            self._timed(kind,lambda:self.models[name].observe(action,outcome))
            self.cursors[name] += 1; self.telemetry[kind+'_updates'] += 1
        def settle():
            baseline = logloss(forecasts['frequency'],outcome)
            for name,forecast in forecasts.items():
                self.gains[name].append([t,max(-8.,min(8.,baseline-logloss(forecast,outcome)))])
                self.gains[name] = self.gains[name][-self.config.max_history:]
            self.history.append((action,outcome)); self.pending = None
        self._timed('bookkeeping',settle)
        self._timed('detector',lambda:self._detect(logloss(p,outcome)))

    def ingest_public(self, action, outcome):
        self.predict(action); self.observe(action,outcome)

    def peek_probabilities(self, mechanism=None):
        if self.pending is not None: raise RuntimeError('peek requires settled public prefix')
        name = mechanism or self.selected
        if name == 'abstain': return (.5,.5)
        if name not in MECHANISMS: raise ValueError('unregistered mechanism')
        model = self._model(name)
        return self._timed('active',lambda:tuple(probability(copy.deepcopy(model),a) for a in (0,1)))

    def record_verified(self, mechanism, gain, cost_seconds, observation_id, *, independently_verified=False):
        if independently_verified is not True: return False
        if mechanism not in MECHANISMS or type(observation_id) is not str or not 1<=len(observation_id)<=128: raise ValueError('verified observation identity')
        _number(gain,-8,8); _number(cost_seconds,0,3600)
        row = [mechanism,float(gain),float(cost_seconds)]
        if observation_id in self.verified_ids:
            if row != self.verified_ids[observation_id]: raise ValueError('contradictory verified observation')
            return False
        if len(self.verified_ids) >= 512: raise ValueError('verified observation budget')
        # Stored admission metadata cannot fabricate a time-indexed stream
        # observation. Only predict/observe supplies numeric selector credit.
        self.verified_ids[observation_id] = row
        return True

    def evict(self, mechanism, *, reason='memory_pressure'):
        """Deterministically discard a dormant state, retaining bounded prefix.

        This bounds resident learner count; it is not an OS RSS hard limit.
        The next use pays a full observed-prefix reconstruction.
        """
        if self.pending is not None: raise RuntimeError('cannot evict pending public forecast')
        if mechanism not in ('native','temporal') or reason not in ('memory_pressure','expiry','policy_change'):
            raise ValueError('registered expensive learner eviction required')
        if mechanism not in self.models: return False
        if len(self.evictions) >= 512: raise ValueError('eviction event budget')
        del self.models[mechanism]; del self.cursors[mechanism]
        self.evictions.append({'at':len(self.history),'mechanism':mechanism,'reason':reason})
        self.telemetry['cold_evictions'] += 1
        if reason == 'expiry': self.telemetry['expired_states'] += 1
        return True

    def trim_resident(self, maximum=1):
        _integer(maximum,1,3)
        if self.pending is not None: raise RuntimeError('cannot change residency during pending public forecast')
        self.residency_limit = maximum; self.next_decision = len(self.history)
        for name in sorted((n for n in self.models if n != 'frequency'),key=lambda n:(self.cursors[n],n)):
            if len(self.models) <= maximum: break
            self.evict(name)
        return len(self.models)

    def snapshot(self):
        if self.pending is not None: raise RuntimeError('snapshot requires settled observation')
        started = time.perf_counter(),time.process_time()
        policy = digest(asdict(self.config)); states = {}
        for name,model in self.models.items():
            states[name] = predictor_snapshot(model,name,epoch=self.config.epoch,
                prefix_sha256=prefix_digest(self.history[:self.cursors[name]]),policy_sha256=policy)
        payload = {'schema':SCHEMA,'config':asdict(self.config),'source_sha256':source_identity(),
            'runtime':_runtime_identity(),'history':[list(row) for row in self.history],
            'prefix_sha256':prefix_digest(self.history),'states':states,'cursors':dict(self.cursors),'residency_limit':self.residency_limit,
            'gains':copy.deepcopy(self.gains),'selected':self.selected,'decisions':copy.deepcopy(self.decisions),
            'next_decision':self.next_decision,'explored':list(self.explored),'verified_ids':copy.deepcopy(self.verified_ids),
            'detector_losses':list(self.detector_losses),'alarms':copy.deepcopy(self.alarms),'last_alarm':self.last_alarm,
            'credit_start':self.credit_start,'evictions':copy.deepcopy(self.evictions),'telemetry':dict(self.telemetry)}
        self.telemetry['serialization_wall_seconds'] += time.perf_counter()-started[0]
        self.telemetry['serialization_cpu_seconds'] += time.process_time()-started[1]
        payload['telemetry'] = dict(self.telemetry)
        document = _envelope(payload)
        if len(canonical(document)) > self.config.max_state_bytes: raise StateRefused('configured state byte budget exhausted')
        return document

    @classmethod
    def load(cls, document, *, expected_epoch=None, expected_prefix_sha256=None, expected_config=None):
        started = time.perf_counter(),time.process_time()
        try:
            p = _open(document,SCHEMA)
            expected_keys = {'schema','config','source_sha256','runtime','history','prefix_sha256','states','cursors','residency_limit','gains','selected','decisions','next_decision','explored','verified_ids','detector_losses','alarms','last_alarm','credit_start','evictions','telemetry'}
            if set(p) != expected_keys or type(p['config']) is not dict: raise StateRefused('controller fields')
            config = PersistentConfig(**p['config']); config.validate()
            if len(canonical(document)) > config.max_state_bytes: raise StateRefused('configured state byte budget exhausted')
            if expected_config is not None and asdict(config) != asdict(expected_config): raise StateRefused('controller policy mismatch')
            now = config.epoch if expected_epoch is None else expected_epoch
            if p['source_sha256'] != source_identity() or p['runtime'] != _runtime_identity(): raise StateRefused('controller source/runtime mismatch')
            _history(p['history'])
            if len(p['history']) > config.max_history or p['prefix_sha256'] != prefix_digest(p['history']): raise StateRefused('controller prefix')
            if expected_prefix_sha256 is not None and p['prefix_sha256'] != expected_prefix_sha256: raise StateRefused('eligible public prefix mismatch')
            result = cls(config); result.history = [tuple(row) for row in p['history']]
            result.residency_limit = _integer(p['residency_limit'],1,3)
            if type(p['states']) is not dict or not set(p['states']) <= set(MECHANISMS) or 'frequency' not in p['states'] or set(p['states']) != set(p['cursors']): raise StateRefused('state inventory')
            if len(p['states']) > result.residency_limit: raise StateRefused('resident state bound')
            result.models = {}; result.cursors = dict(p['cursors'])
            for name,doc in p['states'].items():
                cursor = _integer(result.cursors[name],0,len(result.history))
                result.models[name] = predictor_restore(doc,name,expected_epoch=now,ttl_epochs=config.ttl_epochs,
                    expected_prefix_sha256=prefix_digest(result.history[:cursor]),expected_policy_sha256=digest(asdict(config)))
                model = result.models[name]
                actual = [(a,y) for a,y,*_ in model.history] if name != 'frequency' else None
                if actual is not None and actual != result.history[:cursor]: raise StateRefused('embedded model prefix mismatch')
            frequency = result.models['frequency']; expected_counts = [[1,1],[1,1]]
            for a,y in result.history: expected_counts[a][y] += 1
            if frequency.counts != expected_counts or result.cursors['frequency'] != len(result.history): raise StateRefused('frequency prefix/count mismatch')
            if set(p['gains']) != set(MECHANISMS): raise StateRefused('gain inventory')
            for rows in p['gains'].values():
                if type(rows) is not list or len(rows) > config.max_history: raise StateRefused('gain bound')
                previous = -1
                for t,g in rows:
                    _integer(t,0,len(result.history)-1); _number(g,-8,8)
                    if t <= previous: raise StateRefused('duplicate/out-of-order credit')
                    previous = t
            if p['selected'] not in (*MECHANISMS,'abstain'): raise StateRefused('selected state')
            if type(p['decisions']) is not list or len(p['decisions']) > 512: raise StateRefused('decision bound')
            previous_prefix = -1
            for i,row in enumerate(p['decisions']):
                if row.get('decision_index') != i or row.get('mechanism') not in (*MECHANISMS,'abstain'): raise StateRefused('decision identity')
                _integer(row['observed_prefix'],0,len(result.history))
                if row['observed_prefix'] < previous_prefix: raise StateRefused('nonchronological decision prefix')
                previous_prefix = row['observed_prefix']
            if p['selected'] != (p['decisions'][-1]['mechanism'] if p['decisions'] else 'frequency'):
                raise StateRefused('selected mechanism differs from durable decision')
            _integer(p['next_decision'],0,2*MAX_HISTORY); _integer(p['credit_start'],0,len(result.history))
            _integer(p['last_alarm'],-config.detector_cooldown,len(result.history))
            if type(p['explored']) is not list or len(set(p['explored'])) != len(p['explored']) or any(n not in ('native','temporal') for n in p['explored']): raise StateRefused('exploration state')
            if len(p['detector_losses']) > 2*config.detector_window: raise StateRefused('detector bound')
            for loss in p['detector_losses']: _number(loss,0,4)
            if len(p['alarms']) > MAX_HISTORY or len(p['evictions']) > 512: raise StateRefused('event bound')
            previous_alarm = -config.detector_cooldown
            for row in p['alarms']:
                _integer(row['at'],1,len(result.history))
                if row['at'] <= previous_alarm or row['at']-previous_alarm < config.detector_cooldown: raise StateRefused('alarm chronology/cooldown')
                previous_alarm = row['at']
                _number(row['before_mean'],0,4); _number(row['after_mean'],0,4); _number(row['difference'],config.detector_threshold,4)
                if abs(row['after_mean']-row['before_mean']) != row['difference']: raise StateRefused('alarm arithmetic')
            if p['last_alarm'] != previous_alarm or p['credit_start'] != (p['alarms'][-1]['at'] if p['alarms'] else 0): raise StateRefused('alarm credit cursor')
            if set(p['telemetry']) != set(result.telemetry): raise StateRefused('telemetry schema')
            for key,value in p['telemetry'].items():
                _number(value,0,1e12)
                if not key.endswith('_seconds'): _integer(value,0,10**9)
            for key,row in p['verified_ids'].items(): result.record_verified(*row,key,independently_verified=True)
            for key in ('gains','selected','decisions','next_decision','explored','detector_losses','alarms','last_alarm','credit_start','evictions','telemetry'):
                setattr(result,key,copy.deepcopy(p[key]))
            result.telemetry['restores'] += 1
            result.telemetry['cache_rebuilds_on_restore'] += int('native' in result.models and result.models['native'].lags is not None)
            result.telemetry['restoration_wall_seconds'] += time.perf_counter()-started[0]
            result.telemetry['restoration_cpu_seconds'] += time.process_time()-started[1]
            return result
        except (TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
            raise StateRefused('malformed bounded controller state') from exc

    @classmethod
    def restore_or_cold(cls, document, config, *, expected_prefix_sha256=None, expected_epoch=None):
        try:
            result = cls.load(document,expected_config=config,expected_prefix_sha256=expected_prefix_sha256,expected_epoch=expected_epoch)
            return result, {'status':'RESTORED','reason':None}
        except (ValueError, RuntimeError, OSError) as exc:
            result = cls(config); result.telemetry['cold_fallbacks'] = 1
            return result, {'status':'COLD_FALLBACK','reason':str(exc),'observations_retained':0}


def deterministic_state_hash(document):
    payload = copy.deepcopy(_open(document,SCHEMA))
    payload['telemetry'] = {k:v for k,v in payload['telemetry'].items() if not k.endswith('_seconds')}
    return digest(payload)


def _unique_pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result: raise StateRefused('duplicate JSON object key')
        result[key] = value
    return result


def _checkpoint_path(path):
    # Inspect unresolved ancestors: resolving first would erase junctions.
    path = Path(path).absolute()
    for part in (path,*path.parents):
        try: info = part.lstat()
        except FileNotFoundError: continue
        if part.is_symlink() or getattr(info,'st_reparse_tag',0) or getattr(info,'st_file_attributes',0) & 0x400:
            raise StateRefused('checkpoint reparse/link path refused')
        if part == path and part.is_file() and info.st_nlink != 1:
            raise StateRefused('checkpoint hard link refused')
    return path


def read_checkpoint(path):
    path = _checkpoint_path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES: raise StateRefused('checkpoint path/size')
    try:
        return json.loads(path.read_bytes(),object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(StateRefused('nonfinite JSON constant')))
    except (json.JSONDecodeError,UnicodeError,RecursionError) as exc:
        raise StateRefused('partial/corrupt JSON checkpoint') from exc


def write_checkpoint(path, document):
    """Atomic single-file publication; a leftover .tmp is never read as state."""
    path = _checkpoint_path(path)
    raw = canonical(document)
    if len(raw) > MAX_BYTES: raise StateRefused('checkpoint bytes')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
