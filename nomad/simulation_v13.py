"""NOMAD v0.13 TRANSCEND: cross-language *bounded* grammar transfer.

Release studies run native target-language code on public/challenge/final
samples. Trained priors are frozen in distinct processes before evaluating a
held-out language and disjoint expression families. The generator intentionally
shares an arithmetic IR; external/unrestricted transfer is NOT established.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from .genesis import synthesize, fixed_v9_reachable
from .simulation_v10 import make_tasks
from .transcend import (TransferMemory, native_available, run_native,
                        witnessed, shifted_context, render, digest)

TRAIN_FAMILIES=('square_plus','sum_times_y','times_shift','shift_times_y')
HOLDOUT_FAMILIES=('difference_product','sum_times_x_shift','bilinear_plus','shifted_product')
TRAIN_SEEDS={'python':(4211,4241,4283),'javascript':(5219,5249,5297)}
RELEASE_SEEDS={'python':(7211,7213,7229),'javascript':(6211,6217,6221)}
DEV_SEEDS={'python':(811,821),'javascript':(911,923)}
PER_FAMILY=2
MAX_EVAL=65000


def train_language(language: str, seeds: tuple[int,...]) -> tuple[TransferMemory,dict]:
    if not native_available(language):
        raise RuntimeError('no native runtime: '+language)
    mem=TransferMemory()
    records=[]
    for seed in seeds:
        for task in make_tasks(seed, TRAIN_FAMILIES, n_per_family=PER_FAMILY):
            attempt=synthesize(task, max_nodes=7,max_eval=MAX_EVAL)
            if attempt.candidate is None:
                records.append({'task_id':task.task_id,'status':'no_candidate','attempts':attempt.candidates_evaluated})
                continue
            receipt,detail=witnessed(language,task,attempt.candidate)
            final=run_native(language,attempt.candidate,task.final)
            final_valid=final.status=='passed' and final.values==tuple(e.expected for e in task.final)
            is_accepted=receipt is not None and receipt.supported and final_valid
            if is_accepted:
                mem.add(language,task,attempt.candidate,receipt)
            records.append({'task_id':task.task_id,'status':'accepted' if is_accepted else 'refused',
                            'attempts':attempt.candidates_evaluated,'source_lang':language,
                            'challenge_supported':receipt.supported if receipt else False,
                            'final_correct':final_valid,'program_hash':detail['program_sha256']})
    mem.freeze()
    return mem,{'schema':'nomad.transcend.training.v1','language':language,
                'source_seeds':list(seeds),'attempted':len(records),'witnessed':len(mem.events),
                'records':records,'ledger_head':mem.head}


def _evaluate(language: str, task, policy: str, prior) -> dict:
    search=synthesize(task,prior=prior,max_nodes=7,max_eval=MAX_EVAL)
    if search.candidate is None:
        return {'task_id':task.task_id,'language':language,'family_evaluator_only':task.hidden_family,
                'policy':policy,'attempts':search.candidates_evaluated,'candidate':None,
                'final_correct':False,'witness_supported':False,'abstained':search.abstained,
                'context':search.source_context,'native_status':'not_run'}
    receipt,detail=witnessed(language,task,search.candidate)
    final=run_native(language,search.candidate,task.final)
    final_correct=final.status=='passed' and final.values==tuple(e.expected for e in task.final)
    # Full success requires an independent target-language witness and a
    # separate final split; passing only the finite public examples is insufficient.
    return {'task_id':task.task_id,'language':language,'family_evaluator_only':task.hidden_family,
            'policy':policy,'attempts':search.candidates_evaluated,'candidate':search.candidate,
            'source_sha256':detail['program_sha256'],'context':search.source_context,
            'witness_supported':receipt.supported if receipt else False,
            'witness_receipt_sha256':receipt.receipt_hash if receipt else None,
            'final_correct':bool(receipt is not None and receipt.supported and final_correct),
            'native_status':final.status,'abstained':None}


def evaluate_direction(*,source_language:str,target_language:str,memory: TransferMemory,
                       seeds:tuple[int,...]) -> dict:
    if source_language==target_language:raise ValueError('transfer must cross a language boundary')
    if memory.source_languages() != (source_language,):raise ValueError('training language scope invalid')
    if not memory.frozen:raise ValueError('training memory must be frozen')
    if not native_available(target_language):raise RuntimeError('native target runtime unavailable')
    tasks=[task for seed in seeds for task in make_tasks(seed,HOLDOUT_FAMILIES,n_per_family=PER_FAMILY)]
    contextual=memory.prior(contextual=True)
    controls={'cold':None,'global':memory.prior(contextual=False),
              'shuffled_context':shifted_context(contextual), 'bitwork_transfer':contextual}
    result={}
    for mode,prior in controls.items():
        records=[_evaluate(target_language,task,mode,prior) for task in tasks]
        result[mode]={'records':records,'summary':{
            'tasks':len(records),
            'final_correct':sum(r['final_correct'] for r in records),
            'witness_supported':sum(r['witness_supported'] for r in records),
            'false_witness_support':sum(r['witness_supported'] and not r['final_correct'] for r in records),
            'mean_candidate_vectors':round(mean(r['attempts'] for r in records),6),
            'total_candidate_vectors':sum(r['attempts'] for r in records),
            'non_native_results':sum(r['native_status']!='passed' for r in records),
        }}
    cold=result['cold']['summary']['total_candidate_vectors']
    active=result['bitwork_transfer']['summary']['total_candidate_vectors']
    global_cost=result['global']['summary']['total_candidate_vectors']
    return {'source_language':source_language,'heldout_language':target_language,
            'seeds':list(seeds),'heldout_families':list(HOLDOUT_FAMILIES),
            'target_count':len(tasks),'memory_events':len(memory.events),'memory_head':memory.head,
            'policies':result,'savings_vs_cold':(cold-active)/cold if cold else 0.,
            'savings_vs_global':(global_cost-active)/global_cost if global_cost else 0.}


def study(memory_python:TransferMemory,memory_js:TransferMemory,*,
          seeds:dict[str,tuple[int,...]]=RELEASE_SEEDS) -> dict:
    a=evaluate_direction(source_language='python',target_language='javascript',
                         memory=memory_python,seeds=seeds['javascript'])
    b=evaluate_direction(source_language='javascript',target_language='python',
                         memory=memory_js,seeds=seeds['python'])
    directions=[a,b]
    per_policy={}
    for policy in ('cold','global','shuffled_context','bitwork_transfer'):
        cases=[d['policies'][policy]['summary'] for d in directions]
        per_policy[policy]={'tasks':sum(c['tasks'] for c in cases),
                            'final_correct':sum(c['final_correct'] for c in cases),
                            'false_witness_support':sum(c['false_witness_support'] for c in cases),
                            'mean_candidate_vectors':round(sum(c['total_candidate_vectors'] for c in cases)/sum(c['tasks'] for c in cases),6),
                            'total_candidate_vectors':sum(c['total_candidate_vectors'] for c in cases)}
    cold=per_policy['cold']['total_candidate_vectors']
    active=per_policy['bitwork_transfer']['total_candidate_vectors']
    global_cost=per_policy['global']['total_candidate_vectors']
    rust_emission={'status':'not_native_verified','rustc_present':native_available('rust'),
                   'example_source':render('rust','(x*x)+y'),
                   'note':'Rust compilation is a separate optional gate and may be unavailable. It is not counted in primary transfer metrics.'}
    if native_available('rust'):
        sample=make_tasks(821,('square_plus',),n_per_family=1)[0]
        native_rust=run_native('rust','(x*x)+y',sample.public)
        rust_emission={'status':native_rust.status,'rustc_present':True,
                       'example_source':render('rust','(x*x)+y'),
                       'tested_rows':len(sample.public),'reason':native_rust.reason}
    return {'schema':'nomad.transcend.study.v1','version':'0.13.0',
            'claim_scope':'Two native languages, shared bounded integer IR, generated synthetic tasks; Rust compiler optional and excluded from cross-language transfer evidence',
            'training_families':list(TRAIN_FAMILIES),'holdout_families':list(HOLDOUT_FAMILIES),
            'train_seeds':{k:list(v) for k,v in TRAIN_SEEDS.items()},
            'evaluation_seeds':{k:list(v) for k,v in seeds.items()},
            'budgets':{'max_synthesis_vectors_per_case':MAX_EVAL,'node_limit':7,
                       'public_examples':12,'challenge_examples':10,'final_examples':10},
            'directions':directions,'policies':per_policy,
            'overall_savings_vs_cold':(cold-active)/cold if cold else 0.,
            'overall_savings_vs_global':(global_cost-active)/global_cost if global_cost else 0.,
            'rust':rust_emission}


def release_gates(report:dict,trained_py:TransferMemory,trained_js:TransferMemory)->dict:
    policies=report['policies']
    total=policies['bitwork_transfer']['tasks']
    checks={
        'two_native_directions':len(report['directions'])==2 and {d['heldout_language'] for d in report['directions']}=={'python','javascript'},
        'language_disjoint_source':all(d['source_language']!=d['heldout_language'] for d in report['directions']),
        'witnessed_training':len(trained_py.events)>=12 and len(trained_js.events)>=12,
        'frozen_training':trained_py.frozen and trained_js.frozen,
        'no_target_in_memory':trained_py.source_languages()==('python',) and trained_js.source_languages()==('javascript',),
        'all_targets_challenge_correct':policies['bitwork_transfer']['final_correct']==total,
        'controls_correct':all(p['final_correct']==total for p in policies.values()),
        'zero_false_witness':all(p['false_witness_support']==0 for p in policies.values()),
        'context_improves_on_cold':report['overall_savings_vs_cold']>0,
        'context_improves_on_global':report['overall_savings_vs_global']>0,
        'both_directions_better_than_global':all(d['savings_vs_global']>0 for d in report['directions']),
        'native_execution_only':all(all(r['native_status']=='passed' for r in d['policies']['bitwork_transfer']['records']) for d in report['directions']),
        'rust_scope_honest':report['rust']['status'] in ('not_native_verified','passed'),
    }
    return {'schema':'nomad.transcend.gates.v1','status':'passed' if all(checks.values()) else 'hold',
            'checks':checks,'evaluated_tasks':total,'witnessed_training_tasks':len(trained_py.events)+len(trained_js.events)}
