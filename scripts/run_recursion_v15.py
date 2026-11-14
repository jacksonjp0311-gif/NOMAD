"""NOMAD v0.15: reproducible, conservative research evaluation.

All task labels are marked retrospective or synthetic. No external transfer or
production self-modification claim is issued by this script.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.recursion import (EvidenceScopedPrior,RankingExample,SyntheticTask,
                             synthesize_ranking_source,assess_candidate,stable_hash)
from nomad.frontier import order_candidates,candidates,public_test_clues,verify_witness
from nomad.native_bitwork import shadow_study, checksum
from scripts.study_frontier_v14 import TASKS,prepare,FROZEN
import tempfile


def toy_tasks(seed:int,number:int,kind:str)->list[SyntheticTask]:
    rng=random.Random(seed);out=[]
    for i in range(number):
        # Artificial construction for evaluating source-patch gating only.
        # No claim of transfer to actual repositories.
        rows=[]
        for j in range(5):
            correct=(j==4)
            if kind=='favorable':
                sem=(2 if correct else 4)
                prior=(5 if correct else 0)
            elif kind=='adversarial':
                sem=(5 if correct else 1)
                prior=(0 if correct else 5)
            else:raise ValueError(kind)
            rows.append(RankingExample(semantic=sem,prior=prior,
                                       line=(rng.randint(1,10000)*10+j),is_correct=correct))
        out.append(SyntheticTask(f'{seed}-{i}',tuple(rows)))
    return out


def eligible_prior_study(study:dict)->tuple[dict,EvidenceScopedPrior]:
    prior=EvidenceScopedPrior(min_support=3)
    admitted=[]
    for rec in study['training']:
        if rec['selected'] and rec['witness'].get('supported'):
            admitted.append(prior.admit(bits=rec['bitwork_signature'],
                                        family=rec['selected']['family'],task_id=rec['id'],
                                        expected_source_sha256=rec['selected']['candidate_sha256'],
                                        project=rec['project'],receipt=rec['witness'],
                                        independently_observed=True))
    # Deliberately inspect the previously known false-positive repair. It is
    # training feedback for v0.15, not an independently unseen holdout.
    for rec in study['transferred']:
        if rec['selected'] and rec['witness'].get('supported') is False and verify_witness(rec['witness']):
            prior.admit(bits=rec['bitwork_signature'],family=rec['selected']['family'],
                        task_id=rec['id'],expected_source_sha256=rec['selected']['candidate_sha256'],
                        project=rec['project'],receipt=rec['witness'],independently_observed=True)
    source_match=[]
    for task in (t for t in TASKS if t.split=='release'):
        with tempfile.TemporaryDirectory(prefix='nomad-v15-ranking-') as td:
            workspace,corrupted=prepare(task,Path(td))
            clues=public_test_clues(workspace/task.project/'tests',task.selector)
            all_candidates=candidates(corrupted,f'{task.project}/__init__.py',task.selector,clues)
            old_row=next(x for x in study['cold'] if x['id']==task.id)
            got_cold=order_candidates(all_candidates,old_row['bitwork_signature'],None)
            got_gated=order_candidates(all_candidates,old_row['bitwork_signature'],prior)
            eq=[(x.start,x.before,x.after) for x in got_cold]==[(x.start,x.before,x.after) for x in got_gated]
            source_match.append({'task_id':task.id,'ranking_same_as_cold':eq,
                                 'candidates':len(all_candidates)})
    rec={'schema':'nomad.recursion.external-prior-gate.v1',
         'study_scope':'retrospective reanalysis of previously seen v0.14 tasks; NOT a new blind external benchmark',
         'training_witnessed_task_ids':[r['id'] for r in study['training'] if r['witness'].get('supported')],
         'admitted_training_receipts':sum(admitted),
         'required_distinct_witnessed_task_ids_per_signature':prior.min_support,
         'eligible_keys':sum(prior.score(int(k.split(':',1)[0]),type('C',(),{'family':k.split(':',1)[1]})())>0 for k in prior.positive),
         'contested_keys':sorted(prior.contested),
         'ranking_comparisons':source_match,
         'all_match_cold':all(x['ranking_same_as_cold'] for x in source_match),
         'previous_v14_transferred_witnessed':study['transferred_summary']['witnessed_repairs'],
         'previous_v14_cold_witnessed':study['cold_summary']['witnessed_repairs'],
         'new_blind_accepted_repairs':'NOT_TESTED',
         'witness_status':'integrity and scoped compatibility; not cryptographic authentication'}
    return rec,prior


def run_all()->dict:
    original=json.loads((ROOT/'results/FRONTIER_STUDY_V014.json').read_text(encoding='utf-8'))
    retro,prior=eligible_prior_study(original)
    native=shadow_study(original['training']+original['cold'])
    base=synthesize_ranking_source('cold')
    candidate=synthesize_ranking_source('prior_first')
    favorable=assess_candidate(base_source=base,candidate_source=candidate,
        dev=toy_tasks(5001,32,'favorable'),heldout=toy_tasks(7001,32,'favorable'))
    shift=assess_candidate(base_source=base,candidate_source=candidate,
        dev=toy_tasks(5001,32,'favorable'),heldout=toy_tasks(8001,32,'adversarial'))
    accepted=[]
    for k, result in [('friendly_toy',favorable),('distribution_shift_toy',shift)]:
        accepted.append({'case':k,**result})
    return {'schema':'nomad.recursion.v0.15.study.v1','version':'0.15.0',
            'predecessor_archive_sha256':checksum(ROOT/'baseline/NOMAD-v0.14.0.zip'),
            'bgr_runtime_archive_sha256':checksum(ROOT/'vendor/BGR-v1.4.0-runtime.zip'),
            'research_states':{'native_bgr_import':'CONNECTED',
                               'native_bgr_real_task_advantage':'HOLD',
                               'external_witnessed_transfer':'HOLD',
                               'self_revision_safety':'CANDIDATE_ONLY',
                               'production_readiness':'HOLD'},
            'external_retro':retro,
            'prior_snapshot':prior.snapshot(),
            'native_bitwork':native,
            'self_revision_lab':accepted,
            'interpretation':'Self-revision works as pure AST candidate synthesis and evidence-gated evaluation; no general autonomous self-improvement established.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    result=run_all()
    if args.output:
        if args.output.exists():raise SystemExit('refusing overwrite')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'native_bitwork':{k:v for k,v in result['native_bitwork'].items() if k!='trace'},
                      'external_retro':{k:v for k,v in result['external_retro'].items() if k not in ('ranking_comparisons','contested_keys')},
                      'lab':[{'case':r['case'],'improved':r['improved_in_bounded_lab'],
                              'promotion':r['production_promotion']} for r in result['self_revision_lab']]},indent=2))

if __name__=='__main__':main()
