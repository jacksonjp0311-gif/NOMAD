"""New FRONTIER A/B/C/D repository protocol; the older arm protocol is immutable.

This controller reuses reviewed path, corpus metadata and native receipt checks.
Actual unknown code runs only through the qualified function-mission adapter.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import experiment_qualification_v18 as shared
from nomad.isolation import snapshot_source, docker_preflight
from nomad.platform_bitwork import NativeDecisionRanker

SCHEMA = 'nomad.frontier-repository-experiment.v18'
ARMS = {'A': {'adaptive_enabled': False, 'ranker_mode': 'cold'},
        'B': {'adaptive_enabled': False, 'ranker_mode': 'frequency'},
        'C': {'adaptive_enabled': False, 'ranker_mode': 'native'},
        'D': {'adaptive_enabled': True, 'ranker_mode': 'native'}}
SEEDS = (1818201, 1818207, 1818211)
BOUNDS = {'max_candidates': 64, 'max_executions': 96, 'probe_budget': 3, 'max_files_changed': 2}
ACTION_SCHEMA = 'python-call-relational-vs-other'
ADAPTER = 'python-functions-v1'
EXPOSED_DEVELOPMENT_REPOSITORIES = {'keon/algorithms', 'thealgorithms/python'}


def code_identity():
    return {**shared.code_identity(), 'scripts/experiment_frontier_v18.py': shared.file_hash(Path(__file__)),
            'scripts/qualify_function_recovery_frontier_v18.py':
                shared.file_hash(ROOT/'scripts/qualify_function_recovery_frontier_v18.py'),
            'experiments/FRONTIER_PUBLIC_DEVELOPMENT_LEADS_V018.json':
                shared.file_hash(ROOT/'experiments/FRONTIER_PUBLIC_DEVELOPMENT_LEADS_V018.json')}


def protocol():
    return {'schema': SCHEMA+'.protocol', 'arms': json.loads(shared.canonical(ARMS)),
        'seeds': list(SEEDS), 'bounds': dict(BOUNDS), 'sandbox': {key: shared.BOUNDS[key] for key in
            ('timeout_s','memory_mib','cpus','pids_limit','max_files','max_total_bytes')},
        'whole_mission_compute_budget': {'qualified': False,
            'required': 'matched hard limits over controller plus all workers for CPU, peak memory and elapsed wall time',
            'blocker': 'worker limits exist; aggregate controller-plus-worker CPU/memory/wall supervision is not qualified'},
        'adapter': ADAPTER, 'action_schema': ACTION_SCHEMA,
        'native_binary_meaning': {'0': 'comparison AST family', '1': 'other registered AST families'},
        'minimum_training_repositories': 2, 'minimum_evaluation_repositories': 8, 'minimum_evaluation_tasks': 24,
        'training': 'common independently accepted cold training observations; fresh frozen clone before every evaluation trial',
        'evaluation_updates': False,
        'matching': 'same source, available public contract, candidate inventory, training evidence and declared budgets; arm policy may choose different public probes',
        'acceptance': {'contrasts': ['D>A', 'D>B', 'C>B', 'D>C'],
            'metric': 'independent final accepted repair rate grouped by upstream repository',
            'test': 'one-sided paired exact sign test, ties omitted; Holm four contrasts alpha0.05',
            'joint_claim_requires': 'matched whole-mission hard compute budgets qualified, all four contrasts significant, no integrity/containment failure'},
        'limits': ['finite independent examples, not general semantic correctness',
            'two coarse action classes do not distinguish candidates within a class',
            'controller CPU/RSS hard cap absent; isolated and controller costs reported separately',
            'native recovery must explicitly exercise this function adapter',
            'no repository efficacy inferred from trusted synthetic stream mechanism study']}


def corpus_template():
    data = shared.corpus_template()
    data['schema'] = SCHEMA+'.corpus'
    data['notes'].append('Public specs contain goal_text, public JSON function cases, and optional registered public_command.')
    return data


def audit(corpus, root, *, inspect_public=True):
    if corpus.get('schema') != SCHEMA+'.corpus': raise ValueError('wrong FRONTIER corpus schema')
    # Reuse established metadata independence checks, with an explicit schema
    # adapter; neither the old protocol nor its arm configuration is mutated.
    result = shared.audit_corpus({**corpus, 'schema': shared.SCHEMA+'.corpus'}, root, check_public_files=False)
    if any(task['split'] == 'evaluation' and shared._repository(task['repository']) in
           EXPOSED_DEVELOPMENT_REPOSITORIES for task in corpus['tasks']):
        raise ValueError('exposed FRONTIER development repository cannot be unseen evaluation')
    if inspect_public:
        import tempfile
        from nomad import frontier, platform_mission
        for task in corpus['tasks']:
            public = shared.read_json(shared._path(root, task['public_spec']), 65536,
                                      expected_sha256=task['public_spec_sha256'])
            if not {'goal_text', 'public'} <= set(public) or set(public)-{'goal_text', 'public', 'public_command'}:
                raise ValueError('unsupported public specification fields')
            if not isinstance(public['goal_text'], str) or not 1 <= len(public['goal_text']) <= 4096:
                raise ValueError('public goal exceeds scope')
            if public.get('public_command') not in (None, platform_mission.COMMAND):
                raise ValueError('unregistered public suite command')
            frontier.validate_function_cases(public['public'])
            with tempfile.TemporaryDirectory(prefix='nomad-frontier-audit-') as temporary:
                snapshot = snapshot_source(shared._path(root, task['source']), Path(temporary)/'source',
                                           shared.execution_policy('nomad/identity@sha256:'+'0'*64))
                if snapshot.digest != task['source_sha256']: raise ValueError('source snapshot changed')
                frontier.inspect_function_repository(snapshot.root, public['public'],
                    max_candidates=BOUNDS['max_candidates'], max_files_changed=BOUNDS['max_files_changed'])
    return result


def freeze_design(output):
    payload = {'schema': SCHEMA+'.design-only', 'protocol': protocol(), 'source_sha256': code_identity(),
               'status': 'AWAITING_CURATED_CORPUS_NOT_AN_EXPERIMENT_PLAN', 'tasks_registered': 0,
               'private_contracts_opened': False}
    document = {'payload': payload, 'sha256': shared.digest(payload)}
    shared.write_new(output, document); return document


def freeze(corpus_path, root, output, image, qualification, recovery):
    shared.execution_policy(image).validate()
    corpus = shared.read_json(corpus_path)
    payload = {'schema': SCHEMA+'.plan', 'protocol': protocol(), 'corpus': corpus,
        'independence_audit': audit(corpus, root), 'source_sha256': code_identity(),
        'corpus_document_sha256': shared.file_hash(corpus_path), 'image': image,
        'qualification_sha256': shared.file_hash(qualification), 'recovery_sha256': shared.file_hash(recovery)}
    document = {'payload': payload, 'sha256': shared.digest(payload)}
    shared.write_new(output, document); return document


def validate(document):
    payload = document.get('payload')
    if (not isinstance(payload, dict) or document.get('sha256') != shared.digest(payload)
            or payload.get('schema') != SCHEMA+'.plan' or payload.get('protocol') != protocol()
            or payload.get('source_sha256') != code_identity()):
        raise ValueError('FRONTIER plan/source/arm design differs from preregistration')
    shared.execution_policy(payload['image']).validate()
    return payload


def function_recovery_binding(record, image, qualification_sha256):
    from dataclasses import asdict
    from scripts import qualify_function_recovery_frontier_v18 as recovery
    from scripts.qualify_isolation_v18 import qualification_host_identity
    body={key:value for key,value in record.items() if key!='receipt_sha256'}
    policy=asdict(shared.execution_policy(image))
    sources=recovery.source_identity()
    if (record.get('schema')!='nomad.function-recovery-qualification.frontier.v18'
            or record.get('receipt_sha256')!=shared.digest(body) or record.get('backend')!='docker'
            or record.get('status')!='PASS' or record.get('isolated_mission_recovery')!='PASS'
            or ADAPTER not in record.get('adapter_scopes',[]) or record.get('image')!=image
            or record.get('policy')!=policy or record.get('policy_sha256')!=shared.digest(policy)
            or record.get('host_identity_sha256')!=shared.digest(qualification_host_identity())
            or record.get('isolation_receipt_sha256')!=qualification_sha256
            or record.get('source_stable') is not True or record.get('source_sha256_before')!=sources
            or record.get('source_sha256_after')!=sources
            or record.get('evidence_inventory_complete') is not True
            or record.get('protected_host_sentinel_unchanged') is not True
            or record.get('original_source_unchanged') is not True):
        raise ValueError('function recovery receipt lacks exact native scope/source/policy/host binding')
    cases=record.get('cases'); expected=set(recovery.required_cases())
    if (not isinstance(cases,list) or len(cases)!=len(expected)
            or any(not isinstance(case,dict) or case.get('status')!='PASS' for case in cases)
            or {case.get('case') for case in cases}!=expected):
        raise ValueError('function recovery lacks all registered native passing cases')
    for case in cases:
        if case['case'] in recovery.EXPECTED_CONTROL_CASES and case.get('result',{}).get('passed') is not True:
            raise ValueError('function recovery control did not independently pass')
        if case['case'].startswith('tampered-') and (case.get('refused') is not True or case.get('dispatched') is not False):
            raise ValueError('function recovery tamper case did not refuse before dispatch')
        if case['case']=='final_rejection_restores_source' and (
                case.get('restored_original') is not True or case.get('no_learning_admitted') is not True
                or case.get('result',{}).get('status')!='rejected'):
            raise ValueError('function recovery failed negative rollback/no-learning requirement')
        if case['case']=='two_file_partial_patch_recovery':
            reference=case.get('reference_control',{})
            if (case.get('actual_mixed_two_file_snapshot_observed') is not True
                    or reference.get('passed') is not True or reference.get('changed_files')!=2):
                raise ValueError('function recovery did not observe and compare a genuinely partial two-file snapshot')
    death=next(case for case in cases if case['case']=='owner_hard_death_with_live_container').get('death',{})
    if any(death.get(key) is not True for key in ('observed_live_container_before_owner_death',
            'cleanup_confirmed_after_owner_death','held_before_cleanup')):
        raise ValueError('function recovery lacks actual live-worker death and cleanup observations')


def preflight(document, root, qualification, recovery):
    if document is None:
        check = shared.preflight(None, root, qualification, recovery)
        check['reasons'].append('function-adapter native recovery requires source-bound review in a corpus plan')
        check['reasons'].append('matched whole-mission controller-plus-worker CPU/memory/wall budget is not qualified')
        return check
    try:
        plan = validate(document)
        audit(plan['corpus'], root, inspect_public=False)
        if protocol()['whole_mission_compute_budget']['qualified'] is not True:
            raise ValueError('matched whole-mission controller-plus-worker CPU/memory/wall budget is not qualified')
        for kind, path in (('qualification', qualification), ('recovery', recovery)):
            if path is None: raise ValueError('trusted '+kind+' receipt absent')
            record = shared.read_json(path, expected_sha256=plan[kind+'_sha256'])
            if record.get('status') != 'PASS': raise ValueError(kind+' is not PASS')
            if kind == 'qualification':
                shared._receipt_binding(record, plan['image'], kind)
                if record.get('native_containment_gate') != 'PASS': raise ValueError('native containment not PASS')
            else:
                function_recovery_binding(record, plan['image'], plan['qualification_sha256'])
                shared._recovery_evidence(record)
        current = docker_preflight(shared.execution_policy(plan['image']))
        if not current.get('ready'): raise ValueError('current native Docker preflight is HOLD')
        return {'status': 'PASS', 'execution': 'NOT_STARTED', 'private_contracts_opened': False, 'reasons': []}
    except (ValueError, TypeError, KeyError, OSError, ImportError) as error:
        return {'status': 'HOLD', 'execution': 'NOT_RUN', 'private_contracts_opened': False, 'reasons': [str(error)]}


def trial(task, root, destination, memory, settings, image):
    from nomad import platform_mission
    started, cpu = time.perf_counter(), time.process_time()
    public = shared.read_json(shared._path(root, task['public_spec']), 65536,
                              expected_sha256=task['public_spec_sha256'])
    private = shared._private_contract(task, root)
    ranker = (platform_mission.read_function_memory_ranker(memory, mode=settings['ranker_mode'], now_epoch=0)
              if memory.exists() else NativeDecisionRanker(settings['ranker_mode'], action_schema=ACTION_SCHEMA))
    initial = platform_mission.initialize_functions(destination, shared._path(root, task['source']),
        policy=shared.execution_policy(image), ranker=ranker, memory_root=memory,
        adaptive_enabled=settings['adaptive_enabled'], **BOUNDS, **public, **private)
    if shared.digest(initial['baseline_entries']) != task['source_sha256']:
        raise ValueError('actual function mission snapshot differs from registered source')
    result = platform_mission.run(destination)
    goal = platform_mission.resolved_goal(destination)
    events = [json.loads(line) for line in (destination/'events.jsonl').read_text().splitlines()]
    public_passed = any(row['kind'] == 'F_OBSERVED' and row['data']['operation'].startswith('search:')
                        and row['data']['result'].get('supported') is True for row in events)
    private_rejected = any(row['kind'] in ('F_WITNESS', 'F_FINAL') and
        (row['data'].get('supported') is False or row['data'].get('receipt', {}).get('supported') is False) for row in events)
    return {'task_id': task['id'], 'repository': shared._repository(task['repository']),
        'source_sha256': task['source_sha256'], 'public_spec_sha256': task['public_spec_sha256'],
        'status': result['status'], 'accepted': result['status'] == 'completed',
        'public_passed': public_passed, 'independent_contract_rejected': private_rejected,
        'candidate_inventory_sha256': result['candidate_inventory_sha256'],
        'candidate_inventory_count': result['candidate_inventory_count'],
        'candidate_evaluations': result['public_executions_recorded'], 'isolated_executions': result['dispatches'],
        'mission_id': result['mission_id'], 'journal_head': result['journal_head'],
        'wall_seconds': time.perf_counter()-started, 'controller_cpu_seconds': time.process_time()-cpu,
        'supervisor_resources': [row['data']['execution'].get('supervisor_metrics') for row in events if row['kind'] == 'F_OBSERVED'],
        'planning': goal.get('planning', {}), 'authority': 'finite isolated function contract only'}


def assess(rows):
    # Reuse matching and descriptive denominator validation only; the old
    # registered C>A/C>B/C>D analysis is intentionally not reused.
    seen, pairs, repositories = set(), {}, {}
    for row in rows:
        key = row['seed'], row['task_id'], row['arm']
        if key in seen or row['seed'] not in SEEDS or row['arm'] not in ARMS:
            raise ValueError('duplicate or unregistered trial')
        seen.add(key); pair = key[:2]
        identity = tuple(row[k] for k in ('repository','source_sha256','public_spec_sha256','candidate_inventory_sha256'))
        existing = pairs.setdefault(pair, {'identity': identity, 'arms': set()})
        if existing['identity'] != identity: raise ValueError('unmatched source/public information/candidate inventory')
        existing['arms'].add(row['arm'])
        repositories.setdefault(row['repository'], {}).setdefault(row['arm'], []).append(int(row['accepted']))
    if any(value['arms'] != set(ARMS) for value in pairs.values()): raise ValueError('unmatched arm observations')
    contrasts = []
    for label in protocol()['acceptance']['contrasts']:
        proposed, control = label.split('>'); wins = losses = ties = 0
        for group in repositories.values():
            d = sum(group[proposed])/len(group[proposed])-sum(group[control])/len(group[control])
            wins += d > 0; losses += d < 0; ties += d == 0
        n = wins+losses
        contrasts.append({'contrast': label, 'repository_wins': wins, 'repository_losses': losses,
            'repository_ties': ties, 'p_one_sided': sum(math.comb(n,i) for i in range(wins,n+1))/2**n if n else 1.0})
    rejecting = True
    for index, row in enumerate(sorted(contrasts,key=lambda x:x['p_one_sided'])):
        row['holm_threshold'] = .05/(len(contrasts)-index)
        row['significant'] = rejecting and row['p_one_sided'] <= row['holm_threshold']; rejecting = row['significant']
    outcomes = {}
    for arm in ARMS:
        selected = [row for row in rows if row['arm'] == arm]
        public = sum(row.get('public_passed') is True for row in selected)
        false = sum(row.get('public_passed') is True and row.get('independent_contract_rejected') is True for row in selected)
        outcomes[arm] = {'trials': len(selected), 'accepted': sum(row['accepted'] for row in selected),
            'public_passes': public, 'independently_rejected_public_successes': false,
            'false_success_rate': false/public if public else None,
            'denominator': 'public-pass trials; seed repetitions are not independent repositories'}
    return {'contrasts': contrasts, 'outcomes': outcomes,
        'repository_advantage': 'SUPPORTED_WITHIN_REGISTERED_SCOPE' if len(repositories)>=8 and all(r['significant'] for r in contrasts) else 'NOT_ESTABLISHED'}


def run(document, root, qualification, recovery, output):
    if output.exists(): raise FileExistsError('never overwrite FRONTIER results')
    check = preflight(document, root, qualification, recovery)
    report = {'schema': SCHEMA+'.run', 'status': 'HOLD', 'execution': 'NOT_RUN', 'preflight': check,
        'plan_sha256': document.get('sha256') if document else None, 'trials': [],
        'private_contracts_opened': False, 'repository_advantage': 'NOT_ESTABLISHED',
        'energy_joules': None, 'api_cost_usd': 0, 'cloud_calls': 0}
    if check['status'] != 'PASS': shared.write_new(output, report); return report
    plan = validate(document)
    evidence = output.with_suffix('.missions')
    try:
        audit(plan['corpus'], root)
        evidence.mkdir(parents=True, exist_ok=False)
        memory = evidence/'training-memory'
        for index, task in enumerate(sorted((t for t in plan['corpus']['tasks'] if t['split']=='training'),key=lambda t:t['id'])):
            report['active_trial'] = {'phase':'training','task_id':task['id']}; report['private_contracts_opened'] = True
            row = trial(task,root,evidence/('training-'+str(index)),memory,ARMS['A'],plan['image'])
            report['trials'].append({**row,'phase':'training','arm':'common','seed':None})
        for seed in SEEDS:
            tasks = [t for t in plan['corpus']['tasks'] if t['split']=='evaluation']; random.Random(seed).shuffle(tasks)
            for index, task in enumerate(tasks):
                arms = list(ARMS); random.Random(str(seed)+':'+task['id']).shuffle(arms)
                for arm in arms:
                    name = str(seed)+'-'+str(index)+'-'+arm; clone = evidence/(name+'-memory')
                    report['active_trial'] = {'phase':'evaluation','task_id':task['id'],'arm':arm,'seed':seed}
                    started = time.perf_counter()
                    if memory.exists(): shutil.copytree(memory,clone)
                    clone_wall = time.perf_counter()-started
                    row = trial(task,root,evidence/name,clone,ARMS[arm],plan['image'])
                    report['trials'].append({**row,'phase':'evaluation','arm':arm,'seed':seed,'memory_clone_wall_seconds':clone_wall})
                    if (not shared._sha(row['candidate_inventory_sha256']) or row['candidate_evaluations']>BOUNDS['max_candidates']
                            or row['isolated_executions']>BOUNDS['max_executions']): raise ValueError('registered inventory/execution budget violated')
        if code_identity() != plan['source_sha256']: raise ValueError('pipeline source changed during evaluation')
        report['assessment'] = assess([row for row in report['trials'] if row['phase']=='evaluation'])
        report['repository_advantage'] = report['assessment']['repository_advantage']
        report['status'] = report['execution'] = 'COMPLETED'; report.pop('active_trial',None)
    except Exception as error:
        report['execution'] = 'INTERRUPTED_HOLD'; report['reason'] = type(error).__name__+': '+str(error)
    shared.write_new(output,report); return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='action',required=True)
    for name in ('protocol','template'):
        child=sub.add_parser(name); child.add_argument('--output',type=Path,required=True)
    child=sub.add_parser('freeze'); child.add_argument('--corpus',type=Path,required=True); child.add_argument('--image',required=True)
    for name in ('corpus-root','qualification','recovery','output'): child.add_argument('--'+name,type=Path,required=True)
    child=sub.add_parser('run'); child.add_argument('--plan',type=Path); child.add_argument('--corpus-root',type=Path,default=Path('.'))
    child.add_argument('--qualification',type=Path); child.add_argument('--recovery',type=Path); child.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.action=='protocol': result=freeze_design(args.output)
    elif args.action=='template': result=corpus_template(); shared.write_new(args.output,result)
    elif args.action=='freeze': result=freeze(args.corpus,args.corpus_root,args.output,args.image,args.qualification,args.recovery)
    else: result=run(shared.read_json(args.plan) if args.plan else None,args.corpus_root,args.qualification,args.recovery,args.output)
    print(json.dumps({'status':result.get('status',result.get('payload',{}).get('status','FROZEN')),
                      'execution':result.get('execution'),'sha256':result.get('sha256')}))
    return 3 if result.get('status')=='HOLD' else 0


if __name__=='__main__': raise SystemExit(main())
