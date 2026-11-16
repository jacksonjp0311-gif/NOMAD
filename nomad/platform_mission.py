"""v0.18 bounded repository missions with Docker-only execution.

The original adapter repairs one strict ``solve(x, y)`` arithmetic function;
its independent bounded interpreter never executes repository code. The typed
JSON function adapter admits a wider restricted grammar, uses Docker-only
observations, and compares private expectations in the trusted parent. GENESIS
and proposal ranking see public evidence only. Neither adapter verifies
arbitrary Python behavior or substitutes host execution for containment.
Original repositories are never edited. A completed mission commits its own
disposable snapshot, not Git or a remote effect. Checksums are not signatures.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, replace
import copy
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
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
from . import inquiry, repo_world, frontier
from .causal_atlas import AtlasTask, ChangeReceipt, Contract, SymbolGraph, source_digest
from .mnemonic import EvidenceMemory, action_digest, digest as memory_digest, encode_features
from .platform_bitwork import NativeDecisionRanker, PublicObservation
from .python_model import PythonExample, PythonTask
from .python_runtime import PythonExecution, TestObservation
from .resonance import encode_resonance
from .adaptive import AdaptiveConfig, AdaptiveController
from .persistent import (PersistentConfig, PersistentController, prefix_digest,
                         _runtime_identity as _persistent_runtime_identity,
                         source_identity as _persistent_source_identity)

SCHEMA = 'nomad.platform-mission.v1'
WITNESS_ID = 'nomad-v018-bounded-arithmetic-observer'
COMMAND = ['python', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-q']
CHECKPOINTS = ('after_plan', 'after_patch_write', 'after_patch_record',
               'after_dispatch', 'after_public', 'after_witness', 'after_final',
               'after_commit', 'after_learning', 'after_rollback_write',
               'after_rollback_record', 'after_probe_dispatch', 'after_probe',
               'after_proposal', 'before_memory', 'after_memory')
FUNCTION_CHECKPOINTS = (*CHECKPOINTS, 'after_multifile_patch_write', 'after_control')
PERSISTENT_CHECKPOINTS = ('after_persistent_control','after_persistent_forecast','after_persistent_update',
                         'after_persistent_search_observation')
MEMORY_ID = 'nomad-platform-memory-v018'


def _publish_staged_mission(stage: Path, root: Path) -> None:
    """Publish once, retrying only bounded Windows access/sharing refusals.

    A directory handle can transiently deny a Windows rename. The error alone
    does not identify the holder. Persistent denial, source replacement, a
    destination conflict or an ambiguous result is never treated as success.
    """
    def metadata(path):
        try:
            return path.lstat()
        except FileNotFoundError:
            return None
    initial = metadata(stage)
    if (initial is None or not stat.S_ISDIR(initial.st_mode) or _reparse(initial)
            or stat.S_ISLNK(initial.st_mode) or stage.parent != root.parent):
        raise MissionHold('mission publication requires an owned same-parent staging directory')
    identity = (initial.st_dev, initial.st_ino)
    delays = (0.05, 0.1, 0.2, 0.4, 0.8)
    for attempt in range(len(delays) + 1):
        if metadata(root) is not None:
            raise FileExistsError('mission destination exists; refusing publication overwrite')
        current = metadata(stage)
        if (current is None or _reparse(current) or not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != identity):
            raise MissionHold('mission staging identity changed before publication')
        try:
            stage.rename(root)
        except OSError as error:
            # An exception does not prove that nothing moved. A newly visible
            # destination is never adopted as ours, even if its bytes match.
            remaining = metadata(stage)
            if metadata(root) is not None or remaining is None:
                raise MissionHold('mission publication outcome ambiguous; inspect destination before retry') from error
            if os.name != 'nt' or getattr(error, 'winerror', None) not in (5, 32):
                raise
            if attempt == len(delays):
                raise MissionHold('Windows mission publication remained denied after bounded retries') from error
            time.sleep(delays[attempt])
        else:
            published = metadata(root)
            if (metadata(stage) is not None or published is None or _reparse(published)
                    or not stat.S_ISDIR(published.st_mode)
                    or (published.st_dev, published.st_ino) != identity):
                raise MissionHold('published mission identity is unconfirmed')
            return


def _runtime_identity(*, persistent=False) -> dict[str, str]:
    package = Path(__file__).parent
    names = (
            ('platform_mission.py', 'genesis.py', 'safe_eval.py', 'witness.py', 'isolation.py',
             'supervised.py', 'windows_job.py', 'mission_runtime.py', 'effects.py',
             'python_operators.py', 'platform_bitwork.py', 'resonance.py', 'repo_world.py',
             'inquiry.py', 'mnemonic.py', 'causal_atlas.py', 'frontier.py', 'adaptive.py'))
    return {name: digest((package / name).read_bytes()) for name in names + (('persistent.py',) if persistent else ())}


def _origin_goal(goal: dict) -> dict:
    return goal.get('_origin', goal)


def _hydrate(goal: dict, rows: list[dict]) -> dict:
    proposals = [row for row in rows if row['kind'] == 'PROPOSAL_SELECTED']
    if len(proposals) > 1:
        raise MissionHold('multiple sealed proposals in one mission')
    if proposals:
        data = proposals[0]['data']
        return {**goal, '_origin': goal, 'candidate': data['candidate'], 'planning': data['planning']}
    return goal


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


def _execution_identity(goal: dict, container_name: str, *, baseline: bool = False) -> dict:
    candidate = goal['candidate']
    entries = [[path, candidate['sha256'], len(candidate['source'].encode())]
               if not baseline and path == goal['target'] else [path, sha, size]
               for path, sha, size in goal['baseline_entries']]
    snapshot = digest(json.dumps(entries, separators=(',', ':'), ensure_ascii=True).encode())
    return {'container_name': container_name, 'snapshot_sha256': snapshot,
            'source_files': len(entries), 'source_bytes': sum(row[2] for row in entries),
            'image_digest': goal['policy']['image'].split('@sha256:')[-1], 'command': COMMAND}


def _validate_execution(goal: dict, dispatch: dict, result: dict, supported: bool,
                        *, baseline: bool = False) -> None:
    identity = _execution_identity(goal, dispatch['container_name'], baseline=baseline)
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
            ranker: Any = None, now_epoch: int = 0, memory: EvidenceMemory | None = None,
            features: tuple[str, ...] = (), task_id: str | None = None,
            adaptive_enabled: bool = True) -> tuple[PlatformCandidate | None, dict]:
    # Search receives no private rows. GENESIS actually computes a proposal.
    task = SynthesisTask('platform-public', original, public, (), ())
    synthesis = synthesize(task, max_eval=max_eval, max_nodes=7)
    items = []
    if synthesis.candidate is not None:
        source = _render(synthesis.candidate)
        items.append(PlatformCandidate('GENESIS', source, digest(source.encode()), 'genesis'))
    ast_generated = 0
    ast_evaluated = 0
    for family, candidates in generate_python_candidates(original).items():
        for candidate in candidates:
            ast_generated += 1
            try:
                expr = _expression(candidate.source)
            except MissionHold:
                continue
            ast_evaluated += 1
            if _values(expr, public) == tuple(float(r.expected) for r in public):
                items.append(PlatformCandidate(family, candidate.source,
                             digest(candidate.source.encode()), 'ast-transform'))
    unique = {c.sha256: c for c in reversed(items)}
    items = list(reversed(list(unique.values())))
    if ranker is not None:
        items = list(ranker.rank(items, now_epoch=now_epoch))
    predictions = {c.sha256: memory.recall(action_source=c.source, features=features,
                    now_epoch=now_epoch, target_task_id=task_id).as_dict() for c in items} if memory else {}
    if adaptive_enabled and predictions:
        # Existing MNEMONIC can prefer an independently supported impact. It
        # never authorizes acceptance, and contested/stale cells remain neutral.
        items.sort(key=lambda c: -int(predictions[c.sha256]['outcome'] == 'impact'))
    selected = items[0] if items else None
    return selected, {'genesis': asdict(synthesis), 'public_correct_candidates': len(items),
                      'ast_candidates_generated': ast_generated,
                      'ast_candidates_evaluated': ast_evaluated,
                      'candidate_evaluation_units': 'public arithmetic vectors; GENESIS and AST counted separately',
                      'selection_authority': 'proposal_only',
                      'ranking': ranker.summary(now_epoch=now_epoch) if ranker is not None else {'mode': 'cold'},
                      'mnemonic_recall': predictions,
                      'candidate_inventory_sha256': digest(canonical(sorted(c.sha256 for c in items)))}


def _safe_resonance(source: str, public: tuple[IOExample, ...]):
    expr = _expression(source)
    observations = []
    for row in public:
        try:
            actual = evaluate(expr, {'x': row.x, 'y': row.y})
            observations.append(TestObservation(actual == row.expected, row.expected,
                                               actual, None, None, 0))
        except ArithmeticError as error:
            observations.append(TestObservation(False, row.expected, None, type(error).__name__, 2, 0))
    execution = PythonExecution(True, None, None, None, len(list(ast.walk(ast.parse(source)))),
                                tuple(observations), 0)
    task = PythonTask('platform-public-observer', source,
                     [PythonExample({'x': r.x, 'y': r.y}, r.expected) for r in public])
    return encode_resonance(task, execution=execution)


def _read_python_sources(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.glob('*.py')):
        if len(files) >= 64 or path.stat().st_size > 8192:
            raise MissionHold('bounded structural adapter supports at most 64 small top-level Python modules')
        source = path.read_text(encoding='utf-8')
        try:
            if len(list(ast.walk(ast.parse(source)))) > 512:
                raise MissionHold('structural AST budget exceeded')
        except (SyntaxError, RecursionError) as error:
            raise MissionHold('structural adapter cannot parse repository module') from error
        files[path.name] = source
    return files


def _discover(root: Path, files: dict[str, str], target: str | None,
              entry_module: str | None) -> tuple[str, list[str], str]:
    supported = []
    for filename, source in files.items():
        try:
            _expression(source)
            supported.append(filename)
        except MissionHold:
            pass
    if target is not None:
        target = _target(target)
        if target not in supported:
            raise MissionHold('explicit target is outside supported top-level arithmetic modules')
        entry_module = entry_module or Path(target).stem
    if entry_module is None:
        imported = set()
        for test in sorted((root / 'tests').rglob('test_*.py')):
            if test.stat().st_size > 16384 or len(imported) > 64:
                raise MissionHold('public test inspection budget exceeded')
            tree = ast.parse(test.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and any(a.name == 'solve' for a in node.names):
                    if node.module + '.py' in files:
                        imported.add(node.module)
        if len(imported) == 1:
            entry_module = next(iter(imported))
        elif not imported and len(supported) == 1:
            entry_module = Path(supported[0]).stem
        else:
            raise MissionHold('public API is ambiguous; provide an entry_module contract')
    if not isinstance(entry_module, str) or not entry_module.isidentifier() or entry_module + '.py' not in files:
        raise MissionHold('entry_module must name an admitted top-level Python module')
    # Only transparent public aliases are resolved; arbitrary wrapper execution
    # and dynamic imports remain unsupported. No repository module is imported.
    current = entry_module + '.py'
    seen = set()
    while current not in supported:
        if current in seen or len(seen) >= 8:
            raise MissionHold('cyclic or overly deep public alias')
        seen.add(current)
        body = ast.parse(files[current]).body
        if (len(body) != 1 or not isinstance(body[0], ast.ImportFrom) or body[0].level
                or len(body[0].names) != 1 or body[0].names[0].name != 'solve'
                or body[0].names[0].asname not in (None, 'solve')):
            raise MissionHold('public entry must be arithmetic solve or a transparent solve import')
        current = str(body[0].module) + '.py'
        if current not in files:
            raise MissionHold('public alias leaves admitted source')
    if target is not None and target != current:
        raise MissionHold('target does not implement the declared public API')
    return current, supported, entry_module


def _atlas(goal: dict, files: dict[str, str]) -> AtlasTask:
    public = _rows(goal['public'])
    # The independent arithmetic observer checks the resolved leaf directly.
    # Transparent import aliases are established by source admission, not by
    # pretending SymbolGraph resolves re-exported symbols it cannot represent.
    contract = Contract(Path(goal['target']).stem, 'solve', tuple((r.x, r.y) for r in public))
    return AtlasTask(goal['analysis']['task_identity'], files, goal['target'], (contract,), public, (), ())


def _rebuild_memory_models(memory_root: Path | None, *, now_epoch: int, mode: str = 'native',
                           target_task_id: str | None = None) -> dict:
    memory = EvidenceMemory()
    world = repo_world.RepositoryWorldModel(include_failure=True)
    probes = inquiry.ProbeLikelihoods()
    ranker = NativeDecisionRanker(mode, action_schema='genesis-vs-ast')
    state = {'memory': memory, 'world': world, 'probes': probes, 'ranker': ranker,
             'head': '0' * 64, 'records': [], 'eligible_tasks': 0, 'chain_heads': set()}
    if memory_root is None or not memory_root.exists():
        return state
    if (memory_root / 'events.jsonl').stat().st_size > 64_000_000:
        raise MissionHold('persistent memory exceeds storage budget')
    rows = Journal(memory_root / 'events.jsonl', MEMORY_ID).read()
    if len(rows) > 513:
        raise MissionHold('persistent memory exceeds observation budget')
    if not rows or rows[0]['kind'] != 'MEMORY_CREATED' or rows[0]['data'] != {'schema': 'nomad.platform-memory.v1'}:
        raise MissionHold('memory origin mismatch')
    seen = set()
    trained_tasks = set()
    trained_sources = set()
    for row in rows[1:]:
        if row['kind'] != 'OBSERVATION_ADMITTED':
            raise MissionHold('unknown memory event')
        record = row['data']
        goal = record['goal']
        identity = {key: value for key, value in _origin_goal(goal).items() if key != 'mission_id'}
        if digest(canonical(identity))[:32] != goal['mission_id'] or record['files'] != goal['analysis']['files']:
            raise MissionHold('memory source or mission identity mismatched')
        task = _atlas(goal, record['files'])
        receipt = ChangeReceipt(**{**record['change_receipt'],
                                   'before': tuple(record['change_receipt']['before']),
                                   'after': tuple(record['change_receipt']['after'])})
        witness = WitnessReceipt(**record['witness'])
        final = record['final']
        observation = {k: v for k, v in final.items() if k != 'observation_sha256'}
        obs_id = record['observation_id']
        if (obs_id != digest(canonical([task.task_id, action_digest(goal['candidate']['source'])]))
                or obs_id in seen or not witness.verify_checksum() or not witness.supported
                or witness.task_id != goal['mission_id'] or witness.transmission_id != goal['candidate']['sha256']
                or witness.witness_id != WITNESS_ID or witness.world_epoch != 0
                or witness.schema != 'nomad.v0.6.witness-receipt.v1'
                or final.get('supported') is not True
                or final.get('candidate_sha256') != goal['candidate']['sha256']
                or final.get('observation_sha256') != digest(canonical(observation))
                or final['observed_sha256'] != final['expected_sha256']
                or type(record['capture_epoch']) is not int or record['capture_epoch'] < 0
                or record['capture_epoch'] != goal['analysis']['capture_epoch']):
            raise MissionHold('memory verification provenance invalid')
        seen.add(obs_id)
        execution = record['public_execution']
        _validate_execution(goal, {'container_name': execution['container_name']}, execution, True)
        baseline_execution = record['baseline_execution']
        _validate_execution(goal, {'container_name': baseline_execution['container_name']}, baseline_execution,
                            baseline_execution['tests_passed'], baseline=True)
        public = _rows(goal['public'])
        expected_before = _values(_expression(task.files[task.changed_file]), public)
        expected_after = _values(_expression(goal['candidate']['source']), public)
        if receipt.before != expected_before or receipt.after != expected_after:
            raise MissionHold('memory consequence differs from bounded observer')
        if goal.get('runtime_sha256') == _runtime_identity():
            try:
                memory.record(task=task, contract=task.contracts[0].key,
                              action_source=goal['candidate']['source'], receipt=receipt,
                              capture_epoch=record['capture_epoch'])
            except ValueError as error:
                raise MissionHold('memory admission invalid: ' + str(error)) from error
        state['records'].append(record)
        eligible = (task.task_id != target_task_id and 0 <= now_epoch - record['capture_epoch'] <= memory.ttl_epochs
                    and goal.get('runtime_sha256') == _runtime_identity()
                    and task.task_id not in trained_tasks and source_digest(task.files) not in trained_sources)
        if eligible:
            trained_tasks.add(task.task_id)
            trained_sources.add(source_digest(task.files))
            world.observe(goal['analysis']['signatures'][goal['target']], receipt.changed)
            probes.observe(goal['analysis']['roles'][goal['target']], record['probe_role'],
                           passed=record['baseline_execution']['tests_passed'])
            probes.fit_cases += 1
            ranker.observe(PublicObservation(task.task_id, source_digest(task.files),
                goal['candidate']['sha256'], digest(canonical(execution)), goal['candidate']['family'],
                True, record['capture_epoch']), independently_observed=True)
            state['eligible_tasks'] += 1
    state['head'] = rows[-1]['sha256']
    state['chain_heads'] = {row['sha256'] for row in rows}
    return state


def _memory_models(memory_root: Path | None, *, now_epoch: int, mode: str = 'native',
                   target_task_id: str | None = None) -> dict:
    try:
        return _rebuild_memory_models(memory_root, now_epoch=now_epoch, mode=mode,
                                      target_task_id=target_task_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise MissionHold('persistent learning evidence is missing or malformed') from error


def read_memory_ranker(memory_root: Path, *, mode: str = 'native', now_epoch: int = 0) -> NativeDecisionRanker:
    """Rebuild a ranking-only native model from validated durable observations."""
    root = Path(memory_root).resolve(strict=True)
    with exclusive_owner(root):
        return _memory_models(root, now_epoch=now_epoch, mode=mode)['ranker']


def _probe_model(snapshot: dict) -> inquiry.ProbeLikelihoods:
    model = inquiry.ProbeLikelihoods()
    if snapshot.get('schema') != 'nomad.v0.9.probe-likelihoods.v1':
        raise MissionHold('incompatible public probe model')
    for row in snapshot['rows']:
        key = (row['hypothesis_role'], row['probe_role'])
        for name, table in (('passed', model.pass_counts), ('failed', model.fail_counts)):
            value = row[name]
            if type(value) is not int or not 0 <= value <= 20000:
                raise MissionHold('invalid public probe counts')
            table[key] = value
    model.fit_cases = snapshot['training_tasks']
    return model


def _pipeline_plan(root: Path, files: dict[str, str], target: str, supported: list[str],
                   entry_module: str, public: tuple[IOExample, ...], models: dict,
                   *, now_epoch: int, adaptive_enabled: bool) -> dict:
    task_id = digest(canonical({'source_ast': {name: ast.dump(ast.parse(src), include_attributes=False)
                              for name, src in files.items()}, 'public': [asdict(r) for r in public]}))
    repo = repo_world.RepoTask(task_id, files, entry_module,
        tuple(repo_world.RepoExample({'x': r.x, 'y': r.y}, r.expected) for r in public), (), (), '', '')
    edges, _, distance = repo_world.build_graph(repo)
    signatures = {}
    resonances = {}
    scores = {}
    for filename in supported:
        resonance = _safe_resonance(files[filename], public)
        resonances[filename] = {**asdict(resonance), 'fusion_signature': resonance.fusion_signature,
                               'observer': 'bounded interpreter model; no repository host execution'}
        sig = set(repo_world.file_signature(root, repo, filename, include_failure=False))
        sig.add('numeric_failure' if resonance.failures else 'no_public_failure')
        sig.add('runtime_error' if resonance.runtime_errors else 'runtime_ok')
        signatures[filename] = sorted(sig)
        scores[filename] = models['world'].score(sig) if adaptive_enabled else 0.0
    # Interface reachability is observed source structure, not hidden bug metadata.
    top = max(scores.values())
    weights = {name: math.exp(max(-40.0, (score - top) / 12.0)) *
               (1.0 if distance.get(name, 999) < 999 else 0.05) for name, score in scores.items()}
    prior = {name: weight / sum(weights.values()) for name, weight in weights.items()}
    costs = {name: max(1, sum(len(x) for x in generate_python_candidates(files[name]).values())) for name in supported}
    roles = {name: 'entry' if name == entry_module + '.py' else
             'reachable_leaf' if distance.get(name, 999) < 999 else 'unreachable_leaf' for name in supported}
    menu = [inquiry.ProbeMenu('public-suite', roles[target], 0.25)]
    probe_model = models['probes'] if adaptive_enabled else inquiry.ProbeLikelihoods()
    decision = inquiry.choose_probe(prior, costs, roles, probe_model, menu, frozenset(), 1.0)
    return {'task_identity': task_id, 'entry_module': entry_module, 'files': files,
            'graph': {name: sorted(values) for name, values in edges.items()},
            'signatures': signatures, 'roles': roles, 'resonance': resonances,
            'world_scores': scores, 'world_prior': prior,
            'world_observations': models['world'].observations,
            'inquiry': {'decision': asdict(decision) if decision else None,
                        'reason': 'positive expected utility' if decision else 'no informative discretionary probe; baseline validation remains required',
                        'probe_role': roles[target], 'probe_id': 'public-suite',
                        'model': probe_model.snapshot()},
            'memory_head': models['head'], 'eligible_memory_tasks': models['eligible_tasks'],
            'capture_epoch': now_epoch, 'adaptive_enabled': adaptive_enabled,
            'component_calls': {'repo_world.build_graph': 1, 'RepositoryWorldModel.score': len(scores) if adaptive_enabled else 0,
                 'resonance.encode_resonance': len(resonances), 'inquiry.choose_probe': 1,
                 }}


def initialize(root: Path, source: Path, *, goal_text: str, public: list[dict],
               challenge: list[dict], final: list[dict], policy: SandboxPolicy,
               target: str | None = None, max_eval: int = 65000,
               ranker: Any = None, entry_module: str | None = None,
               memory_root: Path | None = None, capture_epoch: int = 0,
               adaptive_enabled: bool = True, max_executions: int = 4) -> dict:
    policy.validate()
    if type(max_eval) is not int or not 1 <= max_eval <= 65000:
        raise ValueError('GENESIS evaluation budget must be 1..65000')
    if not isinstance(goal_text, str) or not 1 <= len(goal_text) <= 4096:
        raise ValueError('a bounded mission goal is required')
    if type(capture_epoch) is not int or capture_epoch < 0 or type(adaptive_enabled) is not bool:
        raise ValueError('invalid memory epoch or adaptive mode')
    if type(max_executions) is not int or not 2 <= max_executions <= 8:
        raise ValueError('mission container execution budget must be 2..8')
    if target is not None:
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
    memory_root = Path(memory_root).resolve() if memory_root is not None else None
    if memory_root is not None and any(memory_root == p or memory_root in p.parents or p in memory_root.parents
                                       for p in (source, root)):
        raise ValueError('persistent learning store must be disjoint from source and mission')
    # Admission and planning finish in an owned staging directory. Bad input
    # cannot leave a partially initialized mission at the requested destination.
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nomad-platform-init-', dir=root.parent) as tmp:
        stage = Path(tmp)
        snapshot_source(source, stage / 'baseline', policy)
        files = _read_python_sources(stage / 'baseline')
        target, supported, entry_module = _discover(stage / 'baseline', files, target, entry_module)
        original_path = stage / 'baseline' / target
        if not original_path.is_file():
            raise MissionHold('target file missing from admitted repository')
        original = original_path.read_text(encoding='utf-8')
        _expression(original)
        if not (stage / 'baseline' / 'tests').is_dir():
            raise MissionHold('supported repository requires a tests directory')
        task_identity = digest(canonical({'source_ast': {name: ast.dump(ast.parse(src), include_attributes=False)
                                          for name, src in files.items()}, 'public': [asdict(r) for r in pub]}))
        mode = getattr(ranker, 'mode', 'native')
        if memory_root is not None and memory_root.exists():
            with exclusive_owner(memory_root):
                models = _memory_models(memory_root, now_epoch=capture_epoch, mode=mode,
                                        target_task_id=task_identity)
        else:
            models = _memory_models(memory_root, now_epoch=capture_epoch, mode=mode,
                                    target_task_id=task_identity)
        active_ranker = ranker if ranker is not None else models['ranker']
        if isinstance(active_ranker, NativeDecisionRanker) and active_ranker is not models['ranker']:
            for observation in models['ranker'].events:
                active_ranker.observe(observation, independently_observed=True)
        analysis = _pipeline_plan(stage / 'baseline', files, target, supported, entry_module, pub,
                                  models, now_epoch=capture_epoch, adaptive_enabled=adaptive_enabled)
        if not isinstance(active_ranker, NativeDecisionRanker):
            raise ValueError('platform missions require a serializable scoped NativeDecisionRanker')
        models['memory'].save(stage / 'planning_memory.json')
        save_atomic(stage / 'planning_ranker.json', canonical(active_ranker.snapshot()))
        planning_context = {name: digest((stage / name).read_bytes())
                            for name in ('planning_memory.json', 'planning_ranker.json')}
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
                'candidate': None, 'planning': {'status': 'awaiting_bound_public_probe'},
                'planning_context': planning_context, 'command': COMMAND,
                'analysis': analysis, 'memory_root': str(memory_root) if memory_root else None,
                'max_executions': max_executions,
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
        _publish_staged_mission(stage, root)
    return goal


def _load(root: Path) -> tuple[dict, Journal, list[dict]]:
    try:
        if (root/'goal.json').stat().st_size>64_000_000:raise MissionHold('mission goal byte budget exceeded')
        goal = json.loads((root / 'goal.json').read_bytes())
        if goal.get('adapter') == frontier.FUNCTION_ADAPTER:
            return _load_functions(root, goal)
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
        for name, sha in goal['planning_context'].items():
            if name not in ('planning_memory.json', 'planning_ranker.json') or digest((root / name).read_bytes()) != sha:
                raise MissionHold('frozen planning context changed')
        if not EffectLedger(root / 'effects', create=False).snapshot()['replay_safe']:
            raise MissionHold('unresolved external effect; authoritative reconciliation required')
        journal = Journal(root / 'events.jsonl', goal['mission_id'])
        rows = journal.read()
        goal = _hydrate(goal, rows)
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
    except MissionHold:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, OverflowError) as exc:
        raise MissionHold('mission artifact missing, malformed, or stale') from exc


def _validate_state(goal: dict, rows: list[dict]) -> None:
    if not rows or rows[0]['kind'] != 'PLATFORM_CREATED' or rows[0]['data'] != {
            'goal_sha256': digest(canonical(_origin_goal(goal)))}:
        raise MissionHold('mission origin is not pinned')
    allowed = {
        'PLATFORM_CREATED': {'PROBE_DISPATCHED', 'EXHAUSTED'},
        'PROBE_DISPATCHED': {'PROBE_RESULT', 'PROBE_RECOVERED'},
        'PROBE_RECOVERED': {'PROBE_DISPATCHED'},
        'PROBE_RESULT': {'PROPOSAL_SELECTED'},
        'PROPOSAL_SELECTED': {'PATCH_PLANNED', 'EXHAUSTED'},
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
        candidate_sha = goal['candidate']['sha256'] if goal['candidate'] else None
        expected_sha = None if row['kind'] in ('PROBE_DISPATCHED', 'PROBE_RESULT', 'PROBE_RECOVERED') else candidate_sha
        if data.get('candidate_sha256') != expected_sha:
            raise MissionHold('platform event candidate mismatch')
        kind = row['kind']
        if kind == 'PROPOSAL_SELECTED' and goal['candidate']:
            candidate = goal['candidate']
            if digest(candidate['source'].encode()) != candidate['sha256']:
                raise MissionHold('sealed candidate digest differs from source')
            if _values(_expression(candidate['source']), _rows(goal['public'])) != tuple(float(x['expected']) for x in goal['public']):
                raise MissionHold('sealed proposal does not match public contract')
        if kind in ('WITNESS_RESULT', 'FINAL_RESULT', 'COMMITTED') and not previous['data'].get('supported'):
            raise MissionHold('unsupported event cannot authorize next stage')
        if kind == 'REVERTED' and previous['data'].get('supported') is not False:
            raise MissionHold('rollback requires a negative result')
        if kind == 'PUBLIC_RESULT':
            _validate_execution(goal, previous['data'], data['execution'], data['supported'])
        if kind == 'PROBE_RESULT':
            _validate_execution(goal, previous['data'], data['execution'], data['supported'], baseline=True)
            expected = inquiry._update(goal['analysis']['world_prior'], goal['analysis']['roles'],
                _probe_model(goal['analysis']['inquiry']['model']), goal['analysis']['inquiry']['probe_role'],
                data['supported'])
            if data.get('posterior') != expected:
                raise MissionHold('probe update differs from pinned public likelihood model')
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
    if goal.get('adapter') == frontier.FUNCTION_ADAPTER:
        return _function_summary(goal, rows)
    kind = rows[-1]['kind']
    status = {'LEARNED': 'completed', 'COMMITTED': 'committed', 'REVERTED': 'rejected',
              'EXHAUSTED': 'exhausted', 'EXECUTION_DISPATCHED': 'hold_uncertain_execution',
              'PROBE_DISPATCHED': 'hold_uncertain_execution'}.get(kind, 'in_progress')
    return {'schema': SCHEMA + '.summary', 'mission_id': goal['mission_id'], 'status': status,
            'journal_head': rows[-1]['sha256'], 'events': len(rows),
            'committed_sha256': goal['candidate']['sha256'] if kind in ('COMMITTED', 'LEARNED') else None,
            'public_executions_recorded': sum(r['kind'] == 'PUBLIC_RESULT' for r in rows),
            'baseline_probes_recorded': sum(r['kind'] == 'PROBE_RESULT' for r in rows),
            'dispatches': sum(r['kind'] in ('EXECUTION_DISPATCHED', 'PROBE_DISPATCHED') for r in rows),
            'witness_observations': sum(r['kind'] == 'WITNESS_RESULT' for r in rows),
            'final_observations': sum(r['kind'] == 'FINAL_RESULT' for r in rows),
            'cloud_model_calls': 0, 'scope': goal['scope'],
            'pipeline': {**goal['analysis']['component_calls'],
                         'GENESIS.synthesize': sum(r['kind'] == 'PROPOSAL_SELECTED' for r in rows),
                         'NativeDecisionRanker.rank': sum(r['kind'] == 'PROPOSAL_SELECTED' for r in rows),
                         'MNEMONIC.recall_candidates': goal['planning'].get('public_correct_candidates', 0)},
            'memory_head_at_planning': goal['analysis']['memory_head'],
            'authority': 'bounded arithmetic contract only; no merge, deployment or skill promotion'}


def _admit_memory(root: Path, goal: dict, rows: list[dict]) -> dict:
    memory_root = Path(goal['memory_root']) if goal.get('memory_root') else root / 'mnemonic'
    memory_root.mkdir(parents=True, exist_ok=True)
    with exclusive_owner(memory_root):
        path = memory_root / 'events.jsonl'
        if not path.exists():
            if goal['analysis']['memory_head'] != '0' * 64:
                raise MissionHold('pinned memory history missing; refusing to recreate it')
            path.touch(exist_ok=False)
            Journal(path, MEMORY_ID).append('MEMORY_CREATED', {'schema': 'nomad.platform-memory.v1'})
        models = _memory_models(memory_root, now_epoch=goal['analysis']['capture_epoch'])
        pinned_head = goal['analysis']['memory_head']
        if pinned_head != '0' * 64 and pinned_head not in models['chain_heads']:
            raise MissionHold('persistent memory is not a continuation of pinned planning history')
        files = goal['analysis']['files']
        task = _atlas(goal, files)
        observation_id = digest(canonical([task.task_id, action_digest(goal['candidate']['source'])]))
        for record in models['records']:
            if record['observation_id'] == observation_id:
                return {'observation_id': observation_id, 'admitted': False,
                        'reason': 'same source/task/action observation already admitted; TTL unchanged',
                        'memory_head': models['head'], 'mnemonic_head': models['memory'].head}
        if any(record['capture_epoch'] > goal['analysis']['capture_epoch'] for record in models['records']):
            raise MissionHold('memory epoch moved forward; stale mission cannot admit a new observation')
        if len(models['records']) >= 512:
            raise MissionHold('persistent mission admission budget exceeded')
        public = _rows(goal['public'])
        change = {'task_id': task.task_id, 'epoch': 0, 'before_digest': source_digest(files),
                  'after_digest': source_digest({**files, goal['target']: goal['candidate']['source']}),
                  'changed_file': goal['target'], 'contract': task.contracts[0].key,
                  'before': _values(_expression(files[goal['target']]), public),
                  'after': _values(_expression(goal['candidate']['source']), public)}
        change['receipt_digest'] = memory_digest(change)
        receipt = ChangeReceipt(**change)
        admitted = models['memory'].record(task=task, contract=task.contracts[0].key,
            action_source=goal['candidate']['source'], receipt=receipt,
            capture_epoch=goal['analysis']['capture_epoch'])
        if not admitted:
            raise MissionHold('MNEMONIC cannot represent this verified contract; no admission')
        record = {'observation_id': observation_id, 'goal': goal, 'files': files,
                  'capture_epoch': goal['analysis']['capture_epoch'], 'change_receipt': change,
                  'witness': next(r['data']['receipt'] for r in rows if r['kind'] == 'WITNESS_RESULT'),
                  'final': next(r['data'] for r in rows if r['kind'] == 'FINAL_RESULT'),
                  'public_execution': next(r['data']['execution'] for r in rows if r['kind'] == 'PUBLIC_RESULT'),
                  'baseline_execution': next(r['data']['execution'] for r in rows if r['kind'] == 'PROBE_RESULT'),
                  'probe_role': goal['analysis']['inquiry']['probe_role']}
        if path.stat().st_size + len(canonical(record)) + 4096 > 64_000_000:
            raise MissionHold('memory storage budget would be exceeded')
        appended = Journal(path, MEMORY_ID).append('OBSERVATION_ADMITTED', record)
        return {'observation_id': observation_id, 'admitted': True,
                'memory_head': appended['sha256'], 'mnemonic_head': models['memory'].head,
                'authority': 'MNEMONIC prediction only; no test skipping or skill permission'}


def _learn(root: Path, goal: dict, rows: list[dict], *, checkpoint=lambda _: None) -> str:
    witness = next(r['data']['receipt'] for r in rows if r['kind'] == 'WITNESS_RESULT')
    final = next(r['data'] for r in rows if r['kind'] == 'FINAL_RESULT')
    path = root / 'learning.json'
    if path.exists():
        existing = json.loads(path.read_bytes())
        core = {k: v for k, v in existing.items() if k != 'event_id'}
        if (existing.get('mission_id') != goal['mission_id']
                or existing.get('event_id') != digest(canonical(core))
                or existing.get('candidate_sha256') != goal['candidate']['sha256']
                or existing.get('source_snapshot_sha256') != digest(canonical(goal['baseline']))
                or existing.get('sealed_sha256') != goal['sealed_sha256']
                or existing.get('witness_receipt') != witness
                or existing.get('final_observation_sha256') != final['observation_sha256']):
            raise MissionHold('foreign, modified or stale learning observation')
        memory_root = Path(goal['memory_root']) if goal.get('memory_root') else root / 'mnemonic'
        if not memory_root.is_dir():
            raise MissionHold('pending learned observation store is missing')
        with exclusive_owner(memory_root):
            models = _memory_models(memory_root, now_epoch=goal['analysis']['capture_epoch'])
        if not any(record['observation_id'] == existing['mnemonic']['observation_id'] for record in models['records']):
            raise MissionHold('pending learned observation is absent from persistent history')
        return digest(path.read_bytes())
    checkpoint('before_memory')
    memory_receipt = _admit_memory(root, goal, rows)
    checkpoint('after_memory')
    body = {'schema': 'nomad.platform-learning.v1', 'mission_id': goal['mission_id'],
            'source_snapshot_sha256': digest(canonical(goal['baseline'])),
            'candidate_sha256': goal['candidate']['sha256'], 'sealed_sha256': goal['sealed_sha256'],
            'witness_receipt': witness, 'final_observation_sha256': final['observation_sha256'],
            'independent_task_count': 1, 'authority': 'one scoped verified observation; no skill promotion'}
    body['mnemonic'] = memory_receipt
    body['event_id'] = digest(canonical(body))
    expected = canonical(body)
    if path.exists() and path.read_bytes() != expected:
        raise MissionHold('existing learning record differs; cannot overwrite evidence')
    if not path.exists():
        save_atomic(path, expected)
    return digest(expected)


def run(root: Path, *, interrupt_at: str | None = None) -> dict:
    root = Path(root).resolve(strict=True)
    if interrupt_at is not None and interrupt_at not in FUNCTION_CHECKPOINTS+PERSISTENT_CHECKPOINTS:
        raise ValueError('unknown interruption checkpoint')
    with exclusive_owner(root):
        goal, journal, rows = _load(root)
        if goal.get('adapter') == frontier.FUNCTION_ADAPTER:
            return _run_functions(root, goal, journal, rows, interrupt_at=interrupt_at)
        candidate = goal['candidate']
        def checkpoint(name):
            if interrupt_at == name:
                raise InjectedInterruption(name)
        def event(kind, **data):
            journal.append(kind, {'candidate_sha256': candidate['sha256'] if candidate else None, **data})
            return journal.read()
        def reserve_execution():
            used = sum(r['kind'] in ('PROBE_DISPATCHED', 'EXECUTION_DISPATCHED') for r in journal.read())
            if used >= goal['max_executions']:
                raise MissionHold('mission container execution budget exhausted; no additional dispatch')
        if rows[-1]['kind'] in ('EXECUTION_DISPATCHED', 'PROBE_DISPATCHED'):
            raise MissionHold('execution outcome unknown; run explicit cleanup recovery before retry')
        if rows[-1]['kind'] in ('LEARNED', 'REVERTED', 'EXHAUSTED'):
            _check_terminal(root, goal, rows)
            return _summary(goal, rows)
        target = root / 'workspace' / goal['target']
        if rows[-1]['kind'] in ('PLATFORM_CREATED', 'PROBE_RECOVERED'):
            if _manifest(root / 'workspace') != goal['baseline']:
                raise MissionHold('unrecorded modification before planning')
            reserve_execution()
            container_name = 'nomad-' + uuid.uuid4().hex[:24]
            rows = event('PROBE_DISPATCHED', container_name=container_name,
                         probe_id=goal['analysis']['inquiry']['probe_id'])
            checkpoint('after_probe_dispatch')
            result = run_isolated(root / 'workspace', command=COMMAND,
                                  policy=SandboxPolicy(**goal['policy']), container_name=container_name)
            _validate_execution(goal, rows[-1]['data'], result, result.get('tests_passed'), baseline=True)
            posterior = inquiry._update(goal['analysis']['world_prior'], goal['analysis']['roles'],
                _probe_model(goal['analysis']['inquiry']['model']), goal['analysis']['inquiry']['probe_role'],
                result['tests_passed'])
            rows = event('PROBE_RESULT', supported=result['tests_passed'], execution=result, posterior=posterior)
            checkpoint('after_probe')
        if rows[-1]['kind'] == 'PROBE_RESULT':
            public = _rows(goal['public'])
            frozen_ranker = NativeDecisionRanker.load(json.loads((root / 'planning_ranker.json').read_bytes()))
            frozen_memory = EvidenceMemory.load(root / 'planning_memory.json')
            contract = Contract(Path(goal['target']).stem, 'solve', tuple((r.x, r.y) for r in public))
            features = SymbolGraph(goal['analysis']['files']).features(contract, goal['target'])
            candidate_value, planning = _select((root / 'baseline' / goal['target']).read_text(encoding='utf-8'),
                public, max_eval=goal['max_eval'], ranker=frozen_ranker,
                now_epoch=goal['analysis']['capture_epoch'], memory=frozen_memory, features=features,
                task_id=goal['analysis']['task_identity'], adaptive_enabled=goal['analysis']['adaptive_enabled'])
            journal.append('PROPOSAL_SELECTED', {'candidate_sha256': candidate_value.sha256 if candidate_value else None,
                           'candidate': asdict(candidate_value) if candidate_value else None, 'planning': planning,
                           'probe_observation_sha256': rows[-1]['sha256']})
            checkpoint('after_proposal')
            goal, _, rows = _load(root)
            candidate = goal['candidate']
        if rows[-1]['kind'] == 'PROPOSAL_SELECTED':
            if candidate is None:
                journal.append('EXHAUSTED', {'reason': 'GENESIS found no public-correct candidate'})
                return _summary(goal, journal.read())
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
            reserve_execution()
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
            learning_sha = _learn(root, goal, rows, checkpoint=checkpoint)
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
    if goal.get('adapter') == frontier.FUNCTION_ADAPTER:
        _load_functions(root, _origin_goal(goal))
        return
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
        learning = json.loads(path.read_bytes())
        memory_root = Path(goal['memory_root']) if goal.get('memory_root') else root / 'mnemonic'
        if not memory_root.is_dir():
            raise MissionHold('committed persistent observation store missing')
        with exclusive_owner(memory_root):
            models = _memory_models(memory_root, now_epoch=goal['analysis']['capture_epoch'])
        if not any(record['observation_id'] == learning['mnemonic']['observation_id'] for record in models['records']):
            raise MissionHold('committed observation is absent from persistent memory')


def inspect(root: Path) -> dict:
    root = Path(root).resolve(strict=True)
    goal, _, rows = _load(root)
    if rows[-1]['kind'] in ('LEARNED', 'COMMITTED', 'REVERTED', 'EXHAUSTED'):
        _check_terminal(root, goal, rows)
    return _summary(goal, rows)


def resolved_goal(root: Path) -> dict:
    """Read the validated immutable mission origin plus its sealed proposal."""
    return _load(Path(root).resolve(strict=True))[0]


def recover(root: Path) -> dict:
    """Confirm disposal of an ambiguous container; discard its unknown result.

    This does not reconcile external effects, accept lost test observations, or
    clear a foreign/tampered journal. The next run performs a fresh experiment.
    """
    from .isolation import cleanup_isolated
    root = Path(root).resolve(strict=True)
    with exclusive_owner(root):
        goal, journal, rows = _load(root)
        if goal.get('adapter') == frontier.FUNCTION_ADAPTER:
            if rows[-1]['kind'] != 'F_DISPATCHED': return _function_summary(goal, rows)
            if cleanup_isolated(rows[-1]['data']['container_name']) is not True:
                raise MissionHold('function worker disposal unconfirmed')
            journal.append('F_RECOVERED', {'operation': rows[-1]['data']['operation'],
                'container_name': rows[-1]['data']['container_name'], 'disposal_confirmed': True})
            return _function_summary(goal, journal.read())
        if rows[-1]['kind'] not in ('EXECUTION_DISPATCHED', 'PROBE_DISPATCHED'):
            return _summary(goal, rows)
        name = rows[-1]['data']['container_name']
        if cleanup_isolated(name) is not True:
            raise MissionHold('container disposal unconfirmed; recovery remains HOLD')
        kind = 'PROBE_RECOVERED' if rows[-1]['kind'] == 'PROBE_DISPATCHED' else 'EXECUTION_RECOVERED'
        journal.append(kind, {'candidate_sha256': goal['candidate']['sha256'] if goal['candidate'] else None,
                       'container_name': name, 'disposal_confirmed': True,
                       'lost_execution_result': 'discarded; no authority'})
        return _summary(goal, journal.read())


FUNCTION_MEMORY_ID = 'nomad-functions-memory-v018'
FUNCTION_ACTION_SCHEMA = 'python-call-relational-vs-other'
FUNCTION_WITNESS = 'nomad-v018-isolated-function-observer'


def _computation_cost(start):
    return {'wall_seconds': time.perf_counter()-start[0], 'cpu_seconds': time.process_time()-start[1],
            'scope': 'trusted controller process only; excludes isolated worker CPU and peak memory'}


def _validate_computation_cost(value):
    if (not isinstance(value,dict) or set(value)!={'wall_seconds','cpu_seconds','scope'}
            or value['scope']!='trusted controller process only; excludes isolated worker CPU and peak memory'
            or any(type(value[k]) not in (int,float) or not math.isfinite(value[k]) or not 0<=value[k]<=3600
                   for k in ('wall_seconds','cpu_seconds'))):
        raise MissionHold('malformed measured computation cost')


def _controller_state(analysis, *, observations=0, failures=0):
    return {'candidate_count':len(analysis.get('proposals',[])),
            'symbol_count':sum(len(s) for s in analysis['symbols'].values()),
            'edge_count':sum(len(e) for e in analysis['graph'].values()),
            'memory_records':analysis.get('eligible_memory_tasks',0),
            'public_observations':observations,'public_failures':failures}


PERSISTENT_MISSION_SCHEMA = 'nomad.function-persistent-computation.v18'
PERSISTENT_JOURNAL_BYTES = 64_000_000
_PERSISTENT_VALIDATED = {}


def operational_config():
    """Conservative operating policy, separate from frozen research defaults."""
    return PersistentConfig(state_policy='selectivewarm', detector_enabled=False,
                            delayed_credit=False)


def _persistent_decide(controller, public_state, budget, mechanism=None):
    if mechanism is not None and mechanism not in ('frequency', 'temporal', 'native'):
        raise ValueError('unsupported operating mechanism')
    options = {'available_actions': (mechanism,)} if mechanism else {}
    return controller.decide(public_state, remaining_budget=budget, **options)


def _persistent_semantics(document):
    """Compare learned state while retaining all policy/evidence/decision fields.

    Restore/serialization counters differ after restart. Only these concrete
    diagnostic codec paths are omitted, never arbitrary
    fields with a similar name. This is not an authenticity check.
    """
    payload=copy.deepcopy(document['payload']); payload.pop('telemetry')
    diagnostic={
        'GrammarEnsemble':{'telemetry'}, 'ExactCompiledGuardedLearner':{'telemetry'},
        'GovernedBitworkV14':{'telemetry'},
        'ExactCompiledGrammarSynthesizer':{'telemetry','cost','execution_cost'},
        'PackedLagFeatureLearner':{'telemetry','packed_cost'}}
    def normalize(value):
        if isinstance(value,list): return [normalize(v) for v in value]
        if not isinstance(value,dict): return value
        if value.get('t') in diagnostic and set(value)=={'t','version','fields'}:
            return {**value,'fields':{k:normalize(v) for k,v in value['fields'].items()
                                     if k not in diagnostic[value['t']]}}
        return {k:normalize(v) for k,v in value.items()}
    payload['states']={name:{**doc['payload'],'state':normalize(doc['payload']['state'])}
                       for name,doc in payload['states'].items()}
    return payload


def _persistent_load(document, config, history, epoch):
    return PersistentController.load(document,expected_config=config,expected_epoch=epoch,
        expected_prefix_sha256=prefix_digest(history))


def _public_record_search(record):
    evidence=record.get('persistent_evidence') or record.get('computation_evidence')
    return evidence['public_search'] if evidence else [
        {'operation':'search:'+record['candidate']['id'],'result':record['public_result']}]


def _persistent_prefix(config,records):
    chosen=[]; count=0
    limit=config.max_history-min(128,config.max_history//2)
    for record in reversed(records):
        search=_public_record_search(record)
        if count+len(search)>limit: break
        chosen.append((record,search)); count+=len(search)
    history=[]; bindings=[]
    for record,search in reversed(chosen):
        bindings.append({'observation_id':record['observation_id'],
            'source_sha256':digest(canonical(record['baseline'])),
            'public_search_sha256':digest(canonical(search))})
        for observation in search:
            proposal=_function_proposal(record['origin'],observation['operation'].partition(':')[2])
            history.append((int(proposal['family']!='comparison'),int(observation['result']['supported'])))
    return history,bindings,chosen


def _persistent_from_memory(config, models, epoch, operating_mechanism=None):
    """Exact-prefix cache reuse; otherwise measured rebuilding of admitted data."""
    history,bindings,chosen=_persistent_prefix(config,models.get('eligible_records',[]))
    reason='no accepted exact-prefix checkpoint'
    for record,_ in chosen:
        evidence=record.get('persistent_evidence')
        if not evidence: continue
        if record['origin'].get('persistent',{}).get('operating_mechanism') != operating_mechanism:
            reason='accepted checkpoint operating mechanism differs'; continue
        document=evidence['terminal_state']; saved=PersistentConfig(**document['payload']['config'])
        if asdict(replace(saved,epoch=config.epoch))!=asdict(config):
            reason='accepted checkpoint policy differs'; continue
        if document['payload']['history']!=[list(row) for row in history]:
            reason='eligible public prefix changed or expired'; continue
        try:
            controller=_persistent_load(document,saved,history,epoch)
            return controller,{'status':'RESTORED','reason':None,'bindings':bindings,
                'public_prefix_sha256':prefix_digest(history),'observations':len(history),
                'checkpoint_sha256':digest(canonical(document))}
        except (ValueError,RuntimeError) as error:
            reason=str(error)
    controller=PersistentController(replace(config,epoch=epoch))
    for action,outcome in history:
        if operating_mechanism and (not controller.decisions or len(controller.history)>=controller.next_decision):
            _persistent_decide(controller,{}, {'steps':min(config.commitment,config.max_history-len(controller.history)),
                'max_cost_seconds':120.}, operating_mechanism)
        controller.ingest_public(action,outcome)
    return controller,{'status':'REBUILT' if history else 'COLD','reason':reason,'bindings':bindings,
        'public_prefix_sha256':prefix_digest(history),'observations':len(history),'checkpoint_sha256':None}


def _persistent_allocation(controller,analysis,*,max_candidates,probe_budget,max_executions,public_command,
                           operating_mechanism=None):
    reserve=3+int(bool(public_command)); before=controller.snapshot()
    steps=max(0,min(max_candidates,max_executions-reserve-1,controller.config.max_history-len(controller.history),
                    controller.config.commitment))
    state=_controller_state(analysis); budget={'steps':steps,'max_cost_seconds':120.0}
    decision=_persistent_decide(controller,state,budget,operating_mechanism); mechanism=decision['mechanism']
    probes=min(probe_budget,{'frequency':1,'temporal':2,'native':probe_budget,'abstain':0}[mechanism])
    cap=min({'frequency':16,'temporal':32,'native':max_candidates,'abstain':0}[mechanism],
            max_candidates,max(0,max_executions-reserve-probes),controller.config.max_history-len(controller.history))
    result = {'schema':PERSISTENT_MISSION_SCHEMA,'config':asdict(controller.config),
        'controller_before':before,'controller_after':controller.snapshot(),'decision':decision,
        'public_state':state,'remaining_budget':budget,'max_candidates':cap,'probe_budget':probes,
        'private_dispatch_reserve':reserve,'genesis_max_eval':{'frequency':0,'temporal':1024,'native':4096,'abstain':0}[mechanism],
        'ast_check_budget':{'frequency':64,'temporal':256,'native':1024,'abstain':0}[mechanism],
        'use_localization':mechanism in ('temporal','native'),
        'use_retrieval':mechanism in ('temporal','native') and analysis['eligible_memory_tasks']>=3,
        'scope':'registered bounded effort heuristic; no established coding advantage'}
    if operating_mechanism is not None:
        result['operating_mechanism'] = operating_mechanism
    return result


def _persistent_order(goal,remaining,probabilities,posterior,recall):
    order=[_function_proposal(goal,identity) for identity in remaining]
    order.sort(key=lambda p:-probabilities[int(p['family']!='comparison')])
    if goal['analysis']['adaptive_enabled']:
        order.sort(key=lambda p:(-int(recall.get(p['id'],{}).get('outcome')=='impact'),
            -sum(posterior.get(name,0) for name in p['files'])/len(p['files'])))
    return [p['id'] for p in order]


def _persistent_recall(goal,remaining,mechanism):
    invoked=(mechanism in ('native','temporal') and goal['analysis']['adaptive_enabled']
             and goal['analysis']['eligible_memory_tasks']>=3)
    if not invoked:return False,{}
    body=goal['persistent']['mnemonic_snapshot'];memory=EvidenceMemory();template=memory.snapshot()
    if set(body)!=set(template) or any(body[k]!=template[k] for k in template if k not in ('events','head')):
        raise MissionHold('persistent planning memory metadata changed')
    previous=memory.head;seen=set()
    if len(body['events'])>memory.max_events:raise MissionHold('persistent planning memory bound exceeded')
    for row in body['events']:
        evidence=row['evidence']
        if (row['previous']!=previous or row['sha256']!=memory_digest({'evidence':evidence,'previous':previous})
                or evidence['event_id'] in seen):raise MissionHold('persistent planning memory chain changed')
        if (type(evidence['capture_epoch']) is not int or evidence['capture_epoch']<0
                or type(evidence['changed']) is not bool or type(evidence['features']) is not list
                or encode_features(tuple(evidence['features']))!=evidence.get('state_bits')):
            raise MissionHold('persistent planning memory effect shape changed')
        seen.add(evidence['event_id']);previous=row['sha256']
    if previous!=body['head']:raise MissionHold('persistent planning memory head changed')
    memory.events=body['events'];memory.head=previous;memory._event_ids=seen
    first=goal['public'][0];contract=Contract(first['module'],first['function'],tuple((i,0) for i in range(len(goal['public']))))
    symbols=SymbolGraph(goal['analysis']['files']);recall={}
    for identity in remaining:
        proposal=_function_proposal(goal,identity)
        if len(proposal['files'])==1 and '/' not in next(iter(proposal['files'])):
            name=next(iter(proposal['files']))
            recall[identity]=memory.recall(action_source=proposal['files'][name],features=symbols.features(contract,name),
                now_epoch=goal['analysis']['capture_epoch'],target_task_id=goal['analysis']['task_identity']).as_dict()
    return True,recall


def _persistent_public_state(goal,observations):
    return _controller_state(goal['analysis'],observations=len(observations),
                             failures=sum(not row['result']['supported'] for row in observations))


def _validate_persistent_trace(goal,rows,*,complete=False,selected=None):
    # Memoize only complete pure validation of immutable content. Rehashed or
    # altered fields, another policy/runtime, and different terminal authority
    # all produce a different key. This is not a cache of mutable controller objects.
    if len(rows)>2048:raise MissionHold('persistent event count budget exceeded')
    raw=canonical([goal,rows,complete,selected,_runtime_identity(persistent=True),
                   _persistent_source_identity(),_persistent_runtime_identity()])
    if len(raw)>PERSISTENT_JOURNAL_BYTES:raise MissionHold('persistent validation byte budget exceeded')
    key=digest(raw)
    if key in _PERSISTENT_VALIDATED:return json.loads(_PERSISTENT_VALIDATED[key])
    result=_replay_persistent_trace(goal,rows,complete=complete,selected=selected)
    encoded=canonical(result)
    if len(encoded)<=2_000_000:
        while _PERSISTENT_VALIDATED and (len(_PERSISTENT_VALIDATED)>=4 or
                sum(map(len,_PERSISTENT_VALIDATED.values()))+len(encoded)>8_000_000):
            del _PERSISTENT_VALIDATED[next(iter(_PERSISTENT_VALIDATED))]
        _PERSISTENT_VALIDATED[key]=encoded
    return result


def _replay_persistent_trace(goal,rows,*,complete=False,selected=None):
    """Replay only public controller effects; private observations never train."""
    allocation=goal['persistent']; config=PersistentConfig(**allocation['config'])
    epoch=goal['analysis']['capture_epoch']; initial=allocation['controller_before']
    history=[tuple(row) for row in initial['payload']['history']]
    model=_persistent_load(initial,config,history,epoch)
    expected=_persistent_allocation(model,{**goal['analysis'],'proposals':[]},
        max_candidates=allocation['requested_limits']['max_candidates'],
        probe_budget=allocation['requested_limits']['probe_budget'],max_executions=goal['max_executions'],
        public_command=goal['public_command'], operating_mechanism=allocation.get('operating_mechanism'))
    for key,value in expected.items():
        if key.startswith('controller_'):
            if _persistent_semantics(value)!=_persistent_semantics(allocation[key]):
                raise MissionHold('persistent initial learned state changed')
        elif allocation.get(key)!=value: raise MissionHold('persistent allocation changed')
    for field in ('inspection_and_memory_validation_cost','generation_cost'): _validate_computation_cost(allocation[field])
    if (goal['probe_budget']!=allocation['probe_budget'] or len(goal['analysis']['proposals'])>allocation['max_candidates']
            or goal['analysis']['generated_candidates_checked']>allocation['ast_check_budget']):
        raise MissionHold('persistent allocation exceeds registered bounds')
    state=allocation['controller_after']; public=[]; probes=[]; pending=None; forecast=None; control=None
    diagnosis=None; updated=[]; dispatches=0; seen=set();operations=set();previous='0'*64
    for index,row in enumerate(rows,1):
        body={k:v for k,v in row.items() if k!='sha256'}
        if row['seq']!=index or row['prev']!=previous or row['mission_id']!=goal['mission_id'] or row['sha256']!=digest(canonical(body)):
            raise MissionHold('persistent public trace chain changed')
        previous=row['sha256']; kind=row['kind']; data=row['data']
        if index==1 and (kind!='PLATFORM_CREATED' or data!={'goal_sha256':digest(canonical(goal))}):
            raise MissionHold('persistent public origin changed')
        if kind=='F_DIAGNOSIS':
            if diagnosis is not None:raise MissionHold('duplicate persistent diagnosis')
            iterator=iter(probes)
            def observed_probe(operation):
                value=next(iterator,None)
                if value is None or value['operation']!=operation:raise MissionHold('persistent probe choice/order changed')
                return value
            expected_diagnosis=_persistent_diagnosis_data(goal,observed_probe)
            if next(iterator,None) is not None or data!=expected_diagnosis:
                raise MissionHold('persistent public diagnosis differs from its bound probes')
            diagnosis=data
        elif kind=='F_P_CONTROL':
            if diagnosis is None or forecast is not None: raise MissionHold('persistent choice before diagnosis or unsettled outcome')
            if public and public[-1]['result']['supported']:raise MissionHold('persistent search continued after public success')
            if data['state_before_sha256']!=digest(canonical(state)): raise MissionHold('persistent control prefix changed')
            remaining=[p['id'] for p in goal['analysis']['proposals'] if p['id'] not in seen]
            steps=max(0,min(len(remaining),goal['max_executions']-dispatches-allocation['private_dispatch_reserve'],
                            config.max_history-len(history),config.commitment))
            if len(probes)==len(goal['public']) and not public and all(p['result']['supported'] for p in probes): steps=0
            public_state=_persistent_public_state(goal,probes+public); budget={'steps':steps,'max_cost_seconds':120.0}
            if data['public_state']!=public_state or data['remaining_budget']!=budget:
                raise MissionHold('persistent continuation budget or public evidence changed')
            model=_persistent_load(state,config,history,epoch)
            decision=_persistent_decide(model,public_state,budget,allocation.get('operating_mechanism'))
            probabilities=list(model.peek_probabilities(decision['mechanism']))
            baseline=list(model.peek_probabilities('frequency'))
            if data['decision']!=decision or data['probabilities']!=probabilities or data['frequency_probabilities']!=baseline:
                raise MissionHold('persistent choice or forecast does not replay')
            invoked,recall=_persistent_recall(goal,remaining,decision['mechanism'])
            if data['retrieval_invoked']!=invoked or data['mnemonic_recall']!=recall:
                raise MissionHold('persistent recall differs from bound planning memory')
            if data['order']!=_persistent_order(goal,remaining,probabilities,diagnosis['posterior'],data['mnemonic_recall']):
                raise MissionHold('persistent candidate preference changed')
            _persistent_load(data['state'],config,history,epoch)
            if _persistent_semantics(model.snapshot())!=_persistent_semantics(data['state']):
                raise MissionHold('persistent ranked state changed')
            _validate_computation_cost(data['cost']);state=data['state'];control=data
        elif kind=='F_P_FORECAST':
            if forecast is not None or control is None or control['decision']['mechanism']=='abstain':
                raise MissionHold('duplicate or unauthorized persistent forecast')
            remaining=[identity for identity in control['order'] if identity not in seen]
            if not remaining or data['candidate']!=remaining[0] or data['state_before_sha256']!=digest(canonical(state)):
                raise MissionHold('persistent forecast source/order changed')
            if allocation.get('operating_mechanism') is not None and (
                    len(history)>=state['payload']['next_decision']
                    or state['payload']['selected']!=allocation['operating_mechanism']
                    or control['decision']['mechanism']!=allocation['operating_mechanism']
                    or goal['max_executions']-dispatches<=allocation['private_dispatch_reserve']):
                raise MissionHold('operating forecast requires a current authorized control and verification budget')
            proposal=_function_proposal(goal,data['candidate']);action=int(proposal['family']!='comparison')
            model=_persistent_load(state,config,history,epoch);prediction=model.predict(action)
            if data['action']!=action or data['p']!=prediction or data['mechanism']!=model.selected:
                raise MissionHold('persistent pre-observation prediction changed')
            forecast=row
        elif kind=='F_DISPATCHED':
            dispatches+=1
            if pending: raise MissionHold('duplicate persistent dispatch')
            if data['operation'].startswith('search:') and (forecast is None or data['operation']!='search:'+forecast['data']['candidate']):
                raise MissionHold('public outcome requested without persistent forecast')
            pending=data
        elif kind=='F_RECOVERED':
            if not pending or data!={'operation':pending['operation'],'container_name':pending['container_name'],'disposal_confirmed':True}:
                raise MissionHold('persistent recovery does not bind pending dispatch')
            pending=None
        elif kind=='F_OBSERVED':
            if not pending or pending['operation']!=data['operation']: raise MissionHold('unbound persistent observation')
            if data['operation'] in operations:raise MissionHold('duplicate persistent public observation')
            operations.add(data['operation'])
            if data['operation'].startswith(('probe:','search:')):
                result=_validate_function_execution(goal,pending,data['execution'],None)
                if data['result']!=result: raise MissionHold('persistent public result differs')
                (probes if data['operation'].startswith('probe:') else public).append(data)
            elif complete: raise MissionHold('private observation in persistent learning trace')
            pending=None
        elif kind=='F_P_UPDATED':
            if forecast is None or not public or data['candidate']!=forecast['data']['candidate']:
                raise MissionHold('persistent update without unique pending forecast')
            observation=public[-1];action=forecast['data']['action'];outcome=int(observation['result']['supported'])
            if (observation['operation']!='search:'+data['candidate'] or data['forecast_sha256']!=forecast['sha256']
                    or data['observation_sha256']!=digest(canonical(observation)) or data['candidate'] in seen):
                raise MissionHold('persistent update receipt binding changed')
            model=_persistent_load(state,config,history,epoch)
            if model.predict(action)!=forecast['data']['p']: raise MissionHold('persistent resumed prediction differs')
            model.observe(action,outcome);history.append((action,outcome))
            _persistent_load(data['state'],config,history,epoch)
            if _persistent_semantics(model.snapshot())!=_persistent_semantics(data['state']):
                raise MissionHold('persistent post-observation learned state changed')
            _validate_computation_cost(data['cost']);state=data['state'];seen.add(data['candidate']);updated.append(data);forecast=None
        elif kind=='F_SELECTED':
            if (forecast is not None or not updated or data['candidate']!=updated[-1]['candidate']
                    or public[-1]['operation']!='search:'+data['candidate'] or not public[-1]['result']['supported']):
                raise MissionHold('persistent selection before public update')
        elif complete and kind not in ('PLATFORM_CREATED','F_PATCH','F_PATCHED'):
            raise MissionHold('nonpublic event in persistent training trace')
    if complete and (pending or forecast or not public or rows[-1]['kind']!='F_SELECTED'
                     or rows[-1]['data']!={'candidate':selected}):
        raise MissionHold('incomplete persistent accepted public prefix')
    return {'state':state,'history':history,'public_search':public,'probes':probes,'control':control,
            'forecast':forecast,'updated':updated,'dispatches':dispatches,'diagnosis':diagnosis}


def read_function_persistent_controller(memory_root: Path, *, config=None, now_epoch=0, operating_mechanism=None):
    """Read-only admitted reconstruction/cache reuse; never accept external state."""
    config=config or PersistentConfig(state_policy='selectivewarm')
    if type(config) is dict: config=PersistentConfig(**config)
    if type(config) is not PersistentConfig: raise ValueError('persistent configuration only')
    config.validate();path=Path(memory_root)
    if path.exists():
        with exclusive_owner(path):models=_function_memory(path,mode='frequency',epoch=now_epoch)
    else:models=_function_memory(None,mode='frequency',epoch=now_epoch)
    return _persistent_from_memory(config,models,now_epoch,operating_mechanism)


def _persistent_diagnosis(goal,journal,observe,append):
    previous=[r['data'] for r in journal.read() if r['kind']=='F_DIAGNOSIS']
    if previous: return previous[0]
    result=_persistent_diagnosis_data(goal,observe);append('F_DIAGNOSIS',result);return result


def _persistent_diagnosis_data(goal,observe):
    prior=dict(goal['analysis']['world_prior']); roles={name:name for name in prior}
    costs={name:max(1,sum(name in p['files'] for p in goal['analysis']['proposals'])) for name in prior}
    model=inquiry.ProbeLikelihoods();menu=[];seen=set();decisions=[];resonances=[]
    for index,row in enumerate(goal['public']):
        reached=set();pending=[goal['analysis']['modules'][row['module']]]
        while pending:
            name=pending.pop()
            if name in reached: continue
            reached.add(name);pending.extend(goal['analysis']['graph'][name])
        for hypothesis in prior:
            for _ in range(4):model.observe(hypothesis,str(index),passed=hypothesis not in reached)
        menu.append(inquiry.ProbeMenu(str(index),str(index),.05))
    for _ in range(min(goal['probe_budget'],len(menu))):
        decision=(inquiry.choose_probe(prior,costs,roles,model,menu,frozenset(seen),1.)
                  if goal['persistent']['use_localization'] and goal['analysis']['adaptive_enabled'] else None)
        index=int(decision.probe_id) if decision else next(i for i in range(len(menu)) if str(i) not in seen)
        evidence=observe('probe:'+str(index));seen.add(str(index))
        source=goal['analysis']['files'][goal['analysis']['modules'][goal['public'][index]['module']]]
        precomputed=PythonExecution(True,None,None,None,len(list(ast.walk(ast.parse(source)))),
            (TestObservation(evidence['result']['supported'],1,None,None,None,0),),0)
        resonance=encode_resonance(PythonTask('api-equality-probe',source,(PythonExample({},1),)),
                                   execution=precomputed,numeric_inputs=False)
        resonances.append({'index':index,**asdict(resonance),'fusion_signature':resonance.fusion_signature,
            'encoding':'bound isolated API equality; numeric input correlations disabled'})
        prior=inquiry._update(prior,roles,model,str(index),evidence['result']['supported'])
        decisions.append({'index':index,'decision':asdict(decision) if decision else None,'posterior':prior})
    result={'decisions':decisions,'posterior':prior,'order':[p['id'] for p in goal['analysis']['proposals']],
        'resonance':resonances,'mnemonic_recall':{},'ranking':{'authority':'ranking_only','mechanism':'persistent_pending'},
        'likelihood_scope':'declared reachability heuristic; not calibrated learned probability'}
    return result


def _persistent_search(root,goal,journal,observe,patch,append,checkpoint):
    allocation=goal['persistent'];config=PersistentConfig(**allocation['config']);epoch=goal['analysis']['capture_epoch']
    if allocation['decision']['mechanism']=='abstain' or not goal['analysis']['proposals']:
        append('F_ABSTAINED',{'reason':'persistent initial allocation declined work'});return None
    diagnosis=_persistent_diagnosis(goal,journal,observe,append);checkpoint('after_proposal')
    context=_validate_persistent_trace(_origin_goal(goal),journal.read())
    controller=_persistent_load(context['state'],config,context['history'],epoch)
    while True:
        completed=context['public_search']; updated=context['updated'];forecast=context['forecast']
        if (forecast is None and updated and completed[-1]['operation']=='search:'+updated[-1]['candidate']
                and completed[-1]['result']['supported']):
            chosen=updated[-1]['candidate'];append('F_SELECTED',{'candidate':chosen});return chosen
        if updated:patch(None,'search-revert:'+updated[-1]['candidate'])
        remaining=[p['id'] for p in goal['analysis']['proposals'] if p['id'] not in {r['candidate'] for r in updated}]
        if not remaining:
            append('F_EXHAUSTED',{'reason':'persistent bounded inventory exhausted'});return None
        state=context['state'];history=context['history']
        if forecast is None:
            cached_control=context['control']
            # An operating mechanism is explicitly fixed. Within its committed
            # interval keep its ordered inventory and live learned state. Public
            # updates still receive durable checkpoints; no redundant ranking
            # checkpoint is needed before every failed candidate's successor.
            retain_control = (allocation.get('operating_mechanism') is not None
                and cached_control is not None
                and cached_control['decision']['mechanism'] == controller.selected != 'abstain'
                and len(history) < controller.next_decision
                and goal['max_executions']-context['dispatches'] > allocation['private_dispatch_reserve'])
            if cached_control is not None and (cached_control['state']==state or retain_control):
                control=cached_control;decision=control['decision']
            else:
                started=(time.perf_counter(),time.process_time())
                steps=max(0,min(len(remaining),goal['max_executions']-context['dispatches']-allocation['private_dispatch_reserve'],
                                config.max_history-len(history),config.commitment))
                if len(context['probes'])==len(goal['public']) and not completed and all(p['result']['supported'] for p in context['probes']):steps=0
                public_state=_persistent_public_state(goal,context['probes']+completed);budget={'steps':steps,'max_cost_seconds':120.}
                decision=_persistent_decide(controller,public_state,budget,allocation.get('operating_mechanism'))
                probabilities=list(controller.peek_probabilities(decision['mechanism']));baseline=list(controller.peek_probabilities('frequency'))
                retrieval,recall=_persistent_recall(goal,remaining,decision['mechanism'])
                control={'state_before_sha256':digest(canonical(state)),'public_state':public_state,'remaining_budget':budget,
                    'decision':decision,'probabilities':probabilities,'frequency_probabilities':baseline,
                    'mnemonic_recall':recall,'retrieval_invoked':retrieval,
                    'order':_persistent_order(goal,remaining,probabilities,diagnosis['posterior'],recall),
                    'state':controller.snapshot(),'cost':_computation_cost(started)}
                append('F_P_CONTROL',control);checkpoint('after_persistent_control')
            if decision['mechanism']=='abstain':
                patch(None,'persistent-abstain');append('F_ABSTAINED',{'reason':'persistent continuation declined remaining search'});return None
            identity=next(identity for identity in control['order'] if identity in remaining)
            proposal=_function_proposal(goal,identity)
            action=int(proposal['family']!='comparison')
            if not retain_control: state=control['state']
            prediction=controller.predict(action)
            append('F_P_FORECAST',{'candidate':identity,'action':action,'p':prediction,'mechanism':controller.selected,
                'state_before_sha256':digest(canonical(state))});checkpoint('after_persistent_forecast')
            forecast=journal.read()[-1]
        else:
            identity=forecast['data']['candidate'];action=forecast['data']['action']
            if controller.predict(action)!=forecast['data']['p']:raise MissionHold('resumed persistent forecast differs')
        patch(identity,'search-apply:'+identity)
        result=observe('search:'+identity)
        checkpoint('after_persistent_search_observation')
        started=(time.perf_counter(),time.process_time());controller.observe(action,int(result['result']['supported']))
        update={'candidate':identity,'forecast_sha256':forecast['sha256'],'observation_sha256':digest(canonical(result)),
                'state':controller.snapshot(),'cost':_computation_cost(started)}
        append('F_P_UPDATED',update);checkpoint('after_persistent_update')
        public=context['public_search']
        if not public or public[-1]['operation']!=result['operation']:public=public+[result]
        context={**context,'state':update['state'],'history':history+[(action,int(result['result']['supported']))],
            'public_search':public,'forecast':None,'updated':updated+[update],
            'control':control if 'control' in locals() else context['control'],
            'dispatches':sum(r['kind']=='F_DISPATCHED' for r in journal.read())}


def _controller_from_memory(config, models):
    """Import only validated, current, independently accepted PUBLIC evidence.

    An operator supplies configuration, never a trained snapshot. Whole-source
    duplicates and expired observations have already been excluded by the
    memory reader. Accepted-only sampling is explicitly not a causal estimate.
    """
    controller=AdaptiveController(config)
    if not config.use_memory: return controller
    records=models.get('eligible_records',[])
    # Retain whole missions, bounded from newest to oldest; never partial labels.
    chosen=[]; count=0
    for record in reversed(records):
        evidence=record.get('computation_evidence')
        history=(evidence['public_search'] if evidence else
                 [{'operation':'search:'+record['candidate']['id'],'result':record['public_result']}])
        if count+len(history)>config.max_history: break
        chosen.append((record,evidence,history)); count+=len(history)
    for record,evidence,history in reversed(chosen):
        for observation in history:
            proposal=_function_proposal(record['origin'],observation['operation'].partition(':')[2])
            controller.ingest_public(int(proposal['family']!='comparison'),int(observation['result']['supported']))
        if evidence:
            mechanism=evidence['control']['decision']['mechanism']
            controller.record_verified(mechanism,evidence['public_log_gain'],evidence['cost']['wall_seconds'],
                record['observation_id'],independently_verified=True)
    return controller


def _allocation(controller, analysis, *, max_candidates, probe_budget, max_executions, public_command):
    # Explicit registered effort heuristics. The selector's frozen per-forecast
    # costs are not estimates of GENESIS or Docker work; both are measured apart.
    reserve=3+int(bool(public_command))
    steps=max(0,min(max_candidates,max_executions-reserve-1))
    before=controller.snapshot()
    decision=controller.decide(_controller_state(analysis),remaining_budget={'steps':steps,'max_cost_seconds':120.0})
    mechanism=decision['mechanism']
    cap={'frequency':16,'temporal':32,'native':max_candidates,'abstain':0}[mechanism]
    probes=min(probe_budget,{'frequency':1,'temporal':2,'native':probe_budget,'abstain':0}[mechanism])
    cap=min(cap,max_candidates,max(0,max_executions-reserve-probes))
    return {'schema':'nomad.function-computation-allocation.v18','decision':decision,
            'controller_before':before,'controller_after':controller.snapshot(),
            'max_candidates':cap,'probe_budget':probes,'private_dispatch_reserve':reserve,
            'genesis_max_eval':{'frequency':0,'temporal':1024,'native':4096,'abstain':0}[mechanism],
            'ast_check_budget':{'frequency':64,'temporal':256,'native':1024,'abstain':0}[mechanism],
            'use_localization':mechanism in ('temporal','native') and controller.config.use_structure,
            'use_retrieval':mechanism in ('temporal','native') and controller.config.use_memory
                            and analysis['eligible_memory_tasks']>=3,
            'scope':'registered bounded effort heuristic; no demonstrated repository utility'}


def _validate_control(data, expected_before=None):
    """Replay choice from settled public state; never replay measured timings."""
    if expected_before is not None and data['controller_before']!=expected_before:
        raise MissionHold('computation history differs from bound public prefix')
    controller=AdaptiveController.load(data['controller_before'])
    decision=data['decision']
    actions=data.get('available_actions',('frequency','temporal','native'))
    observed=controller.decide(decision['public_state'],available_actions=tuple(actions),
                               remaining_budget=decision['remaining_budget'])
    if canonical(observed)!=canonical(decision) or controller.snapshot()!=data['controller_after']:
        raise MissionHold('computation choice does not replay from its public evidence')
    return controller


def _validate_function_control(goal,data,probes):
    controller=_validate_control(data,goal['computation']['controller_after'])
    if (len(probes)!=min(goal['probe_budget'],len(goal['public']))
            or len({p['operation'] for p in probes})!=len(probes)):
        raise MissionHold('computation choice lacks the allocated distinct public probes')
    failures=sum(not p['result']['supported'] for p in probes)
    steps=0 if len(probes)==len(goal['public']) and failures==0 else len(goal['analysis']['proposals'])
    if (data['public_prefix_sha256']!=digest(canonical(probes))
            or data['available_actions']!=['frequency','temporal','native']
            or data['decision']['remaining_budget']!={'steps':steps,'max_cost_seconds':120.0}
            or data['decision']['public_state']!=_controller_state(goal['analysis'],observations=len(probes),failures=failures)):
        raise MissionHold('computation choice public prefix or registered budget changed')
    return controller


def _validate_public_forecast(control,ranking):
    # The cheap comparator is independently recomputable without loading BGR.
    # Native/temporal forecasts retain trusted controller+source+journal origin;
    # a hostile writer able to replace every anchor is outside checksum trust.
    controller=AdaptiveController.load(control['controller_after'])
    baseline=[controller.frequency.predict(action) for action in (0,1)]
    if (ranking['frequency_probabilities']!=baseline or ranking['mechanism']!=control['decision']['mechanism']
            or ranking['action_schema']!=FUNCTION_ACTION_SCHEMA
            or ranking['mechanism']=='frequency' and ranking['probabilities']!=baseline):
        raise MissionHold('forecast comparator or frequency prediction differs from its public history')


def _adaptive_function_diagnosis(root,goal,journal,observe,checkpoint):
    previous=[r['data'] for r in journal.read() if r['kind']=='F_DIAGNOSIS']
    if previous: return previous[0]
    computation=goal['computation']; config=AdaptiveConfig(**computation['controller_after']['payload']['config'])
    prior=dict(goal['analysis']['world_prior']); roles={name:name for name in prior}
    costs={name:max(1,sum(name in p['files'] for p in goal['analysis']['proposals'])) for name in prior}
    model=inquiry.ProbeLikelihoods(); menu=[]
    for i,row in enumerate(goal['public']):
        reached=set(); pending=[goal['analysis']['modules'][row['module']]]
        while pending:
            name=pending.pop()
            if name in reached: continue
            reached.add(name); pending.extend(goal['analysis']['graph'][name])
        for hypothesis in prior:
            for _ in range(4): model.observe(hypothesis,str(i),passed=hypothesis not in reached)
        menu.append(inquiry.ProbeMenu(str(i),str(i),0.05))
    seen=set(); decisions=[]; resonances=[]
    for _ in range(min(goal['probe_budget'],len(menu))):
        decision=(inquiry.choose_probe(prior,costs,roles,model,menu,frozenset(seen),1.0)
                  if config.use_structure and goal['analysis']['adaptive_enabled'] else None)
        index=int(decision.probe_id) if decision else next(i for i in range(len(menu)) if str(i) not in seen)
        evidence=observe('probe:'+str(index)); seen.add(str(index))
        source=goal['analysis']['files'][goal['analysis']['modules'][goal['public'][index]['module']]]
        observation=TestObservation(evidence['result']['supported'],1,None,None,None,0)
        precomputed=PythonExecution(True,None,None,None,len(list(ast.walk(ast.parse(source)))),(observation,),0)
        resonance=encode_resonance(PythonTask('api-equality-probe',source,(PythonExample({},1),)),
                                   execution=precomputed,numeric_inputs=False)
        resonances.append({'index':index,**asdict(resonance),'fusion_signature':resonance.fusion_signature,
                           'encoding':'bound isolated API equality; numeric input correlations disabled'})
        prior=inquiry._update(prior,roles,model,str(index),evidence['result']['supported'])
        decisions.append({'index':index,'decision':asdict(decision) if decision else None,'posterior':prior})
    probes=[r['data'] for r in journal.read() if r['kind']=='F_OBSERVED' and r['data']['operation'].startswith('probe:')]
    started=(time.perf_counter(),time.process_time())
    failures=sum(not r['result']['supported'] for r in probes)
    controller=AdaptiveController.load(computation['controller_after'])
    previous_control=[r['data'] for r in journal.read() if r['kind']=='F_CONTROL']
    if previous_control:
        control=previous_control[0]; controller=_validate_control(control,computation['controller_after'])
    else:
        # A complete passing PUBLIC contract supplies no repair target. No
        # private observations are consulted to manufacture a search incentive.
        steps=0 if len(probes)==len(goal['public']) and failures==0 else len(goal['analysis']['proposals'])
        control={'controller_before':controller.snapshot(),'public_prefix_sha256':digest(canonical(probes)),
                 'available_actions':['frequency','temporal','native']}
        control['decision']=controller.decide(_controller_state(goal['analysis'],observations=len(probes),failures=failures),
            remaining_budget={'steps':steps,'max_cost_seconds':120.0})
        control['controller_after']=controller.snapshot()
        journal.append('F_CONTROL',control); checkpoint('after_control')
    mechanism=control['decision']['mechanism']
    probabilities=controller.peek_probabilities(mechanism)
    baseline=controller.peek_probabilities('frequency')
    order=list(goal['analysis']['proposals'])
    order.sort(key=lambda p:-probabilities[int(p['family']!='comparison')])
    use_retrieval=(mechanism in ('temporal','native') and config.use_memory
                   and goal['analysis']['eligible_memory_tasks']>=3)
    recall={}
    if use_retrieval:
        memory=EvidenceMemory.load(root/'planning_memory.json'); first=goal['public'][0]
        contract=Contract(first['module'],first['function'],tuple((i,0) for i in range(len(goal['public']))))
        symbols=SymbolGraph(goal['analysis']['files'])
        for p in order:
            if len(p['files'])==1 and '/' not in next(iter(p['files'])):
                filename=next(iter(p['files']))
                recall[p['id']]=memory.recall(action_source=p['files'][filename],features=symbols.features(contract,filename),
                    now_epoch=goal['analysis']['capture_epoch'],target_task_id=goal['analysis']['task_identity']).as_dict()
    # Probe observations affect actual localization priority. The cheap profile
    # still uses already-paid public diagnostics, but does not retrieve memory.
    if config.use_structure and goal['analysis']['adaptive_enabled']:
        order.sort(key=lambda p:(-int(recall.get(p['id'],{}).get('outcome')=='impact'),
            -sum(prior.get(n,0) for n in p['files'])/len(p['files'])))
    diagnosis={'decisions':decisions,'posterior':prior,'order':[p['id'] for p in order],
        'resonance':resonances,'mnemonic_recall':recall,'control_sha256':digest(canonical(control)),
        'ranking':{'mechanism':mechanism,'probabilities':list(probabilities),'frequency_probabilities':list(baseline),
                   'authority':'ranking_only','action_schema':FUNCTION_ACTION_SCHEMA},
        'computation_cost':_computation_cost(started),'telemetry':dict(controller.telemetry),
        'retrieval_invoked':use_retrieval,
        'likelihood_scope':'declared reachability heuristic; not calibrated learned probability'}
    journal.append('F_DIAGNOSIS',diagnosis)
    return diagnosis


def _validate_computation_evidence(goal,evidence,selected):
    """Bind public forecasts before outcomes; private labels never enter it."""
    trace=evidence['public_trace']
    if not isinstance(trace,list) or not 4<=len(trace)<=2048: raise MissionHold('public computation trace budget invalid')
    previous='0'*64; control=None; diagnosis=None; pending=None; public=[]; probes=[]
    for number,row in enumerate(trace,1):
        payload={k:v for k,v in row.items() if k!='sha256'}
        if (row['prev']!=previous or row['seq']!=number or row['mission_id']!=goal['mission_id']
                or row['sha256']!=digest(canonical(payload))): raise MissionHold('public computation trace changed')
        previous=row['sha256']; kind=row['kind']; data=row['data']
        if number==1 and (kind!='PLATFORM_CREATED' or data!={'goal_sha256':digest(canonical(goal))}):
            raise MissionHold('public computation origin changed')
        if kind=='F_CONTROL':
            if control is not None or public: raise MissionHold('duplicate or retrospective computation choice')
            control=data; _validate_function_control(goal,control,probes)
        elif kind=='F_DIAGNOSIS':
            if diagnosis is not None or public or control is None: raise MissionHold('retrospective or duplicate forecast')
            diagnosis=data
            if data.get('control_sha256')!=digest(canonical(control)): raise MissionHold('unbound computation forecast')
            _validate_public_forecast(control,data['ranking'])
            _validate_computation_cost(data['computation_cost'])
            for field in ('probabilities','frequency_probabilities'):
                values=data['ranking'][field]
                if (not isinstance(values,list) or len(values)!=2 or any(type(p) not in (int,float)
                        or not math.isfinite(p) or not 0<p<1 for p in values)):
                    raise MissionHold('malformed pre-observation probabilities')
            if (data['ranking']['mechanism']!=control['decision']['mechanism']
                    or data['ranking']['action_schema']!=FUNCTION_ACTION_SCHEMA
                    or sorted(data['order'])!=sorted(p['id'] for p in goal['analysis']['proposals'])):
                raise MissionHold('forecast mechanism or candidate inventory changed')
        elif kind=='F_DISPATCHED':
            if pending or not data['operation'].startswith(('probe:','search:')): raise MissionHold('private or duplicate dispatch in public training')
            if data['operation'].startswith('search:') and diagnosis is None: raise MissionHold('forecast recorded after its outcome')
            pending=data
        elif kind=='F_RECOVERED':
            if not pending or data['container_name']!=pending['container_name'] or data.get('disposal_confirmed') is not True:
                raise MissionHold('public training cleanup changed')
            pending=None
        elif kind=='F_OBSERVED':
            if not pending or data['operation']!=pending['operation']: raise MissionHold('unbound public training outcome')
            result=_validate_function_execution(goal,pending,data['execution'],None)
            if result!=data['result']: raise MissionHold('public training result differs from bound receipt')
            (probes if data['operation'].startswith('probe:') else public).append(data); pending=None
        elif kind not in ('PLATFORM_CREATED','F_PATCH','F_PATCHED','F_SELECTED'):
            raise MissionHold('nonpublic evidence in computation training')
    if (pending or not public or diagnosis is None or trace[-1]['kind']!='F_SELECTED'
            or trace[-1]['data']!={'candidate':selected} or not public[-1]['result']['supported']
            or public[-1]['operation']!='search:'+selected or any(r['result']['supported'] for r in public[:-1])
            or [r['operation'].partition(':')[2] for r in public]!=diagnosis['order'][:len(public)]):
        raise MissionHold('public computation outcomes are not the accepted search prefix')
    gain=0.0
    for row in public:
        proposal=_function_proposal(goal,row['operation'].partition(':')[2]); action=int(proposal['family']!='comparison')
        p=diagnosis['ranking']['probabilities'][action]; base=diagnosis['ranking']['frequency_probabilities'][action]
        outcome=row['result']['supported']
        gain+=math.log((p if outcome else 1-p)/(base if outcome else 1-base))
    gain=max(-8.0,min(8.0,gain/len(public)))
    expected={'control':control,'public_search':public,'public_log_gain':gain,'cost':diagnosis['computation_cost']}
    if {k:evidence[k] for k in expected}!=expected: raise MissionHold('relabelled public computation benefit or cost')
    return expected


def _function_memory(path: Path | None, *, mode='native', epoch=0) -> dict:
    try:
        return _rebuild_function_memory(path, mode=mode, epoch=epoch)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, OverflowError) as error:
        raise MissionHold('function memory artifact missing, malformed, or inconsistent') from error


def _rebuild_function_memory(path: Path | None, *, mode='native', epoch=0) -> dict:
    ranker = NativeDecisionRanker(mode, action_schema=FUNCTION_ACTION_SCHEMA)
    world = repo_world.RepositoryWorldModel(include_failure=False)
    memory = EvidenceMemory()
    result = {'ranker': ranker, 'world': world, 'memory': memory, 'head': '0'*64,
              'heads': [], 'records': [], 'eligible_tasks': 0, 'eligible_records': []}
    if path is None or not path.exists(): return result
    journal_path = path / 'events.jsonl'
    if not journal_path.is_file(): raise MissionHold('function memory history missing')
    if journal_path.stat().st_size > 64_000_000: raise MissionHold('function memory byte budget exceeded')
    rows = Journal(journal_path, FUNCTION_MEMORY_ID).read()
    if not rows or rows[0]['kind'] != 'MEMORY_CREATED' or len(rows) > 513 or journal_path.stat().st_size > 64_000_000:
        raise MissionHold('function memory origin or budget invalid')
    seen = set(); eligible_sources = set()
    for row in rows[1:]:
        record = row['data']
        if row['kind'] != 'OBSERVATION_ADMITTED' or record.get('scope') != frontier.FUNCTION_ADAPTER:
            raise MissionHold('cross-adapter function memory refused')
        origin=record['origin']
        origin_identity={k:v for k,v in origin.items() if k!='mission_id'}
        if digest(canonical(origin_identity))[:32]!=origin['mission_id'] or origin['adapter']!=frontier.FUNCTION_ADAPTER:
            raise MissionHold('stored function origin changed')
        if (record['mission_id']!=origin['mission_id'] or record['baseline']!=origin['baseline']
                or record['files']!=origin['analysis']['files'] or record['task_identity']!=origin['analysis']['task_identity']
                or record['capture_epoch']!=origin['analysis']['capture_epoch'] or record['runtime']!=origin['runtime_sha256']
                or record['signatures']!=origin['analysis']['signatures']
                or record['candidate']!=_function_proposal(origin,record['candidate']['id'])
                or record['candidate']['id']!=frontier.digest(json.dumps(record['candidate']['files'],sort_keys=True))):
            raise MissionHold('function memory source/task/action scope changed')
        recomputed_task=digest(canonical({'files':{k:ast.dump(ast.parse(v),include_attributes=False) for k,v in record['files'].items()},
                                         'public':origin['public']}))
        expected_execution_goal={k:origin[k] for k in ('public','policy','baseline','baseline_entries','public_command')}
        expected_execution_goal['analysis']={'proposals':[record['candidate']]}
        if recomputed_task!=record['task_identity'] or record['execution_goal']!=expected_execution_goal:
            raise MissionHold('function memory execution origin differs')
        acceptance=record['acceptance']; body={k:v for k,v in acceptance.items() if k!='sha256'}
        if (acceptance.get('sha256')!=digest(canonical(body)) or acceptance.get('final_supported') is not True
                or acceptance.get('candidate_sha256')!=record['candidate']['id']
                or acceptance.get('sealed_sha256')!=origin['sealed_sha256']
                or acceptance.get('witness_receipt_sha256')!=record['witness']['receipt_hash']
                or any(not isinstance(acceptance.get(k),str) or len(acceptance[k])!=64
                       for k in ('final_observation_sha256','commit_sha256'))):
            raise MissionHold('function final acceptance provenance changed')
        witness = WitnessReceipt(**record['witness'])
        if (not witness.verify_checksum() or not witness.supported or witness.witness_id != FUNCTION_WITNESS
                or witness.transmission_id != record['candidate']['id']
                or witness.task_id != record['mission_id']
                or record['observation_id'] != digest(canonical([record['task_identity'], record['candidate']['id']]))
                or record['public_result']['supported'] is not True
                or record['capture_epoch'] < 0):
            raise MissionHold('function memory evidence binding invalid')
        observed = _validate_function_execution(record['execution_goal'],
            {'operation':'search:'+record['candidate']['id'],
             'container_name':record['public_result']['execution']['container_name']},
            record['public_result']['execution'], None)
        if observed != {k:v for k,v in record['public_result'].items() if k!='execution'}:
            raise MissionHold('stored function public evidence changed')
        if 'computation_evidence' in record:
            _validate_computation_evidence(record['origin'],record['computation_evidence'],record['candidate']['id'])
        elif record['origin'].get('computation') is not None:
            raise MissionHold('accepted adaptive observation lost its public computation evidence')
        if origin.get('persistent') is not None:
            pinned=origin['analysis']['memory_head'];prior_records=[];prior_sources=set()
            if pinned!='0'*64:
                indices=[i for i,r in enumerate(rows) if r['sha256']==pinned]
                if len(indices)!=1 or rows.index(row)<=indices[0]:raise MissionHold('persistent origin memory prefix missing or future')
                for prior_row in rows[1:indices[0]+1]:
                    prior_record=prior_row['data'];source=digest(canonical(prior_record['baseline']))
                    if (prior_record['runtime']!=_runtime_identity(persistent=prior_record['origin'].get('persistent') is not None)
                            or not 0<=origin['analysis']['capture_epoch']-prior_record['capture_epoch']<=4
                            or source in prior_sources):continue
                    prior_sources.add(source);prior_records.append(prior_record)
            prefix,bindings,_=_persistent_prefix(PersistentConfig(**origin['persistent']['config']),prior_records)
            cache=origin['persistent']['memory_cache']
            if (origin['persistent']['controller_before']['payload']['history']!=[list(pair) for pair in prefix]
                    or cache['bindings']!=bindings or cache['public_prefix_sha256']!=prefix_digest(prefix)
                    or cache['observations']!=len(prefix)):
                raise MissionHold('persistent initial state does not bind the admitted memory prefix')
            evidence=record['persistent_evidence']
            checked=_validate_persistent_trace(origin,evidence['public_trace'],complete=True,selected=record['candidate']['id'])
            if evidence['public_search']!=checked['public_search'] or evidence['terminal_state']!=checked['state']:
                raise MissionHold('persistent accepted state differs from its public receipts')
        elif 'persistent_evidence' in record:
            raise MissionHold('persistent state lacks a persistent mission origin')
        if record['observation_id'] in seen: raise MissionHold('duplicate function memory admission')
        seen.add(record['observation_id'])
        result['records'].append(record)
        if record['runtime'] != _runtime_identity(persistent=origin.get('persistent') is not None) or not 0 <= epoch-record['capture_epoch'] <= 4: continue
        source_sha = digest(canonical(record['baseline']))
        if source_sha in eligible_sources: continue
        eligible_sources.add(source_sha)
        result['eligible_records'].append(record)
        ranker.observe(PublicObservation(record['task_identity'], source_sha, record['candidate']['id'],
            digest(canonical(record['public_result']['execution'])), record['candidate']['family'], True,
            record['capture_epoch']), independently_observed=True)
        for name, signature in record['signatures'].items():
            world.observe(signature, name in record['candidate']['files'])
        result['eligible_tasks'] += 1
        if record.get('mnemonic') is not None:
            saved = record['mnemonic']
            changed=list(record['candidate']['files']); public=origin['public']; first=public[0]
            if (len(changed)!=1 or '/' in changed[0] or saved['changed_file']!=changed[0]
                    or saved['module']!=first['module'] or saved['function']!=first['function']
                    or saved['rows']!=[[i,0] for i in range(len(public))]
                    or saved['receipt']['after']!=[1.0]*len(public)
                    or digest(canonical({'current':saved['receipt']['before'],'target':[1.0]*len(public),
                                         'candidate':[1.0]*len(public)}))!=witness.public_evidence_digest):
                raise MissionHold('MNEMONIC effect differs from bound public WITNESS observation')
            task = AtlasTask(record['task_identity'], record['files'], saved['changed_file'],
                (Contract(saved['module'], saved['function'], tuple(tuple(x) for x in saved['rows'])),), (), (), ())
            receipt = ChangeReceipt(**{**saved['receipt'], 'before': tuple(saved['receipt']['before']),
                                       'after': tuple(saved['receipt']['after'])})
            memory.record(task=task, contract=receipt.contract,
                action_source=record['candidate']['files'][saved['changed_file']], receipt=receipt,
                capture_epoch=record['capture_epoch'])
    result.update(head=rows[-1]['sha256'], heads=[r['sha256'] for r in rows])
    return result


def read_function_memory_ranker(memory_root: Path, *, mode='native', now_epoch=0) -> NativeDecisionRanker:
    path = Path(memory_root)
    if not path.exists(): return _function_memory(None, mode=mode, epoch=now_epoch)['ranker']
    with exclusive_owner(path): return _function_memory(path, mode=mode, epoch=now_epoch)['ranker']


def read_function_computation_controller(memory_root: Path, *, config=None, now_epoch=0):
    """Read-only rebuilt public predictor, never an admission or verifier."""
    configuration=config or AdaptiveConfig()
    if type(configuration) is dict: configuration=AdaptiveConfig(**configuration)
    if type(configuration) is not AdaptiveConfig: raise ValueError('configuration required')
    path=Path(memory_root)
    if path.exists():
        with exclusive_owner(path): models=_function_memory(path,mode='frequency',epoch=now_epoch)
    else: models=_function_memory(None,mode='frequency',epoch=now_epoch)
    return _controller_from_memory(configuration,models)


def initialize_functions(root: Path, source: Path, *, goal_text: str, public: list[dict],
        challenge: list[dict], final: list[dict], policy: SandboxPolicy, ranker=None,
        memory_root: Path | None = None, capture_epoch=0, adaptive_enabled=True,
        max_candidates=64, max_executions=96, probe_budget=3, max_files_changed=2,
        public_command: list[str] | None = None, computation_controller=None, persistent_controller=None,
        operating_mechanism=None) -> dict:
    """Initialize a bounded function mission without importing repository code.

    Public cases, finite AST inventory and planning models are frozen. Private
    values are sealed separately. No native qualification is inferred here.
    """
    policy.validate()
    config=None
    persistent_config=None
    if operating_mechanism is not None:
        if operating_mechanism not in ('frequency', 'temporal', 'native'):
            raise ValueError('unsupported operating mechanism')
        if persistent_controller is not None or computation_controller is not None or ranker is not None:
            raise ValueError('operating mechanism cannot be combined with research controllers or rankers')
        persistent_controller=operational_config()
    if persistent_controller is not None:
        if computation_controller is not None or ranker is not None:raise ValueError('persistent and adaptive/static controllers are mutually exclusive')
        if type(persistent_controller) is dict:
            if len(canonical(persistent_controller))>8192:raise ValueError('persistent configuration byte budget exceeded')
            persistent_config=PersistentConfig(**persistent_controller)
        elif type(persistent_controller) is PersistentConfig:persistent_config=PersistentConfig(**asdict(persistent_controller))
        else:raise ValueError('persistent controller accepts configuration only, never unverified learned state')
        persistent_config.validate()
    if computation_controller is not None:
        if type(computation_controller) is dict:
            if len(canonical(computation_controller))>8192: raise ValueError('computation configuration byte budget exceeded')
            config=AdaptiveConfig(**computation_controller)
        elif type(computation_controller) is AdaptiveConfig:
            config=AdaptiveConfig(**asdict(computation_controller))
        else: raise ValueError('computation controller accepts configuration only, never unverified learned state')
        config.validate()
        if ranker is not None: raise ValueError('adaptive computation owns ranking; explicit static ranker conflicts')
    public, challenge, final = (frontier.validate_function_cases(r) for r in (public, challenge, final))
    for partition in (public,challenge,final,public+challenge): frontier.function_command(partition)
    inputs = [digest(canonical(frontier.function_inputs(rows))) for rows in (public, challenge, final)]
    all_inputs = [digest(canonical(r)) for rows in (public, challenge, final) for r in frontier.function_inputs(rows)]
    if len(set(all_inputs)) != len(all_inputs): raise ValueError('function evidence partitions overlap')
    if (not isinstance(goal_text, str) or not 1 <= len(goal_text) <= 4096
            or type(capture_epoch) is not int or capture_epoch < 0 or type(adaptive_enabled) is not bool
            or type(max_executions) is not int or not 5 <= max_executions <= 256
            or type(probe_budget) is not int or not 1 <= probe_budget <= 8
            or type(max_candidates) is not int or not 1<=max_candidates<=128 or max_files_changed not in (1,2)):
        raise ValueError('function mission goal or budget invalid')
    if public_command not in (None, COMMAND): raise ValueError('only the registered full unittest command is supported')
    source = Path(source)
    metadata = source.lstat()
    if stat.S_ISLNK(metadata.st_mode) or _reparse(metadata): raise UnsafeWorkspace('source root links refused')
    source, root = source.resolve(strict=True), Path(root).resolve()
    if root == source or root in source.parents or source in root.parents: raise ValueError('source and mission must be disjoint')
    if root.exists(): raise FileExistsError('mission root exists')
    memory_root = Path(memory_root).resolve() if memory_root else None
    if memory_root and any(memory_root == p or memory_root in p.parents or p in memory_root.parents for p in (source, root)):
        raise ValueError('function memory must be disjoint')
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nomad-function-init-', dir=root.parent) as temporary:
        stage = Path(temporary)
        snapshot_source(source, stage/'baseline', policy)
        started=(time.perf_counter(),time.process_time())
        analysis = (frontier.inspect_function_structure(stage/'baseline',public) if config or persistent_config else
            frontier.inspect_function_repository(stage/'baseline', public,
                max_candidates=max_candidates, max_files_changed=max_files_changed))
        for row in challenge+final:
            filename = analysis['modules'].get(row['module'])
            if not filename or row['function'] not in analysis['symbols'][filename]:
                raise ValueError('private callable outside admitted interface')
        if public_command and not (stage/'baseline'/'tests').is_dir(): raise ValueError('registered suite requires tests directory')
        manifest = _manifest(stage/'baseline')
        entries = [[name,sha,(stage/'baseline'/name).stat().st_size] for name,sha in manifest.items()]
        mode = 'frequency' if config or persistent_config else getattr(ranker, 'mode', 'native')
        if memory_root and memory_root.exists():
            with exclusive_owner(memory_root): models = _function_memory(memory_root, mode=mode, epoch=capture_epoch)
        else: models = _function_memory(memory_root, mode=mode, epoch=capture_epoch)
        computation=None;persistent=None
        if config or persistent_config:
            analysis['eligible_memory_tasks']=models['eligible_tasks']
            if persistent_config:
                controller,cache=_persistent_from_memory(persistent_config,models,capture_epoch,operating_mechanism)
            else:controller=_controller_from_memory(config,models)
            allocation=(_persistent_allocation if persistent_config else _allocation)(controller,analysis,max_candidates=max_candidates,probe_budget=probe_budget,
                                   max_executions=max_executions,public_command=public_command,
                                   **({'operating_mechanism':operating_mechanism} if persistent_config else {}))
            inspection_cost=_computation_cost(started)
            started=(time.perf_counter(),time.process_time())
            # Only source-reachable modules enter the optional inventory. This
            # is static graph localization, not evidence of fault correctness.
            reachable=set(); pending=[analysis['modules'][r['module']] for r in public]
            while pending:
                name=pending.pop()
                if name in reachable: continue
                reachable.add(name); pending.extend(analysis['graph'][name])
            generation_files=sorted(reachable)
            if allocation['use_localization']:
                generation_files.sort(key=lambda n:-models['world'].score(sorted(repo_world._ast_tokens(analysis['files'][n])|{'reachable'})))
            analysis=frontier.inspect_function_repository(stage/'baseline',public,
                max_candidates=allocation['max_candidates'],max_files_changed=max_files_changed,
                genesis_max_eval=allocation['genesis_max_eval'],generation_files=generation_files,
                ast_check_budget=allocation['ast_check_budget'])
            computation={**allocation,'generation_files':generation_files,
                'requested_limits':{'max_candidates':max_candidates,'probe_budget':probe_budget},
                'inspection_and_memory_validation_cost':inspection_cost,'generation_cost':_computation_cost(started),
                'objective':'public log-loss gain versus frequency; accepted-only sampling, no causal utility claim'}
            if persistent_config:
                persistent={**computation,'memory_cache':cache,'mnemonic_snapshot':models['memory'].snapshot()};computation=None
            probe_budget=allocation['probe_budget']
        active = ranker or models['ranker']
        if not isinstance(active, NativeDecisionRanker) or active.action_schema != FUNCTION_ACTION_SCHEMA:
            raise ValueError('function mission requires the scoped native ranker')
        if ranker is not None:
            for observation in models['ranker'].events: active.observe(observation, independently_observed=True)
        files = analysis['files']
        graph_task = repo_world.RepoTask('function-structure',files,public[0]['module'],(),(),(),'','')
        graph,_,_ = repo_world.build_graph(graph_task)
        if {k:sorted(v) for k,v in graph.items()} != analysis['graph']:
            raise ValueError('static import observers disagree')
        # Existing WORLD MODEL structural tokens; no host failure harness.
        reachable=set(); pending=[analysis['modules'][row['module']] for row in public]
        while pending:
            current=pending.pop()
            if current in reachable: continue
            reachable.add(current);pending.extend(graph[current])
        signatures = {name: sorted(repo_world._ast_tokens(text) | {'reachable' if name in reachable else 'unreachable'})
                      for name, text in files.items()}
        effort=persistent or computation
        localize=adaptive_enabled and (effort is None or effort['use_localization'])
        scores = {name: models['world'].score(sig) if localize else 0.0 for name, sig in signatures.items()}
        weights = {name: math.exp(max(-40, (score-max(scores.values()))/12)) for name, score in scores.items()}
        prior = {name: w/sum(weights.values()) for name,w in weights.items()}
        analysis.update(signatures=signatures, world_scores=scores, world_prior=prior,
            task_identity=digest(canonical({'files': {k: ast.dump(ast.parse(v), include_attributes=False) for k,v in files.items()},
                                            'public': public})), memory_head=models['head'],
            eligible_memory_tasks=models['eligible_tasks'], capture_epoch=capture_epoch, adaptive_enabled=adaptive_enabled)
        sealed = canonical({'challenge': challenge, 'final': final})
        models['memory'].save(stage/'planning_memory.json')
        save_atomic(stage/'planning_ranker.json', canonical(active.snapshot()))
        goal = {'schema': SCHEMA, 'version': '0.18.0', 'adapter': frontier.FUNCTION_ADAPTER,
            'goal': goal_text, 'public': public, 'policy': asdict(policy), 'baseline': manifest, 'baseline_entries':entries,
            'runtime_sha256': _runtime_identity(persistent=persistent is not None), 'sealed_sha256': digest(sealed),
            'analysis': analysis, 'candidate': None, 'memory_root': str(memory_root) if memory_root else None,
            'planning':{'candidate_inventory_sha256':analysis['candidate_inventory_sha256'],
                        'ast_candidates_evaluated':analysis['generated_candidates_checked'],
                        'genesis':analysis['genesis']},
            'max_executions': max_executions, 'probe_budget': probe_budget, 'public_command': public_command,
            'planning_context': {n: digest((stage/n).read_bytes()) for n in ('planning_memory.json','planning_ranker.json')},
            'scope': 'bounded JSON Python functions, local import graph, up to two edited files; no arbitrary Python authority'}
        if computation is not None: goal['computation']=computation
        if persistent is not None:goal['persistent']=persistent
        goal['mission_id'] = digest(canonical(goal))[:32]
        shutil.copytree(stage/'baseline', stage/'workspace')
        save_atomic(stage/'goal.json', canonical(goal)); save_atomic(stage/'sealed.json', sealed)
        EffectLedger(stage/'effects')
        (stage/'events.jsonl').touch()
        Journal(stage/'events.jsonl', goal['mission_id']).append('PLATFORM_CREATED', {'goal_sha256': digest(canonical(goal))})
        _publish_staged_mission(stage, root)
    return goal


def _function_proposal(goal, identity):
    if identity is None: return None
    found = [p for p in goal['analysis']['proposals'] if p['id'] == identity]
    if len(found) != 1: raise MissionHold('unrecognized function proposal')
    return found[0]


def _function_manifest(goal, identity):
    proposal = _function_proposal(goal, identity)
    return {**goal['baseline'], **({k: digest(v.encode()) for k,v in proposal['files'].items()} if proposal else {})}


def _function_spec(goal, sealed, operation):
    stage, _, value = operation.partition(':')
    proposal = None
    if stage == 'probe':
        index = int(value)
        if not 0<=index<len(goal['public']) or value!=str(index): raise MissionHold('invalid canonical public probe index')
        rows = [goal['public'][index]]
    elif stage == 'search':
        proposal = _function_proposal(goal, value); rows = goal['public']
    elif stage in ('before', 'challenge', 'final', 'suite'):
        proposal = _function_proposal(goal, value)
        rows = (goal['public']+sealed['challenge']) if stage == 'before' else sealed['challenge'] if stage == 'challenge' else sealed['final'] if stage == 'final' else []
    else: raise MissionHold('unrecognized function operation')
    command = goal['public_command'] if stage == 'suite' else frontier.function_command(rows)
    if not command: raise MissionHold('unregistered full-suite operation')
    return rows, command, None if stage in ('probe','before') else proposal['id']


def _validate_function_execution(goal, data, execution, root):
    sealed = json.loads((root/'sealed.json').read_bytes()) if root is not None else {}
    rows, command, identity = _function_spec(goal, sealed, data['operation'])
    manifest = _function_manifest(goal, identity)
    proposal = _function_proposal(goal, identity)
    baseline_sizes = {row[0]:row[2] for row in goal['baseline_entries']}
    entries = [[name, sha, len(proposal['files'][name].encode()) if proposal and name in proposal['files']
                else baseline_sizes[name]] for name,sha in sorted(manifest.items())]
    expected = {'schema': 'nomad.isolated-test.v1', 'container_name': data['container_name'],
        'image_digest': goal['policy']['image'].split('@sha256:')[-1], 'command': command,
        'snapshot_sha256': digest(canonical(entries)), 'source_files': len(entries),
        'source_bytes': sum(row[2] for row in entries), 'container_cleanup_confirmed': True}
    if any(execution.get(k) != v for k,v in expected.items()): raise MissionHold('foreign function execution receipt')
    if (type(execution.get('returncode')) is not int or type(execution.get('timed_out')) is not bool
            or execution.get('tests_passed') is not (execution['returncode'] == 0 and not execution['timed_out'])):
        raise MissionHold('inconsistent function execution verdict')
    return ({'supported': execution['tests_passed'], 'matches': [], 'observed_sha256': execution['output_sha256']}
            if not rows else frontier.compare_function_output(execution, rows))


def _load_functions(root, goal):
    original = _origin_goal(goal)
    identity = {k:v for k,v in original.items() if k != 'mission_id'}
    if digest(canonical(identity))[:32] != original['mission_id'] or original['runtime_sha256'] != _runtime_identity(persistent=original.get('persistent') is not None):
        raise MissionHold('function goal or runtime identity changed')
    SandboxPolicy(**original['policy']).validate()
    computation=original.get('computation')
    if computation is not None:
        _validate_control(computation)
        before=AdaptiveController.load(computation['controller_before'])
        limits=computation['requested_limits']
        inspected={**original['analysis'],'proposals':[]}
        allocation=_allocation(before,inspected,max_candidates=limits['max_candidates'],probe_budget=limits['probe_budget'],
            max_executions=original['max_executions'],public_command=original['public_command'])
        if any(computation.get(key)!=value for key,value in allocation.items()):
            raise MissionHold('registered computation allocation changed')
        for field in ('inspection_and_memory_validation_cost','generation_cost'):
            _validate_computation_cost(computation[field])
        if (original['probe_budget']!=computation['probe_budget']
                or len(original['analysis']['proposals'])>computation['max_candidates']
                or original['analysis']['generated_candidates_checked']>computation['ast_check_budget']):
            raise MissionHold('computation allocation or proposal budget changed')
    if _manifest(root/'baseline') != original['baseline'] or digest((root/'sealed.json').read_bytes()) != original['sealed_sha256']:
        raise MissionHold('function source or private evidence changed')
    for name, sha in original['planning_context'].items():
        if name not in ('planning_memory.json','planning_ranker.json') or digest((root/name).read_bytes()) != sha:
            raise MissionHold('function planning context changed')
    if original.get('persistent') is not None and original['persistent']['mnemonic_snapshot']!=json.loads((root/'planning_memory.json').read_bytes())['payload']:
        raise MissionHold('persistent planning memory differs from sealed snapshot')
    if not EffectLedger(root/'effects', create=False).snapshot()['replay_safe']: raise MissionHold('unresolved function external effect')
    journal = Journal(root/'events.jsonl', original['mission_id'])
    if original.get('persistent') is not None and (root/'events.jsonl').stat().st_size>PERSISTENT_JOURNAL_BYTES:
        raise MissionHold('persistent journal byte budget exceeded')
    rows = journal.read()
    if not rows or rows[0]['kind'] != 'PLATFORM_CREATED' or rows[0]['data'] != {'goal_sha256': digest(canonical(original))}:
        raise MissionHold('function mission origin changed')
    persistent_context=_validate_persistent_trace(original,rows) if original.get('persistent') is not None else None
    pending = None; expected = dict(original['baseline']); patch = None; selected = None
    observations = {}; committed = False; finished = False; witness = None; final = None
    patch_ids = set(); dispatches = 0; diagnosed = False; control = None; diagnosis = None
    for row in rows[1:]:
        kind, data = row['kind'], row['data']
        if finished: raise MissionHold('events after function terminal state')
        if committed and kind!='F_LEARNED': raise MissionHold('committed function candidate is immutable')
        if pending and kind not in ('F_OBSERVED','F_RECOVERED'): raise MissionHold('unreconciled function dispatch')
        if patch and kind != 'F_PATCHED': raise MissionHold('uncompleted function patch transaction')
        if kind == 'F_PATCH':
            if data['id'] in patch_ids or data['before'] != expected: raise MissionHold('duplicate or stale function patch')
            patch_ids.add(data['id']); target = _function_manifest(original, data['candidate'])
            if data['after'] != target: raise MissionHold('foreign function patch target')
            patch = data
        elif kind == 'F_PATCHED':
            if patch is None or data != {'id': patch['id']}: raise MissionHold('function patch completion without intent')
            expected = patch['after']; patch = None
        elif kind == 'F_DISPATCHED':
            dispatches += 1
            if dispatches > original['max_executions']: raise MissionHold('function execution budget exceeded')
            _, _, candidate_id = _function_spec(original, json.loads((root/'sealed.json').read_bytes()), data['operation'])
            stage=data['operation'].split(':')[0]
            if computation is not None and stage=='search' and (not diagnosed or control['decision']['mechanism']=='abstain'):
                raise MissionHold('search without an eligible recorded computation choice')
            if (stage in ('before','challenge','final','suite') and (selected is None or data['operation'].partition(':')[2]!=selected['id'])
                    or stage in ('probe','search') and selected is not None
                    or stage=='final' and (witness is None or not witness.supported)):
                raise MissionHold('function observation stage violates evidence separation')
            if expected != _function_manifest(original, candidate_id): raise MissionHold('function operation source mismatch')
            if data['operation'] in observations: raise MissionHold('duplicate completed function operation')
            pending = data
        elif kind == 'F_RECOVERED':
            if not pending or data != {'operation': pending['operation'], 'container_name': pending['container_name'], 'disposal_confirmed': True}:
                raise MissionHold('foreign function cleanup receipt')
            pending = None
        elif kind == 'F_OBSERVED':
            if not pending or data['operation'] != pending['operation']: raise MissionHold('unbound function observation')
            observed = _validate_function_execution(original, pending, data['execution'], root)
            if data['result'] != observed: raise MissionHold('function observation differs from trusted comparison')
            observations[data['operation']] = data; pending = None
        elif kind == 'F_DIAGNOSIS':
            if selected is not None or diagnosed: raise MissionHold('duplicate or late function diagnosis')
            if sorted(data['order'])!=sorted(p['id'] for p in original['analysis']['proposals']):
                raise MissionHold('function diagnosis changed frozen candidate inventory')
            if computation is not None:
                if control is None or data.get('control_sha256')!=digest(canonical(control)):
                    raise MissionHold('adaptive forecast lacks a prior computation decision')
                _validate_computation_cost(data['computation_cost'])
                _validate_public_forecast(control,data['ranking'])
                if data['ranking']['mechanism']!=control['decision']['mechanism']:
                    raise MissionHold('ranking mechanism differs from registered choice')
                for key in ('probabilities','frequency_probabilities'):
                    values=data['ranking'][key]
                    if len(values)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<1 for v in values):
                        raise MissionHold('invalid public forecast probability')
            diagnosis=data
            diagnosed = True
        elif kind == 'F_CONTROL':
            if computation is None or control is not None or diagnosed or selected is not None:
                raise MissionHold('duplicate or late adaptive computation decision')
            probes=[value for key,value in observations.items() if key.startswith('probe:')]
            if any(not key.startswith('probe:') for key in observations):
                raise MissionHold('adaptive choice recorded after candidate outcomes')
            _validate_function_control(original,data,probes)
            control=data
        elif kind in ('F_P_CONTROL','F_P_FORECAST','F_P_UPDATED'):
            if persistent_context is None or selected is not None:raise MissionHold('foreign or late persistent controller event')
        elif kind == 'F_SELECTED':
            if not diagnosed or selected is not None or not observations.get('search:'+data['candidate'], {}).get('result',{}).get('supported'):
                raise MissionHold('function selection lacks public support')
            selected = _function_proposal(original, data['candidate'])
        elif kind == 'F_WITNESS':
            if selected is None or witness is not None: raise MissionHold('duplicate witness or witness before function selection')
            witness = WitnessReceipt(**data['receipt'])
            expected_witness = _function_witness(original, selected, observations)
            if asdict(witness) != asdict(expected_witness): raise MissionHold('function WITNESS observation changed')
        elif kind == 'F_FINAL':
            if final is not None or witness is None or not witness.supported or selected is None: raise MissionHold('duplicate final or final without supported WITNESS')
            final = observations.get('final:'+selected['id'])
            if final is None or data != {'supported': final['result']['supported'], 'observation_sha256': digest(canonical(final))}:
                raise MissionHold('unbound final function observation')
        elif kind == 'F_COMMITTED':
            if committed or data != {'candidate':selected['id'] if selected else None}:
                raise MissionHold('duplicate or foreign function commit')
            if not final or not final['result']['supported'] or selected is None or expected != _function_manifest(original, selected['id']):
                raise MissionHold('unverified function commit')
            if original['public_command'] and not observations.get('suite:'+selected['id'],{}).get('result',{}).get('supported'):
                raise MissionHold('full suite did not support commit')
            committed = True
        elif kind == 'F_LEARNED':
            if not committed or digest((root/'learning.json').read_bytes()) != data['learning_sha256']:
                raise MissionHold('unbound function learning')
            memory_path = Path(original['memory_root']) if original['memory_root'] else root/'mnemonic'
            model = _function_memory(memory_path, epoch=original['analysis']['capture_epoch'])
            learning = json.loads((root/'learning.json').read_bytes())
            if not any(r['observation_id'] == learning['observation_id'] for r in model['records']):
                raise MissionHold('function learned observation lost')
            finished = True
        elif kind == 'F_ABSTAINED':
            if persistent_context is not None:
                declined=(original['persistent']['decision']['mechanism']=='abstain' or not original['analysis']['proposals']
                    or persistent_context['control'] is not None and persistent_context['control']['decision']['mechanism']=='abstain')
                if expected!=original['baseline'] or selected is not None or not declined or persistent_context['forecast'] is not None:
                    raise MissionHold('persistent abstention does not match settled public state')
            elif (computation is None or expected!=original['baseline'] or selected is not None
                    or any(k.startswith('search:') for k in observations)
                    or (computation['decision']['mechanism']!='abstain' and original['analysis']['proposals']
                        and (control is None or control['decision']['mechanism']!='abstain'))):
                raise MissionHold('abstention does not match public-only computation state')
            finished=True
        elif kind in ('F_REJECTED','F_EXHAUSTED'):
            if expected != original['baseline']: raise MissionHold('terminal function rollback incomplete')
            finished = True
        else: raise MissionHold('unknown function transition')
    actual = _manifest(root/'workspace')
    if patch:
        if set(actual) != set(expected) or any(actual[k] not in (patch['before'][k],patch['after'][k]) for k in actual):
            raise MissionHold('unexpected partial function patch')
    elif actual != expected: raise MissionHold('unexpected function workspace modification')
    return {**original, '_origin': original, 'candidate': selected}, journal, rows


def _function_summary(goal, rows):
    status = {'F_LEARNED':'completed','F_REJECTED':'rejected','F_EXHAUSTED':'exhausted',
              'F_ABSTAINED':'abstained','F_DISPATCHED':'hold_uncertain_execution','F_COMMITTED':'committed'}.get(rows[-1]['kind'],'in_progress')
    result={'schema': SCHEMA+'.summary', 'adapter': frontier.FUNCTION_ADAPTER, 'mission_id': goal['mission_id'],
        'status':status, 'events':len(rows), 'journal_head':rows[-1]['sha256'],
        'dispatches':sum(r['kind']=='F_DISPATCHED' for r in rows),
        'public_executions_recorded':sum(r['kind']=='F_OBSERVED' and r['data']['operation'].startswith('search:') for r in rows),
        'baseline_probes_recorded':sum(r['kind']=='F_OBSERVED' and r['data']['operation'].startswith('probe:') for r in rows),
        'witness_observations':sum(r['kind']=='F_WITNESS' for r in rows),
        'final_observations':sum(r['kind']=='F_FINAL' for r in rows),
        'candidate_inventory_sha256':goal['analysis']['candidate_inventory_sha256'],
        'candidate_inventory_count':len(goal['analysis']['proposals']), 'cloud_model_calls':0,
        'scope':goal['scope'], 'authority':'finite isolated API observations; candidate review only, no deployment or skill promotion'}
    if goal.get('persistent') is not None:
        controls=[r['data'] for r in rows if r['kind']=='F_P_CONTROL']
        updates=[r['data'] for r in rows if r['kind']=='F_P_UPDATED']
        costs=[goal['persistent'][name] for name in ('inspection_and_memory_validation_cost','generation_cost')]
        costs += [row['cost'] for row in controls+updates]
        result['persistent']={'allocation':goal['persistent']['decision']['mechanism'],
            'mechanisms':[row['decision']['mechanism'] for row in controls],
            'public_updates':len(updates),'memory_cache':goal['persistent']['memory_cache'],
            'recorded_controller_cpu_seconds':sum(c['cpu_seconds'] for c in costs),
            'recorded_controller_wall_seconds':sum(c['wall_seconds'] for c in costs),
            'cost_scope':'recorded controller stages; excludes Docker worker CPU, validation/replay and strict peak memory',
            'authority':'ranking and bounded effort only; coding advantage NOT_ESTABLISHED'}
    if goal.get('computation') is not None:
        costs=[goal['computation'][name] for name in ('inspection_and_memory_validation_cost','generation_cost')]
        costs += [r['data']['computation_cost'] for r in rows if r['kind']=='F_DIAGNOSIS']
        result['computation']={'allocation':goal['computation']['decision']['mechanism'],
            'ranking':next((r['data']['decision']['mechanism'] for r in rows if r['kind']=='F_CONTROL'),None),
            'recorded_controller_wall_seconds':sum(c['wall_seconds'] for c in costs),
            'recorded_controller_cpu_seconds':sum(c['cpu_seconds'] for c in costs),
            'controller_cost_scope':'completed inspection/memory audit, generation and ranking stages; excludes worker CPU, recovery/replay overhead and peak memory',
            'abstention_is_verification':False}
    return result


def _function_witness(goal, candidate, observations):
    before = observations['before:'+candidate['id']]['result']['matches']
    public = observations['search:'+candidate['id']]['result']['matches']
    challenge = observations['challenge:'+candidate['id']]['result']['matches']
    n = len(public)
    return Witness(FUNCTION_WITNESS).attest(task_id=goal['mission_id'], transmission_id=candidate['id'], world_epoch=0,
        current_public=tuple(map(float,before[:n])), target_public=(1.0,)*n, candidate_public=tuple(map(float,public)),
        current_challenge=tuple(map(float,before[n:])), target_challenge=(1.0,)*len(challenge),
        candidate_challenge=tuple(map(float,challenge)))


def _function_learn(root, goal, rows, candidate):
    path = Path(goal['memory_root']) if goal['memory_root'] else root/'mnemonic'
    pinned = goal['analysis']['memory_head']; observation_id = digest(canonical([goal['analysis']['task_identity'],candidate['id']]))
    if not path.exists() and pinned != '0'*64: raise MissionHold('pinned function memory history lost')
    path.mkdir(parents=True, exist_ok=True)
    with exclusive_owner(path):
        ledger_path = path/'events.jsonl'
        if not ledger_path.exists():
            if pinned != '0'*64: raise MissionHold('pinned function memory journal lost')
            ledger_path.touch(exist_ok=False)
            Journal(ledger_path, FUNCTION_MEMORY_ID).append('MEMORY_CREATED', {'scope':frontier.FUNCTION_ADAPTER})
        models = _function_memory(path, epoch=goal['analysis']['capture_epoch'])
        if pinned != '0'*64 and pinned not in models['heads']: raise MissionHold('function memory no longer continues planning history')
        if any(r['capture_epoch'] > goal['analysis']['capture_epoch'] for r in models['records']): raise MissionHold('function memory epoch moved backwards')
        matching = [r for r in models['records'] if r['observation_id']==observation_id or
                    (r['baseline']==goal['baseline'] and r['candidate']['id']==candidate['id'])]
        if matching: observation_id=matching[0]['observation_id']
        if not matching:
            observed = {r['data']['operation']:r['data'] for r in rows if r['kind']=='F_OBSERVED'}
            record = {'scope':frontier.FUNCTION_ADAPTER, 'observation_id':observation_id,
                'mission_id':goal['mission_id'],
                'origin':_origin_goal(goal),
                'task_identity':goal['analysis']['task_identity'], 'baseline':goal['baseline'],
                'capture_epoch':goal['analysis']['capture_epoch'], 'runtime':goal['runtime_sha256'],
                'candidate':candidate, 'files':goal['analysis']['files'], 'signatures':goal['analysis']['signatures'],
                'witness':next(r['data']['receipt'] for r in rows if r['kind']=='F_WITNESS'),
                'public_result':{**observed['search:'+candidate['id']]['result'],
                                 'execution':observed['search:'+candidate['id']]['execution']}, 'mnemonic':None}
            record['execution_goal']={k:goal[k] for k in ('public','policy','baseline','baseline_entries','public_command')}
            record['execution_goal']['analysis']={'proposals':[candidate]}
            final=next(r['data'] for r in rows if r['kind']=='F_FINAL')
            acceptance={'candidate_sha256':candidate['id'],'sealed_sha256':goal['sealed_sha256'],
                'final_supported':final['supported'],'final_observation_sha256':final['observation_sha256'],
                'commit_sha256':next(r['sha256'] for r in rows if r['kind']=='F_COMMITTED'),
                'witness_receipt_sha256':record['witness']['receipt_hash']}
            acceptance['sha256']=digest(canonical(acceptance));record['acceptance']=acceptance
            if goal.get('computation') is not None:
                stop=next(i for i,r in enumerate(rows) if r['kind']=='F_SELECTED')
                trace=rows[:stop+1]
                control=next(r['data'] for r in trace if r['kind']=='F_CONTROL')
                diagnosis=next(r['data'] for r in trace if r['kind']=='F_DIAGNOSIS')
                public_search=[r['data'] for r in trace if r['kind']=='F_OBSERVED' and r['data']['operation'].startswith('search:')]
                gain=0.0
                for result in public_search:
                    proposal=_function_proposal(goal,result['operation'].partition(':')[2]); action=int(proposal['family']!='comparison')
                    probability=diagnosis['ranking']['probabilities'][action]
                    baseline_probability=diagnosis['ranking']['frequency_probabilities'][action]
                    supported=result['result']['supported']
                    gain+=math.log((probability if supported else 1-probability)/(baseline_probability if supported else 1-baseline_probability))
                record['computation_evidence']={'public_trace':trace,'control':control,'public_search':public_search,
                    'public_log_gain':max(-8.0,min(8.0,gain/len(public_search))),'cost':diagnosis['computation_cost']}
                _validate_computation_evidence(_origin_goal(goal),record['computation_evidence'],candidate['id'])
            if goal.get('persistent') is not None:
                stop=next(i for i,r in enumerate(rows) if r['kind']=='F_SELECTED');trace=rows[:stop+1]
                checked=_validate_persistent_trace(_origin_goal(goal),trace,complete=True,selected=candidate['id'])
                record['persistent_evidence']={'public_trace':trace,'public_search':checked['public_search'],
                    'terminal_state':checked['state'],'authority':'accepted public prefix only; private values excluded'}
            # Existing MNEMONIC grammar can represent single-file root-module
            # effects. Package/multi-edit effects abstain rather than fabricate
            # per-file causal evidence from a jointly successful intervention.
            changed = list(candidate['files'])
            if len(changed)==1 and '/' not in changed[0]:
                public = goal['public']; contract = Contract(public[0]['module'],public[0]['function'],tuple((i,0) for i in range(len(public))))
                task = AtlasTask(record['task_identity'],record['files'],changed[0],(contract,),(),(),())
                before = observed['before:'+candidate['id']]['result']['matches'][:len(public)]
                body = {'task_id':task.task_id,'epoch':0,'before_digest':source_digest(task.files),
                    'after_digest':source_digest({**task.files,**candidate['files']}), 'changed_file':changed[0],
                    'contract':contract.key,'before':tuple(map(float,before)), 'after':(1.0,)*len(public)}
                receipt = ChangeReceipt(**body,receipt_digest=memory_digest(body))
                if models['memory'].record(task=task,contract=contract.key,action_source=candidate['files'][changed[0]],
                                          receipt=receipt,capture_epoch=record['capture_epoch']):
                    record['mnemonic']={'changed_file':changed[0],'module':contract.module,'function':contract.function,
                        'rows':contract.rows,'receipt':asdict(receipt)}
            if len(models['records']) >= 512 or ledger_path.stat().st_size+len(canonical(record))>64_000_000:
                raise MissionHold('function memory storage budget exhausted')
            Journal(ledger_path,FUNCTION_MEMORY_ID).append('OBSERVATION_ADMITTED',record)
        learning = {'schema':'nomad.function-learning.v1','mission_id':goal['mission_id'],
                    'observation_id':observation_id,'candidate_sha256':candidate['id']}
        existing = root/'learning.json'
        if existing.exists() and existing.read_bytes()!=canonical(learning): raise MissionHold('foreign pending function learning')
        save_atomic(existing,canonical(learning))
        return digest(canonical(learning))


def _run_functions(root, goal, journal, rows, *, interrupt_at=None):
    def checkpoint(name):
        if interrupt_at==name: raise InjectedInterruption(name)
    if rows[-1]['kind']=='F_DISPATCHED': raise MissionHold('function execution ambiguous; explicit cleanup recovery required')
    if rows[-1]['kind'] in ('F_LEARNED','F_REJECTED','F_EXHAUSTED','F_ABSTAINED'): return _function_summary(goal,rows)
    sealed = json.loads((root/'sealed.json').read_bytes())
    def append(kind,data):
        if goal.get('persistent') is not None and (root/'events.jsonl').stat().st_size+len(canonical(data))+1024>PERSISTENT_JOURNAL_BYTES:
            raise MissionHold('persistent journal byte budget exhausted')
        journal.append(kind,data)
    def patch(identity, tag):
        found = [r for r in journal.read() if r['kind']=='F_PATCH' and r['data']['id']==tag]
        done = [r for r in journal.read() if r['kind']=='F_PATCHED' and r['data']['id']==tag]
        if done: return
        if not found:
            append('F_PATCH',{'id':tag,'candidate':identity,'before':_manifest(root/'workspace'),
                              'after':_function_manifest(goal,identity)})
            checkpoint('after_plan')
        proposal = _function_proposal(goal,identity)
        intended = _function_manifest(goal,identity)
        for name,sha in intended.items():
            destination=root/'workspace'/name
            if digest(destination.read_bytes())!=sha:
                data=proposal['files'][name].encode() if proposal and name in proposal['files'] else (root/'baseline'/name).read_bytes()
                save_atomic(destination,data); checkpoint('after_patch_write')
                if proposal and len(proposal['files'])==2: checkpoint('after_multifile_patch_write')
        append('F_PATCHED',{'id':tag}); checkpoint('after_patch_record')
    def observe(operation):
        previous = [r['data'] for r in journal.read() if r['kind']=='F_OBSERVED' and r['data']['operation']==operation]
        if previous: return previous[0]
        if sum(r['kind']=='F_DISPATCHED' for r in journal.read())>=goal['max_executions']:
            raise MissionHold('function execution budget exhausted')
        requested,command,_ = _function_spec(goal,sealed,operation)
        dispatch={'operation':operation,'container_name':'nomad-'+uuid.uuid4().hex[:24]}
        append('F_DISPATCHED',dispatch); checkpoint('after_dispatch')
        execution=run_isolated(root/'workspace',command=command,policy=SandboxPolicy(**goal['policy']),
                               container_name=dispatch['container_name'],include_output=bool(requested))
        result=_validate_function_execution(goal,dispatch,execution,root)
        data={'operation':operation,'execution':execution,'result':result}
        append('F_OBSERVED',data); checkpoint('after_public')
        return data
    # Complete a recorded partially applied multi-file transaction first.
    if rows[-1]['kind']=='F_PATCH': patch(rows[-1]['data']['candidate'],rows[-1]['data']['id'])
    chosen = next((r['data']['candidate'] for r in journal.read() if r['kind']=='F_SELECTED'),None)
    if chosen is None and goal.get('persistent') is not None:
        chosen=_persistent_search(root,goal,journal,observe,patch,append,checkpoint)
        if chosen is None:return _function_summary(goal,journal.read())
    if chosen is None:
        if goal.get('computation') is not None:
            if goal['computation']['decision']['mechanism']=='abstain' or not goal['analysis']['proposals']:
                append('F_ABSTAINED',{'reason':'registered computation allocation declined work'})
                return _function_summary(goal,journal.read())
            diagnosis=_adaptive_function_diagnosis(root,goal,journal,observe,checkpoint)
            if diagnosis['ranking']['mechanism']=='abstain':
                append('F_ABSTAINED',{'reason':'public-only computation choice declined search'})
                return _function_summary(goal,journal.read())
            order=[_function_proposal(goal,identity) for identity in diagnosis['order']]
        else:
            prior=dict(goal['analysis']['world_prior']); roles={name:name for name in prior}
            costs={name:max(1,sum(name in p['files'] for p in goal['analysis']['proposals'])) for name in prior}
            model=inquiry.ProbeLikelihoods(); menu=[]
            # Explicit structural likelihood assumption, not training evidence:
            # a faulty reachable module is more likely to break this public API.
            for i,row in enumerate(goal['public']):
                filename=goal['analysis']['modules'][row['module']]
                reachable=set(); pending=[filename]
                while pending:
                    name=pending.pop()
                    if name in reachable: continue
                    reachable.add(name); pending.extend(goal['analysis']['graph'][name])
                for hypothesis in prior:
                    for _ in range(4): model.observe(hypothesis,str(i),passed=hypothesis not in reachable)
                menu.append(inquiry.ProbeMenu(str(i),str(i),0.05))
            seen=set(); decisions=[]; resonances=[]
            for step in range(min(goal['probe_budget'],len(menu))):
                decision=(inquiry.choose_probe(prior,costs,roles,model,menu,frozenset(seen),1.0)
                          if goal['analysis']['adaptive_enabled'] else None)
                index=int(decision.probe_id) if decision else next(i for i in range(len(menu)) if str(i) not in seen)
                evidence=observe('probe:'+str(index)); seen.add(str(index))
                filename=goal['analysis']['modules'][goal['public'][index]['module']]
                source=goal['analysis']['files'][filename]
                model_task=PythonTask('api-equality-probe',source,(PythonExample({},1),))
                observation=TestObservation(evidence['result']['supported'],1,None,None,None,0)
                precomputed=PythonExecution(True,None,None,None,sum(1 for _ in ast.walk(ast.parse(source))),(observation,),0)
                resonance=encode_resonance(model_task,execution=precomputed,numeric_inputs=False)
                resonances.append({'index':index,**asdict(resonance),'fusion_signature':resonance.fusion_signature,
                                   'encoding':'bound isolated API equality; numeric input correlations disabled'})
                prior=inquiry._update(prior,roles,model,str(index),evidence['result']['supported'])
                decisions.append({'index':index,'decision':asdict(decision) if decision else None,'posterior':prior})
            ranker=NativeDecisionRanker.load(json.loads((root/'planning_ranker.json').read_bytes()))
            proposals=goal['analysis']['proposals']
            @dataclass
            class Ranked:
                family:str
                item:dict
            ranked=ranker.rank([Ranked(p['family'],p) for p in proposals],now_epoch=goal['analysis']['capture_epoch'])
            order=[p.item for p in ranked]
            memory=EvidenceMemory.load(root/'planning_memory.json')
            recall={}
            first=goal['public'][0]
            contract=Contract(first['module'],first['function'],tuple((i,0) for i in range(len(goal['public']))))
            symbols=SymbolGraph(goal['analysis']['files'])
            for p in order:
                if len(p['files'])==1 and '/' not in next(iter(p['files'])):
                    filename=next(iter(p['files']))
                    recall[p['id']]=memory.recall(action_source=p['files'][filename],
                        features=symbols.features(contract,filename),now_epoch=goal['analysis']['capture_epoch'],
                        target_task_id=goal['analysis']['task_identity']).as_dict()
            if goal['analysis']['adaptive_enabled']:
                # Stable priority consumes measured posterior; native rank breaks
                # ties. A failed direct leaf probe can outrank the public facade.
                order.sort(key=lambda p:(-int(recall.get(p['id'],{}).get('outcome')=='impact'),
                    -sum(prior.get(n,0) for n in p['files'])/len(p['files'])))
            diagnosis={'decisions':decisions,'posterior':prior,'order':[p['id'] for p in order],
                       'resonance':resonances,'mnemonic_recall':recall,
                       'ranking':ranker.summary(now_epoch=goal['analysis']['capture_epoch']),
                       'likelihood_scope':'declared reachability heuristic; not calibrated learned probability'}
            prior_diagnosis=[r['data'] for r in journal.read() if r['kind']=='F_DIAGNOSIS']
            if prior_diagnosis and canonical(prior_diagnosis)!=canonical([diagnosis]): raise MissionHold('function diagnosis replay differs')
            if not prior_diagnosis: append('F_DIAGNOSIS',diagnosis)
        checkpoint('after_proposal')
        for candidate in order:
            patch(candidate['id'],'search-apply:'+candidate['id'])
            result=observe('search:'+candidate['id'])
            if result['result']['supported']:
                chosen=candidate['id']; append('F_SELECTED',{'candidate':chosen}); break
            patch(None,'search-revert:'+candidate['id'])
        if chosen is None:
            append('F_EXHAUSTED',{'reason':'bounded function inventory exhausted'})
            return _function_summary(goal,journal.read())
    candidate=_function_proposal(goal,chosen)
    if goal['public_command'] and not observe('suite:'+chosen)['result']['supported']:
        patch(None,'reject-suite'); append('F_REJECTED',{'reason':'full public suite rejected'}); return _function_summary(goal,journal.read())
    patch(None,'witness-baseline')
    observe('before:'+chosen)
    patch(chosen,'witness-candidate')
    challenge=observe('challenge:'+chosen)
    observations={r['data']['operation']:r['data'] for r in journal.read() if r['kind']=='F_OBSERVED'}
    receipt=_function_witness(goal,candidate,observations)
    if not any(r['kind']=='F_WITNESS' for r in journal.read()): append('F_WITNESS',{'receipt':asdict(receipt)})
    checkpoint('after_witness')
    if not receipt.supported:
        patch(None,'reject-witness'); append('F_REJECTED',{'reason':'independent challenge rejected'})
        return _function_summary(goal,journal.read())
    final=observe('final:'+chosen)
    if not any(r['kind']=='F_FINAL' for r in journal.read()):
        append('F_FINAL',{'supported':final['result']['supported'],'observation_sha256':digest(canonical(final))})
    checkpoint('after_final')
    if not final['result']['supported']:
        patch(None,'reject-final'); append('F_REJECTED',{'reason':'independent final rejected; no search feedback'})
        return _function_summary(goal,journal.read())
    if not any(r['kind']=='F_COMMITTED' for r in journal.read()): append('F_COMMITTED',{'candidate':chosen})
    checkpoint('after_commit'); checkpoint('before_memory')
    learning=_function_learn(root,goal,journal.read(),candidate)
    checkpoint('after_memory'); checkpoint('after_learning')
    append('F_LEARNED',{'learning_sha256':learning})
    validated,_,rows=_load(root)
    return _function_summary(validated,rows)
