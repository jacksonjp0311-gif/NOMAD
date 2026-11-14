"""Fenced external-effect journal: conservative recovery for side effects.

A prepared effect is not proof of execution. After DISPATCHED, a restart MUST
HOLD if authoritative readback cannot distinguish executed from unexecuted.
This library does not promise exactly-once external effects: that requires a
remote service that enforces idempotency tokens/fencing and supports readback.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterator
import json
import re
import secrets

from .mission_runtime import MissionHold, canonical, digest, exclusive_owner, save_atomic

SCHEMA = 'nomad.effects.event.v1'
TYPES = frozenset(('read_only', 'idempotent_write', 'non_idempotent_external'))
ID_RE = re.compile(r'^[a-zA-Z0-9_.:-]{1,128}$')
HEX_RE = re.compile(r'^[a-f0-9]{64}$')


@dataclass
class Owner:
    epoch: int
    nonce: str
    active: bool = True


class EffectLedger:
    def __init__(self, root: Path, *, create: bool = True):
        self.root = Path(root)
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        elif not self.root.is_dir() or not (self.root / 'effects.jsonl').is_file():
            raise MissionHold('required external-effect ledger missing')
        self.events = self.root / 'effects.jsonl'
        self.owner_file = self.root / 'owner-epoch.json'
        if create and not self.events.exists():
            self.events.touch(exist_ok=False)

    def _owner_epoch(self) -> int:
        if not self.owner_file.exists():
            return 0
        try:
            rec=json.loads(self.owner_file.read_bytes())
            if rec.get('schema')!='nomad.effects.owner.v1' or type(rec.get('epoch')) is not int or rec['epoch'] < 1:
                raise ValueError('bad epoch record')
            claim=rec.pop('sha256')
            if digest(canonical(rec)) != claim:
                raise ValueError('epoch checksum mismatch')
            return rec['epoch']
        except (ValueError, KeyError, TypeError) as e:
            raise MissionHold('owner epoch record invalid') from e

    @contextmanager
    def ownership(self) -> Iterator[Owner]:
        with exclusive_owner(self.root):
            # Check journal chain before advancing the durable fencing epoch.
            self._states()
            epoch=self._owner_epoch()+1
            rec={'schema':'nomad.effects.owner.v1','epoch':epoch}
            save_atomic(self.owner_file, canonical({**rec,'sha256':digest(canonical(rec))}))
            owner=Owner(epoch,secrets.token_hex(16))
            try:
                yield owner
            finally:
                owner.active=False

    def _require(self, owner:Owner):
        if not owner.active or owner.epoch != self._owner_epoch():
            raise MissionHold('stale external-effect owner or fencing epoch')

    def _records(self) -> list[dict]:
        last='0'*64
        rows=[]
        with self.events.open('rb') as f:
            for line, raw in enumerate(f, 1):
                if not raw.endswith(b'\n'):
                    raise MissionHold('truncated external-effect record')
                try:
                    obj=json.loads(raw)
                    payload={k:v for k,v in obj.items() if k!='sha256'}
                    expected=digest(canonical(payload))
                    if (obj.get('sha256')!=expected or payload.get('schema')!=SCHEMA
                        or payload.get('seq')!=line or payload.get('prev')!=last):
                        raise ValueError('event mismatch')
                except (ValueError, KeyError, TypeError) as e:
                    raise MissionHold('external-effect journal corrupted') from e
                rows.append(obj)
                last=expected
        return rows

    def _states(self) -> dict[str,dict]:
        states={}
        for row in self._records():
            event=row['event']
            eid=row['id']
            if event=='PREPARED':
                if eid in states or row['type'] not in TYPES or not HEX_RE.fullmatch(row['request_sha256']):
                    raise MissionHold('invalid effect preparation')
                states[eid]={'state':'PREPARED','type':row['type'],
                             'request_sha256':row['request_sha256'], 'epoch':row['epoch']}
            elif event=='DISPATCHED':
                if eid not in states or states[eid]['state']!='PREPARED':
                    raise MissionHold('duplicate or unprepared external dispatch')
                states[eid]['state']='UNCERTAIN'
                states[eid]['epoch']=row['epoch']
            elif event in ('CONFIRMED_APPLIED','CONFIRMED_NOT_APPLIED'):
                if eid not in states or states[eid]['state'] not in ('UNCERTAIN','PREPARED'):
                    raise MissionHold('invalid external reconciliation')
                if event=='CONFIRMED_NOT_APPLIED' and states[eid]['state']=='PREPARED':
                    pass
                if not HEX_RE.fullmatch(row['evidence_sha256']):
                    raise MissionHold('invalid reconciliation evidence')
                states[eid]['state']='APPLIED' if event=='CONFIRMED_APPLIED' else 'NOT_APPLIED'
                states[eid]['evidence_sha256']=row['evidence_sha256']
            else:
                raise MissionHold('unexpected external-effect event')
        return states

    def _append(self, event:str, effect_id:str, owner:Owner, extra:dict):
        self._require(owner)
        rows=self._records()
        payload={'schema':SCHEMA,'seq':len(rows)+1,'prev':rows[-1]['sha256'] if rows else '0'*64,
                 'event':event,'id':effect_id,'epoch':owner.epoch,**extra}
        obj={**payload,'sha256':digest(canonical(payload))}
        with self.events.open('ab') as f:
            f.write(canonical(obj)+b'\n')
            f.flush()
            import os
            os.fsync(f.fileno())

    def prepare(self, owner:Owner, effect_id:str, effect_type:str, request_sha256:str) -> str:
        self._require(owner)
        if not ID_RE.fullmatch(effect_id) or effect_type not in TYPES or not HEX_RE.fullmatch(request_sha256):
            raise ValueError('effect identity, type or request hash invalid')
        states=self._states()
        if effect_id in states:
            raise MissionHold('effect already known: replay refused')
        if any(s['state'] in ('UNCERTAIN','PREPARED') for s in states.values()):
            raise MissionHold('unresolved effect blocks new external operation')
        self._append('PREPARED',effect_id,owner,{'type':effect_type,'request_sha256':request_sha256})
        return f'{owner.epoch}:{effect_id}'

    def dispatch(self, owner:Owner, effect_id:str) -> str:
        self._require(owner)
        state=self._states().get(effect_id)
        if state is None or state['state']!='PREPARED':
            raise MissionHold('cannot dispatch unprepared, repeated or uncertain effect')
        # This event MUST be fsynced BEFORE an external call. On restart, the
        # effect remains uncertain even if process died before actual dispatch.
        self._append('DISPATCHED',effect_id,owner,{})
        return f'{owner.epoch}:{effect_id}'

    def reconcile(self, owner:Owner, effect_id:str, *, was_applied:bool,
                  evidence_sha256:str,
                  independent_check:Callable[[str, bool, str], bool]|None=None) -> None:
        self._require(owner)
        state=self._states().get(effect_id)
        if state is None or state['state'] not in ('UNCERTAIN','PREPARED'):
            raise MissionHold('no uncertain effect to reconcile')
        if state['state']=='PREPARED' and was_applied:
            raise MissionHold('cannot claim applied before dispatch')
        if not HEX_RE.fullmatch(evidence_sha256):
            raise ValueError('missing evidence digest')
        if independent_check is None or independent_check(effect_id,was_applied,evidence_sha256) is not True:
            raise MissionHold('independent external readback missing or disagrees')
        self._append('CONFIRMED_APPLIED' if was_applied else 'CONFIRMED_NOT_APPLIED',
                     effect_id,owner,{'evidence_sha256':evidence_sha256})

    def snapshot(self) -> dict:
        states=self._states()
        uncertain=sorted(k for k,v in states.items() if v['state'] in ('UNCERTAIN','PREPARED'))
        return {'schema':'nomad.effects.status.v1','owner_epoch':self._owner_epoch(),
                'states':{k:v['state'] for k,v in sorted(states.items())},
                'hold_uncertain':uncertain,'replay_safe':not uncertain}
