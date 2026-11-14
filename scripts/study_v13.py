"""Separate process: load frozen memory, generate heldout, compare policies."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v13 import study,release_gates,RELEASE_SEEDS,DEV_SEEDS
from nomad.transcend import TransferMemory


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--memory-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--development',action='store_true')
    args=p.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):p.error('refusing to overwrite existing results')
    a=TransferMemory.load(args.memory_dir/'python-memory.json')
    b=TransferMemory.load(args.memory_dir/'javascript-memory.json')
    result=study(a,b,seeds=DEV_SEEDS if args.development else RELEASE_SEEDS)
    gates=release_gates(result,a,b)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for filename,payload in [('STUDY.json',result),('GATES.json',gates)]:
        (args.output_dir/filename).write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':gates['status'],'policies':result['policies'],'gates':gates['checks']},indent=2))
    return 0 if gates['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
