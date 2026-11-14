"""Frozen v0.16 mission-continuity study: one case per independent invocation.

Output paths must not already exist. The script uses newly generated CodeWorld
fixtures and never updates the archived v0.15 research or mission source.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.codeworld import make_codeworld_tasks
from nomad.mission_runtime import InjectedInterruption, initialize, run, inspect, canonical, digest


def transcript(path:Path)->list[dict]:
    return [json.loads(row) for row in path.read_text().splitlines()]


def projection(rows:list[dict])->list[dict]:
    out=[]
    for row in rows:
        d=row['data'];kind=row['kind']
        if kind=='ATTEMPT_PLANNED':
            out.append({'kind':kind,'attempt':d['attempt'],'candidate':d['candidate_sha256']})
        elif kind=='PUBLIC_RESULT':
            out.append({'kind':kind,'attempt':d['attempt'],'passed':d['passed'],
                        'returncode':d['returncode'],'timed_out':d['timed_out']})
        elif kind=='WITNESS_RESULT':
            out.append({'kind':kind,'attempt':d['attempt'],'supported':d['supported'],
                        'witness_sha256':d['receipt']['receipt_hash']})
        elif kind=='FINAL_RESULT':
            out.append({'kind':kind,'attempt':d['attempt'],'supported':d['supported'],
                        'observed_sha256':d['observed_sha256']})
        elif kind in ('COMPLETED','EXHAUSTED'):
            out.append({'kind':kind,'attempt':d.get('attempt'),
                        'candidate_sha256':d.get('candidate_sha256')})
        else:
            out.append({'kind':kind,'attempt':d.get('attempt')})
    return out


def case(name:str, root:Path, out:Path, *, timeout_s:float=12.0)->dict:
    plan=json.loads((ROOT/'experiments/PLAN_V016.json').read_text())
    freeze=json.loads((ROOT/'experiments/FREEZE_V016.json').read_text())
    for rel, expected in freeze['sha256_by_path'].items():
        if digest((ROOT/rel).read_bytes())!=expected:
            raise ValueError('source changed after holdout registration: '+rel)
    spec=next((x for x in plan['cases'] if x['name']==name),None)
    if not spec:raise ValueError('not a registered release case')
    task=next(t for t in make_codeworld_tasks(spec['seed'],per_family=1)
              if '-'+spec['family']+'-' in t.task_id)
    if out.exists() or root.exists():
        raise FileExistsError('refusing to overwrite original research output')
    root.mkdir(parents=True)
    goal_base=initialize(root/'baseline',task,budget=30)
    goal_restart=initialize(root/'restart',task,budget=30)
    if goal_base!=goal_restart:raise AssertionError('study not matched')
    plain=run(root/'baseline',trusted_fixture=True,timeout_s=timeout_s)
    stopped=False
    try:
        run(root/'restart',trusted_fixture=True,timeout_s=timeout_s,
            interrupt_at=spec['interrupt_at'],interrupt_attempt=spec['interrupt_attempt'])
    except InjectedInterruption:
        stopped=True
    resumed=run(root/'restart',trusted_fixture=True,timeout_s=timeout_s)
    before=transcript(root/'baseline'/'events.jsonl')
    after=transcript(root/'restart'/'events.jsonl')
    structural_match=projection(before)==projection(after)
    source_match=((root/'baseline'/'workspace'/'solution.py').read_bytes()==
                  (root/'restart'/'workspace'/'solution.py').read_bytes())
    complete=(plain['status']=='completed' and resumed['status']=='completed' and
              resumed['committed_sha256']==plain['committed_sha256'])
    no_duplicate_logical_actions=all(sum(row['kind']==kind and row['data'].get('attempt')==i
                 for row in after)<=1 for i in range(1,resumed['attempts']+1)
                 for kind in ('ATTEMPT_PLANNED','PATCH_APPLIED','PUBLIC_RESULT',
                              'WITNESS_RESULT','FINAL_RESULT','PATCH_REVERTED'))
    result={'schema':'nomad.mission.study-case.v1', 'name':name,'seed':spec['seed'],
            'family':spec['family'],'interrupt_at':spec['interrupt_at'],
            'interrupt_attempt':spec['interrupt_attempt'],
            'interruption_observed':stopped, 'task_id':task.task_id,
            'goal':goal_base,
            'source_sha256':digest(task.source.encode()),
            'baseline':plain, 'resumed':resumed,
            'structural_transcript_match':structural_match,
            'committed_source_match':source_match,
            'completed_both':complete,
            'logical_action_uniqueness':no_duplicate_logical_actions,
            'before_projection':projection(before),
            'after_projection':projection(after),
            'baseline_witness_receipts':[{'attempt':r['data']['attempt'],
                 'supported':r['data']['supported'],'receipt':r['data']['receipt']}
                 for r in before if r['kind']=='WITNESS_RESULT'],
            'restart_witness_receipts':[{'attempt':r['data']['attempt'],
                 'supported':r['data']['supported'],'receipt':r['data']['receipt']}
                 for r in after if r['kind']=='WITNESS_RESULT'],
            'before_journal_sha256':digest((root/'baseline'/'events.jsonl').read_bytes()),
            'after_journal_sha256':digest((root/'restart'/'events.jsonl').read_bytes()),
        }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canonical(result))
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name',required=True)
    p.add_argument('--run-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    x=case(a.name,a.run_root,a.output)
    print(json.dumps({k:x[k] for k in ('name','interruption_observed','completed_both',
          'structural_transcript_match','committed_source_match','logical_action_uniqueness')},indent=2))
    if not all((x['interruption_observed'],x['completed_both'],x['structural_transcript_match'],
                x['committed_source_match'],x['logical_action_uniqueness'])):
        raise SystemExit('CASE RESEARCH GATE FAILED')

if __name__=='__main__':main()
