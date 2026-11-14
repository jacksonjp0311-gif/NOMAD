"""Read-only independent study audit: checks sealed case receipts and final code.

Reconstructs the source edit independently from the original CodeWorld fixture;
does not read the saved mission workspace, overwrite study results, or consult
GENESIS's evaluator-only family label to choose a patch.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.codeworld import make_codeworld_tasks
from nomad.mission_runtime import edits_from_source, digest, canonical
from nomad.witness import Witness, WitnessReceipt


def audit(path:Path)->dict:
    root=path.resolve()
    plan=json.loads((ROOT/'experiments/PLAN_V016.json').read_text())
    freeze=json.loads((ROOT/'experiments/FREEZE_V016.json').read_text())
    for rel,exp in freeze['sha256_by_path'].items():
        if digest((ROOT/rel).read_bytes())!=exp:
            raise ValueError('frozen source changed: '+rel)
    names={x['name'] for x in plan['cases']}
    inputs=sorted(root.glob('case-*.json'))
    seen=[]
    attempts=0
    receipts=0
    for p in inputs:
        row=json.loads(p.read_text())
        name=row['name']
        if name not in names or name in seen or p.name!=f'case-{name}.json':
            raise ValueError('case identity mismatch')
        spec=next(x for x in plan['cases'] if x['name']==name)
        if row['seed']!=spec['seed'] or row['family']!=spec['family']:
            raise ValueError('changed release case specification')
        task=next(t for t in make_codeworld_tasks(spec['seed'],per_family=1)
                  if f'-{spec["family"]}-' in t.task_id)
        if row['task_id']!=task.task_id or row['source_sha256']!=digest(task.source.encode()):
            raise ValueError('task source or identity altered')
        if not all(row[k] for k in ('interruption_observed','completed_both',
                'structural_transcript_match','committed_source_match','logical_action_uniqueness')):
            raise ValueError('restart replay or completion not verified')
        if row['before_projection']!=row['after_projection']:
            raise ValueError('resume projection diverged')
        edits=edits_from_source(task.source)
        final=row['baseline']['committed_sha256']
        matching=[ed for ed in edits if ed.sha256==final]
        if len(matching)!=1:
            raise ValueError('cannot reconstruct unique committed transformation')
        selected=matching[0]
        if row['baseline']['attempts']!=selected.ordinal or row['resumed']['attempts']!=selected.ordinal:
            raise ValueError('candidate attempt count contradicts selected operator')
        if len([x for x in row['before_projection'] if x['kind']=='COMPLETED'])!=1:
            raise ValueError('mission did not complete exactly once')
        witness_events=[x for x in row['before_projection'] if x['kind']=='WITNESS_RESULT']
        if row['baseline_witness_receipts']!=row['restart_witness_receipts']:
            raise ValueError('witness receipts changed during recovery')
        for proof in row['baseline_witness_receipts']:
            idx=proof['attempt']
            edit=edits[idx-1]
            receipt=WitnessReceipt(**proof['receipt'])
            if (not receipt.verify_checksum() or
                not Witness('nomad-v016-independent-process').valid_for_context(
                    receipt,task_id=task.task_id,transmission_id=edit.transmission_id,world_epoch=0) or
                receipt.supported != proof['supported']):
                raise ValueError('invalid independent-process witness receipt')
            matching_projection=[x for x in witness_events if x['attempt']==idx]
            if len(matching_projection)!=1 or matching_projection[0]['witness_sha256'] != receipt.receipt_hash:
                raise ValueError('witness event reference mismatch')
        final_events=[x for x in row['before_projection'] if x['kind']=='FINAL_RESULT']
        if not witness_events or not final_events or not final_events[-1]['supported']:
            raise ValueError('missing positive independent consequence evidence')
        # Independent replay via Python's native compiled program, using only
        # heldout final samples supplied by the fixture generator.
        scope={}
        exec(compile(selected.source,'<independent-audit>','exec'),{'__builtins__':{}},scope)
        native_out=[scope['solve'](**ex.inputs) for ex in task.final]
        if any(x!=ex.expected for x,ex in zip(native_out,task.final)):
            raise ValueError('independent final outcome mismatch')
        expected_observation_hash=digest(canonical([float(v) for v in native_out]))
        if final_events[-1]['observed_sha256'] != expected_observation_hash:
            raise ValueError('independent final digest mismatch')
        attempts+=selected.ordinal
        receipts+=len(witness_events)
        seen.append(name)
    if set(seen)!=names:
        raise ValueError('missing preregistered cases')
    return {'schema':'nomad.v0.16.audit.v1','status':'passed',
            'cases':len(seen),'independent_native_final_replays':len(seen),
            'candidate_attempts':attempts,'witness_receipts':receipts,
            'simulated_restart_cases':len(seen),
            'coverage':'trusted synthetic fixtures; not blind external repos or adversarial isolation'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--study-dir',type=Path,default=ROOT/'results/v016')
    a=p.parse_args()
    print(json.dumps(audit(a.study_dir),indent=2))

if __name__=='__main__':main()
