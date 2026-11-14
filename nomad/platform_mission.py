"""v0.18 bounded repository missions with Docker-only execution.

Supported repair contract: one strict ``solve(x, y)`` arithmetic function in a
source-only Python repository. GENESIS searches public examples; an independent
bounded interpreter evaluates private examples without executing repository code.
This is deliberately narrower than arbitrary Python behavioral verification.
Original repositories are never edited. A completed mission commits its own
disposable snapshot, not Git or a remote effect. Checksums are not signatures.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import uuid
from typing import Any

from .effects import EffectLedger
from .genesis import IOExample, SynthesisTask, _render, synthesize
from .isolation import (SandboxPolicy, UnsafeWorkspace, _input_paths, _reparse,
                        run_isolated, snapshot_source)
from .mission_runtime import (InjectedInterruption, Journal, MissionHold, canonical,
                              digest, exclusive_owner, save_atomic)
from .python_operators import generate_python_candidates
from .safe_eval import evaluate, parse_expr
from .witness import Witness, WitnessReceipt

SCHEMA = 'nomad.platform-mission.v1'
WITNESS_ID = 'nomad-v018-bounded-arithmetic-observer'
COMMAND = ['python', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-q']
CHECKPOINTS = ('after_plan', 'after_patch_write', 'after_patch_record',
               'after_dispatch', 'after_public', 'after_witness', 'after_final',
               'after_commit', 'after_learning', 'after_rollback_write',
               'after_rollback_record')


def _runtime_identity() -> dict[str, str]:
    package = Path(__file__).parent
    return {name: digest((package / name).read_bytes()) for name in
            ('platform_mission.py', 'genesis.py', 'safe_eval.py', 'witness.py', 'isolation.py',
             'supervised.py', 'windows_job.py', 'mission_runtime.py', 'effects.py',
             'python_operators.py', 'platform_bitwork.py')}


@dataclass(frozen=True)
class PlatformCandidate:
    family: str
    source: str
    sha256: str
    origin: str


def _expression(source: str) -> str:
    """Strict syntax prevents decorators/default arguments from hiding effects."""
    if len(source.encode('utf-8')) > 8192:
        raise MissionHold('target exceeds bounded arithmetic adapter')
    try:
        tree = ast.parse(source)
        if len(list(ast.walk(tree))) > 128 or len(tree.body) != 1:
            raise ValueError('one bounded function required')
        fn = tree.body[0]
        if (not isinstance(fn, ast.FunctionDef) or fn.name != 'solve'
                or [a.arg for a in fn.args.args] != ['x', 'y']
                or fn.decorator_list or fn.returns or fn.type_comment
                or getattr(fn, 'type_params', []) or fn.args.posonlyargs
                or fn.args.kwonlyargs or fn.args.vararg or fn.args.kwarg
                or fn.args.defaults or fn.args.kw_defaults
                or any(a.annotation for a in fn.args.args)
                or len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return)
                or fn.body[0].value is None):
            raise ValueError('strict solve(x,y) expression required')
        expr = ast.unparse(fn.body[0].value)
        expression = parse_expr(expr)
        for node in ast.walk(expression):
            if isinstance(node, ast.Constant) and (
                    type(node.value) is not int or abs(node.value) > 1000):
                raise ValueError('constant outside bounded integer grammar')
        return expr
    except (ValueError, SyntaxError, RecursionError) as exc:
        raise MissionHold('unsupported target; repository code was not executed') from exc


def _rows(rows: list[dict]) -> tuple[IOExample, ...]:
    if not isinstance(rows, list) or not 1 <= len(rows) <= 128:
        raise ValueError('each evidence partition needs 1..128 observations')
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'x', 'y', 'expected'}:
            raise ValueError('observation must contain exactly x, y, expected')
        if any(type(row[key]) is not int for key in row):
            raise ValueError('observations require integers, not booleans')
        if max(abs(row['x']), abs(row['y'])) > 1000 or abs(row['expected']) > 1_000_000:
            raise ValueError('observation exceeds bounded arithmetic range')
        identity = (row['x'], row['y'])
        if identity in seen:
            raise ValueError('duplicate observation is not independent evidence')
        seen.add(identity)
        result.append(IOExample(**row))
    return tuple(result)


def _validate_partitions(public: list[dict], challenge: list[dict], final: list[dict]):
    parts = tuple(_rows(rows) for rows in (public, challenge, final))
    identities = [{(r.x, r.y) for r in rows} for rows in parts]
    if any(identities[i] & identities[j] for i, j in ((0, 1), (0, 2), (1, 2))):
        raise ValueError('public, challenge and final input identities must be disjoint')
    return parts


def _values(expr: str, rows: tuple[IOExample, ...]) -> tuple[float, ...]:
    values = []
    for row in rows:
        try:
            value = evaluate(expr, {'x': row.x, 'y': row.y})
            # Bounded grammar and inputs keep arithmetic finite. Out-of-range
            # behavior is an explicit mismatch, never a matching overflow.
            values.append(float(value) if abs(value) <= 1_000_000 else 2_000_001.0)
        except (ArithmeticError, ValueError):
            values.append(2_000_001.0)
    return tuple(values)


def _manifest(root: Path) -> dict[str, str]:
    # Reuse admission's bounded, reparse-aware traversal even for protected
    # snapshots: stale journals cannot authorize a swapped junction/hardlink.
    policy = SandboxPolicy('nomad/identity@sha256:' + '0' * 64,
                           max_files=20000, max_total_bytes=200_000_000)
    files = {}
    try:
        for path, relative, expected in _input_paths(root, policy=policy):
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
            with os.fdopen(os.open(path, flags), 'rb') as handle:
                current = os.fstat(handle.fileno())
                if (current.st_ino, current.st_dev, current.st_size, current.st_nlink) != (
                        expected.st_ino, expected.st_dev, expected.st_size, 1):
                    raise MissionHold('snapshot changed during identity check')
                content = handle.read(expected.st_size + 1)
                after = os.fstat(handle.fileno())
                if (len(content) != expected.st_size or
                        (after.st_mtime_ns, after.st_ctime_ns) !=
                        (current.st_mtime_ns, current.st_ctime_ns)):
                    raise MissionHold('snapshot changed during identity read')
                files[relative.as_posix()] = digest(content)
    except UnsafeWorkspace as exc:
        raise MissionHold('unsafe mission snapshot: ' + str(exc)) from exc
    return files


def _target(value: str) -> str:
    if not isinstance(value, str) or '\\' in value or ':' in value:
        raise ValueError('target must be a relative POSIX Python path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts or path.suffix != '.py':
        raise ValueError('target must stay within repository')
    return path.as_posix()


def _execution_identity(goal: dict, container_name: str) -> dict:
    candidate = goal['candidate']
    entries = [[path, candidate['sha256'], len(candidate['source'].encode())]
               if path == goal['target'] else [path, sha, size]
               for path, sha, size in goal['baseline_entries']]
    snapshot = digest(json.dumps(entries, separators=(',', ':'), ensure_ascii=True).encode())
    return {'container_name': container_name, 'snapshot_sha256': snapshot,
            'source_files': len(entries), 'source_bytes': sum(row[2] for row in entries),
            'image_digest': goal['policy']['image'].split('@sha256:')[-1], 'command': COMMAND}


def _validate_execution(goal: dict, dispatch: dict, result: dict, supported: bool) -> None:
    identity = _execution_identity(goal, dispatch['container_name'])
    if (result.get('schema') != 'nomad.isolated-test.v1'
            or any(result.get(key) != value for key, value in identity.items())
            or result.get('container_cleanup_confirmed') is not True
            or type(result.get('returncode')) is not int
            or type(result.get('timed_out')) is not bool
            or type(result.get('tests_passed')) is not bool
            or result['tests_passed'] != (result['returncode'] == 0 and not result['timed_out'])
            or supported is not result['tests_passed']):
        raise MissionHold('foreign, stale, inconsistent or unconfirmed isolated execution receipt')


def _select(original: str, public: tuple[IOExample, ...], *, max_eval: int,
            ranker: Any = None) -> tuple[PlatformCandidate | None, dict]:
    # Search receives no private rows. GENESIS actually computes a proposal.
    task = SynthesisTask('platform-public', original, public, (), ())
    synthesis = synthesize(task, max_eval=max_eval, max_nodes=7)
    items = []
    if synthesis.candidate is not None:
        source = _render(synthesis.candidate)
        items.append(PlatformCandidate('GENESIS', source, digest(source.encode()), 'genesis'))
    for family, candidates in generate_python_candidates(original).items():
        for candidate in candidates:
            try:
                expr = _expression(candidate.source)
            except MissionHold:
                continue
            if _values(expr, public) == tuple(float(r.expected) for r in public):
                items.append(PlatformCandidate(family, candidate.source,
                             digest(candidate.source.encode()), 'ast-transform'))
    unique = {c.sha256: c for c in reversed(items)}
    items = list(reversed(list(unique.values())))
    if ranker is not None:
        items = list(ranker.rank(items, now_epoch=0))
    selected = items[0] if items else None
    return selected, {'genesis': asdict(synthesis), 'public_correct_candidates': len(items),
                      'selection_authority': 'proposal_only',
                      'ranking': ranker.summary(now_epoch=0) if ranker is not None else {'mode': 'cold'}}


def initialize(root: Path, source: Path, *, goal_text: str, public: list[dict],
               challenge: list[dict], final: list[dict], policy: SandboxPolicy,
               target: str = 'solution.py', max_eval: int = 65000,
               ranker: Any = None) -> dict:
    policy.validate()
    if type(max_eval) is not int or not 1 <= max_eval <= 65000:
        raise ValueError('GENESIS evaluation budget must be 1..65000')
    if not isinstance(goal_text, str) or not 1 <= len(goal_text) <= 4096:
        raise ValueError('a bounded mission goal is required')
    target = _target(target)
    pub, _, _ = _validate_partitions(public, challenge, final)
    source = Path(source)
    metadata = source.lstat()
    if stat.S_ISLNK(metadata.st_mode) or _reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise UnsafeWorkspace('source root link/reparse point refused before resolution')
    source = source.resolve(strict=True)
    root = Path(root).resolve()
    if root == source or source in root.parents or root in source.parents:
        raise ValueError('mission evidence and source repository must be disjoint')
    if root.exists():
        raise FileExistsError('mission root already exists')
    # Admission and planning finish in an owned staging directory. Bad input
    # cannot leave a partially initialized mission at the requested destination.
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nomad-platform-init-', dir=root.parent) as tmp:
        stage = Path(tmp)
        snapshot_source(source, stage / 'baseline', policy)
        original_path = stage / 'baseline' / target
        if not original_path.is_file():
            raise MissionHold('target file missing from admitted repository')
        original = original_path.read_text(encoding='utf-8')
        _expression(original)
        if not (stage / 'baseline' / 'tests').is_dir():
            raise MissionHold('supported repository requires a tests directory')
        candidate, planning = _select(original, pub, max_eval=max_eval, ranker=ranker)
        manifest = _manifest(stage / 'baseline')
        entries = [[name, sha, (stage / 'baseline' / name).stat().st_size]
                   for name, sha in manifest.items()]
        sealed = {'challenge': challenge, 'final': final}
        sealed_bytes = canonical(sealed)
        goal = {'schema': SCHEMA, 'version': '0.18.0', 'goal': goal_text,
                'target': target, 'public': public, 'policy': asdict(policy),
                'max_eval': max_eval, 'baseline': manifest, 'baseline_entries': entries,
                'runtime_sha256': _runtime_identity(),
                'sealed_sha256': digest(sealed_bytes),
                'candidate': asdict(candidate) if candidate else None,
                'planning': planning, 'command': COMMAND,
                'scope': 'single strict arithmetic solve(x,y), source-only Python repository'}
        goal['mission_id'] = digest(canonical(goal))[:32]
        shutil.copytree(stage / 'baseline', stage / 'workspace')
        os.chmod(stage / 'workspace' / target, 0o600)
        save_atomic(stage / 'sealed.json', sealed_bytes)
        save_atomic(stage / 'goal.json', canonical(goal))
        EffectLedger(stage / 'effects')
        (stage / 'events.jsonl').touch()
        Journal(stage / 'events.jsonl', goal['mission_id']).append('PLATFORM_CREATED',
                            {'goal_sha256': digest(canonical(goal))})
        stage.rename(root)
    return goal


def _load(root: Path) -> tuple[dict, Journal, list[dict]]:
    try:
        goal = json.loads((root / 'goal.json').read_bytes())
        if goal.get('schema') != SCHEMA or goal.get('version') != '0.18.0':
            raise MissionHold('platform mission identity changed')
        identity = dict(goal)
        identity.pop('mission_id')
        if digest(canonical(identity))[:32] != goal['mission_id']:
            raise MissionHold('platform mission identity mismatch')
        SandboxPolicy(**goal['policy']).validate()
        if goal['runtime_sha256'] != _runtime_identity():
            raise MissionHold('mission runtime or verifier changed; fresh mission required')
        _target(goal['target'])
        if goal['command'] != COMMAND:
            raise MissionHold('unrecognized public execution contract')
        if _manifest(root / 'baseline') != goal['baseline']:
            raise MissionHold('baseline source snapshot changed')
        if digest((root / 'sealed.json').read_bytes()) != goal['sealed_sha256']:
            raise MissionHold('private evidence changed')
        if not EffectLedger(root / 'effects', create=False).snapshot()['replay_safe']:
            raise MissionHold('unresolved external effect; authoritative reconciliation required')
        journal = Journal(root / 'events.jsonl', goal['mission_id'])
        rows = journal.read()
        _validate_state(goal, rows)
        expected = dict(goal['baseline'])
        candidate = goal['candidate']
        actual = _manifest(root / 'workspace')
        if candidate:
            pending = dict(expected)
            pending[goal['target']] = candidate['sha256']
            if actual not in (expected, pending):
                raise MissionHold('unexpected workspace modification')
        elif actual != expected:
            raise MissionHold('unexpected workspace modification')
        return goal, journal, rows
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise MissionHold('mission artifact missing, malformed, or stale') from exc


def _validate_state(goal: dict, rows: list[dict]) -> None:
    if not rows or rows[0]['kind'] != 'PLATFORM_CREATED' or rows[0]['data'] != {
            'goal_sha256': digest(canonical(goal))}:
        raise MissionHold('mission origin is not pinned')
    allowed = {
        'PLATFORM_CREATED': {'PATCH_PLANNED', 'EXHAUSTED'},
        'PATCH_PLANNED': {'PATCH_APPLIED'},
        'PATCH_APPLIED': {'EXECUTION_DISPATCHED'},
        'EXECUTION_DISPATCHED': {'PUBLIC_RESULT', 'EXECUTION_RECOVERED'},
        'EXECUTION_RECOVERED': {'EXECUTION_DISPATCHED'},
        'PUBLIC_RESULT': {'WITNESS_RESULT', 'REVERTED'},
        'WITNESS_RESULT': {'FINAL_RESULT', 'REVERTED'},
        'FINAL_RESULT': {'COMMITTED', 'REVERTED'},
        'COMMITTED': {'LEARNED'}, 'LEARNED': set(), 'REVERTED': set(), 'EXHAUSTED': set()}
    previous = rows[0]
    for row in rows[1:]:
        if row['kind'] not in allowed.get(previous['kind'], set()):
            raise MissionHold('platform journal transition invalid')
        data = row['data']
        if row['kind'] == 'EXHAUSTED':
            if goal['candidate'] is not None:
                raise MissionHold('existing proposal cannot be marked exhausted')
            previous = row
            continue
        if data.get('candidate_sha256') != goal['candidate']['sha256']:
            raise MissionHold('platform event candidate mismatch')
        kind = row['kind']
        if kind in ('WITNESS_RESULT', 'FINAL_RESULT', 'COMMITTED') and not previous['data'].get('supported'):
            raise MissionHold('unsupported event cannot authorize next stage')
        if kind == 'REVERTED' and previous['data'].get('supported') is not False:
            raise MissionHold('rollback requires a negative result')
        if kind == 'PUBLIC_RESULT':
            _validate_execution(goal, previous['data'], data['execution'], data['supported'])
        if kind == 'WITNESS_RESULT':
            receipt = WitnessReceipt(**data['receipt'])
            if (not receipt.verify_checksum() or receipt.supported != data['supported']
                    or receipt.witness_id != WITNESS_ID or receipt.task_id != goal['mission_id']
                    or receipt.transmission_id != goal['candidate']['sha256'] or receipt.world_epoch != 0):
                raise MissionHold('foreign or tampered WITNESS receipt')
        if kind == 'FINAL_RESULT':
            observation = {k: v for k, v in data.items() if k != 'observation_sha256'}
            if (data.get('observation_sha256') != digest(canonical(observation)) or
                    data.get('supported') is not (data['observed_sha256'] == data['expected_sha256'])):
                raise MissionHold('final observation integrity or verdict mismatch')
        previous = row


def _summary(goal: dict, rows: list[dict]) -> dict:
    kind = rows[-1]['kind']
    status = {'LEARNED': 'completed', 'COMMITTED': 'committed', 'REVERTED': 'rejected',
              'EXHAUSTED': 'exhausted', 'EXECUTION_DISPATCHED': 'hold_uncertain_execution'}.get(kind, 'in_progress')
    return {'schema': SCHEMA + '.summary', 'mission_id': goal['mission_id'], 'status': status,
            'journal_head': rows[-1]['sha256'], 'events': len(rows),
            'committed_sha256': goal['candidate']['sha256'] if kind in ('COMMITTED', 'LEARNED') else None,
            'public_executions_recorded': sum(r['kind'] == 'PUBLIC_RESULT' for r in rows),
            'dispatches': sum(r['kind'] == 'EXECUTION_DISPATCHED' for r in rows),
            'witness_observations': sum(r['kind'] == 'WITNESS_RESULT' for r in rows),
            'final_observations': sum(r['kind'] == 'FINAL_RESULT' for r in rows),
            'cloud_model_calls': 0, 'scope': goal['scope'],
            'authority': 'bounded arithmetic contract only; no merge, deployment or skill promotion'}


def _learn(root: Path, goal: dict, rows: list[dict]) -> str:
    witness = next(r['data']['receipt'] for r in rows if r['kind'] == 'WITNESS_RESULT')
    final = next(r['data'] for r in rows if r['kind'] == 'FINAL_RESULT')
    body = {'schema': 'nomad.platform-learning.v1', 'mission_id': goal['mission_id'],
            'source_snapshot_sha256': digest(canonical(goal['baseline'])),
            'candidate_sha256': goal['candidate']['sha256'], 'sealed_sha256': goal['sealed_sha256'],
            'witness_receipt': witness, 'final_observation_sha256': final['observation_sha256'],
            'independent_task_count': 1, 'authority': 'one scoped verified observation; no skill promotion'}
    body['event_id'] = digest(canonical(body))
    path = root / 'learning.json'
    expected = canonical(body)
    if path.exists() and path.read_bytes() != expected:
        raise MissionHold('existing learning record differs; cannot overwrite evidence')
    if not path.exists():
        save_atomic(path, expected)
    return digest(expected)


def run(root: Path, *, interrupt_at: str | None = None) -> dict:
    root = Path(root).resolve(strict=True)
    if interrupt_at is not None and interrupt_at not in CHECKPOINTS:
        raise ValueError('unknown interruption checkpoint')
    with exclusive_owner(root):
        goal, journal, rows = _load(root)
        candidate = goal['candidate']
        def checkpoint(name):
            if interrupt_at == name:
                raise InjectedInterruption(name)
        def event(kind, **data):
            journal.append(kind, {'candidate_sha256': candidate['sha256'], **data})
            return journal.read()
        if rows[-1]['kind'] == 'EXECUTION_DISPATCHED':
            raise MissionHold('execution outcome unknown; run explicit cleanup recovery before retry')
        if rows[-1]['kind'] in ('LEARNED', 'REVERTED', 'EXHAUSTED'):
            _check_terminal(root, goal, rows)
            return _summary(goal, rows)
        if candidate is None:
            journal.append('EXHAUSTED', {'reason': 'GENESIS found no public-correct candidate'})
            return _summary(goal, journal.read())
        target = root / 'workspace' / goal['target']
        if rows[-1]['kind'] == 'PLATFORM_CREATED':
            if _manifest(root / 'workspace') != goal['baseline']:
                raise MissionHold('unrecorded modification before planning')
            rows = event('PATCH_PLANNED', origin=candidate['origin'], family=candidate['family'])
            checkpoint('after_plan')
        if rows[-1]['kind'] == 'PATCH_PLANNED':
            save_atomic(target, candidate['source'].encode())
            checkpoint('after_patch_write')
            rows = event('PATCH_APPLIED')
            checkpoint('after_patch_record')
        negative = rows[-1]['data'].get('supported') is False
        if digest(target.read_bytes()) != candidate['sha256'] and not negative:
            raise MissionHold('candidate snapshot differs from planned source')
        if rows[-1]['kind'] in ('PATCH_APPLIED', 'EXECUTION_RECOVERED'):
            # The container name is durable before dispatch. A crash can be
            # reconciled by an explicit independently observed cleanup, never by
            # guessing that an absent process implies completed tests.
            # Semantic mission IDs intentionally deduplicate learning, while
            # disposable execution IDs must be unique across concurrent roots.
            container_name = 'nomad-' + uuid.uuid4().hex[:24]
            rows = event('EXECUTION_DISPATCHED', container_name=container_name)
            checkpoint('after_dispatch')
            result = run_isolated(root / 'workspace', command=COMMAND,
                                  policy=SandboxPolicy(**goal['policy']), container_name=container_name)
            _validate_execution(goal, rows[-1]['data'], result, result.get('tests_passed'))
            rows = event('PUBLIC_RESULT', supported=result['tests_passed'] is True, execution=result)
            checkpoint('after_public')
        public = _rows(goal['public'])
        # Private partitions are read only after immutable public proposal and
        # public execution receipt. Rejection terminates this mission; private
        # results never become counterexamples for adaptive search.
        sealed = json.loads((root / 'sealed.json').read_bytes())
        original = _expression((root / 'baseline' / goal['target']).read_text(encoding='utf-8'))
        expr = _expression(candidate['source'])
        if rows[-1]['kind'] == 'PUBLIC_RESULT' and rows[-1]['data']['supported']:
            challenge = _rows(sealed['challenge'])
            receipt = Witness(WITNESS_ID).attest(task_id=goal['mission_id'],
                transmission_id=candidate['sha256'], world_epoch=0,
                current_public=_values(original, public),
                target_public=tuple(float(r.expected) for r in public),
                candidate_public=_values(expr, public),
                current_challenge=_values(original, challenge),
                target_challenge=tuple(float(r.expected) for r in challenge),
                candidate_challenge=_values(expr, challenge))
            rows = event('WITNESS_RESULT', supported=receipt.supported, receipt=asdict(receipt))
            checkpoint('after_witness')
        if rows[-1]['kind'] == 'WITNESS_RESULT' and rows[-1]['data']['supported']:
            final = _rows(sealed['final'])
            observed = _values(expr, final)
            expected = tuple(float(r.expected) for r in final)
            observation = {'observed_sha256': digest(canonical(observed)),
                           'expected_sha256': digest(canonical(expected)), 'observations': len(final),
                           'candidate_sha256': candidate['sha256'], 'supported': observed == expected}
            observation['observation_sha256'] = digest(canonical(observation))
            rows = event('FINAL_RESULT', **{k: v for k, v in observation.items() if k != 'candidate_sha256'})
            checkpoint('after_final')
        if rows[-1]['kind'] == 'FINAL_RESULT' and rows[-1]['data']['supported']:
            if digest(target.read_bytes()) != candidate['sha256']:
                raise MissionHold('candidate changed after final observation')
            rows = event('COMMITTED', supported=True)
            checkpoint('after_commit')
        if rows[-1]['kind'] == 'COMMITTED':
            learning_sha = _learn(root, goal, rows)
            checkpoint('after_learning')
            rows = event('LEARNED', learning_sha256=learning_sha)
            return _summary(goal, rows)
        if rows[-1]['data'].get('supported') is False:
            original_bytes = (root / 'baseline' / goal['target']).read_bytes()
            if digest(target.read_bytes()) not in (candidate['sha256'], digest(original_bytes)):
                raise MissionHold('unrecognized source cannot be rolled back')
            save_atomic(target, original_bytes)
            checkpoint('after_rollback_write')
            rows = event('REVERTED', supported=False, reason='public or independent contract rejected')
            checkpoint('after_rollback_record')
            return _summary(goal, rows)
        raise MissionHold('mission cannot advance from its observed state')


def _check_terminal(root: Path, goal: dict, rows: list[dict]) -> None:
    kind = rows[-1]['kind']
    expected = dict(goal['baseline'])
    if kind in ('LEARNED', 'COMMITTED'):
        expected[goal['target']] = goal['candidate']['sha256']
    if _manifest(root / 'workspace') != expected:
        raise MissionHold('terminal snapshot changed')
    if kind == 'LEARNED':
        path = root / 'learning.json'
        if not path.is_file() or digest(path.read_bytes()) != rows[-1]['data']['learning_sha256']:
            raise MissionHold('committed learning observation changed')


def inspect(root: Path) -> dict:
    root = Path(root).resolve(strict=True)
    goal, _, rows = _load(root)
    if rows[-1]['kind'] in ('LEARNED', 'COMMITTED', 'REVERTED', 'EXHAUSTED'):
        _check_terminal(root, goal, rows)
    return _summary(goal, rows)


def recover(root: Path) -> dict:
    """Confirm disposal of an ambiguous container; discard its unknown result.

    This does not reconcile external effects, accept lost test observations, or
    clear a foreign/tampered journal. The next run performs a fresh experiment.
    """
    from .isolation import cleanup_isolated
    root = Path(root).resolve(strict=True)
    with exclusive_owner(root):
        goal, journal, rows = _load(root)
        if rows[-1]['kind'] != 'EXECUTION_DISPATCHED':
            return _summary(goal, rows)
        name = rows[-1]['data']['container_name']
        if cleanup_isolated(name) is not True:
            raise MissionHold('container disposal unconfirmed; recovery remains HOLD')
        journal.append('EXECUTION_RECOVERED', {'candidate_sha256': goal['candidate']['sha256'],
                       'container_name': name, 'disposal_confirmed': True,
                       'lost_execution_result': 'discarded; no authority'})
        return _summary(goal, journal.read())
