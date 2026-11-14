"""GENESIS v0.10 verified-prior persistence.

Checksum detects accidental drift, not malicious rewriting of both payload and
checksum. Only learning from witnessed outcomes is admitted by GrammarPrior.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .genesis import GrammarPrior
from .learner import Counts

_ALLOWED_OPS={'Add','Sub','Mult'}


def _serialized(payload:dict) -> bytes:
    return json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def save_prior(path:Path,prior:GrammarPrior) -> str:
    payload=prior.snapshot()
    sha=hashlib.sha256(_serialized(payload)).hexdigest()
    record={'schema':'nomad.genesis.learned-prior-receipt.v1','sha256':sha,'prior':payload}
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n',encoding='utf8')
    os.replace(temp,path)
    return sha


def load_prior(path:Path) -> GrammarPrior:
    data=json.loads(Path(path).read_text(encoding='utf8'))
    if data.get('schema')!='nomad.genesis.learned-prior-receipt.v1':
        raise ValueError('unknown prior receipt schema')
    payload=data['prior']
    if hashlib.sha256(_serialized(payload)).hexdigest()!=data['sha256']:
        raise ValueError('learned-prior checksum mismatch')
    if payload.get('schema')!='nomad.v0.10.grammar-prior.v1':
        raise ValueError('unknown model schema')
    model=payload['operator']
    prior=GrammarPrior(contextual=payload['contextual'])
    if model.get('contextual')!=payload['contextual']:
        raise ValueError('model mode mismatch')
    for name,record in model['global'].items():
        if name not in _ALLOWED_OPS:raise ValueError('unknown grammar op')
        prior.operator.global_counts[name]=_counts(record)
    for key,record in model['contexts'].items():
        sid,family=key.split(':',1)
        if family not in _ALLOWED_OPS:raise ValueError('unknown grammar op')
        context=int(sid)
        if context<0:raise ValueError('invalid context')
        prior.operator.context_counts[(context,family)]=_counts(record)
    prior.witnessed=payload['witnessed']
    if not isinstance(prior.witnessed,int) or prior.witnessed<0:
        raise ValueError('invalid witness support count')
    return prior


def _counts(value:dict) -> Counts:
    s=value['success'];f=value['failure']
    if not isinstance(s,int) or isinstance(s,bool) or not isinstance(f,int) or isinstance(f,bool) or min(s,f)<0:
        raise ValueError('invalid count')
    return Counts(s,f)
