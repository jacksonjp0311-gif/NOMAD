"""Assemble separate-process, seed-scoped witness audits without re-evaluation."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def assemble():
    study_path=ROOT/'results/study-v011-release.json'
    study=json.loads(study_path.read_text())
    seeds=study['configuration']['heldout_seeds']
    all_records={(r['task_id'],r['contract']) for r in study['effect_records']}
    union=set();audits=[];errors=[]
    for seed in seeds:
        fragment=ROOT/f'results/audit_batches/seed-{seed}.json'
        result=ROOT/f'results/audit_batches/seed-{seed}-bound-audit.json'
        d=json.loads(fragment.read_text());a=json.loads(result.read_text())
        if d['configuration']['heldout_seeds'] != [seed] or a['status']!='passed' or a.get('seed')!=seed or a.get('study_fragment_sha256')!=sha(fragment):
            errors.append(f'seed {seed} bad fragment or audit')
        ids={(r['task_id'],r['contract']) for r in d['effect_records']}
        if any(not task.startswith(f'a{seed}-') for task,_ in ids):errors.append(f'seed {seed} wrong case')
        if len(ids)!=a['distinct_contract_replays'] or len(ids)!=len(d['effect_records']):errors.append(f'seed {seed} count')
        if union & ids:errors.append(f'seed {seed} duplicate key')
        union|=ids
        audits.append({'seed':seed,'fragment_sha256':sha(fragment),'audit_sha256':sha(result),
                       'repositories':a['distinct_repositories'],'independent_contract_checks':a['distinct_contract_replays'],
                       'processes':a['separate_processes']})
    if union!=all_records:errors.append('union not identical to recorded study')
    report={'schema':'nomad.v011.batched-independent-audit.v1',
      'status':'passed' if not errors else 'failed',
      'study_sha256':sha(study_path),'source_freeze_sha256':sha(ROOT/'experiments/FREEZE_V011_RELEASE.json'),
      'repositories':sum(x['repositories'] for x in audits),
      'contract_replays':sum(x['independent_contract_checks'] for x in audits),
      'separate_python_processes':sum(x['processes'] for x in audits),
      'batches':audits,'previous_failed_precheck_preserved':(ROOT/'results/AUDIT_V011.json').exists(),
      'issues':errors,
      'scope':'Independent-process replay of program outputs within authored synthetic fixtures; not external researcher replication.'}
    return report

if __name__=='__main__':
    a=assemble();p=ROOT/'results/AUDIT_V011_RELEASE.json'
    p.write_text(json.dumps(a,indent=2,sort_keys=True)+'\n')
    print(json.dumps(a,indent=2))
    if a['status']!='passed':raise SystemExit(1)
