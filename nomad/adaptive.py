"""Bounded, public-evidence computation selection; never verification authority.

Existing BGR learners are loaded lazily. Selection uses frozen cost estimates,
not noisy live timing. Realized timing is reported separately and includes
catch-up work. Structural scores and risk penalties are heuristics, not causal
identification or calibrated confidence guarantees.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import copy
import hashlib
import json
import math
import time

from .native_bitwork import load_native

SCHEMA = 'nomad.adaptive-computation.v18'
MECHANISMS = ('frequency', 'temporal', 'native')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class AdaptiveConfig:
    # These conservative prior costs come from the earlier trusted study's wall
    # measurements. A new experiment supplies a separately frozen calibration.
    cost_seconds: dict = field(default_factory=lambda: {'frequency': .00001, 'temporal': .0006, 'native': .02})
    setup_seconds: dict = field(default_factory=lambda: {'frequency': 0.0, 'temporal': .02, 'native': .02})
    cost_weight: float = 2.0
    risk_weight: float = .15
    block_size: int = 16
    max_history: int = 512
    exploration_interval: int = 4
    structural_window: int = 64
    maximum_lag: int = 8
    minimum_observations: int = 32
    use_history: bool = True
    use_structure: bool = True
    use_memory: bool = True
    adaptive_selection: bool = True

    def validate(self):
        if set(self.cost_seconds) != set(MECHANISMS) or any(
                type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 10
                for v in self.cost_seconds.values()):
            raise ValueError('positive finite registered mechanism costs required')
        if set(self.setup_seconds) != set(MECHANISMS) or any(
                type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=120
                for v in self.setup_seconds.values()):
            raise ValueError('finite registered initialization costs required')
        for name in ('cost_weight', 'risk_weight'):
            v = getattr(self, name)
            if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100:
                raise ValueError('invalid registered objective weight')
        for name, low, high in (('block_size', 4, 64), ('max_history', 32, 2048),
                ('exploration_interval', 2, 32), ('structural_window', 16, 128),
                ('maximum_lag', 1, 8), ('minimum_observations', 16, 128)):
            if type(getattr(self, name)) is not int or not low <= getattr(self, name) <= high:
                raise ValueError('invalid bounded controller parameter: '+name)
        if any(type(getattr(self, name)) is not bool for name in
                ('use_history','use_structure','use_memory','adaptive_selection')):
            raise ValueError('ablation flags must be boolean')


class FrequencyPredictor:
    """Two action-conditional Beta(1,1) counts, shared by all new study arms."""
    def __init__(self): self.counts = [[1, 1], [1, 1]]
    def predict(self, action): return self.counts[action][1]/sum(self.counts[action])
    def observe(self, action, outcome): self.counts[action][outcome] += 1


def make_predictor(mechanism):
    if mechanism == 'frequency': return FrequencyPredictor()
    native = load_native()  # includes original manifest verification before import
    if mechanism == 'native': return native()
    if mechanism == 'temporal':
        from bgr100.grammar import GrammarEnsemble
        return GrammarEnsemble()
    raise ValueError('unknown registered mechanism')


def probability(model, action):
    value = model.predict(action)
    value = float(value.probability_one if hasattr(value, 'probability_one') else value)
    if not math.isfinite(value) or not 0 < value < 1: raise ValueError('invalid model probability')
    return value


def logloss(p, y): return -math.log(p if y else 1-p)


class AdaptiveController:
    def __init__(self, config=None):
        self.config = config or AdaptiveConfig(); self.config.validate()
        self.frequency = FrequencyPredictor()
        self.history = []
        self.models, self.cursors = {}, {}
        self.actual_cursors = {}
        self.gains = {name: [] for name in MECHANISMS}
        self.verified_ids = {}
        self.decisions = []
        self.selected = 'frequency'
        self.pending = None
        self.last_exploration = -self.config.exploration_interval
        self.explorations = 0
        self.telemetry = {name: 0.0 for name in ('decision_wall_seconds', 'decision_cpu_seconds',
            'predictor_wall_seconds', 'predictor_cpu_seconds', 'catchup_wall_seconds',
            'catchup_cpu_seconds', 'build_wall_seconds', 'build_cpu_seconds',
            'bookkeeping_wall_seconds', 'bookkeeping_cpu_seconds')}
        self.telemetry.update(catchup_observations=0, native_builds=0, temporal_builds=0,
                              native_forecasts=0, temporal_forecasts=0)

    @staticmethod
    def _binary(value):
        if type(value) is not int or value not in (0, 1): raise ValueError('binary integer required')

    def _timed(self, kind, call):
        wall, cpu = time.perf_counter(), time.process_time()
        try: return call()
        finally:
            self.telemetry[kind+'_wall_seconds'] += time.perf_counter()-wall
            self.telemetry[kind+'_cpu_seconds'] += time.process_time()-cpu

    def _model(self, name):
        if name == 'frequency': return self.frequency
        if not self.config.use_history: raise ValueError('history ablation forbids temporal/native inference')
        if name not in self.models:
            self.models[name] = self._timed('build', lambda: make_predictor(name))
            self.actual_cursors[name] = 0; self.telemetry[name+'_builds'] += 1
        model = self.models[name]
        def catchup():
            while self.actual_cursors[name] < len(self.history):
                a, y = self.history[self.actual_cursors[name]]
                probability(model, a); model.observe(a, y)
                self.actual_cursors[name] += 1; self.telemetry['catchup_observations'] += 1
            self.cursors[name] = len(self.history)
        self._timed('catchup', catchup)
        return model

    def structural_diagnostic(self):
        """BIC-penalized finite conditional contingency screen, past data only.

        This explores 2*maximum_lag public history bits. It does not supply a
        competing learned forecast, prove causation, or access a generator.
        """
        if not self.config.use_structure or not self.config.use_history:
            return {'score': 0.0, 'lag': 0, 'history_bit': None, 'observations': len(self.history)}
        begin = max(self.config.maximum_lag, len(self.history)-self.config.structural_window)
        n = len(self.history)-begin
        best = {'score': 0.0, 'lag': 0, 'history_bit': None, 'observations': len(self.history)}
        if n < 16: return best
        for lag in range(1, self.config.maximum_lag+1):
            for bit in (0, 1):
                counts = [[[0, 0] for _ in range(2)] for _ in range(2)]
                for index in range(begin, len(self.history)):
                    a,y = self.history[index]; f = self.history[index-lag][bit]
                    counts[a][f][y] += 1
                information = 0.0
                for action in counts:
                    totals = [sum(c[y] for c in action) for y in (0,1)]; total = sum(totals)
                    for cell in action:
                        size = sum(cell)
                        for y, count in enumerate(cell):
                            if count: information += count*math.log(count*total/(size*totals[y]))/n
                score = information-(math.log(n)+math.log(2*self.config.maximum_lag))/n
                if score > best['score']:
                    best = {'score': score, 'lag': lag, 'history_bit': bit, 'observations': len(self.history)}
        return best

    def decide(self, public_state=None, available_actions=MECHANISMS, remaining_budget=None):
        def choose():
            state = public_state or {}; budget = remaining_budget or {}
            allowed_fields = {'candidate_count','symbol_count','edge_count','memory_records','public_failures','public_observations'}
            if not isinstance(state,dict) or set(state)-allowed_fields or any(
                    type(v) is not int or not 0 <= v <= 1000000 for v in state.values()):
                raise ValueError('public structural counts only; task labels/outcomes are not selection state')
            if not isinstance(budget,dict) or set(budget)-{'steps','max_cost_seconds'}:
                raise ValueError('unsupported public computation budget')
            steps = budget.get('steps', self.config.block_size)
            maximum = budget.get('max_cost_seconds', 120.0)
            if type(steps) is not int or not 0 <= steps <= 2048 or type(maximum) not in (float,int) or not math.isfinite(maximum) or not 0 <= maximum <= 3600:
                raise ValueError('invalid remaining computation budget')
            actions = tuple(available_actions)
            if not actions or len(set(actions)) != len(actions) or any(a not in (*MECHANISMS,'abstain') for a in actions):
                raise ValueError('unregistered computation actions')
            if len(self.decisions) >= 256: raise ValueError('decision budget exhausted')
            if not self.config.use_memory:
                self.gains = {name: [] for name in MECHANISMS}
            diagnostic = self.structural_diagnostic()
            index = len(self.decisions); scores = {}; available = []
            for name in actions:
                if name == 'abstain': continue
                if not self.config.use_history and name != 'frequency': continue
                rebuilding = name != 'frequency' and name not in self.models
                catchup = len(self.history)-self.actual_cursors.get(name,0) if name != 'frequency' else 0
                setup = self.config.setup_seconds[name] if rebuilding else 0.0
                cost = setup+self.config.cost_seconds[name]*(steps+catchup)
                values = self.gains[name] if self.config.use_memory else []
                mean = sum(values)/len(values) if values else 0.0
                variance = sum((v-mean)**2 for v in values)/max(1,len(values)-1)
                risk = math.sqrt(variance/max(1,len(values)))+1/math.sqrt(4+len(values)) if name != 'frequency' else 0.0
                score = mean-self.config.cost_weight*(cost/max(1,steps)-self.config.cost_seconds['frequency'])-self.config.risk_weight*risk
                scores[name] = {'score':score,'mean_gain':mean,'risk_proxy':risk,'observations':len(values),
                                'estimated_cost_seconds':cost,'catchup_observations':catchup,
                                'estimated_setup_seconds':setup,'requires_reconstruction':rebuilding}
                if cost <= maximum and steps: available.append(name)
            selected = max(available,key=lambda a:(scores[a]['score'],-MECHANISMS.index(a))) if available else 'abstain'
            reason = 'public-gain-minus-frozen-cost-and-risk'; exploration = False
            if not self.config.adaptive_selection:
                selected = 'native' if 'native' in available else selected; reason = 'selection-disabled-fixed-native'
            elif len(self.history) >= self.config.minimum_observations and index-self.last_exploration >= self.config.exploration_interval:
                candidates = [a for a in ('temporal','native') if a in available]
                # Exploration consumes at most one block per configured interval.
                # A positive screen orders exploration but does not manufacture gain.
                if self.config.use_structure:
                    candidates = candidates if diagnostic['score'] > 0.015 else []
                if candidates:
                    preferred = 'native' if diagnostic['lag'] > 1 else 'temporal'
                    candidates.sort(key=lambda a:(len(self.gains[a]),a != preferred,MECHANISMS.index(a)))
                    selected = candidates[0]; exploration = True; reason = 'bounded-public-evidence-exploration'
                    self.last_exploration = index; self.explorations += 1
            row = {'decision_index':index,'observed_prefix':len(self.history),'mechanism':selected,
                'exploration':exploration,'reason':reason,'diagnostic':diagnostic,'scores':scores,
                'public_state':dict(state),'remaining_budget':{'steps':steps,'max_cost_seconds':maximum},
                'authority':'computation-selection-only'}
            self.decisions.append(row); self.selected = selected
            return copy.deepcopy(row)
        return self._timed('decision', choose)

    def predict(self, action):
        self._binary(action)
        if self.pending is not None: raise RuntimeError('public observation pending')
        if len(self.history) >= self.config.max_history: raise ValueError('observed-history budget exhausted')
        if len(self.history)%self.config.block_size == 0 or not self.decisions:
            self.decide()
        baseline = self.frequency.predict(action)
        name = self.selected
        if name == 'abstain': p = .5
        elif name == 'frequency': p = baseline
        else:
            model = self._model(name)
            p = self._timed('predictor', lambda: probability(model,action))
            self.telemetry[name+'_forecasts'] += 1
        self.pending = (action,p,baseline,name)
        return p

    def _append(self, action, outcome):
        if len(self.history) >= self.config.max_history: raise ValueError('observed-history budget exhausted')
        self.frequency.observe(action,outcome); self.history.append((action,outcome))

    def observe(self, action, outcome):
        self._binary(action); self._binary(outcome)
        if self.pending is None or self.pending[0] != action: raise RuntimeError('matching public prediction required')
        _,p,baseline,name = self.pending
        if name in ('temporal','native'):
            self._timed('predictor',lambda: self.models[name].observe(action,outcome))
            self.cursors[name] += 1; self.actual_cursors[name] += 1
        def bookkeeping():
            if name in MECHANISMS and self.config.use_memory:
                self.gains[name].append(max(-8.,min(8.,logloss(baseline,outcome)-logloss(p,outcome))))
                self.gains[name] = self.gains[name][-128:]
            self._append(action,outcome); self.pending = None
        self._timed('bookkeeping',bookkeeping)

    def ingest_public(self, action, outcome):
        self._binary(action); self._binary(outcome)
        if self.pending is not None: raise RuntimeError('cannot ingest past pending forecast')
        self._timed('bookkeeping',lambda:self._append(action,outcome))

    def peek_probabilities(self, mechanism=None):
        if self.pending is not None: raise RuntimeError('counterfactual request during pending forecast')
        name = mechanism or self.selected
        if name == 'abstain': return (.5,.5)
        if name not in MECHANISMS: raise ValueError('unregistered counterfactual mechanism')
        model = self._model(name)
        return self._timed('predictor',lambda:tuple(probability(copy.deepcopy(model),a) for a in (0,1)))

    def record_verified(self, mechanism, gain, cost_seconds, observation_id, *, independently_verified=False):
        if independently_verified is not True: return False
        if mechanism not in MECHANISMS or not isinstance(observation_id,str) or not 1 <= len(observation_id) <= 128:
            raise ValueError('scoped verified observation required')
        if any(type(v) not in (float,int) or not math.isfinite(v) for v in (gain,cost_seconds)) or not -8 <= gain <= 8 or not 0 <= cost_seconds <= 3600:
            raise ValueError('bounded public quality and measured cost required')
        value = [mechanism,float(gain),float(cost_seconds)]
        if observation_id in self.verified_ids:
            if self.verified_ids[observation_id] != value: raise ValueError('contradictory verified computation observation')
            return False
        if len(self.verified_ids) >= 512: raise ValueError('verified evidence budget exhausted')
        self.verified_ids[observation_id] = value
        if self.config.use_memory:
            self.gains[mechanism].append(float(gain)); self.gains[mechanism] = self.gains[mechanism][-128:]
        return True

    def snapshot(self):
        if self.pending is not None: raise RuntimeError('snapshot requires settled public observation')
        payload = {'schema':SCHEMA,'config':asdict(self.config),'history':self.history,'gains':self.gains,
            'verified_ids':self.verified_ids,'decisions':self.decisions,'selected':self.selected,
            'logical_cursors':self.cursors,
            'last_exploration':self.last_exploration,'explorations':self.explorations}
        payload = json.loads(canonical(payload))
        return {'payload':payload,'sha256':digest(payload)}

    @classmethod
    def load(cls, document):
        payload = document.get('payload')
        if not isinstance(payload,dict) or payload.get('schema') != SCHEMA or document.get('sha256') != digest(payload):
            raise ValueError('modified adaptive snapshot')
        result = cls(AdaptiveConfig(**payload['config']))
        for action,outcome in payload['history']: result.ingest_public(action,outcome)
        for name,values in payload['gains'].items():
            if name not in MECHANISMS or not isinstance(values,list) or len(values)>128 or any(type(v) not in (int,float) or not math.isfinite(v) or not -8<=v<=8 for v in values):
                raise ValueError('invalid adaptive public utility history')
        if set(payload['gains']) != set(MECHANISMS): raise ValueError('missing adaptive mechanism history')
        if not isinstance(payload['decisions'],list) or len(payload['decisions'])>256 or any(
                row.get('decision_index') != i or row.get('mechanism') not in (*MECHANISMS,'abstain')
                or type(row.get('observed_prefix')) is not int or not 0<=row['observed_prefix']<=len(result.history)
                for i,row in enumerate(payload['decisions'])):
            raise ValueError('invalid adaptive decision history')
        if payload['selected'] not in (*MECHANISMS,'abstain'): raise ValueError('invalid selected computation')
        for key,value in payload['verified_ids'].items():
            result.record_verified(*value,key,independently_verified=True)
        result.gains = copy.deepcopy(payload['gains']); result.decisions = copy.deepcopy(payload['decisions'])
        if not isinstance(payload['logical_cursors'],dict) or any(k not in ('temporal','native') or type(v) is not int or not 0<=v<=len(result.history) for k,v in payload['logical_cursors'].items()):
            raise ValueError('invalid logical learner progress')
        result.cursors = dict(payload['logical_cursors'])
        result.selected = payload['selected']; result.last_exploration = payload['last_exploration']; result.explorations = payload['explorations']
        if type(result.explorations) is not int or not 0<=result.explorations<=len(result.decisions) or type(result.last_exploration) is not int or not -result.config.exploration_interval<=result.last_exploration<len(result.decisions):
            raise ValueError('invalid adaptive exploration state')
        return result
