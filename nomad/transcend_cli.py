"""Demonstrate cross-language NOMAD synthesis using native runtimes."""
from __future__ import annotations
import argparse,json
from .simulation_v10 import make_tasks
from .genesis import synthesize
from .transcend import render,run_native,witnessed,native_available


def main() -> int:
    parser=argparse.ArgumentParser(description='NOMAD TRANSCEND demonstration on trusted fixtures')
    parser.add_argument('--language',choices=('python','javascript','rust'),default='javascript')
    parser.add_argument('--demo',action='store_true')
    args=parser.parse_args()
    task=make_tasks(1998,('square_plus',),n_per_family=1)[0]
    candidate=synthesize(task).candidate
    if candidate is None:return 1
    receipt,information=witnessed(args.language,task,candidate)
    final=run_native(args.language,candidate,task.final)
    record={'version':'0.13.0','task':task.task_id,'language':args.language,
            'candidate':candidate,'source':render(args.language,candidate),
            'native_available':native_available(args.language),
            'native_status':final.status,'witness_supported':receipt.supported if receipt else None,
            'final_correct':final.status=='passed' and final.values==tuple(e.expected for e in task.final),
            'execution_scope':'bounded trusted arithmetic fixture only'}
    print(json.dumps(record,indent=2))
    return 0 if final.status=='passed' and receipt and receipt.supported else 2
if __name__=='__main__':raise SystemExit(main())
