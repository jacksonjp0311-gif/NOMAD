"""Offline operator entry point; unknown repositories always use isolation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from .isolation import IsolationUnavailable, UnsafeWorkspace, snapshot_source
from .mission_runtime import MissionHold
from .platform import doctor, load_policy, runtime_smoke


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
    for name in ('status', 'recover', 'run'):
        child = commands.add_parser(name)
        child.add_argument('--root', type=Path, required=True)
    init = commands.add_parser('init', help='initialize an admitted arithmetic or typed function mission')
    init.add_argument('--root', type=Path, required=True)
    init.add_argument('--source', type=Path, required=True)
    init.add_argument('--contract', type=Path, required=True)
    init.add_argument('--ranker', choices=('cold', 'native', 'frequency', 'shuffled'), default='native')
    init.add_argument('--candidate-budget', type=int, default=64, help='typed function proposal inventory limit')
    init.add_argument('--probe-budget', type=int, default=3, help='typed function public diagnostic limit')
    init.add_argument('--max-files-changed', type=int, choices=(1,2), default=2)
    demo = commands.add_parser('isolated-demo')
    demo.add_argument('--root', type=Path, required=True)
    demo.add_argument('--ranker', choices=('cold', 'native', 'frequency', 'shuffled'), default='native')
    for mission_parser in (init, demo):
        mission_parser.add_argument('--memory-root', type=Path, help='shared trusted append-only learning store')
        mission_parser.add_argument('--epoch', type=int, default=0, help='monotonic evidence epoch for expiry')
        mission_parser.add_argument('--no-adaptive', action='store_true', help='disable world/memory preference; retain verification')
        mission_parser.add_argument('--execution-budget', type=int, help='total dispatch budget including recovery; arithmetic4/functions96')
        mission_parser.add_argument('--max-eval', type=int, default=65000, help='GENESIS evaluation budget')
    args = parser.parse_args(argv)
    try:
        policy = load_policy(args.config, args.image)
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
            elif args.action == 'init':
                from .platform_mission import initialize, initialize_functions
                from .platform_bitwork import NativeDecisionRanker
                if args.contract.stat().st_size > 65536:
                    raise ValueError('contract exceeds size budget')
                contract = json.loads(args.contract.read_text(encoding='utf-8'))
                adapter=contract.pop('adapter',None) if isinstance(contract,dict) else None
                required = {'goal_text', 'public', 'challenge', 'final'}
                optional={'public_command'} if adapter=='python-functions-v1' else {'target','entry_module'}
                if adapter not in (None,'python-functions-v1') or not isinstance(contract, dict) or not required <= set(contract) or set(contract) - required - optional:
                    raise ValueError('invalid mission contract')
                functions=adapter=='python-functions-v1'
                ranker = NativeDecisionRanker(args.ranker, action_schema='python-call-relational-vs-other' if functions else 'genesis-vs-ast')
                options={'max_candidates':args.candidate_budget,'probe_budget':args.probe_budget,
                         'max_files_changed':args.max_files_changed} if functions else {'max_eval':args.max_eval}
                report = (initialize_functions if functions else initialize)(args.root, args.source, policy=policy, ranker=ranker,
                    memory_root=args.memory_root, capture_epoch=args.epoch, adaptive_enabled=not args.no_adaptive,
                    max_executions=args.execution_budget if args.execution_budget is not None else (96 if functions else 4),
                    **options, **contract)
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
        if args.action in ('trusted-demo', 'isolated-demo', 'run') and report.get('status') != 'completed':
            return 3
        return 0
    except (IsolationUnavailable, UnsafeWorkspace, MissionHold, OSError, ValueError, TypeError) as error:
        print(json.dumps({'schema': 'nomad.platform.hold.v1', 'status': 'HOLD',
                          'reason': str(error), 'untrusted_host_fallback': False}), file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
