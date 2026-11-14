"""NOMAD v0.16 MISSION RUNTIME.

Durable, content-addressed coding missions for explicitly trusted CodeWorld fixtures.
This is a research execution controller, not an adversarial sandbox or a general
multi-file coding agent. It reuses v0.7 AST repair candidates, public unittest
execution, v0.6 independent WITNESS, and separate final evidence. Events are
append-only and fsynced. Source edits use content-addressed atomic replacement.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator
import json
import os
import sys
import tempfile

from .codeworld import CodeWorldExample, CodeWorldTask, materialize
from .python_operators import PY_FAMILIES, generate_python_candidates
from .witness import WitnessReceipt
from .supervised import minimal_env, run_supervised

SCHEMA = 'nomad.mission.event.v1'
GOAL_SCHEMA = 'nomad.mission.goal.v1'
RELEASE = '0.16.0'


class MissionHold(RuntimeError):
    pass


class InjectedInterruption(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def save_atomic(path: Path, content: bytes) -> None:
    """Write, fsync and replace within the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        if os.name == 'posix':
            dfd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def exclusive_owner(root: Path) -> Iterator[None]:
    """Kernel-released, nonblocking exclusive ownership across processes."""
    lock = root / 'mission.lock'
    with lock.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            if not handle.read(1):
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as ex:
                raise MissionHold('mission already owned by another process') from ex
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as ex:
                raise MissionHold('mission already owned by another process') from ex
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class Journal:
    def __init__(self, path: Path, mission_id: str):
        self.path = path
        self.mission_id = mission_id

    def read(self) -> list[dict]:
        if not self.path.is_file():
            raise MissionHold('mission journal missing')
        records = []
        last = '0' * 64
        with self.path.open('rb') as f:
            for number, raw in enumerate(f, start=1):
                if not raw.endswith(b'\n'):
                    raise MissionHold('truncated journal row')
                try:
                    obj = json.loads(raw)
                    payload = {k:v for k,v in obj.items() if k != 'sha256'}
                    expected = digest(canonical(payload))
                except (ValueError, TypeError, UnicodeDecodeError) as e:
                    raise MissionHold('unparseable journal row') from e
                if (payload.get('schema') != SCHEMA or
                    payload.get('mission_id') != self.mission_id or
                    payload.get('seq') != number or
                    payload.get('prev') != last or
                    obj.get('sha256') != expected):
                    raise MissionHold('journal chain or identity mismatch')
                records.append(obj)
                last = expected
        return records

    def append(self, kind: str, data: dict) -> dict:
        rows = self.read()
        obj = {
            'schema': SCHEMA, 'mission_id': self.mission_id,
            'seq': len(rows) + 1, 'prev': rows[-1]['sha256'] if rows else '0'*64,
            'kind': kind, 'data': data,
        }
        obj['sha256'] = digest(canonical(obj))
        with self.path.open('ab') as f:
            f.write(canonical(obj) + b'\n')
            f.flush()
            os.fsync(f.fileno())
        return obj


@dataclass(frozen=True)
class Edit:
    ordinal: int
    family: str
    source: str
    sha256: str
    description: str

    @property
    def transmission_id(self) -> str:
        return digest(canonical({'ordinal': self.ordinal,
                                 'family': self.family, 'candidate': self.sha256}))[:32]


def edits_from_source(original: str) -> list[Edit]:
    groups = generate_python_candidates(original)
    out: list[Edit] = []
    for family in PY_FAMILIES:
        for candidate in groups[family]:
            out.append(Edit(len(out)+1, family, candidate.source,
                            digest(candidate.source.encode()), candidate.description))
    return out


