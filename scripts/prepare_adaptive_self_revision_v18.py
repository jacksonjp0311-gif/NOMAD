"""Prepare the existing finite ranking-policy revision; no heldout evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from nomad.recursion import RankingExample, SyntheticTask, prepare_ranking_experiment


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development',type=Path,required=True)
    parser.add_argument('--heldout-sha256',help='independently frozen digest; omission creates development-only nomination')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=18018)
    args=parser.parse_args(argv)
    try:
        if args.development.stat().st_size>1_000_000: raise ValueError('development fixture byte budget exceeded')
        values=json.loads(args.development.read_bytes())
        if not isinstance(values,list) or len(values)>128: raise ValueError('bounded development task list required')
        tasks=[]
        for row in values:
            if not isinstance(row,dict) or set(row)!={'id','candidates'}: raise ValueError('development task fields invalid')
            tasks.append(SyntheticTask(row['id'],tuple(RankingExample(**candidate) for candidate in row['candidates'])))
        report=prepare_ranking_experiment(args.output,tasks,heldout_sha256=args.heldout_sha256,seed=args.seed)
        print(json.dumps(report,indent=2,sort_keys=True)); return 0
    except (ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps({'status':'HOLD','reason':str(error),'authoritative_source_replaced':False}),file=sys.stderr)
        return 3


if __name__=='__main__': raise SystemExit(main())
