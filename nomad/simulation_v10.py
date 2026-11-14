"""Finite, reproducible v0.10 GENESIS program synthesis experiment.

Fixture author holds target oracles, distinct from synthesizer interface. Report
all failures; results are synthetic and NOT external coding benchmarks.
"""
from __future__ import annotations

import hashlib
import copy
import json
import random
from collections import defaultdict
from statistics import mean

from .genesis import (
    IOExample, SynthesisTask, evaluate_task, fixed_v9_reachable, train_prior,
)


def _targets():
    # None of these expressions can be produced by *one* unchanged v0.9
    # operator edit to the supplied x+y source. The generator is evaluator-only.
    return {
        "square_plus": lambda x,y: x*x+y,
        "sum_times_y":lambda x,y:(x+y)*y,
        "times_shift":lambda x,y:x*(y+2),
        "shift_times_y":lambda x,y:(x+1)*y,
        "difference_product":lambda x,y:(x+y)*(x-y),
        "sum_times_x_shift":lambda x,y:(x+y)*(x+1),
        "bilinear_plus":lambda x,y:x*y+2*y,
        "shifted_product":lambda x,y:(x+1)*(y+1),
    }


def make_tasks(seed:int, families:tuple[str,...], *, n_per_family:int=2) -> list[SynthesisTask]:
    r=random.Random(seed)
    all_targets=_targets()
    out=[]
    for f in families:
        oracle=all_targets[f]
        for j in range(n_per_family):
            # Diverse evaluation inputs break trivial interpolation and expose
            # overfitting. No oracle expression or family is provided to search.
            pts = [(x,y) for x in range(-6,8) for y in range(-6,8) if not (x==y==0)]
            r.shuffle(pts)
            # Deliberate zero and sign probes in every PUBLIC split.
            pub=[(-2,3),(0,4),(4,-2),(2,0),(1,1)]
            taken=set(pub)
            pub += [p for p in pts if p not in taken][:7]
            taken=set(pub)
            rest=[p for p in pts if p not in taken]
            challenge=rest[:10]
            final=rest[10:20]
            def examples(pairs):
                return tuple(IOExample(x,y,oracle(x,y)) for x,y in pairs)
            digest=hashlib.sha256(f'{seed}|{f}|{j}'.encode()).hexdigest()[:12]
            out.append(SynthesisTask(f'gen-{digest}', 'def solve(x, y):\n    return x + y\n',
                                     examples(pub), examples(challenge), examples(final), hidden_family=f))
    r.shuffle(out)
    return out


def _summary(records:list[dict]) -> dict:
    return {
        'tasks':len(records),
        'public_solved':sum(r['synthesized'] and r['public_tests'] for r in records),
        'witness_supported':sum(r['witness_supported'] for r in records),
        'final_correct':sum(r['final_correct'] for r in records),
        'false_witness_support':sum(r['witness_supported'] and not r['final_correct'] for r in records),
        'mean_candidate_vectors':mean(r['candidate_evaluations'] for r in records),
        'mean_visible_counterexamples':mean(r['counterexamples'] for r in records),
        'v9_public_reachable':sum(r['v9_reachable'] for r in records),
        'v9_candidate_count':sorted(set(r['v9_candidate_count'] for r in records)),
    }


def run_suite(*, n_train_per_family:int=2,n_eval_per_family:int=2,train_seeds=(313,337,359),eval_seeds=(17011,17047,17101),
              max_eval:int=65000) -> dict:
    training_families=('square_plus','sum_times_y','times_shift','shift_times_y')
    withheld_families=('difference_product','sum_times_x_shift','bilinear_plus','shifted_product')
    train=[]
    eval_tasks=[]
    for seed in train_seeds:
        train.extend(make_tasks(seed,training_families,n_per_family=n_train_per_family))
    for seed in eval_seeds:
        eval_tasks.extend(make_tasks(seed,withheld_families,n_per_family=n_eval_per_family))
    prior,training=train_prior(train,max_nodes=7,max_eval=max_eval,contextual=True)
    global_prior,global_training=train_prior(train,max_nodes=7,max_eval=max_eval,contextual=False)
    # Negative control: same attested skills and global frequencies, but the
    # relation between observed Bitwork states and production priors is shifted.
    shuffled=copy.deepcopy(prior)
    contexts=sorted({c for c,_ in shuffled.operator.context_counts})
    if len(contexts)>1:
        rotate={c:contexts[(i+1)%len(contexts)] for i,c in enumerate(contexts)}
        shuffled.operator.context_counts={
            (rotate[context],family):counts for (context,family),counts in shuffled.operator.context_counts.items()
        }
    modes={'enumerative':None,'global':global_prior,'shuffled_context':shuffled,'bitwork_context':prior}
    results={}
    for name,p in modes.items():
        records=[]
        for task in eval_tasks:
            ev,_=evaluate_task(task,prior=p,max_nodes=7,max_eval=max_eval,actual_tests=False)
            records.append(ev.__dict__)
        results[name]={'summary':_summary(records),'records':records}
    return {
        'schema':'nomad.genesis.synthetic-evaluation.v1',
        'version':'0.10.0',
        'claim_scope':'bounded two-variable integer arithmetic AST synthesis on generated fixtures; no unrestricted coding or AGI',
        'experiment':{'training_families':training_families,'heldout_families':withheld_families,
                      'training_seeds':train_seeds,'evaluation_seeds':eval_seeds,
                      'train_cases':len(train),'evaluation_cases':len(eval_tasks),
                      'max_ast_nodes':7,'max_candidate_vectors_per_task':max_eval,
                      'public_rows':12,'witness_rows':10,'final_rows':10},
        'training':training,'global_training':global_training,
        'learned_prior':prior.snapshot(),
        'policies':results,
    }