def initialize(root: Path, task: CodeWorldTask, *, budget: int = 40) -> dict:
    if budget <= 0 or budget > 200:
        raise ValueError('mission budget outside bounded research range')
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    sealed = {
        'schema':'nomad.mission.sealed.v1', 'task_id': task.task_id,
        'challenge': [{'inputs': x.inputs, 'expected': x.expected} for x in task.challenge],
        'final': [{'inputs': x.inputs, 'expected': x.expected} for x in task.final],
    }
    if not task.public or not task.challenge or not task.final:
        raise ValueError('public, challenge and final partitions required')
    sealed_bytes = canonical(sealed)
    save_atomic(root / 'sealed' / 'withheld.json', sealed_bytes)
    goal = {
        'schema': GOAL_SCHEMA, 'version': RELEASE, 'task_id': task.task_id,
        'mission_id': digest(canonical({'task': task.task_id,
                                        'original': digest(task.source.encode()),
                                        'public': [dict(inputs=x.inputs,expected=x.expected) for x in task.public]}))[:32],
        'original_sha256': digest(task.source.encode()),
        'sealed_sha256': digest(sealed_bytes),
        'budget': budget,
        'public': [{'inputs':x.inputs, 'expected':x.expected} for x in task.public],
        'candidate_count': len(edits_from_source(task.source)),
        'workload': 'explicitly trusted synthetic CodeWorld fixture, single solution.py',
    }
    save_atomic(root / 'original.py', task.source.encode())
    materialize(task, root / 'workspace')
    goal['public_tests_sha256'] = digest((root/'workspace'/'tests'/'test_public.py').read_bytes())
    # v0.17 adds a distinct journal for potentially external effects. Existing
    # v0.16 missions (without this marker) remain readable.
    from .effects import EffectLedger
    EffectLedger(root / 'effects')
    goal['external_effect_ledger_required'] = True
    save_atomic(root / 'goal.json', canonical(goal))
    journal_path = root / 'events.jsonl'
    journal_path.touch(exist_ok=False)
    j = Journal(journal_path, goal['mission_id'])
    j.append('MISSION_CREATED', {'goal_sha256':digest(canonical(goal)),
                                 'baseline_sha256':goal['original_sha256'],
                                 'candidate_count':goal['candidate_count']})
    return goal


def _read_goal(root: Path) -> dict:
    goal = json.loads((root / 'goal.json').read_text())
    if goal.get('schema') != GOAL_SCHEMA or goal.get('version') != RELEASE:
        raise MissionHold('unknown or altered mission version')
    if digest((root / 'original.py').read_bytes()) != goal['original_sha256']:
        raise MissionHold('original source changed')
    if digest((root / 'sealed' / 'withheld.json').read_bytes()) != goal['sealed_sha256']:
        raise MissionHold('withheld evaluation partition changed')
    if digest((root/'workspace'/'tests'/'test_public.py').read_bytes()) != goal['public_tests_sha256']:
        raise MissionHold('public test contract changed')
    return goal


