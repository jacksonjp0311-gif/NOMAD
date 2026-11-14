"""NOMAD v0.17 security boundary and recovery CLI.

Only `sandbox` can run unfamiliar code, and it NEVER selects the host backend.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .archive_guard import extract_checked
from .effects import EffectLedger
from .isolation import IsolationUnavailable, SandboxPolicy, UnsafeWorkspace, run_isolated, sandbox_available
from .mission_runtime import MissionHold


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description='NOMAD PROTECT v0.17: explicit boundaries and evidence')
    sub=p.add_subparsers(dest='action',required=True)
    d=sub.add_parser('doctor',help='Report isolation backend readiness, run no source code')
    d.add_argument('--image',default=None,help='trusted pre-pulled image reference with @sha256')
    s=sub.add_parser('sandbox',help='Run untrusted source tests in digest-pinned Docker ONLY')
    s.add_argument('--source',type=Path,required=True)
    s.add_argument('--image',required=True)
    s.add_argument('--kind',choices=('python-unittest','node-test'),default='python-unittest')
    s.add_argument('--timeout',type=float,default=20)
    a=sub.add_parser('extract',help='Safely extract a bounded ZIP source archive; no code execution')
    a.add_argument('--archive',type=Path,required=True)
    a.add_argument('--destination',type=Path,required=True)
    e=sub.add_parser('effects-status',help='Read the external side-effect ledger; no execution')
    e.add_argument('--root',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.action=='doctor':
            if args.image is not None:SandboxPolicy(image=args.image).validate()
            result={'schema':'nomad.protect.doctor.v1','docker_binary_present':sandbox_available(),
                    'docker_kernel_isolation_tested_here':False,
                    'image_pinned':args.image is not None,
                    'untrusted_host_fallback':False,
                    'ready_for_untrusted_code':False,
                    'explanation':'Docker CLI presence does not verify daemon isolation; run native containment acceptance on deployment host'}
        elif args.action=='sandbox':
            policy=SandboxPolicy(image=args.image,timeout_s=args.timeout)
            command=(['python','-B','-m','unittest','discover','-s','tests','-q']
                     if args.kind=='python-unittest' else ['node','--test'])
            result=run_isolated(args.source,command=command,policy=policy)
        elif args.action=='extract':
            result=extract_checked(args.archive,args.destination)
        else:
            result=EffectLedger(args.root,create=False).snapshot()
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (IsolationUnavailable, UnsafeWorkspace, MissionHold, PermissionError,
            ValueError, OSError) as e:
        print('NOMAD PROTECT HOLD: '+str(e),file=sys.stderr)
        return 3

if __name__=='__main__':
    raise SystemExit(main())
