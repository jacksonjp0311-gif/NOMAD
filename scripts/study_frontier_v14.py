"""Reproducible offline external-source mutation study, not SWE-bench.

All defects below are injected by EVALUATOR into independently authored upstream
code. The repair policy gets only a disposable mutated source tree and a public
test selector, never these mutation definitions. We do not claim real upstream
issues or independent general coding ability.
"""
from __future__ import annotations
from dataclasses import dataclass
import argparse, dataclasses, hashlib, json, os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys, tempfile
if __package__ in (None,''):
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nomad.frontier import (Prior,repair,witness_and_record,clone_frozen,run_tests,digest,
                           verify_witness)

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'external_sources'
@dataclass(frozen=True)
class Task:
    id:str
    project:str
    original:str
    corrupted:str
    selector:str
    split:str='release'

TASKS=(
    Task('affine-almost','affine','if abs(self[i] - other[i]) >= precision:',
         'if abs(self[i] - other[i]) <= precision:','almost_equals','train'),
    Task('affine-rectilinear','affine','abs(a) < self.precision and abs(e) < self.precision',
         'abs(a) > self.precision and abs(e) < self.precision','is_rectilinear','release'),
    Task('affine-vector','affine','sa * oa + sb * od',
         'sa * oa - sb * od','mul_transform','release'),
    Task('catalogue-contains','catalogue','return has_entry_point or namespace in REGISTRY',
         'return has_entry_point and namespace in REGISTRY','registry_call or registry_get_set','train'),
    Task('catalogue-names','catalogue','len(self.namespace) == len(keys) - 1 and all(',
         'len(self.namespace) != len(keys) - 1 and all(',
         'create_single_namespace or create_multi_namespace','release'),
    Task('confection-merge','confection','elif key not in config:',
         'elif key in config:','deep_merge','release'),
)

def prepare(task:Task, tmp:Path)->tuple[Path,str]:
    repo=tmp/'repo'
    clone_frozen(FROZEN,task.project,repo)
    p=repo/task.project/'__init__.py'
    original=p.read_text()
    if original.count(task.original)!=1:
        raise RuntimeError(f'mutation marker ambiguous ({original.count(task.original)}): {task.id}')
    corrupted=original.replace(task.original,task.corrupted,1)
    p.write_text(corrupted)
    return repo,corrupted


def case(task:Task,prior:Prior|None,budget:int,*,timeout_s:float=5.0)->dict:
    import threading
    tic=time.monotonic()
    print(f'START {task.id} {"learned" if prior else "cold"}',file=sys.stderr,flush=True)
    with tempfile.TemporaryDirectory(prefix='nomad-frontier-') as td:
        repo,source=prepare(task,Path(td))
        result,bits,candidate=repair(workspace=repo,project=task.project,
                                     test_selector=task.selector,prior=prior,
                                     budget=budget,timeout_s=timeout_s,task_id=task.id)
        witness=witness_and_record(repo,task.project,candidate,source,timeout_s=timeout_s)
        exact_restoration=(candidate is not None and digest(candidate.render(source)) == digest((FROZEN/task.project/task.project/'__init__.py').read_text(encoding='utf-8')))
        print(f'END {task.id} {"learned" if prior else "cold"}: {result.candidate_attempts} attempts in {time.monotonic()-tic:.1f}s',file=sys.stderr,flush=True)
        return {'id':task.id,'project':task.project,'split':task.split,
                'policy':result.policy,'initial_public_failed':not result.initial_public['passed'],
                'attempts':result.candidate_attempts,'budget':budget,
                'selected':result.selected,'public_repaired':result.repaired,
                'witness':witness,'witness_valid':verify_witness(witness) if candidate else False,
                'evaluator_exact_original_restoration':exact_restoration,
                'bitwork_signature':bits,'trace':result.trace,
                'failure_reason':result.abstention,'context_key':'no language/repo name in prior key'} ,candidate


def run(budget:int=36,groups=('train','release')) ->dict:
    # Train only on successfully witnessed training cases. No release holdout outcomes
    # are accessed until after this prior is frozen; later results never update it.
    train_tasks=[t for t in TASKS if t.split=='train']
    with ThreadPoolExecutor(max_workers=2) as pool:
        train_rows=list(pool.map(lambda task:case(task,None,budget),train_tasks))
    train=[];prior=Prior()
    for rec,c in train_rows:
        train.append(rec)
        if c and rec['witness'].get('supported'):
            prior.observe(rec['bitwork_signature'],c,True)
    frozen_prior=prior.snapshot()
    release_tasks=[t for t in TASKS if t.split=='release']
    jobs=[(task,policy) for task in release_tasks for policy in ('cold','learned')]
    def evaluate(job):
        task,policy=job
        mem=Prior.load(frozen_prior) if policy=='learned' else None
        rec,_=case(task,mem,budget)
        return rec
    with ThreadPoolExecutor(max_workers=4) as pool:
        evaluated=list(pool.map(evaluate,jobs))
    control=[r for r in evaluated if r['policy']=='cold']
    learned=[r for r in evaluated if r['policy']=='learned']
    def summary(rows):
        return {'tasks':len(rows),'public_repaired':sum(r['public_repaired'] for r in rows),
                'witnessed_repairs':sum(r['witness'].get('supported',False) for r in rows),
                'exact_restorations':sum(r['evaluator_exact_original_restoration'] for r in rows),
                'attempts_all':sum(r['attempts'] for r in rows),
                'mean_attempts':round(sum(r['attempts'] for r in rows)/len(rows),3) if rows else None}
    return {'schema':'nomad.frontier.study.v1',
            'scope':'evaluator-injected single-token defects in independently authored packaged source; NOT authentic upstream bug reports',
            'task_ids':[t.id for t in TASKS], 'budget_per_task':budget,
            'training':train,'frozen_prior':frozen_prior,'cold':control,'transferred':learned,
            'training_summary':summary(train),'cold_summary':summary(control),'transferred_summary':summary(learned),
            'rust':'NOT_TESTED: rustc absent',
            'external_issue_gate':'HOLD: authentic unrelated issues and true unseen repositories not evaluated',
            'source_snapshots':[json.loads((FROZEN/(p+'.manifest.json')).read_text()) for p in ('affine','catalogue','confection')]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--budget',type=int,default=36)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--single',type=str)
    args=parser.parse_args()
    if args.single:
        task=next(t for t in TASKS if t.id==args.single)
        row,_=case(task,None,args.budget)
        print(json.dumps(row,indent=2))
        return
    result=run(args.budget)
    if args.output:
        if args.output.exists():raise SystemExit('refusing to overwrite existing frozen result')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k.endswith('summary') or k in ('scope','external_issue_gate','rust')},indent=2))
if __name__=='__main__':main()
