"""NOMAD v0.11 post-amendment frozen evaluation, new disjoint seeds."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v11 import run_study

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='results/study-v011-release.json');p.add_argument('--disk-tests',action='store_true')
    a=p.parse_args()
    study=run_study(eval_seeds=(5513,5563,5611),actual_disk_tests=a.disk_tests)
    path=ROOT/a.output;path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(study,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'configuration':study['configuration'],'metrics':study['impact_metrics'],
       'repair_summary':{k:{q:v for q,v in row.items() if q!='case_receipts'} for k,row in study['repairs'].items()}},indent=2))
