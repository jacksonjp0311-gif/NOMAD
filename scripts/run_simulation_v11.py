"""NOMAD v0.11 reproducible study runner."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v11 import run_study

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default=None)
    p.add_argument('--no-repairs',action='store_true');p.add_argument('--integration-cases',type=int,default=4)
    p.add_argument('--disk-tests',action='store_true')
    a=p.parse_args()
    data=run_study(include_repairs=not a.no_repairs,integration_cases=a.integration_cases,actual_disk_tests=a.disk_tests)
    if a.output:
        dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'configuration':data['configuration'],'impact_metrics':data['impact_metrics'],
        'repairs':{k:{x:v for x,v in r.items() if x!='case_receipts'} for k,r in data['repairs'].items()}},indent=2))