def _events_per_attempt(rows: list[dict], edits: list[Edit], goal: dict) -> dict[int, dict[str, dict]]:
    """Reconstruct and validate transitions, rejecting skips, duplicates and future claims."""
    if not rows or rows[0]['kind'] != 'MISSION_CREATED' or rows[0]['data'] != {
        'goal_sha256':digest(canonical(goal)), 'baseline_sha256':goal['original_sha256'],
        'candidate_count':len(edits)}:
        raise MissionHold('mission origin not pinned')
    allowed = ('ATTEMPT_PLANNED','PATCH_APPLIED','PUBLIC_RESULT','WITNESS_RESULT',
               'FINAL_RESULT','PATCH_REVERTED','COMPLETED','EXHAUSTED')
    attempts: dict[int, dict[str, dict]] = {}
    prev_done = True
    terminal = False
    last_index = 0
    for row in rows[1:]:
        kind = row['kind']
        data = row['data']
        if terminal or kind not in allowed:
            raise MissionHold('invalid or after-terminal journal event')
        if kind == 'EXHAUSTED':
            if not prev_done or data.get('attempts') != last_index:
                raise MissionHold('premature exhaustion')
            terminal = True
            continue
        i = data.get('attempt')
        if type(i) is not int or i < 1 or i > len(edits) or i > goal['budget']:
            raise MissionHold('invalid attempt in journal')
        if kind == 'ATTEMPT_PLANNED':
            if not prev_done or i != last_index + 1:
                raise MissionHold('attempts out of order')
            edit = edits[i-1]
            if data != {'attempt': i, 'candidate_sha256': edit.sha256,
                        'transmission_id': edit.transmission_id, 'family':edit.family}:
                raise MissionHold('mismatched candidate provenance')
            attempts[i] = {kind:data}
            prev_done = False
            last_index = i
            continue
        if i != last_index or i not in attempts:
            raise MissionHold('observation without planned action')
        state = attempts[i]
        if kind in state:
            raise MissionHold('repeated logical action event')
        req = {
            'PATCH_APPLIED':'ATTEMPT_PLANNED',
            'PUBLIC_RESULT':'PATCH_APPLIED',
            'WITNESS_RESULT':'PUBLIC_RESULT',
            'FINAL_RESULT':'WITNESS_RESULT',
            'PATCH_REVERTED':'PATCH_APPLIED',
            'COMPLETED':'FINAL_RESULT',
        }
        if req.get(kind) not in state:
            raise MissionHold('out-of-order action event')
        if kind == 'WITNESS_RESULT' and state['PUBLIC_RESULT'].get('passed') is not True:
            raise MissionHold('witness without passing public tests')
        if kind == 'FINAL_RESULT' and state['WITNESS_RESULT'].get('supported') is not True:
            raise MissionHold('final check without passing witness')
        if kind == 'COMPLETED':
            if state['FINAL_RESULT'].get('supported') is not True:
                raise MissionHold('completion despite failed final verification')
            terminal = True
        if kind == 'PATCH_REVERTED':
            if (state.get('PUBLIC_RESULT',{}).get('passed') is True and
                state.get('WITNESS_RESULT',{}).get('supported') is not False and
                state.get('FINAL_RESULT',{}).get('supported') is not False):
                raise MissionHold('rollback without negative observation')
            prev_done = True
        state[kind] = data
    return attempts


def _replace_content(source_path: Path, candidate: str, original_sha: str,
                     desired_sha: str) -> bool:
    current = digest(source_path.read_bytes())
    if current == desired_sha:
        return False
    if current != original_sha:
        raise MissionHold('workspace source changed outside mission ownership')
    save_atomic(source_path, candidate.encode())
    return True


def _public_tests(root: Path, *, timeout_s: float) -> dict:
    """Trusted fixtures only. Isolated unfamiliar repositories use nomad.isolation."""
    command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-q']
    result = run_supervised(command, cwd=root/'workspace', timeout_s=timeout_s,
                            env=minimal_env(), max_output_bytes=262144)
    return {'passed':result.returncode == 0 and not result.timed_out,
            'returncode':result.returncode, 'output_sha256':result.output_sha256,
            'timed_out':result.timed_out}


def _observer(root: Path, goal: dict, edit: Edit, stage: str, timeout_s: float) -> dict:
    command = [sys.executable, '-B', '-m','nomad.mission_witness',
               '--root',str(root),'--stage',stage,
               '--task-id',goal['task_id'], '--transmission-id',edit.transmission_id,
               '--candidate-sha256',edit.sha256, '--trusted-fixture']
    repo=Path(__file__).resolve().parents[1]
    env=minimal_env({'PYTHONPATH':str(repo)})
    p=run_supervised(command, cwd=repo, env=env, timeout_s=timeout_s,
                     max_output_bytes=262144)
    if p.timed_out:
        raise MissionHold('independent verifier timed out; outcome uncertain')
    if p.returncode:
        raise MissionHold('independent verifier refused; '+p.output.decode(errors='replace')[-200:])
    try:
        data=json.loads(p.output.decode())
        expected = digest(canonical({k:v for k,v in data.items() if k != 'observation_sha256'}))
        if (data.get('schema')!='nomad.mission.observation.v1' or
            data['stage']!=stage or data['task_id']!=goal['task_id'] or
            data['transmission_id']!=edit.transmission_id or
            data['candidate_sha256']!=edit.sha256 or
            data['observation_sha256']!=expected):
            raise ValueError('observer identity or checksum mismatch')
        if stage == 'witness':
            receipt = WitnessReceipt(**data['receipt'])
            if not receipt.verify_checksum() or receipt.supported != data['supported']:
                raise ValueError('witness attestation invalid')
        return data
    except (ValueError, KeyError, TypeError) as ex:
        raise MissionHold('independent observation malformed') from ex


