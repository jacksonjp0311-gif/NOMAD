"""Emit a data-only computation-config nomination from validated development."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.recursion import prepare_computation_experiment


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development',type=Path,required=True)
    parser.add_argument('--future-plan-sha256',help='optional independently frozen digest; no plan or heldout bytes are opened')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        report=prepare_computation_experiment(args.output,args.development,future_plan_sha256=args.future_plan_sha256)
        print(json.dumps({'status':report['status'],'nominated_profile':report['nominated_profile'],
            'development_objective_improved':report['development_objective_improved'],
            'self_improvement_advantage':report['self_improvement_advantage'],'receipt_sha256':report['receipt_sha256']}))
        return 0
    except (ValueError,TypeError,KeyError,OSError,RecursionError) as error:
        print(json.dumps({'status':'HOLD','reason':str(error),'authoritative_source_replaced':False}),file=sys.stderr)
        return 3


if __name__=='__main__':raise SystemExit(main())
