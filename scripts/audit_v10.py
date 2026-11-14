"""Independent finite-domain result audit for the frozen GENESIS study.

Intentionally does not import GENESIS's evaluator, expression enumerator,
ranking policy, WITNESS comparison or precomputed candidate outputs.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Mapping

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.simulation_v10 import make_tasks


def ref_eval(node:ast.AST, x:int,y:int) -> int:
    if isinstance(node,ast.Constant) and type(node.value) is int and abs(node.value)<=100:
        return node.value
    if isinstance(node,ast.Name) and node.id in ('x','y'):
        return {'x':x,'y':y}[node.id]
    if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult)):
        a=ref_eval(node.left,x,y)
        b=ref_eval(node.right,x,y)
        if isinstance(node.op,ast.Add): return a+b
        if isinstance(node.op,ast.Sub): return a-b
        return a*b
    raise ValueError('unsupported expression in reference audit')


def independent_observations(candidate: str, rows) -> tuple[int,...]:
    tree=ast.parse(candidate,mode='eval')
    return tuple(ref_eval(tree.body,e.x,e.y) for e in rows)


def audit(doc:dict) -> dict:
    settings=doc['experiment']
    eval_tasks=[]
    for seed in settings['evaluation_seeds']:
        eval_tasks.extend(make_tasks(seed,tuple(settings['heldout_families']),
                                    n_per_family=settings['evaluation_cases']//(len(settings['evaluation_seeds'])*len(settings['heldout_families']))))
    by_id={t.task_id:t for t in eval_tasks}
    if len(by_id)!=len(eval_tasks): raise AssertionError('duplicate generated IDs')
    policies=doc['policies']
    checked=0
    public_correct=0
    witness_correct=0
    final_correct=0
    false_claims=0
    all_baseline_unreachable=True
    limits_satisfied=True
    for name, p in policies.items():
        records=p['records']
        if len(records)!=len(by_id) or {r['task_id'] for r in records}!=set(by_id):
            raise AssertionError(f'missing or extra tasks in {name}')
        for record in records:
            task=by_id[record['task_id']]
            if record['family']!=task.hidden_family:
                raise AssertionError('source family mismatch')
            if record['candidate_evaluations']>settings['max_candidate_vectors_per_task']:
                limits_satisfied=False
            text=record['candidate']
            if text is None:
                if record['witness_supported'] or record['final_correct']:
                    raise AssertionError('unsupported candidate claimed certified')
                continue
            checked+=1
            p_ok=independent_observations(text,task.public)==tuple(e.expected for e in task.public)
            w_ok=independent_observations(text,task.challenge)==tuple(e.expected for e in task.challenge)
            f_ok=independent_observations(text,task.final)==tuple(e.expected for e in task.final)
            if p_ok: public_correct+=1
            if w_ok and p_ok: witness_correct+=1
            if f_ok: final_correct+=1
            if (p_ok,w_ok and p_ok,f_ok)!=(record['public_tests'],record['witness_supported'],record['final_correct']):
                false_claims+=1
            if record['v9_reachable']: all_baseline_unreachable=False
    result={
      'schema':'nomad.genesis.independent-audit.v1',
      'policies_checked':list(policies),
      'heldout_worlds':len(by_id),
      'candidate_programs_recomputed':checked,
      'public_correct':public_correct,
      'challenge_correct':witness_correct,
      'final_correct':final_correct,
      'result_disagreements':false_claims,
      'old_v9_fixed_reachable':not all_baseline_unreachable,
      'candidate_budgets_respected':limits_satisfied,
      'status':'passed' if false_claims==0 and all_baseline_unreachable and limits_satisfied else 'failed',
      'limitations':'oracle generator belongs to same experimental package; independent interpretation of candidate syntax, not external validation',
    }
    return result


def main() -> None:
    path=ROOT/'results'/'study-v010.json'
    result=audit(json.loads(path.read_text()))
    print(json.dumps(result,indent=2))
    if result['status']!='passed': raise SystemExit(1)

if __name__=='__main__':main()
