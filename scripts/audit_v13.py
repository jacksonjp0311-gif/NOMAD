"""Independent arithmetic re-evaluation and fresh native replay of v0.13.

Does not use the learned ranked search to evaluate a candidate's semantics.
Regenerates each heldout fixture and reinterprets AST with a separate scalar
implementation. Replays the actual native runtimes for TRANSFER policy.
This is independent-code internal auditing, not independent external replication.
"""
from __future__ import annotations
import argparse,ast,hashlib,json,operator,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v10 import make_tasks
from nomad.simulation_v13 import HOLDOUT_FAMILIES,PER_FAMILY
from nomad.transcend import run_native,render,witnessed,TransferMemory,digest


BINARY={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul}


def scalar(expr:str,x:int,y:int)->int:
    def walk(node):
        if isinstance(node,ast.Name) and node.id in ('x','y'):
            return {'x':x,'y':y}[node.id]
        if isinstance(node,ast.Constant) and type(node.value) is int and -3<=node.value<=3:
            return node.value
        if isinstance(node,ast.BinOp) and type(node.op) in BINARY:
            return BINARY[type(node.op)](walk(node.left),walk(node.right))
        raise ValueError('unsupported AST')
    return walk(ast.parse(expr,mode='eval').body)


def audit(study_path:Path,python_memory:Path,js_memory:Path)->dict:
    study=json.loads(study_path.read_text())
    mems={'python':TransferMemory.load(python_memory),
          'javascript':TransferMemory.load(js_memory)}
    errors=[];scalar_cases=0;scalar_rows=0;native_cases=0;native_rows=0;receipts=0
    if study.get('schema')!='nomad.transcend.study.v1':errors.append('wrong study schema')
    for direction in study['directions']:
        source_lang=direction['source_language'];target_lang=direction['heldout_language']
        memory=mems[source_lang]
        if source_lang==target_lang or memory.source_languages()!=(source_lang,) or direction['memory_head']!=memory.head:
            errors.append('wrong frozen source memory scope '+source_lang)
        cases={task.task_id:task for seed in direction['seeds']
               for task in make_tasks(seed,HOLDOUT_FAMILIES,n_per_family=PER_FAMILY)}
        if len(cases)!=direction['target_count']:
            errors.append('missing or colliding regenerated tasks')
        for policy,data in direction['policies'].items():
            for record in data['records']:
                task=cases.get(record['task_id'])
                if task is None:
                    errors.append('unregistered task '+record['task_id']);continue
                if record['policy']!=policy or record['language']!=target_lang or record['family_evaluator_only']!=task.hidden_family:
                    errors.append('task metadata mismatch '+record['task_id'])
                candidate=record.get('candidate')
                if candidate is None:
                    if record['final_correct'] or record['witness_supported']:
                        errors.append('successful abstention')
                    continue
                scalar_cases+=1
                for split_name in ('public','challenge','final'):
                    rows=getattr(task,split_name)
                    got=tuple(scalar(candidate,e.x,e.y) for e in rows)
                    scalar_rows+=len(rows)
                    if (got==tuple(e.expected for e in rows))!=record['final_correct']:
                        errors.append('independent scalar mismatch '+record['task_id']+'/'+policy+'/'+split_name)
                src_hash=hashlib.sha256(render(target_lang,candidate).encode()).hexdigest()
                if src_hash!=record['source_sha256']:
                    errors.append('source digest mismatch '+record['task_id']+'/'+policy)
                if policy=='bitwork_transfer':
                    result=run_native(target_lang,candidate,task.final)
                    witness,info=witnessed(target_lang,task,candidate)
                    native_cases+=1;native_rows+=len(task.public)+len(task.challenge)+len(task.final)
                    if (result.status!='passed' or result.values!=tuple(e.expected for e in task.final)
                        or witness is None or not witness.supported
                        or not witness.verify_checksum()
                        or witness.receipt_hash!=record['witness_receipt_sha256']):
                        errors.append('native or WITNESS mismatch '+record['task_id'])
                    else:receipts+=1
    return {'schema':'nomad.transcend.audit.v1',
            'status':'passed' if not errors else 'failed',
            'independent_scalar_candidates':scalar_cases,'independent_scalar_rows':scalar_rows,
            'fresh_native_transfer_cases':native_cases,'fresh_native_rows':native_rows,
            'matching_witness_receipts':receipts,
            'study_sha256':hashlib.sha256(study_path.read_bytes()).hexdigest(),
            'memory_heads':{k:v.head for k,v in mems.items()},
            'errors':errors}


def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True)
    p.add_argument('--memory-dir',type=Path,required=True)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    report=audit(args.study,args.memory_dir/'python-memory.json',args.memory_dir/'javascript-memory.json')
    if args.output:
        if args.output.exists():p.error('refusing to overwrite existing audit')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
