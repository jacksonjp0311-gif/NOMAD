"""Preregister and run a prospective, matched four-arm NOMAD experiment.

Unknown repository code runs only through the qualified isolated mission API.
Preflight precedes all reads of private contracts and all trial execution.
The bundled unit fixtures test protocol software, not coding efficacy.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import inspect
import json
import math
from pathlib import Path
import random
import shutil
import sys
import tempfile
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nomad.isolation import SandboxPolicy, docker_preflight, snapshot_source
from nomad.platform_bitwork import NativeDecisionRanker, PublicObservation

SCHEMA = 'nomad.intelligence-qualification.v18'
ARM_SPECS = {
    'A': {'adaptive_enabled': False, 'ranker_mode': 'cold', 'native_enabled': False},
    'B': {'adaptive_enabled': True, 'ranker_mode': 'frequency', 'native_enabled': False},
    'C': {'adaptive_enabled': True, 'ranker_mode': 'native', 'native_enabled': True},
    'D': {'adaptive_enabled': False, 'ranker_mode': 'frequency', 'native_enabled': False},
}
SEEDS = (1801801, 1801807, 1801811)
SEEN_REPOSITORIES = {'rasterio/affine', 'explosion/catalogue', 'explosion/confection',
                     'more-itertools/more-itertools', 'mahmoud/boltons'}
BOUNDS = {'max_eval': 65000, 'max_nodes': 7, 'candidate_attempts': 1,
          'container_executions': 2,
          'timeout_s': 10.0, 'memory_mib': 128, 'cpus': 0.5, 'pids_limit': 16,
          'max_files': 3000, 'max_total_bytes': 30_000_000}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execution_policy(image: str) -> SandboxPolicy:
    return SandboxPolicy(image=image, **{key: BOUNDS[key] for key in
        ('timeout_s', 'memory_mib', 'cpus', 'pids_limit', 'max_files', 'max_total_bytes')})


def read_json(path: Path, limit: int = 1_000_000, *, expected_sha256: str | None = None) -> dict:
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('protocol document exceeds size budget')
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('protocol input bytes changed from their frozen commitment')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('protocol document must be an object')
    return value


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(value, output, sort_keys=True, indent=2, allow_nan=False)
        output.write('\n')


def _sha(value: str, length: int = 64) -> bool:
    return isinstance(value, str) and len(value) == length and all(c in '0123456789abcdef' for c in value)


def _path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('corpus paths must be relative POSIX paths')
    requested = Path(relative)
    if requested.is_absolute() or '..' in requested.parts:
        raise ValueError('corpus path escapes supplied root')
    result = root / requested
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('corpus path resolves outside supplied root')
    return result


def _repository(value: str) -> str:
    parsed = urlparse(value)
    parts = parsed.path.strip('/').removesuffix('.git').split('/')
    if (parsed.scheme != 'https' or parsed.netloc.casefold() != 'github.com'
            or len(parts) != 2 or not all(parts) or parsed.query or parsed.fragment):
        raise ValueError('upstream repository requires canonical HTTPS GitHub identity')
    return '/'.join(parts).casefold()


def code_identity() -> dict:
    paths = sorted((ROOT/'nomad').glob('*.py')) + [Path(__file__).resolve(),
        ROOT/'scripts/qualify_isolation_v18.py', ROOT/'scripts/qualify_recovery_v18.py',
        ROOT/'vendor/BGR-v1.4.0-runtime/MANIFEST.sha256',
        ROOT/'experiments/PUBLIC_TRAINING_CANDIDATES_V018.json']
    return {path.relative_to(ROOT).as_posix(): file_hash(path) for path in paths}


def protocol() -> dict:
    record = {'schema': SCHEMA + '.protocol', 'arms': ARM_SPECS, 'seeds': list(SEEDS),
        'bounds': BOUNDS, 'action_schema': 'genesis-vs-ast',
        'adapter': 'platform_mission strict bounded arithmetic repository adapter',
        'training': 'one common cold isolated training stream; identical frozen memory for B/C/D',
        'evaluation_updates': False, 'private_contract_access': 'after native qualification preflight only',
        'matching': ['source', 'public information', 'candidate grammar and inventory', 'max_eval', 'execution budgets',
                     'private partitions', 'training observations', 'task order per seed'],
        'primary_metric': 'independent final accepted repair rate, grouped by upstream repository',
        'secondary_metrics': ['candidate attempts', 'isolated execution count', 'wall_seconds',
                              'controller_cpu_seconds', 'observed supervisor resource metrics',
                              'public success rejected independently / public-pass trials'],
        'controller_limits': 'bounded inputs and synthesis enumeration; controller CPU/RSS hard cap not enforced',
        'minimum_training_repositories': 2, 'minimum_evaluation_repositories': 8,
        'minimum_evaluation_tasks': 24,
        'acceptance': {'comparison': ['C>A', 'C>B', 'C>D'],
            'test': 'one-sided exact paired sign test on per-repository acceptance rate, ties omitted',
            'multiple_comparisons': 'Holm correction across the three frozen contrasts',
            'alpha': 0.05, 'required': 'all three contrasts significant, no containment/integrity failure'},
        'negative_outcomes': 'retain every rejection, exhaustion, hold, failure, and unavailable task',
        'claims': 'No prospective efficacy result exists until an admissible completed run.'}
    # A caller mutating its plan must never mutate the expected comparison policy.
    return json.loads(canonical(record))


def corpus_template() -> dict:
    return {'schema': SCHEMA + '.corpus', 'status': 'INCOMPLETE_NOT_PREREGISTERED',
        'curator': {'identity': '', 'independently_authored_sources': False,
                    'evaluation_not_previously_seen_by_developer': False},
        'tasks': [], 'task_fields': ['id', 'split', 'repository', 'author_group', 'revision',
            'issue_url', 'provenance_kind', 'source', 'source_sha256', 'public_spec',
            'public_spec_sha256', 'private_contract', 'private_contract_sha256'],
        'notes': ['Use independent upstream source snapshots and actual issue provenance.',
            'Do not put hidden expected values in this public manifest or repository snapshots.',
            'An independent curator supplies private contract hashes without opening outcomes here.',
            'The public training candidate catalogue is not an evaluation corpus.']}


def freeze_protocol(output: Path) -> dict:
    """Freeze design/code without pretending that missing tasks are registered."""
    payload = {'schema': SCHEMA+'.protocol-freeze', 'protocol': protocol(),
               'source_sha256': code_identity(),
               'status': 'AWAITING_CURATED_CORPUS_NOT_AN_EXPERIMENT_PLAN',
               'tasks_registered': 0, 'private_contracts_opened': False}
    document = {'payload': payload, 'sha256': digest(payload)}
    write_new(output, document)
    return document


def audit_corpus(corpus: dict, corpus_root: Path, *, check_public_files: bool = True) -> dict:
    if corpus.get('schema') != SCHEMA + '.corpus':
        raise ValueError('unsupported corpus schema')
    curator = corpus.get('curator', {})
    if (not curator.get('identity') or curator.get('independently_authored_sources') is not True
            or curator.get('evaluation_not_previously_seen_by_developer') is not True):
        raise ValueError('independent curator and unseen-evaluation declarations are required')
    tasks = corpus.get('tasks')
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 256:
        raise ValueError('curated corpus is absent or exceeds task budget')
    ids, sources, issues = set(), set(), set()
    repositories = {'training': set(), 'evaluation': set()}
    authors = {'training': set(), 'evaluation': set()}
    source_paths, private_paths = [], []
    for task in tasks:
        required = {'id', 'split', 'repository', 'author_group', 'revision', 'issue_url',
                    'provenance_kind', 'source', 'source_sha256', 'public_spec',
                    'public_spec_sha256', 'private_contract', 'private_contract_sha256'}
        if not isinstance(task, dict) or set(task) != required:
            raise ValueError('task fields differ from the frozen protocol')
        split = task['split']; repo = _repository(task['repository'])
        if split not in repositories or not isinstance(task['id'], str) or not task['id']:
            raise ValueError('invalid task identity or partition')
        if (task['id'] in ids or task['source_sha256'] in sources or task['issue_url'] in issues):
            raise ValueError('repeated task, source snapshot, or issue is not independent evidence')
        if task['provenance_kind'] != 'authentic_upstream_issue':
            raise ValueError('decisive corpus requires authentic upstream issues, not injected defects')
        issue = urlparse(task['issue_url'])
        if (issue.scheme != 'https' or issue.netloc != 'github.com'
                or not issue.path.casefold().startswith('/'+repo+'/issues/')
                or not issue.path.rsplit('/', 1)[-1].isdigit()):
            raise ValueError('task issue does not belong to declared upstream repository')
        if not _sha(task['revision'], 40) or not all(_sha(task[key]) for key in
                ('source_sha256', 'public_spec_sha256', 'private_contract_sha256')):
            raise ValueError('exact source revision and input hashes are required')
        if not isinstance(task['author_group'], str) or not task['author_group']:
            raise ValueError('independent authorship group is required')
        if split == 'evaluation' and repo in SEEN_REPOSITORIES:
            raise ValueError('previously inspected repository cannot become an unseen evaluation source')
        ids.add(task['id']); sources.add(task['source_sha256']); issues.add(task['issue_url'])
        repositories[split].add(repo); authors[split].add(task['author_group'])
        source = _path(corpus_root, task['source'])
        public_path = _path(corpus_root, task['public_spec'])
        private_path = _path(corpus_root, task['private_contract'])
        source_paths.append(source.resolve()); private_paths.append(private_path.resolve())
        if public_path == private_path:
            raise ValueError('private contract cannot be the public specification')
        if check_public_files:
            public = read_json(public_path, 65536, expected_sha256=task['public_spec_sha256'])
            if not {'goal_text', 'public'} <= set(public) or set(public) - {
                    'goal_text', 'public', 'target', 'entry_module'}:
                raise ValueError('public specification contains unrecognized/private fields')
            from nomad import platform_mission
            platform_mission._rows(public['public'])
            if not isinstance(public['goal_text'], str) or not 1 <= len(public['goal_text']) <= 4096:
                raise ValueError('public mission goal exceeds supported scope')
            with tempfile.TemporaryDirectory(prefix='nomad-corpus-inspection-') as temporary:
                snapshot = snapshot_source(source, Path(temporary)/'source',
                    SandboxPolicy('nomad/identity@sha256:'+'0'*64))
                if snapshot.digest != task['source_sha256']:
                    raise ValueError('curated repository snapshot changed')
                # Parse-only adapter admission is completed before any private
                # expected result is opened. No transplanted/wrapped task is
                # silently substituted for unsupported authentic source.
                from nomad import platform_mission
                parsed = platform_mission._read_python_sources(snapshot.root)
                platform_mission._discover(snapshot.root, parsed, public.get('target'), public.get('entry_module'))
    if repositories['training'] & repositories['evaluation'] or authors['training'] & authors['evaluation']:
        raise ValueError('training and evaluation repository/authorship groups overlap')
    if len(repositories['training']) < 2 or len(repositories['evaluation']) < 8:
        raise ValueError('insufficient disjoint training/evaluation repositories for the registered test')
    if sum(t['split'] == 'evaluation' for t in tasks) < 24:
        raise ValueError('at least 24 evaluation tasks are required')
    if any(private == source or private.is_relative_to(source) for private in private_paths for source in source_paths):
        raise ValueError('private contracts must stay outside every source mount')
    return {'training_repositories': sorted(repositories['training']),
            'evaluation_repositories': sorted(repositories['evaluation']), 'tasks': len(tasks),
            'independence': 'distinct declared repositories/authors/tasks/source hashes; curator truth remains a trust boundary',
            'private_contracts_opened': False}


def freeze(corpus_path: Path, corpus_root: Path, output: Path, *, image: str,
           qualification: Path, recovery: Path) -> dict:
    if output.exists():
        raise FileExistsError('frozen plan already exists; never overwrite preregistration')
    execution_policy(image).validate()
    corpus = read_json(corpus_path)
    audit = audit_corpus(corpus, corpus_root)
    payload = {'schema': SCHEMA + '.plan', 'protocol': protocol(), 'corpus': corpus,
               'corpus_document_sha256': file_hash(corpus_path), 'independence_audit': audit,
               'source_sha256': code_identity(), 'image': image,
               'qualification_sha256': file_hash(qualification), 'recovery_sha256': file_hash(recovery)}
    document = {'payload': payload, 'sha256': digest(payload)}
    write_new(output, document)
    return document


def _validate_plan(document: dict) -> dict:
    payload = document.get('payload')
    if not isinstance(payload, dict) or document.get('sha256') != digest(payload):
        raise ValueError('plan changed or lacks its frozen identity')
    if payload.get('schema') != SCHEMA + '.plan' or payload.get('protocol') != protocol():
        raise ValueError('plan protocol differs from this implementation')
    if payload.get('source_sha256') != code_identity():
        raise ValueError('source changed after preregistration; do not reuse this holdout')
    execution_policy(payload['image']).validate()
    return payload


def _receipt_binding(record: dict, image: str, kind: str) -> None:
    schemas = {'qualification': 'nomad.native-isolation-qualification.v18',
               'recovery': 'nomad.platform-recovery-qualification.v18'}
    if kind not in schemas or record.get('schema') != schemas[kind]:
        raise ValueError(kind+' receipt has an unsupported qualification schema')
    core = {key: value for key, value in record.items() if key != 'receipt_sha256'}
    policy = asdict(execution_policy(image))
    if (record.get('receipt_sha256') != digest(core) or record.get('backend') != 'docker'
            or record.get('image') != image or record.get('policy') != policy
            or record.get('policy_sha256') != digest(policy) or record.get('source_stable') is not True):
        raise ValueError(kind+' receipt lacks exact backend/image/policy/source integrity binding')
    before = record.get('source_sha256_before')
    after = record.get('source_sha256_after')
    required = {'nomad/isolation.py', 'nomad/supervised.py', 'nomad/windows_job.py'}
    required.add('scripts/qualify_isolation_v18.py')
    if kind == 'recovery':
        required.update(path.relative_to(ROOT).as_posix() for path in (ROOT/'nomad').glob('*.py'))
        required.add('scripts/qualify_recovery_v18.py')
    if not isinstance(before, dict) or before != after or not required <= set(before):
        raise ValueError(kind+' receipt lacks required runtime source identities')
    for relative, expected in before.items():
        if not _sha(expected) or file_hash(_path(ROOT, relative)) != expected:
            raise ValueError(kind+' receipt belongs to stale runtime source')
    from scripts.qualify_isolation_v18 import qualification_host_identity
    current_host = qualification_host_identity()
    current_hash = current_host if isinstance(current_host, str) else digest(current_host)
    if record.get('host_identity_sha256') != current_hash:
        raise ValueError(kind+' receipt belongs to a different host')
    from scripts.qualify_isolation_v18 import CONTROLLED_CASES
    from nomad.platform_mission import CHECKPOINTS
    expected_cases = (set(CONTROLLED_CASES) | {'supervisor_hard_death_cleanup'}
        if kind == 'qualification' else set(CHECKPOINTS) | {'reference_and_terminal_replay',
            'owner_hard_death_with_live_container', 'tampered-sealed.json',
            'tampered-planning_memory.json', 'tampered-events.jsonl', 'tampered-baseline/arithmetic.py'})
    cases = record.get('cases')
    if (not isinstance(cases, list) or len(cases) != len(expected_cases)
            or any(not isinstance(case, dict) or case.get('status') != 'PASS' for case in cases)
            or {case.get('case') for case in cases} != expected_cases
            or record.get('protected_host_sentinel_unchanged') is not True):
        raise ValueError(kind+' receipt does not record all required native cases as PASS')
    if kind == 'qualification':
        death = next(case for case in cases if case['case'] == 'supervisor_hard_death_cleanup')
        if (death.get('observed_live_container_before_owner_death') is not True
                or death.get('cleanup_confirmed_after_owner_death') is not True):
            raise ValueError('native containment lacks actual owner-death observation and cleanup')
    else:
        death = next(case for case in cases if case['case'] == 'owner_hard_death_with_live_container').get('death', {})
        if (death.get('observed_running_container') is not True or death.get('held_before_cleanup') is not True
                or record.get('original_source_unchanged') is not True):
            raise ValueError('native recovery lacks actual owner-death and source preservation evidence')


def preflight(document: dict | None, corpus_root: Path, qualification: Path | None,
              recovery: Path | None) -> dict:
    reasons = []
    if document is None:
        reasons = ['fresh curated corpus and frozen plan absent']
        for kind, path in (('native containment', qualification), ('isolated recovery', recovery)):
            if path is None or not path.is_file():
                reasons.append(kind+' qualification receipt absent')
            else:
                state = read_json(path)
                reasons.append(kind+' recorded status: '+str(state.get('status', state.get('isolated_mission_recovery', 'UNKNOWN'))))
        return {'status': 'HOLD', 'execution': 'NOT_RUN', 'reasons': reasons,
                'private_contracts_opened': False}
    try:
        plan = _validate_plan(document)
        # Metadata audit reads no private contracts and performs no repository execution.
        audit_corpus(plan['corpus'], corpus_root, check_public_files=False)
        for kind, path in (('qualification', qualification), ('recovery', recovery)):
            if path is None or not path.is_file():
                reasons.append('trusted '+kind+' receipt absent'); continue
            if file_hash(path) != plan[kind+'_sha256']:
                reasons.append(kind+' receipt differs from preregistration'); continue
            record = read_json(path)
            _receipt_binding(record, plan['image'], kind)
            if kind == 'qualification':
                if (record.get('native_containment_gate') != 'PASS' or record.get('status') != 'PASS'
                        or record.get('image') != plan['image']):
                    reasons.append('native containment qualification is not PASS for this image')
            elif (record.get('isolated_mission_recovery') != 'PASS' or record.get('status') != 'PASS'
                    or record.get('image') != plan['image']):
                reasons.append('native isolated mission recovery is not PASS for this image')
            elif record.get('isolation_receipt_sha256') != plan['qualification_sha256']:
                reasons.append('native recovery was not qualified against the same containment receipt')
            else:
                _recovery_evidence(record)
        if reasons:
            return {'status': 'HOLD', 'execution': 'NOT_RUN', 'reasons': reasons,
                    'private_contracts_opened': False}
        current = docker_preflight(execution_policy(plan['image']))
        if not current.get('ready'):
            reasons.append('current local Docker readiness HOLD: '+'; '.join(current.get('reasons', [])))
        from nomad import platform_mission
        parameters = inspect.signature(platform_mission.initialize).parameters
        if not {'memory_root', 'capture_epoch', 'adaptive_enabled'} <= set(parameters):
            reasons.append('matched integrated mission adapter API unavailable')
        if not callable(getattr(platform_mission, 'resolved_goal', None)):
            reasons.append('durable post-probe proposal resolver unavailable')
        return {'status': 'PASS' if not reasons else 'HOLD', 'execution': 'NOT_STARTED' if not reasons else 'NOT_RUN',
                'reasons': reasons, 'private_contracts_opened': False, 'docker': current}
    except (ValueError, TypeError, KeyError, OSError, ImportError) as error:
        return {'status': 'HOLD', 'execution': 'NOT_RUN', 'reasons': [str(error)], 'private_contracts_opened': False}


def _recovery_evidence(record: dict) -> None:
    """Require the independently reviewable native mission evidence to remain present."""
    directory, identities = record.get('evidence_root'), record.get('evidence_files_sha256')
    if not isinstance(directory, str) or not isinstance(identities, dict) or not identities:
        raise ValueError('native recovery lacks retained mission evidence')
    from nomad import platform_mission
    try:
        actual = platform_mission._manifest(Path(directory))
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError('native recovery evidence is unavailable or unsafe: '+str(error)) from error
    if actual != identities:
        raise ValueError('native recovery evidence changed, is missing, or contains unbound extra files')


def _private_contract(task: dict, root: Path) -> dict:
    path = _path(root, task['private_contract'])
    result = read_json(path, 65536, expected_sha256=task['private_contract_sha256'])
    if set(result) != {'challenge', 'final'}:
        raise ValueError('private contract requires only challenge and final partitions')
    return result


def _trial(task: dict, corpus_root: Path, destination: Path, memory_root: Path,
           settings: dict, image: str) -> dict:
    from nomad import platform_mission
    started, cpu = time.perf_counter(), time.process_time()
    source = _path(corpus_root, task['source'])
    public = read_json(_path(corpus_root, task['public_spec']), 65536,
                       expected_sha256=task['public_spec_sha256'])
    private = _private_contract(task, corpus_root)
    ranker = (platform_mission.read_memory_ranker(memory_root, mode=settings['ranker_mode'], now_epoch=0)
              if memory_root.exists() else NativeDecisionRanker(settings['ranker_mode'], action_schema='genesis-vs-ast'))
    initial_goal = platform_mission.initialize(destination, source, policy=execution_policy(image),
        memory_root=memory_root, capture_epoch=0, adaptive_enabled=settings['adaptive_enabled'],
        max_eval=BOUNDS['max_eval'], max_executions=BOUNDS['container_executions'],
        ranker=ranker, **public, **private)
    if digest(initial_goal['baseline_entries']) != task['source_sha256']:
        raise ValueError('actual admitted mission snapshot differs from frozen corpus source')
    result = platform_mission.run(destination)
    goal = platform_mission.resolved_goal(destination)
    elapsed, used_cpu = time.perf_counter()-started, time.process_time()-cpu
    rows = [json.loads(line) for line in (destination/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    planning = goal.get('planning') or {}
    public_passed = any(row['kind'] == 'PUBLIC_RESULT' and row['data'].get('supported') is True
                        for row in rows)
    private_rejected = any(row['kind'] in ('WITNESS_RESULT', 'FINAL_RESULT')
                           and row['data'].get('supported') is False for row in rows)
    return {'task_id': task['id'], 'repository': _repository(task['repository']),
        'status': result['status'], 'accepted': result['status'] == 'completed',
        'public_passed': public_passed, 'independent_contract_rejected': private_rejected,
        'wall_seconds': elapsed, 'controller_cpu_seconds': used_cpu,
        'candidate_attempts': sum(row['kind'] == 'PATCH_APPLIED' for row in rows),
        'public_executions': sum(row['kind'] == 'PUBLIC_RESULT' for row in rows),
        'isolated_executions': sum(row['kind'] in ('PROBE_DISPATCHED', 'EXECUTION_DISPATCHED') for row in rows),
        'source_sha256': task['source_sha256'], 'public_spec_sha256': task['public_spec_sha256'],
        'mission_id': result['mission_id'], 'journal_head': result['journal_head'],
        'planning': planning,
        'genesis_candidates_evaluated': planning.get('genesis', {}).get('candidates_evaluated'),
        'ast_candidates_evaluated': planning.get('ast_candidates_evaluated'),
        'candidate_inventory_sha256': planning.get('candidate_inventory_sha256'),
        'supervisor_resources': [row['data']['execution'].get('supervisor_metrics')
            for row in rows if row['kind'] in ('PUBLIC_RESULT', 'PROBE_RESULT')],
        'authority': 'independent bounded contract, not general repository correctness'}


def _sign_p(wins: int, losses: int) -> float:
    n = wins + losses
    return sum(math.comb(n, i) for i in range(wins, n+1)) / (2**n) if n else 1.0


def assess(rows: list[dict]) -> dict:
    by_repo = {}
    identities = set()
    paired = {}
    for row in rows:
        key = (row['seed'], row['arm'], row['task_id'])
        if key in identities:
            raise ValueError('repeated trial is not independent evidence')
        identities.add(key)
        if row['arm'] not in ARM_SPECS or row['seed'] not in SEEDS:
            raise ValueError('unregistered arm or seed')
        pair = (row['seed'], row['task_id'])
        core = (row['repository'], row['source_sha256'], row['public_spec_sha256'],
                row.get('candidate_inventory_sha256'))
        if pair in paired and paired[pair]['identity'] != core:
            raise ValueError('arms did not receive identical repository and public information')
        paired.setdefault(pair, {'identity': core, 'arms': set()})['arms'].add(row['arm'])
        by_repo.setdefault(row['repository'], {}).setdefault(row['arm'], []).append(int(row['accepted']))
    if any(value['arms'] != set(ARM_SPECS) for value in paired.values()):
        raise ValueError('unmatched task/seed arm observations')
    contrasts = {}
    for control in ('A', 'B', 'D'):
        wins = losses = ties = 0
        for arms in by_repo.values():
            if set(arms) != set(ARM_SPECS) or len(arms['C']) != len(arms[control]):
                raise ValueError('unmatched arm observations cannot support a comparison')
            difference = sum(arms['C'])/len(arms['C']) - sum(arms[control])/len(arms[control])
            wins += difference > 0; losses += difference < 0; ties += difference == 0
        contrasts['C>'+control] = {'repository_wins': wins, 'repository_losses': losses,
                                  'repository_ties': ties, 'p_one_sided': _sign_p(wins, losses)}
    ordered = sorted(contrasts, key=lambda key: contrasts[key]['p_one_sided'])
    still_rejecting = True
    for index, key in enumerate(ordered):
        threshold = 0.05 / (len(ordered)-index)
        significant = still_rejecting and contrasts[key]['p_one_sided'] <= threshold
        contrasts[key]['holm_threshold'] = threshold
        contrasts[key]['significant'] = significant
        still_rejecting = significant
    outcomes = {}
    for arm in ARM_SPECS:
        selected = [row for row in rows if row['arm'] == arm]
        public_passes = sum(row.get('public_passed') is True for row in selected)
        false_successes = sum(row.get('public_passed') is True and
                              row.get('independent_contract_rejected') is True for row in selected)
        outcomes[arm] = {'trial_count': len(selected), 'accepted': sum(row['accepted'] is True for row in selected),
            'accepted_rate': sum(row['accepted'] is True for row in selected)/len(selected) if selected else None,
            'public_passes': public_passes, 'public_success_rejected_independently': false_successes,
            'false_success_denominator': 'public-pass trials; repeated seeds retained as repeated measurements',
            'false_success_rate': false_successes/public_passes if public_passes else None,
            'status_counts': {status: sum(row.get('status', 'unspecified') == status for row in selected)
                              for status in sorted({row.get('status', 'unspecified') for row in selected})}}
    return {'contrasts': contrasts, 'outcomes_by_arm': outcomes,
            'intelligence_advantage': 'SUPPORTED_WITHIN_REGISTERED_SCOPE'
            if len(by_repo) >= 8 and all(row['significant'] for row in contrasts.values()) else 'NOT_ESTABLISHED',
            'independent_units': 'upstream repository; seeds and repeated task trials are not independent units'}


def run(document: dict | None, corpus_root: Path, qualification: Path | None,
        recovery: Path | None, output: Path) -> dict:
    if output.exists():
        raise FileExistsError('experiment evidence already exists; never overwrite a run')
    check = preflight(document, corpus_root, qualification, recovery)
    report = {'schema': SCHEMA + '.run', 'preflight': check, 'status': 'HOLD', 'execution': 'NOT_RUN',
              'plan_sha256': document.get('sha256') if document else None, 'trials': [],
              'private_contracts_opened': False, 'intelligence_advantage': 'NOT_ESTABLISHED',
              'cloud_calls': 0, 'api_cost_usd': 0, 'energy_joules': None, 'electricity_cost_usd': None}
    if check['status'] != 'PASS':
        write_new(output, report)
        return report
    plan = _validate_plan(document)
    report['source_sha256_before'] = code_identity()
    # Recheck every admitted public source after prerequisites pass, before a
    # private contract is opened. No historical evaluation trace is imported.
    try:
        audit_corpus(plan['corpus'], corpus_root)
    except (ValueError, TypeError, KeyError, OSError) as error:
        report['reason'] = 'public source recheck failed: '+str(error)
        write_new(output, report)
        return report
    run_root = output.with_suffix('.missions')
    if run_root.exists():
        raise FileExistsError('mission evidence directory already exists')
    run_root.mkdir(parents=True)
    report['execution'] = 'STARTED'
    try:
        training_memory = run_root/'training-memory'
        training = [t for t in plan['corpus']['tasks'] if t['split'] == 'training']
        training.sort(key=lambda task: task['id'])
        for index, task in enumerate(training):
            destination = run_root/('training-'+str(index))
            report['active_trial'] = {'phase': 'training', 'task_id': task['id']}
            report['private_contracts_opened'] = True
            row = _trial(task, corpus_root, destination, training_memory, ARM_SPECS['A'], plan['image'])
            row.update({'phase': 'training', 'arm': 'common', 'seed': None})
            report['trials'].append(row)
        for seed in SEEDS:
            evaluation = [t for t in plan['corpus']['tasks'] if t['split'] == 'evaluation']
            random.Random(seed).shuffle(evaluation)
            for index, task in enumerate(evaluation):
                arm_order = list(ARM_SPECS)
                random.Random(str(seed)+':'+task['id']).shuffle(arm_order)
                for arm in arm_order:
                    report['active_trial'] = {'phase': 'evaluation', 'task_id': task['id'], 'arm': arm, 'seed': seed}
                    destination = run_root/(str(seed)+'-'+str(index)+'-'+arm)
                    memory = run_root/(destination.name+'-memory')
                    clone_started = time.perf_counter()
                    if training_memory.exists():
                        shutil.copytree(training_memory, memory)
                    clone_wall = time.perf_counter()-clone_started
                    row = _trial(task, corpus_root, destination, memory, ARM_SPECS[arm],
                                 plan['image'])
                    row.update({'phase': 'evaluation', 'arm': arm, 'seed': seed})
                    row['memory_clone_wall_seconds'] = clone_wall
                    report['trials'].append(row)
                    if not _sha(row.get('candidate_inventory_sha256')):
                        raise ValueError('candidate inventory identity unavailable; comparison remains HOLD')
                    if (row['candidate_attempts'] > BOUNDS['candidate_attempts'] or
                            row['isolated_executions'] > BOUNDS['container_executions']):
                        raise ValueError('candidate/container execution budget exceeded; trial invalid')
        report['source_sha256_after'] = code_identity()
        if report['source_sha256_after'] != report['source_sha256_before']:
            raise ValueError('source changed during the experiment; all trial evidence retained under HOLD')
        evaluated = [row for row in report['trials'] if row['phase'] == 'evaluation']
        report['assessment'] = assess(evaluated)
        report['intelligence_advantage'] = report['assessment']['intelligence_advantage']
        report['status'] = 'COMPLETED'
        report['execution'] = 'COMPLETED'
        report.pop('active_trial', None)
    except Exception as error:
        # Retain all completed rows and mission journals; unknown external
        # execution is never resumed by this experiment harness.
        report['reason'] = type(error).__name__+': '+str(error)
        report['execution'] = 'INTERRUPTED_HOLD'
    write_new(output, report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    template = sub.add_parser('template'); template.add_argument('--output', type=Path, required=True)
    design = sub.add_parser('protocol'); design.add_argument('--output', type=Path, required=True)
    register = sub.add_parser('freeze')
    register.add_argument('--corpus', type=Path, required=True)
    register.add_argument('--corpus-root', type=Path, required=True)
    register.add_argument('--image', required=True)
    register.add_argument('--qualification', type=Path, required=True)
    register.add_argument('--recovery', type=Path, required=True)
    register.add_argument('--output', type=Path, required=True)
    execute = sub.add_parser('run')
    execute.add_argument('--plan', type=Path)
    execute.add_argument('--corpus-root', type=Path, default=Path('.'))
    execute.add_argument('--qualification', type=Path)
    execute.add_argument('--recovery', type=Path)
    execute.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == 'template':
        write_new(args.output, corpus_template()); return 0
    if args.action == 'protocol':
        result = freeze_protocol(args.output)
        print(json.dumps({'protocol_sha256': result['sha256'], 'status': result['payload']['status']})); return 0
    if args.action == 'freeze':
        result = freeze(args.corpus, args.corpus_root, args.output, image=args.image,
                        qualification=args.qualification, recovery=args.recovery)
        print(json.dumps({'plan_sha256': result['sha256'], 'status': 'PREREGISTERED'})); return 0
    document = read_json(args.plan) if args.plan else None
    result = run(document, args.corpus_root, args.qualification, args.recovery, args.output)
    print(json.dumps({'status': result['status'], 'execution': result['execution'],
                      'intelligence_advantage': result['intelligence_advantage'],
                      'reasons': result['preflight']['reasons']}))
    return 0 if result['execution'] == 'COMPLETED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
