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
    # Check bytes before importing executable vendored code. The manifest is a
    # local integrity anchor, not an authenticated signature against a host
    # administrator who can replace both the sources and the manifest.
    verified_runtime_identity()
    runtime_root = RUNTIME.resolve()
    namespaces = {p.name for p in RUNTIME.iterdir() if p.is_dir() and p.name.startswith('bgr')}
    for name, module in tuple(sys.modules.items()):
        if name.split('.')[0] in namespaces and module is not None:
            origin = getattr(module, '__file__', None)
            if origin is None or not Path(origin).resolve().is_relative_to(runtime_root):
                raise RuntimeError('preloaded BGR module is outside preserved runtime: ' + name)
    if str(RUNTIME) not in sys.path:
        sys.path.insert(0, str(RUNTIME))
    m = importlib.import_module('bgr140')
    if not hasattr(m, 'GovernedBitworkV14'):
        raise RuntimeError('wrong BGR release')
    if not Path(m.__file__).resolve().is_relative_to(runtime_root):
        raise RuntimeError('BGR import is outside preserved runtime')
    return m.GovernedBitworkV14


def verified_runtime_identity() -> dict:
    """Read-only verification of every entry in the original runtime manifest."""
    manifest = RUNTIME / 'MANIFEST.sha256'
    checked = 0
    for line in manifest.read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        path = RUNTIME / relative
        if (not path.resolve().is_relative_to(RUNTIME.resolve()) or path.is_symlink()
                or not path.is_file() or checksum(path) != expected):
            raise ValueError('preserved BGR runtime integrity failure: ' + relative)
        checked += 1
    if not checked:
        raise ValueError('empty BGR runtime manifest')
    return {'runtime': 'bgr140.GovernedBitworkV14', 'manifest_sha256': checksum(manifest),
            'verified_files': checked, 'authority': 'local_integrity_only'}


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
