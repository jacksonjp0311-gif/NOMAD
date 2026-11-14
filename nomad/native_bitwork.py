"""An explicit interface to the original BGR 1.4 binary temporal predictor.

This bridge predicts public-test outcomes in *shadow mode*. It never certifies a
repair and never replaces WITNESS. The binary action denotes a declared operator
class, not an arbitrary encoding of a many-way repair choice.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'vendor' / 'BGR-v1.4.0-runtime'
RUNTIME_ZIP = ROOT / 'vendor' / 'BGR-v1.4.0-runtime.zip'


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_native():
    """Load the preserved, immutable runtime—not a reimplementation of BGR."""
    if not (RUNTIME / 'bgr140' / 'engine.py').is_file():
        raise FileNotFoundError('BGR v1.4 source not vendored')
    if str(RUNTIME) not in sys.path:
        sys.path.insert(0, str(RUNTIME))
    m = importlib.import_module('bgr140')
    if not hasattr(m, 'GovernedBitworkV14'):
        raise RuntimeError('wrong BGR release')
    return m.GovernedBitworkV14


def action_for_family(family: str) -> int:
    """0=relational operator change, 1=other expression/operator change."""
    if not isinstance(family, str) or '→' not in family:
        raise ValueError('invalid observed edit family')
    before = family.split('→', 1)[0]
    return 0 if before in ('==', '!=', '>', '<', '<=', '>=', 'in', 'not in') else 1


def logloss(p: float, y: int) -> float:
    p = min(1-1e-9, max(1e-9, p))
    return -math.log(p if y else 1-p)


def shadow_study(rows: Iterable[dict]) -> dict:
    """Prequential, chronological replay from already executed public-test traces.

    No evaluator-only original-source label or hidden WITNESS result is supplied.
    The model predicts before each observation. The fixed comparator uses an
    action-conditional Laplace count, updated at the same time as BGR.
    """
    factory = load_native()
    bgr = factory()
    counts = [[1, 1], [1, 1]]
    events = []
    for row in rows:
        for trace in row['trace']:
            action = action_for_family(trace['edit_family'])
            y = int(trace['public_pass'])
            p_bgr = bgr.predict(action)
            p_fixed = counts[action][1] / sum(counts[action])
            bgr.observe(action, y)
            counts[action][y] += 1
            events.append(dict(action=action, observed=y, bgr_p=round(p_bgr, 10),
                               fixed_p=round(p_fixed, 10),
                               bgr_loss=logloss(p_bgr, y), fixed_loss=logloss(p_fixed, y),
                               source_task=row['id']))
    n = len(events)
    return {
        'schema':'nomad.bitwork.native-shadow.v1',
        'scope':'retrospective replay of v0.14 public-test executions, not independently held-out repair tasks',
        'action_semantics':{'0':'relational edit','1':'other edit'},
        'observed_label':'public_test_pass only; WITNESS acceptance is not supplied to BGR',
        'native_runtime_sha256': checksum(RUNTIME_ZIP),
        'model':'bgr140.GovernedBitworkV14',
        'events':n,
        'mean_bgr_logloss':sum(e['bgr_loss'] for e in events)/n if n else None,
        'mean_fixed_logloss':sum(e['fixed_loss'] for e in events)/n if n else None,
        'bgr_better_than_fixed':(sum(e['bgr_loss'] for e in events) < sum(e['fixed_loss'] for e in events)) if n else False,
        'external_repair_advantage':'NOT_ESTABLISHED — shadow predictor does not choose patches',
        'trace':events,
    }
