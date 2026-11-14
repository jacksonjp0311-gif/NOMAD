"""Registered, synthetic CAUSAL ATLAS experiments (no external benchmark claim)."""
from __future__ import annotations

import json
import random
from collections import Counter
from statistics import mean

from .causal_atlas import (
    AtlasLearner, SymbolGraph, make_atlas_tasks, observe_intervention,
    train_impact_model, score_predictions, repair_atlas_task, source_digest,
)

TRAIN_SEEDS=(907,947)
HELDOUT_SEEDS=(4321,4357,4397)
FAMILIES=('square_plus','sum_times_y','difference_product','shifted_product')
INTERVENTION='def solve(x, y):\n    return x*y+y\n'


def run_study(*, train_seeds=TRAIN_SEEDS, eval_seeds=HELDOUT_SEEDS, per_family=2,
              integration_cases=4, include_repairs=True, actual_disk_tests=False):
    training=[t for seed in train_seeds for t in make_atlas_tasks(seed,per_family=per_family,families=FAMILIES)]
    heldout=[t for seed in eval_seeds for t in make_atlas_tasks(seed,per_family=per_family,families=FAMILIES)]
    model=train_impact_model(training,intervention=INTERVENTION)

    # Negative control: preserve evidence values, but destroy which observed
    # structural signature each piece of evidence belonged to. Not a legitimate
    # training method; intentionally broken association for causal attribution.
    all_training=[]
    for task in training:
        graph=SymbolGraph(task.files)
        for contract,rec in zip(task.contracts,observe_intervention(task,INTERVENTION)):
            if graph.features(contract,task.changed_file)!=('uncertain',):
                all_training.append((graph.features(contract,task.changed_file),rec))
    permuted=[features for features,_ in all_training]
    random.Random(4441).shuffle(permuted)
    negative=AtlasLearner()
    for features, (_,receipt) in zip(permuted, all_training):
        negative.observe(features,receipt)

    preds={'import_graph':[],'direct_call_graph':[],'learned_atlas':[],'shuffled_evidence':[]}
    actual=[]; records=[]
    for task in heldout:
        graph=SymbolGraph(task.files)
        observed=observe_intervention(task,INTERVENTION)
        for contract,receipt in zip(task.contracts,observed):
            features=graph.features(contract,task.changed_file)
            reachable,dist,uncertain,_=graph.reachable(contract.key, f'{task.changed_file[:-3]}.solve')
            pred,prob,n=model.predict(features)
            neg,neg_prob,neg_n=negative.predict(features)
            actual.append(receipt.changed)
            preds['import_graph'].append(graph.imported_reachable(contract.module,task.changed_file[:-3]))
            preds['direct_call_graph'].append(None if uncertain else reachable)
            preds['learned_atlas'].append(None if pred=='abstain' else pred=='impact')
            preds['shuffled_evidence'].append(None if neg=='abstain' else neg=='impact')
            records.append({'task_id':task.task_id,'contract':contract.key,'source_digest':source_digest(task.files),
                            'before_digest':receipt.before_digest,'after_digest':receipt.after_digest,
                            'receipt_digest':receipt.receipt_digest,'before':list(receipt.before),'after':list(receipt.after),
                            'changed':receipt.changed,'features':list(features),
                            'learned_prediction':pred,'learned_probability':prob,'learned_support':n,
                            'negative_prediction':neg,'negative_probability':neg_prob,'negative_support':neg_n})
    metrics={name:score_predictions(actual,arr) for name,arr in preds.items()}

    repairs={}
    if include_repairs:
        # Fresh held-out repos; no evaluator fault-file label passed to either
        # policy. GENESIS receives PUBLIC input/output pairs only. The existing
        # v0.10 synthesizer and WITNESS are reused unmodified.
        tasks=heldout[:integration_cases]
        for policy in ('flat','graph'):
            series=[repair_atlas_task(t,priority=policy,actual_tests=actual_disk_tests) for t in tasks]
            repairs[policy]={
                'cases':len(series),'solved':sum(x['solved'] for x in series),
                'final_correct':sum(x['final_correct'] for x in series),
                'witness_supported':sum(x['witness_supported'] for x in series),
                'actual_fault_file_repaired':sum(x['chosen_file_is_actual_source'] for x in series),
                'total_file_visits':sum(x['files_visited'] for x in series),
                'mean_file_visits':mean(x['files_visited'] for x in series),
                'total_candidate_vectors':sum(x['candidate_vectors'] for x in series),
                'case_receipts':series,
            }
    return {
        'schema':'nomad.v011.causal-atlas.synthetic-study.v1',
        'version':'0.11.0',
        'scope':'generated Python import/call graph with witnessed interventions and bounded GENESIS synthesis; no external repository or real-world causal identification',
        'configuration':{'training_seeds':list(train_seeds),'heldout_seeds':list(eval_seeds),
                         'per_family':per_family,'training_worlds':len(training),
                         'heldout_worlds':len(heldout),'contract_samples':len(records),
                         'integration_cases':integration_cases if include_repairs else 0,
                         'intervention_sha256':__import__('hashlib').sha256(INTERVENTION.encode()).hexdigest()},
        'impact_model':model.snapshot(),
        'negative_control':negative.snapshot(),
        'impact_metrics':metrics,
        'effect_records':records,
        'repairs':repairs,
    }