def _summary(goal:dict, rows:list[dict], state: str, *, info: str|None=None)->dict:
    attempted = [r for r in rows if r['kind']=='ATTEMPT_PLANNED']
    public = [r for r in rows if r['kind']=='PUBLIC_RESULT']
    return {'schema':'nomad.mission.summary.v1','task_id':goal['task_id'],
            'mission_id':goal['mission_id'], 'status':state, 'attempts':len(attempted),
            'public_executions_recorded':len(public),
            'witness_observations':sum(r['kind']=='WITNESS_RESULT' for r in rows),
            'final_observations':sum(r['kind']=='FINAL_RESULT' for r in rows),
            'committed_sha256':next((r['data']['candidate_sha256'] for r in rows if r['kind']=='COMPLETED'),None),
            'journal_head':rows[-1]['sha256'] if rows else None,
            'model_calls':0, 'scope':'trusted synthetic single-file repair only',
            'note':info}


def run(root: Path, *, trusted_fixture: bool = False, timeout_s: float = 12.0,
        interrupt_at: str|None = None, interrupt_attempt: int = 1) -> dict:
    if trusted_fixture is not True:
        raise PermissionError('explicit --trusted-fixture required; no arbitrary repository execution')
    root = root.resolve(strict=True)
    if not (root / 'workspace' / 'solution.py').is_file():
        raise MissionHold('missing trusted workspace')
    with exclusive_owner(root):
        goal = _read_goal(root)
        if goal.get('external_effect_ledger_required'):
            from .effects import EffectLedger
            effects = EffectLedger(root / 'effects', create=False).snapshot()
            if not effects['replay_safe']:
                raise MissionHold('unresolved external effect: mission HOLD until authoritative reconciliation')
        j = Journal(root/'events.jsonl',goal['mission_id'])
        original = (root/'original.py').read_text()
        edits = edits_from_source(original)
        if len(edits) != goal['candidate_count']:
            raise MissionHold('candidate grammar changed after mission creation')

        def checkpoint(mark: str, index: int):
            if interrupt_at == mark and interrupt_attempt == index:
                raise InjectedInterruption(f'injected interruption {mark} at attempt {index}')

        def read_state():
            rows = j.read()
            attempts = _events_per_attempt(rows, edits,goal)
            return rows, attempts

        rows, attempts = read_state()
        terminal = next((r for r in rows if r['kind'] in ('COMPLETED','EXHAUSTED')),None)
        source_path=root/'workspace'/'solution.py'
        if terminal:
            expected = (terminal['data'].get('candidate_sha256') if terminal['kind']=='COMPLETED'
                        else goal['original_sha256'])
            if digest(source_path.read_bytes()) != expected:
                raise MissionHold('terminal mission source unexpectedly changed')
            return _summary(goal,rows,'completed' if terminal['kind']=='COMPLETED' else 'exhausted',
                            info='terminal receipt reused; no new work')

        for edit in edits[:goal['budget']]:
            i=edit.ordinal
            rows, attempts=read_state()
            state=attempts.get(i,{})
            if 'PATCH_REVERTED' in state:
                if digest(source_path.read_bytes()) != goal['original_sha256']:
                    raise MissionHold('reverted candidate source differs from baseline')
                continue
            if not state:
                if digest(source_path.read_bytes()) != goal['original_sha256']:
                    raise MissionHold('unrecorded modification before planning')
                j.append('ATTEMPT_PLANNED',{'attempt':i,'candidate_sha256':edit.sha256,
                            'transmission_id':edit.transmission_id,'family':edit.family})
                checkpoint('after_plan',i)
                _,attempts=read_state();state=attempts[i]
            if 'PATCH_APPLIED' not in state:
                _replace_content(source_path,edit.source,goal['original_sha256'],edit.sha256)
                checkpoint('after_patch_write',i)
                j.append('PATCH_APPLIED',{'attempt':i,'candidate_sha256':edit.sha256})
                checkpoint('after_patch_record',i)
                _,attempts=read_state();state=attempts[i]
            negative_observed = (state.get('PUBLIC_RESULT', {}).get('passed') is False or
                                 state.get('WITNESS_RESULT', {}).get('supported') is False or
                                 state.get('FINAL_RESULT', {}).get('supported') is False)
            source_now = digest(source_path.read_bytes())
            # A crash after an idempotent rollback write but before its event is
            # reconciled from the actual bytes, not mistaken for interference.
            allowed_now = {edit.sha256, goal['original_sha256']} if negative_observed else {edit.sha256}
            if source_now not in allowed_now:
                raise MissionHold('source differs from recorded pending candidate')
            if 'PUBLIC_RESULT' not in state:
                report=_public_tests(root,timeout_s=timeout_s)
                j.append('PUBLIC_RESULT',{'attempt':i,**report})
                checkpoint('after_public',i)
                _,attempts=read_state();state=attempts[i]
            if state['PUBLIC_RESULT']['passed']:
                if 'WITNESS_RESULT' not in state:
                    report=_observer(root,goal,edit,'witness',timeout_s)
                    j.append('WITNESS_RESULT',{'attempt':i, 'supported':report['supported'],
                              'receipt':report['receipt'],
                              'observation_sha256':report['observation_sha256']})
                    checkpoint('after_witness',i)
                    _,attempts=read_state();state=attempts[i]
                if state['WITNESS_RESULT']['supported']:
                    if 'FINAL_RESULT' not in state:
                        report=_observer(root,goal,edit,'final',timeout_s)
                        j.append('FINAL_RESULT',{'attempt':i,'supported':report['supported'],
                                    'observed_sha256':report['observed_sha256'],
                                    'expected_sha256':report['expected_sha256'],
                                    'observation_sha256':report['observation_sha256']})
                        checkpoint('after_final',i)
                        _,attempts=read_state();state=attempts[i]
                    if state['FINAL_RESULT']['supported']:
                        if digest(source_path.read_bytes()) != edit.sha256:
                            raise MissionHold('source changed since final verification')
                        j.append('COMPLETED',{'attempt':i,'candidate_sha256':edit.sha256,
                                              'final_observation_sha256':state['FINAL_RESULT']['observation_sha256']})
                        checkpoint('after_completed',i)
                        return _summary(goal,j.read(),'completed')
            # Public failure, WITNESS contradiction, or final failure: restore
            # the original baseline before trying any new candidate.
            _replace_content(source_path,original,edit.sha256,goal['original_sha256'])
            checkpoint('after_rollback_write',i)
            j.append('PATCH_REVERTED',{'attempt':i,'source_sha256':goal['original_sha256']})
            checkpoint('after_rollback_record',i)
        rows, attempts=read_state()
        if len(attempts) != min(len(edits),goal['budget']):
            raise MissionHold('cannot exhaust mission with pending actions')
        if digest(source_path.read_bytes()) != goal['original_sha256']:
            raise MissionHold('cannot exhaust mission with an applied candidate')
        j.append('EXHAUSTED',{'attempts':len(attempts),'reason':'candidate budget reached'})
        return _summary(goal,j.read(),'exhausted')


def inspect(root: Path) -> dict:
    root=root.resolve(strict=True)
    goal=_read_goal(root)
    if goal.get('external_effect_ledger_required'):
        from .effects import EffectLedger
        effects = EffectLedger(root / 'effects', create=False).snapshot()
        if not effects['replay_safe']:
            raise MissionHold('unresolved external effect: mission HOLD')
    edits=edits_from_source((root/'original.py').read_text())
    rows=Journal(root/'events.jsonl',goal['mission_id']).read()
    _events_per_attempt(rows,edits,goal)
    terminal=next((r for r in rows if r['kind'] in ('COMPLETED','EXHAUSTED')),None)
    if terminal is not None:
        expected=(terminal['data']['candidate_sha256'] if terminal['kind']=='COMPLETED'
                  else goal['original_sha256'])
        if digest((root/'workspace'/'solution.py').read_bytes()) != expected:
            raise MissionHold('terminal mission source unexpectedly changed')
    status='completed' if terminal and terminal['kind']=='COMPLETED' else (
        'exhausted' if terminal else 'in_progress')
    return _summary(goal,rows,status)
