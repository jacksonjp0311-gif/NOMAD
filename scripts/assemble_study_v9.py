"""Assemble independently generated seed receipts without rerunning a solver."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v9 import FROZEN_EVAL_SEEDS, assemble_runs

def main()->int:
    root=ROOT/'results/study-v009'
    runs=[]
    for seed in FROZEN_EVAL_SEEDS:
        path=root/f'seed-{seed}.json'
        if not path.is_file():
            raise SystemExit(f'missing original frozen seed receipt: {path}')
        runs.append(json.loads(path.read_text()))
    report=assemble_runs(runs,FROZEN_EVAL_SEEDS)
    path=ROOT/'results/simulation-v009.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'assembled','file':str(path),'seeds':list(FROZEN_EVAL_SEEDS),
                      'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                      'comparison':report['comparisons'],
                      'integration':report['integration']},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
