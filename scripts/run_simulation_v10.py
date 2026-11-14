"""Re-run frozen GENESIS study; write to an explicitly chosen path only."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.simulation_v10 import run_suite
p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,help='Fresh destination; no overwrite of frozen canonical study')
args=p.parse_args()
result=run_suite()
if args.output:
    if args.output.exists():raise SystemExit('Refusing to overwrite existing result: '+str(args.output))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
print(json.dumps({k:v['summary'] for k,v in result['policies'].items()},indent=2))
