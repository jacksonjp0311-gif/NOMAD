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
import math
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
from . import inquiry, repo_world
from .causal_atlas import AtlasTask, ChangeReceipt, Contract, SymbolGraph, source_digest
from .mnemonic import EvidenceMemory, action_digest, digest as memory_digest
from .platform_bitwork import NativeDecisionRanker, PublicObservation
from .python_model import PythonExample, PythonTask
from .python_runtime import PythonExecution, TestObservation
from .resonance import encode_resonance

SCHEMA = 'nomad.platform-mission.v1'
WITNESS_ID = 'nomad-v018-bounded-arithmetic-observer'
COMMAND = ['python', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-q']
CHECKPOINTS = ('after_plan', 'after_patch_write', 'after_patch_record',
               'after_dispatch', 'after_public', 'after_witness', 'after_final',
               'after_commit', 'after_learning', 'after_rollback_write',
               'after_rollback_record', 'after_probe_dispatch', 'after_probe',
               'after_proposal', 'before_memory', 'after_memory')
MEMORY_ID = 'nomad-platform-memory-v018'


def _runtime_identity() -> dict[str, str]:
    package = Path(__file__).parent
    return {name: digest((package / name).read_bytes()) for name in
            ('platform_mission.py', 'genesis.py', 'safe_eval.py', 'witness.py', 'isolation.py',
             'supervised.py', 'windows_job.py', 'mission_runtime.py', 'effects.py',
             'python_operators.py', 'platform_bitwork.py', 'resonance.py', 'repo_world.py',
             'inquiry.py', 'mnemonic.py', 'causal_atlas.py')}


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
    except (OSError, ValueError, TypeError, KeyError) as exc:
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
    if interrupt_at is not None and interrupt_at not in CHECKPOINTS:
        raise ValueError('unknown interruption checkpoint')
    with exclusive_owner(root):
        goal, journal, rows = _load(root)
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
