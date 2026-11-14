"""CLI: durable trusted-fixture coding missions (v0.16 research)."""
import argparse
import json
from pathlib import Path
import sys

from .codeworld import make_codeworld_tasks
from .mission_runtime import (InjectedInterruption, MissionHold, initialize,
                              inspect, run)


def main(argv=None):
    p=argparse.ArgumentParser(description='NOMAD MISSION RUNTIME v0.16 (trusted fixture only)')
    subs=p.add_subparsers(dest='command',required=True)
    a=subs.add_parser('init',help='Generate one explicitly trusted CodeWorld fixture')
    a.add_argument('--root',type=Path,required=True)
    a.add_argument('--seed',type=int,default=9117)
    a.add_argument('--family',choices=['bin','const','cmp','zero','id','neg'],default='bin')
    a.add_argument('--budget',type=int,default=30)
    b=subs.add_parser('run',help='Resume a persistent fixture mission')
    b.add_argument('--root',type=Path,required=True)
    b.add_argument('--trusted-fixture',action='store_true')
    b.add_argument('--interrupt-at', choices=['after_plan','after_patch_write','after_patch_record',
                        'after_public','after_witness','after_final','after_completed',
                        'after_rollback_write','after_rollback_record'])
    b.add_argument('--interrupt-attempt',type=int,default=1)
    b.add_argument('--timeout-s',type=float,default=12.0)
    c=subs.add_parser('status',help='Verify and inspect journal without executing code')
    c.add_argument('--root',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.command == 'init':
            targets=make_codeworld_tasks(args.seed,per_family=1,include_ood=False)
            matches=[t for t in targets if '-'+args.family+'-' in t.task_id]
            if len(matches)!=1:raise ValueError('unexpected fixture selection')
            result=initialize(args.root,matches[0],budget=args.budget)
            result={k:result[k] for k in ('task_id','mission_id','candidate_count','budget')}
        elif args.command == 'run':
            result=run(args.root,trusted_fixture=args.trusted_fixture,
                       timeout_s=args.timeout_s,interrupt_at=args.interrupt_at,
                       interrupt_attempt=args.interrupt_attempt)
        else:
            result=inspect(args.root)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except InjectedInterruption as e:
        print(str(e),file=sys.stderr)
        return 75
    except (MissionHold, ValueError, PermissionError) as e:
        print(f'NOMAD HOLD: {e}',file=sys.stderr)
        return 3


if __name__=='__main__':
    raise SystemExit(main())
