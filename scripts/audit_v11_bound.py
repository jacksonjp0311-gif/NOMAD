"""Bind each independently replayed seed audit to exact source fragment bytes."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.audit_v11_corrected import audit

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True)
    a=p.parse_args()
    src=ROOT/f'results/audit_batches/seed-{a.seed}.json'
    study=json.loads(src.read_text())
    if study['configuration']['heldout_seeds']!=[a.seed]:raise SystemExit('wrong seed')
    result=audit(study)
    result['seed']=a.seed
    result['study_fragment_sha256']=hashlib.sha256(src.read_bytes()).hexdigest()
    result['observed_projection_sha256']=hashlib.sha256(json.dumps([
        [r['task_id'],r['contract'],r['before'],r['after']]
        for r in study['effect_records']],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    dst=ROOT/f'results/audit_batches/seed-{a.seed}-bound-audit.json'
    dst.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'seed':a.seed,'status':result['status'],'checked':result['distinct_contract_replays'],
                      'fragment_sha256':result['study_fragment_sha256']}))
    if result['status']!='passed':raise SystemExit(1)
