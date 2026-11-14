"""MNEMONIC v0.12: persistent, scoped, non-authoritative effect memory.

NOMAD remembers measured intervention consequences across generated Python
repository sessions.  A stored effect is a search hypothesis, never permission
or independent proof about a fresh repository. The sha256 chain detects local
accidental mutation only: it is NOT a cryptographic signature or secure store.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .causal_atlas import AtlasTask, ChangeReceipt, SymbolGraph, source_digest

SCHEMA = 'nomad.mnemonic.effect-ledger.v1'
FEATURE_SCHEMA = 'nomad.atlas.ast-signature.v1'
GENESIS_EPOCH = '0' * 64

# Fixed, explicit, one-hot coordinates: no Python hash randomization, no name
# features, and no inferred power beyond the supplied v0.11 AST grammar.
FEATURE_COORDINATES = (
    ('import','no_import'),
    ('called','not_called'),
    ('depth_0','depth_1','depth_2','depth_3','depth_absent'),
    ('zero_mask','no_zero_mask'),
    ('self_cancel','no_self_cancel'),
    ('conditional','no_conditional'),
)
_COORD = {item: sum(len(g) for g in FEATURE_COORDINATES[:i]) + j
          for i,group in enumerate(FEATURE_COORDINATES) for j,item in enumerate(group)}


def encode_features(features: tuple[str,...]) -> int | None:
    """Packed Bitwork-style state for the *supplied* AST coordinates.

    A missing, unknown, or duplicated coordinate is unrepresentable and must
    abstain. This is a small categorical bit state, not direct native BGR use.
    """
    if len(features) != len(FEATURE_COORDINATES): return None
    bits = 0
    for value,group in zip(features,FEATURE_COORDINATES):
        if value not in group: return None
        bits |= 1 << _COORD[value]
    return bits


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def action_digest(source: str) -> str:
    """Parse-only action identity: whitespace does not change identity.

    Source is *not executed* by this module. Never treat this parsing step as
    authorization to run untrusted source in the fixture execution harness.
    """
    tree = ast.parse(source)
    return hashlib.sha256((FEATURE_SCHEMA + '\n' + ast.dump(tree, include_attributes=False)).encode()).hexdigest()


@dataclass(frozen=True)
class Prediction:
    outcome: str  # impact / no_impact / abstain
    support_tasks: int
    status: str  # provisional / promoted / contested / expired / insufficient / unknown
    scope: str
    authority: str = 'prediction_only'

    def as_dict(self) -> dict:
        return dict(self.__dict__)


class EvidenceMemory:
    """Append-only witnessed-effect history with bounded temporal recall.

    A claim is promoted only with >= min_tasks distinct source task IDs whose
    observed outcomes unanimously agree for the identical AST action and
    graph-signature. Conflicting evidence marks that cell contested, rather
    than averaging away a counterexample. Unfamiliar cells always abstain.
    """
    def __init__(self, *, ttl_epochs: int = 4, min_tasks: int = 3, max_events: int = 20000):
        if ttl_epochs < 0 or min_tasks < 2 or max_events < 1:
            raise ValueError('invalid memory limits')
        self.ttl_epochs = ttl_epochs
        self.min_tasks = min_tasks
        self.max_events = max_events
        self.events: list[dict] = []
        self.head = GENESIS_EPOCH
        self._event_ids: set[str] = set()
        self.frozen = False

    def record(self, *, task: AtlasTask, contract: str, action_source: str,
               receipt: ChangeReceipt, capture_epoch: int) -> bool:
        if self.frozen:
            raise ValueError('frozen memory cannot admit new evidence')
        if not isinstance(capture_epoch, int) or isinstance(capture_epoch, bool) or capture_epoch < 0:
            raise ValueError('invalid capture epoch')
        if receipt.task_id != task.task_id or receipt.epoch != 0:
            raise ValueError('foreign or unexpected world epoch')
        if receipt.contract != contract or receipt.changed_file != task.changed_file:
            raise ValueError('receipt not bound to the requested intervention')
        if not receipt.verify():
            raise ValueError('invalid intervention receipt checksum')
        originals = source_digest(task.files)
        edited = source_digest({**task.files, task.changed_file: action_source})
        if originals != receipt.before_digest or edited != receipt.after_digest:
            raise ValueError('stale source snapshot or mismatched action')
        matches = [c for c in task.contracts if c.key == contract]
        if len(matches) != 1 or len(receipt.before) != len(matches[0].rows) or len(receipt.after) != len(matches[0].rows):
            raise ValueError('unrecognized or malformed contract')
        features = SymbolGraph(task.files).features(matches[0], task.changed_file)
        bits = encode_features(features)
        if bits is None:
            return False  # no fabricated positive or negative evidence
        act = action_digest(action_source)
        event_id = digest([act, task.task_id, contract, originals, capture_epoch])
        if event_id in self._event_ids:
            raise ValueError('duplicate effect observation')
        if len(self.events) >= self.max_events:
            raise ValueError('memory admission budget exceeded')
        evidence = {
            'event_id': event_id,
            'action': act, 'features': list(features), 'state_bits': bits,
            'task_id': task.task_id, 'contract': contract,
            'source_digest': originals, 'edited_digest': edited,
            'receipt_digest': receipt.receipt_digest,
            'world_epoch': receipt.epoch, 'capture_epoch': capture_epoch,
            'changed': bool(receipt.changed),
        }
        row = {'evidence': evidence, 'previous': self.head}
        row['sha256'] = digest(row)
        self.events.append(row)
        self.head = row['sha256']
        self._event_ids.add(event_id)
        return True

    def recall(self, *, action_source: str, features: tuple[str, ...], now_epoch: int,
               target_task_id: str | None = None) -> Prediction:
        if not isinstance(now_epoch, int) or isinstance(now_epoch, bool) or now_epoch < 0:
            raise ValueError('invalid observation epoch')
        act = action_digest(action_source)
        scope = digest([FEATURE_SCHEMA, act, list(features)])[:16]
        bits = encode_features(tuple(features))
        if bits is None:
            return Prediction('abstain', 0, 'unknown', scope)
        matched = [x['evidence'] for x in self.events
                   if x['evidence']['action'] == act and x['evidence']['state_bits'] == bits
                   and x['evidence']['task_id'] != target_task_id]
        valid = [e for e in matched if 0 <= now_epoch - e['capture_epoch'] <= self.ttl_epochs]
        if matched and not valid:
            return Prediction('abstain', 0, 'expired', scope)
        by_task: dict[str, set[bool]] = {}
        for e in valid:
            by_task.setdefault(e['task_id'], set()).add(e['changed'])
        if any(len(y) > 1 for y in by_task.values()):
            return Prediction('abstain', len(by_task), 'contested', scope)
        values = {next(iter(y)) for y in by_task.values()}
        if len(values) > 1:
            return Prediction('abstain', len(by_task), 'contested', scope)
        support = len(by_task)
        if not values or support < self.min_tasks:
            return Prediction('abstain', support, 'insufficient', scope)
        return Prediction('impact' if True in values else 'no_impact', support, 'promoted', scope)

    def freeze(self) -> None:
        self.frozen = True

    def fork(self) -> "EvidenceMemory":
        """New candidate epoch; preserve immutable predecessor evidence."""
        other = EvidenceMemory(ttl_epochs=self.ttl_epochs, min_tasks=self.min_tasks, max_events=self.max_events)
        other.events = json.loads(json.dumps(self.events))
        other.head = self.head
        other._event_ids = set(self._event_ids)
        return other

    def snapshot(self) -> dict:
        return {
            'schema': SCHEMA,
            'feature_schema': FEATURE_SCHEMA,
            'ttl_epochs': self.ttl_epochs,
            'min_tasks': self.min_tasks,
            'max_events': self.max_events,
            'frozen': self.frozen,
            'events': self.events,
            'head': self.head,
        }

    def save(self, path: str | Path) -> str:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = self.snapshot()
        document = {'payload': body, 'payload_sha256': digest(body)}
        temp = path.with_name(path.name + '.tmp')
        temp.write_text(json.dumps(document, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temp, path)
        return document['payload_sha256']

    @classmethod
    def load(cls, path: str | Path) -> 'EvidenceMemory':
        outer = json.loads(Path(path).read_text(encoding='utf-8'))
        body = outer['payload']
        if digest(body) != outer['payload_sha256']:
            raise ValueError('memory payload changed')
        if body.get('schema') != SCHEMA or body.get('feature_schema') != FEATURE_SCHEMA:
            raise ValueError('unknown memory schema')
        memory = cls(ttl_epochs=body['ttl_epochs'], min_tasks=body['min_tasks'], max_events=body['max_events'])
        previous = GENESIS_EPOCH
        seen = set()
        if len(body['events']) > memory.max_events:
            raise ValueError('memory exceeds event budget')
        for row in body['events']:
            ev = row['evidence']
            if row['previous'] != previous or digest({'evidence': ev, 'previous': previous}) != row['sha256']:
                raise ValueError('memory chain mismatch')
            if ev['event_id'] in seen:
                raise ValueError('duplicate memory event')
            if not isinstance(ev['capture_epoch'], int) or isinstance(ev['capture_epoch'], bool) or ev['capture_epoch'] < 0:
                raise ValueError('malformed memory epoch')
            if not isinstance(ev['changed'], bool) or not isinstance(ev['features'], list):
                raise ValueError('invalid effect evidence')
            if encode_features(tuple(ev['features'])) != ev.get('state_bits'):
                raise ValueError('binary state does not match evidence')
            seen.add(ev['event_id'])
            previous = row['sha256']
        if previous != body['head']:
            raise ValueError('memory head mismatch')
        memory.events = body['events']
        memory.head = previous
        memory._event_ids = seen
        memory.frozen = bool(body['frozen'])
        return memory
