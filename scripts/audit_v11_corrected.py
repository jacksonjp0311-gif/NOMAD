"""Bytecode-disabled independent-process numerical replay of recorded v0.11 interventions.

An audit verifies the frozen synthetic world outputs and release records, but
is not third-party replication. It executes ONLY bundled trusted fixtures.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.causal_atlas import make_atlas_tasks,source_digest,write_world,digest
from nomad.simulation_v11 import INTERVENTION,FAMILIES


CHILD=r'''
import json,importlib,sys
root=sys.argv[1]
sys.path.insert(0,root)
contracts=json.loads(sys.argv[2])
out={}
for c in contracts:
    fn=getattr(importlib.import_module(c['module']),c['function'])
    out[c['key']]=[float(fn(x,y)) for x,y in c['rows']]
print(json.dumps(out,sort_keys=True,allow_nan=False))
'''


def _run_child(root:Path, contracts)->dict:
    data=[{'module':x.module,'function':x.function,'key':x.key,'rows':x.rows} for x in contracts]
    p=subprocess.run([sys.executable,'-I','-B','-c',CHILD,str(root),json.dumps(data)],
                    cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=12)
    if p.returncode!=0:raise RuntimeError('child fixture failed: '+p.stderr[-400:])
    return json.loads(p.stdout)


def audit(study:dict) -> dict:
    issues=[]; compared=0; source_checks=0; receipt_checks=0
    config=study['configuration']
    regenerated=[t for seed in config['heldout_seeds'] for t in make_atlas_tasks(seed,per_family=config['per_family'],families=FAMILIES)]
    expected={t.task_id:t for t in regenerated}
    rows={}
    for rec in study['effect_records']:
        key=(rec['task_id'],rec['contract'])
        if key in rows:issues.append('duplicate record: '+str(key))
        rows[key]=rec
    for task in regenerated:
        src_hash=source_digest(task.files)
        post={**task.files,task.changed_file:INTERVENTION}
        post_hash=source_digest(post)
        source_checks+=1
        with tempfile.TemporaryDirectory(prefix='nomad-atlas-audit-') as d:
            root=Path(d);write_world(root,task.files)
            before=_run_child(root,task.contracts)
            (root/task.changed_file).write_text(INTERVENTION,encoding='utf8')
            after=_run_child(root,task.contracts)
        for contract in task.contracts:
            key=(task.task_id,contract.key)
            record=rows.get(key)
            if record is None:
                issues.append('missing receipt '+str(key));continue
            fields={
                'task_id':task.task_id,'epoch':0,'before_digest':src_hash,
                'after_digest':post_hash,'changed_file':task.changed_file,
                'contract':contract.key,'before':tuple(record['before']),
                'after':tuple(record['after'])}
            if record['source_digest']!=src_hash or record['before_digest']!=src_hash or record['after_digest']!=post_hash:
                issues.append('source digest mismatch '+str(key))
            if record['receipt_digest']!=digest(fields):
                issues.append('receipt mutated '+str(key))
            receipt_checks+=1
            old=before[contract.key];new=after[contract.key]
            if old!=record['before'] or new!=record['after'] or record['changed']!=(old!=new):
                issues.append('separate-process effect mismatch '+str(key))
            compared+=1
    if len(rows)!=len(regenerated)*len(regenerated[0].contracts):
        issues.append('unexpected receipt count')
    return {'schema':'nomad.v011.independent-process-audit.v1',
            'status':'passed' if not issues else 'failed',
            'distinct_repositories':len(regenerated),
            'source_digests_checked':source_checks,
            'distinct_contract_replays':compared,
            'receipt_integrity_checks':receipt_checks,
            'children_per_repository':2,
            'separate_processes':2*len(regenerated),
            'issues':issues}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',default='results/study-v011.json');p.add_argument('--output',default=None)
    a=p.parse_args()
    data=json.loads((ROOT/a.study).read_text())
    result=audit(data)
    if a.output:(ROOT/a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))
    if result['status']!='passed':raise SystemExit(1)
