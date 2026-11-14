"""v0.18 native Bitwork decision preference, with no verification authority.

Only the trusted controller supplies observed public-execution evidence. Hashes
detect accidental alteration; they do not authenticate a hostile host writer.
This ranks already enumerated transformations. It never accepts a patch, admits
a skill, bypasses WITNESS, or treats a public test pass as repair correctness.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import copy
import hashlib
import json
import random
from pathlib import Path

from .native_bitwork import load_native, verified_runtime_identity

SCHEMA = 'nomad.platform.bitwork-evidence.v1'
MODES = ('cold', 'frequency', 'native', 'shuffled')


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _sha(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def action_for_candidate(candidate) -> int:
    """Original BGR action semantics: relational edit=0, other expression=1."""
    family = candidate if isinstance(candidate, str) else candidate.family
    if not isinstance(family, str) or not family:
        raise ValueError('candidate requires an explicit edit family')
    before = family.split('→', 1)[0]
    return 0 if before in ('==', '!=', '>', '<', '<=', '>=', 'in', 'not in',
                           'Eq', 'NotEq', 'Gt', 'Lt', 'GtE', 'LtE', 'In', 'NotIn',
                           'Compare', 'comparison') else 1


@dataclass(frozen=True)
class PublicObservation:
    task_id: str
    source_sha256: str
    candidate_sha256: str
    receipt_sha256: str
    family: str
    outcome: bool
    capture_epoch: int

    def validate(self) -> None:
        if (not isinstance(self.task_id, str) or not self.task_id or
            not all(_sha(v) for v in (self.source_sha256, self.candidate_sha256, self.receipt_sha256)) or
            type(self.outcome) is not bool or type(self.capture_epoch) is not int or self.capture_epoch < 0):
            raise ValueError('malformed public observation')
        action_for_candidate(self.family)


class NativeDecisionRanker:
    """Bounded native predictor rebuilt from eligible distinct observations.

    Public outcomes can legitimately vary between different candidates in one
    coarse action class. A contradictory report about the *same source and
    candidate* contests that observation and excludes it. Independent support
    requires distinct task and source IDs. Cached/replayed receipts never count
    again and never renew expiry. Shuffled mode is an experiment control only.
    """
    def __init__(self, mode: str = 'native', *, ttl_epochs: int = 4,
                 min_tasks: int = 2, max_events: int = 512, seed: int = 18018,
                 action_schema: str = 'relational-vs-other'):
        if (mode not in MODES or type(ttl_epochs) is not int or ttl_epochs < 0 or
                type(min_tasks) is not int or min_tasks < 2 or
                type(max_events) is not int or max_events < 1):
            raise ValueError('invalid native decision configuration')
        if action_schema not in ('relational-vs-other', 'genesis-vs-ast'):
            raise ValueError('unsupported native action semantics')
        self.mode, self.ttl_epochs, self.min_tasks = mode, ttl_epochs, min_tasks
        self.max_events, self.seed = max_events, seed
        self.action_schema = action_schema
        self.events: list[PublicObservation] = []
        self.contested: set[tuple[str, str]] = set()
        self._cache = None

    def _action(self, candidate) -> int:
        if self.action_schema == 'relational-vs-other':
            return action_for_candidate(candidate)
        family = candidate if isinstance(candidate, str) else candidate.family
        from .python_operators import PY_FAMILIES
        if family == 'GENESIS':
            return 0
        if family in PY_FAMILIES:
            return 1
        raise ValueError('evidence outside declared GENESIS-versus-AST action scope')

    def observe(self, observation: PublicObservation, *, independently_observed: bool = False) -> bool:
        if independently_observed is not True:
            return False
        observation.validate()
        self._action(observation.family)
        key = (observation.source_sha256, observation.candidate_sha256)
        for old in self.events:
            if (old.source_sha256, old.candidate_sha256) == key:
                if old.outcome != observation.outcome:
                    self.contested.add(key)
                    self._cache = None
                return False
            if old.receipt_sha256 == observation.receipt_sha256:
                return False
        if len(self.events) >= self.max_events:
            raise ValueError('native predictor observation budget exhausted')
        self.events.append(observation)
        self._cache = None
        return True

    def _eligible(self, now_epoch: int) -> list[PublicObservation]:
        if type(now_epoch) is not int or now_epoch < 0:
            raise ValueError('invalid decision epoch')
        return [o for o in self.events
                if 0 <= now_epoch - o.capture_epoch <= self.ttl_epochs
                and (o.source_sha256, o.candidate_sha256) not in self.contested]

    def _model(self, now_epoch: int):
        rows = self._eligible(now_epoch)
        support = min(len({o.task_id for o in rows}), len({o.source_sha256 for o in rows}))
        if self._cache and self._cache[0] == now_epoch:
            return self._cache[1:]
        counts = [[1, 1], [1, 1]]
        native = load_native()() if self.mode in ('native', 'shuffled') else None
        labels = [int(o.outcome) for o in rows]
        if self.mode == 'shuffled':
            random.Random(self.seed).shuffle(labels)
        for observation, label in zip(rows, labels):
            action = self._action(observation.family)
            if native is not None:
                native.predict(action)  # original predict-before-observe contract
                native.observe(action, label)
            counts[action][label] += 1
        self._cache = (now_epoch, native, counts, support, len(rows))
        return self._cache[1:]

    def probabilities(self, *, now_epoch: int = 0) -> tuple[float, float]:
        native, counts, support, _ = self._model(now_epoch)
        if self.mode == 'cold' or support < self.min_tasks:
            return (0.5, 0.5)
        if native is not None:
            # BGR predict reserves a pending observation. Counterfactual action
            # scores therefore use separate copies; do not fabricate labels to
            # clear the pending state or mutate the chronological predictor.
            return tuple(float(copy.deepcopy(native).predict(action)) for action in (0, 1))
        return tuple(c[1] / sum(c) for c in counts)

    def rank(self, candidates, *, now_epoch: int = 0) -> list:
        items = list(candidates)
        if len(items) > 10000:
            raise ValueError('candidate ranking budget exceeded')
        probabilities = self.probabilities(now_epoch=now_epoch)
        return [item for _, item in sorted(enumerate(items), key=lambda row:
                (-probabilities[self._action(row[1])], row[0]))]

    def summary(self, *, now_epoch: int = 0) -> dict:
        _, _, support, eligible = self._model(now_epoch)
        return {'mode': self.mode, 'authority': 'ranking_only', 'independent_tasks': support,
                'action_schema': self.action_schema,
                'eligible_observations': eligible, 'contested_observations': len(self.contested),
                'status': 'active' if support >= self.min_tasks and self.mode != 'cold' else 'cold',
                'action_probabilities': self.probabilities(now_epoch=now_epoch),
                'external_repair_advantage': 'NOT_ESTABLISHED'}

    def snapshot(self) -> dict:
        core = {'schema': SCHEMA, 'mode': self.mode, 'ttl_epochs': self.ttl_epochs,
                'min_tasks': self.min_tasks, 'max_events': self.max_events, 'seed': self.seed,
                'action_schema': self.action_schema,
                'events': [asdict(o) for o in self.events], 'contested': sorted(self.contested)}
        return {'payload': core, 'sha256': digest(core)}

    @classmethod
    def load(cls, document: dict) -> 'NativeDecisionRanker':
        core = document['payload']
        if core.get('schema') != SCHEMA or document.get('sha256') != digest(core):
            raise ValueError('modified or unsupported Bitwork evidence')
        ranker = cls(**{k: core[k] for k in ('mode', 'ttl_epochs', 'min_tasks', 'max_events', 'seed', 'action_schema')})
        for event in core['events']:
            if not ranker.observe(PublicObservation(**event), independently_observed=True):
                raise ValueError('repeated observation in saved evidence')
        keys = {(o.source_sha256, o.candidate_sha256) for o in ranker.events}
        for key in core['contested']:
            if not isinstance(key, (list, tuple)) or len(key) != 2 or tuple(key) not in keys:
                raise ValueError('invalid contested observation')
            ranker.contested.add(tuple(key))
        return ranker
