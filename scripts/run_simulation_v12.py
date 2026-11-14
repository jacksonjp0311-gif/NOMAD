"""Run registered v0.12 experiment in a new output path (never overwrite evidence)."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v12 import run_study

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    p.add_argument('--memory-file')
    p.add_argument('--heldout-seeds',nargs='+',type=int)
    args=p.parse_args()
    dest=Path(args.output)
    if not dest.is_absolute():dest=ROOT/dest
    if dest.exists():raise SystemExit('Refusing to overwrite an existing study')
    kwargs={}
    if args.memory_file:kwargs["memory_file"]=ROOT/args.memory_file
    if args.heldout_seeds:kwargs["holdout_seeds"]=tuple(args.heldout_seeds)
    result=run_study(**kwargs)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'scores':result['scores'],'drift':result['drift'],'saved_study':str(dest)},indent=2))
