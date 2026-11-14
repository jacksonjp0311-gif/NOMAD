"""Read-only MNEMONIC audit. Replays held-out effects in fresh Python processes.

This checks recorded execution labels and memory predictions against freshly
constructed synthetic worlds. It is not external replication and uses the
same finite-world generator, not arbitrary repositories.
"""
from __future__ import annotations
import json,subprocess,sys
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.mnemonic import EvidenceMemory
from nomad.simulation_v12 import ACTION


def audit(study_path: Path, memory_path: Path) -> dict:
    study=json.loads(Path(study_path).read_text())
    memory=EvidenceMemory.load(memory_path)
    if not memory.frozen:raise ValueError('unfrozen training memory')
    errors=[]
    count=0
    index={(row['task_id'],row['contract']):row for row in study['case_records']}
    if len(index)!=len(study['case_records']): errors.append('duplicate heldout record')
    for seed in study['configuration']['heldout_seeds']:
        cmd=[sys.executable,str(ROOT/'scripts/audit_one_v12.py'),'--seed',str(seed)]
        result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=40,check=True)
        parsed=json.loads(result.stdout)
        if parsed['seed']!=seed:errors.append('unexpected audit seed')
        for replay in parsed['rows']:
            key=(replay['task_id'],replay['contract'])
            original=index.get(key)
            if original is None:
                errors.append('unregistered contract');continue
            for field in ('features','changed','source_digest','observed_digest'):
                if original[field]!=replay[field]:errors.append(f'{key} mismatch {field}')
            fresh=memory.recall(action_source=ACTION,features=tuple(replay['features']),now_epoch=0,
                                target_task_id=replay['task_id'])
            if fresh.outcome!=original['warm'] or fresh.status!=original['warm_status'] or fresh.support_tasks!=original['warm_support']:
                errors.append(f'{key} memory prediction drift')
            count+=1
    if count!=len(index):errors.append('missing replayed contracts')
    for policy in ('warm','graph','shuffled','pooled','cold'):
        raw=study['case_records']
        classified=[r for r in raw if r[policy]!='abstain']
        score=study['scores'][policy]
        if score['classified']!=len(classified) or score['false_classified'] !=sum((r[policy]=='impact')!=r['changed'] for r in classified):
            errors.append(policy+' scoring inconsistency')
    return {'schema':'nomad.mnemonic.independent-process-replay.v1',
            'status':'passed' if not errors else 'failed',
            'replayed_contracts':count,'subprocess_seeds':len(study['configuration']['heldout_seeds']),
            'memory_event_count':len(memory.events),'errors':errors,
            'boundary':'replayed internal synthetic generator on fresh Python processes; not external replication'}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--study',default='results/study-v012.json')
    parser.add_argument('--memory',default='results/MNEMONIC_MEMORY.json');args=parser.parse_args()
    r=audit(ROOT/args.study, ROOT/args.memory)
    print(json.dumps(r,indent=2))
    raise SystemExit(0 if r['status']=='passed' else 1)
