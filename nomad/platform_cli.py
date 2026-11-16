"""Offline operator entry point; unknown repositories always use isolation."""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import sys
import tempfile

from .isolation import IsolationUnavailable, UnsafeWorkspace, snapshot_source, SandboxPolicy
from .mission_runtime import MissionHold, canonical, digest, exclusive_owner
from .platform import doctor, load_policy, runtime_smoke


def _read_json(path, maximum=65536):
    if path.stat().st_size > maximum:
        raise ValueError('configuration/contract exceeds size budget')
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value: raise ValueError('duplicate JSON key')
            value[key]=item
        return value
    return json.loads(path.read_bytes(), object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON value')))


def _review(root, output=None, decision=None):
    """Export an independently checked patch; never modify the original repo."""
    from . import platform_mission as mission
    root=Path(root).resolve(strict=True)
    with exclusive_owner(root):
        goal,_,rows=mission._load(root)
        summary=mission._summary(goal,rows)
        if summary['status']!='completed':
            raise MissionHold('patch review requires completed independent WITNESS and final verification')
        mission._check_terminal(root,goal,rows)
        patches=[]
        for name in sorted(goal['baseline']):
            before=(root/'baseline'/name).read_bytes(); after=(root/'workspace'/name).read_bytes()
            if before==after: continue
            for line in difflib.unified_diff(before.decode('utf-8').splitlines(True),
                    after.decode('utf-8').splitlines(True),fromfile='a/'+name,tofile='b/'+name):
                patches.append(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n')
        patch=''.join(patches)
        report={'schema':'nomad.patch-review.v18','status':'REVIEWABLE','mission':summary,
            'baseline_sha256':goal['baseline'],'candidate_sha256':mission._manifest(root/'workspace'),
            'patch_sha256':digest(patch.encode()),'patch':patch,
            'diagnostics':[r['data'] for r in rows if r['kind'] in ('F_DIAGNOSIS','DIAGNOSED')],
            'witness':[r['data'] for r in rows if r['kind'] in ('F_WITNESS','WITNESS_RESULT')],
            'final':[r['data'] for r in rows if r['kind'] in ('F_FINAL','FINAL_RESULT')],
            'decision':decision,'source_application_performed':False,
            'authority':'operator patch review; no deployment or additional verification authority'}
        if decision:
            if decision not in ('accept','reject') or output is None:
                raise ValueError('review decision requires a new output directory')
            output=Path(output).resolve()
            if output==root or root in output.parents or output in root.parents:
                raise ValueError('review output must be disjoint from mission')
            if output.exists(): raise FileExistsError('review output already exists')
            output.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='nomad-review-',dir=output.parent) as temporary:
                stage=Path(temporary)
                (stage/'proposed.patch').write_bytes(patch.encode())
                (stage/'receipt.json').write_bytes(canonical(report))
                mission._publish_staged_mission(stage,output)
            report['output']=str(output)
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='NOMAD v0.18 PLATFORM')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--image', help='reviewed, pre-pulled image with @sha256 digest')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('doctor')
    commands.add_parser('runtime-smoke')
    commands.add_parser('trusted-demo')
    dry = commands.add_parser('dry-run', help='bounded source inspection; executes no repository code')
    dry.add_argument('--source', type=Path, required=True)
    source_inspection=commands.add_parser('inspect-source', help='list admitted Python interfaces without importing source')
    source_inspection.add_argument('--source',type=Path,required=True)
    for name in ('status', 'recover', 'run'):
        child = commands.add_parser(name)
        child.add_argument('--root', type=Path, required=True)
    init = commands.add_parser('init', help='initialize an admitted arithmetic or typed function mission')
    repair=commands.add_parser('repair',help='initialize and run after native containment qualification')
    repair.add_argument('--isolation-receipt',type=Path,required=True)
    for initial in (init,repair):
        initial.add_argument('--root', type=Path, required=True)
        initial.add_argument('--source', type=Path, required=True)
        initial.add_argument('--contract', type=Path, required=True)
        choice=initial.add_mutually_exclusive_group()
        choice.add_argument('--ranker', choices=('cold', 'native', 'frequency', 'shuffled'))
        choice.add_argument('--mechanism',choices=('temporal','native','frequency'),
            help='typed functions: temporal default; detector off, selective warm state')
        choice.add_argument('--computation-controller', type=Path,help='explicit legacy research AdaptiveConfig')
        choice.add_argument('--persistent-controller', type=Path,help='explicit research PersistentConfig; overrides operating defaults')
        initial.add_argument('--candidate-budget', type=int, default=64)
        initial.add_argument('--probe-budget', type=int, default=3)
        initial.add_argument('--max-files-changed', type=int, choices=(1,2), default=2)
    for name in ('review','accept','reject'):
        review=commands.add_parser(name,help='review verified patch or export an explicit operator decision')
        review.add_argument('--root',type=Path,required=True)
        if name!='review':review.add_argument('--output',type=Path,required=True)
    demo = commands.add_parser('isolated-demo')
    demo.add_argument('--root', type=Path, required=True)
    demo.add_argument('--ranker', choices=('cold', 'native', 'frequency', 'shuffled'), default='native')
    for mission_parser in (init, repair, demo):
        mission_parser.add_argument('--memory-root', type=Path, help='shared trusted append-only learning store')
        mission_parser.add_argument('--epoch', type=int, default=0, help='monotonic evidence epoch for expiry')
        mission_parser.add_argument('--no-adaptive', action='store_true', help='disable world/memory preference; retain verification')
        mission_parser.add_argument('--execution-budget', type=int, help='total dispatch budget including recovery; arithmetic4/functions96')
        mission_parser.add_argument('--max-eval', type=int, default=65000, help='GENESIS evaluation budget')
    args = parser.parse_args(argv)
    try:
        policy = load_policy(args.config, args.image)
        if args.action=='repair' and policy is None:
            record=_read_json(args.isolation_receipt,2_000_000)
            if not isinstance(record,dict) or type(record.get('policy')) is not dict:
                raise IsolationUnavailable('native containment PASS receipt with a reviewed policy is required')
            policy=SandboxPolicy(**record['policy']);policy.validate()
        if args.action == 'doctor':
            report = doctor(policy)
        elif args.action == 'runtime-smoke':
            report = runtime_smoke()
        elif args.action == 'trusted-demo':
            from .codeworld import make_codeworld_tasks
            from .mission_runtime import initialize, run
            with tempfile.TemporaryDirectory(prefix='nomad-trusted-demo-') as temporary:
                root = Path(temporary) / 'mission'
                task = next(t for t in make_codeworld_tasks(9117, per_family=1) if '-bin-' in t.task_id)
                initialize(root, task)
                report = run(root, trusted_fixture=True)
                report['execution_scope'] = 'generated trusted fixture on host; not containment'
        elif args.action in ('review','accept','reject'):
            report=_review(args.root,getattr(args,'output',None),None if args.action=='review' else args.action)
        elif args.action=='inspect-source':
            from .frontier import inspect_function_structure
            inspection_policy=policy or SandboxPolicy('inspection@sha256:'+'0'*64)
            with tempfile.TemporaryDirectory(prefix='nomad-inspect-') as temporary:
                destination=Path(temporary)/'source'
                copied=snapshot_source(args.source,destination,inspection_policy)
                structure=inspect_function_structure(destination)
                report={'schema':'nomad.source-inspection.v18','status':'ADMITTED',
                    'source_sha256':copied.digest,'interfaces':structure['symbols'],
                    'modules':structure['modules'],'imports':structure['graph'],
                    'executed_code':False,'containment_qualified':False}
        elif args.action in ('status', 'recover', 'run'):
            from . import platform_mission
            function = {'status': platform_mission.inspect, 'recover': platform_mission.recover,
                        'run': platform_mission.run}[args.action]
            report = function(args.root)
        else:
            if policy is None:
                raise IsolationUnavailable('set a reviewed digest-pinned image in configuration; no host fallback')
            if args.action == 'dry-run':
                with tempfile.TemporaryDirectory(prefix='nomad-dry-run-') as temporary:
                    result = snapshot_source(args.source, Path(temporary) / 'source', policy)
                    report = {'schema': 'nomad.platform.dry-run.v1', 'status': 'INSPECTED',
                              'files': result.files, 'bytes': result.bytes,
                              'source_sha256': result.digest, 'executed_code': False,
                              'containment_qualified': False}
            elif args.action in ('init','repair'):
                from .platform_mission import initialize, initialize_functions, run
                from .platform_bitwork import NativeDecisionRanker
                if args.action=='repair':
                    from scripts.qualify_recovery_v18 import _validate_isolation_receipt
                    from scripts.qualify_isolation_v18 import qualification_host_identity
                    _validate_isolation_receipt(args.isolation_receipt,policy,qualification_host_identity())
                    from .isolation import docker_preflight
                    preflight=docker_preflight(policy)
                    if not preflight['ready']:raise IsolationUnavailable('; '.join(preflight['reasons']))
                contract = _read_json(args.contract)
                adapter=contract.pop('adapter',None) if isinstance(contract,dict) else None
                required = {'goal_text', 'public', 'challenge', 'final'}
                optional={'public_command'} if adapter=='python-functions-v1' else {'target','entry_module'}
                if adapter not in (None,'python-functions-v1') or not isinstance(contract, dict) or not required <= set(contract) or set(contract) - required - optional:
                    raise ValueError('invalid mission contract')
                functions=adapter=='python-functions-v1'
                computation=None;persistent=None
                if args.persistent_controller:
                    if not functions or args.computation_controller:raise ValueError('persistent controller needs typed functions and cannot be combined with adaptive E')
                    persistent=_read_json(args.persistent_controller,8192)
                    if type(persistent) is not dict:raise ValueError('persistent configuration must be an object')
                if args.computation_controller:
                    if not functions: raise ValueError('adaptive computation is supported only by the typed function adapter')
                    computation=_read_json(args.computation_controller,8192)
                    if not isinstance(computation,dict): raise ValueError('computation configuration must be a JSON object')
                operating=(args.mechanism or 'temporal') if functions and not any((args.ranker,args.computation_controller,args.persistent_controller)) else None
                if args.mechanism and not functions: raise ValueError('mechanism selection requires typed functions')
                ranker = None if computation is not None or persistent is not None or operating else NativeDecisionRanker(args.ranker or 'native', action_schema='python-call-relational-vs-other' if functions else 'genesis-vs-ast')
                options={'max_candidates':args.candidate_budget,'probe_budget':args.probe_budget,
                         'max_files_changed':args.max_files_changed} if functions else {'max_eval':args.max_eval}
                if computation is not None: options['computation_controller']=computation
                if persistent is not None:options['persistent_controller']=persistent
                if operating:options['operating_mechanism']=operating
                report = (initialize_functions if functions else initialize)(args.root, args.source, policy=policy, ranker=ranker,
                    memory_root=args.memory_root, capture_epoch=args.epoch, adaptive_enabled=not args.no_adaptive,
                    max_executions=args.execution_budget if args.execution_budget is not None else (96 if functions else 4),
                    **options, **contract)
                if args.action=='repair':
                    report=run(args.root)
                    if report.get('status')=='completed':report=_review(args.root)
            else:
                from .platform_mission import initialize, run
                from .platform_bitwork import NativeDecisionRanker
                if args.root.exists():
                    raise ValueError('demo root exists; use status/recover/run to resume it')
                with tempfile.TemporaryDirectory(prefix='nomad-platform-demo-input-') as temporary:
                    source = Path(temporary)
                    (source / 'solution.py').write_bytes(b'def solve(x, y):\n    return x - y\n')
                    (source / 'tests').mkdir()
                    (source / 'tests' / 'test_public.py').write_bytes(
                        b'import unittest\nfrom solution import solve\n'
                        b'class PublicTests(unittest.TestCase):\n'
                        b'    def test_sum(self):\n        self.assertEqual(solve(1, 2), 3)\n')
                    def rows(pairs):
                        return [{'x': x, 'y': y, 'expected': x + y} for x, y in pairs]
                    initialize(args.root, source, goal_text='Make solve return the sum of its arguments',
                               public=rows([(1, 2), (3, 4)]), challenge=rows([(-5, 7), (0, 3)]),
                               final=rows([(11, -2), (-6, -9)]), policy=policy,
                               ranker=NativeDecisionRanker(args.ranker, action_schema='genesis-vs-ast'),
                               memory_root=args.memory_root, capture_epoch=args.epoch,
                               adaptive_enabled=not args.no_adaptive, max_executions=args.execution_budget if args.execution_budget is not None else 4,
                               max_eval=args.max_eval)
                report = run(args.root)
        print(json.dumps(report, indent=2, sort_keys=True))
        if args.action == 'runtime-smoke' and any(row['status'] != 'PASS' for row in report['languages'].values()):
            return 3
        if args.action=='repair' and report.get('status')!='REVIEWABLE':return 3
        if args.action in ('trusted-demo', 'isolated-demo', 'run') and report.get('status') != 'completed':
            return 3
        return 0
    except (IsolationUnavailable, UnsafeWorkspace, MissionHold, OSError, ValueError, TypeError) as error:
        print(json.dumps({'schema': 'nomad.platform.hold.v1', 'status': 'HOLD',
                          'reason': str(error), 'untrusted_host_fallback': False}), file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
