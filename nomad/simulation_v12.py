"""Frozen MNEMONIC study: prediction transfer after a process-level memory restart.

Generated synthetic, pure Python modules only. Structural signatures are
provided by v0.11; no claim of arbitrary causal discovery, external validation,
or total end-to-end CPU savings. Final WITNESS remains mandatory.
"""
from __future__ import annotations

import hashlib
import json
import random
import tempfile
from collections import Counter
from pathlib import Path
from statistics import mean

from .causal_atlas import (AtlasTask, SymbolGraph, make_atlas_tasks,
                           observe_intervention)
from .mnemonic import EvidenceMemory, Prediction, digest, action_digest

ACTION = 'def solve(x, y):\n    return x * y + y\n'
TRAIN_SEEDS = (17011,17047,17123,17183)
CAL_SEEDS = (18011,)
HOLDOUT_SEEDS = (19011,19057,19121,19181,19231)


def tasks(seeds: tuple[int,...]) -> list[AtlasTask]:
    return [t for seed in seeds for t in make_atlas_tasks(seed, per_family=1)]


def fit_memory(training: list[AtlasTask]) -> EvidenceMemory:
    memory = EvidenceMemory(ttl_epochs=4,min_tasks=3)
    for task in training:
        graph = SymbolGraph(task.files)
        observed = observe_intervention(task, ACTION)
        for contract,receipt in zip(task.contracts,observed):
            # The learner receives instrumented local observations on training
            # tasks only, not the held-out evaluator labels.
            memory.record(task=task, contract=contract.key, action_source=ACTION,
                          receipt=receipt, capture_epoch=0)
    memory.freeze()
    return memory


def _score_one(rows: list[dict]) -> dict:
    decided = [r for r in rows if r['prediction'] != 'abstain']
    return {
        'total': len(rows), 'classified': len(decided),
        'abstained': len(rows)-len(decided),
        'correct_classified': sum((r['prediction']=='impact')==r['changed'] for r in decided),
        'false_classified': sum((r['prediction']=='impact')!=r['changed'] for r in decided),
        'coverage': len(decided)/len(rows) if rows else 0,
        'accuracy_when_classified': sum((r['prediction']=='impact')==r['changed'] for r in decided)/len(decided) if decided else None,
    }


def _safe_shift(task: AtlasTask) -> tuple[AtlasTask, str]:
    """Real semantic counterexample with the SAME coarse AST signature.

    The conditional remains in the call graph, but x > 999 is never satisfied
    on generated contract rows. With the original x > 0 threshold the upstream
    intervention affected observable results. No fabricated receipt.
    """
    files = dict(task.files)
    matches = [name for name,source in files.items() if 'if x > 0 else x-y' in source]
    if len(matches) != 1: raise AssertionError('expected one conditional module')
    name = matches[0]
    files[name] = files[name].replace('if x > 0 else x-y','if x > 999 else x-y')
    from dataclasses import replace
    return replace(task,task_id=task.task_id+'-conditional-drift',files=files), name.removesuffix('.py')+'.solve'


def run_study(*, train_seeds=TRAIN_SEEDS,cal_seeds=CAL_SEEDS,holdout_seeds=HOLDOUT_SEEDS, memory_file: Path | None = None) -> dict:
    sets = [set(train_seeds),set(cal_seeds),set(holdout_seeds)]
    if any(sets[i] & sets[j] for i in range(3) for j in range(i+1,3)):
        raise ValueError('train/calibration/heldout seeds must be disjoint')
    training = tasks(tuple(train_seeds))
    calibration = tasks(tuple(cal_seeds))
    heldout = tasks(tuple(holdout_seeds))
    if memory_file is None:
        # Unit/development path; persisted and reloaded in one process.
        original = fit_memory(training)
        with tempfile.TemporaryDirectory(prefix='nomad-mnemonic-') as td:
            location = Path(td)/'memory.json'
            saved_hash = original.save(location)
            loaded = EvidenceMemory.load(location)
            if loaded.snapshot() != original.snapshot():
                raise AssertionError('memory changed after reload')
    else:
        # Release path: memory was fitted and frozen in an entirely different
        # Python interpreter, which has already exited before evaluation.
        memory_file = Path(memory_file)
        outer = json.loads(memory_file.read_text(encoding='utf8'))
        saved_hash = outer['payload_sha256']
        loaded = EvidenceMemory.load(memory_file)
    assert loaded.frozen

    # Calibration is not used for selecting features, thresholds, or policies.
    # It is an independent sanity check of immutable predictions.
    calibration_checks=[]
    for task in calibration:
        graph=SymbolGraph(task.files)
        for c,observed in zip(task.contracts,observe_intervention(task,ACTION)):
            p=loaded.recall(action_source=ACTION, features=graph.features(c,task.changed_file),
                            now_epoch=0,target_task_id=task.task_id)
            calibration_checks.append({'prediction':p.outcome,'changed':observed.changed})

    seen_keys=sorted({tuple(row['evidence']['features']) for row in loaded.events})
    labels={k:loaded.recall(action_source=ACTION,features=k,now_epoch=0).outcome for k in seen_keys}
    # Pooled-frequency ablation sees all training outcomes but no Bitwork state.
    pooled_counts=Counter(ev['evidence']['changed'] for ev in loaded.events)
    pooled_prediction='impact' if pooled_counts[True]>pooled_counts[False] else 'no_impact'
    shuffled_keys=list(seen_keys)
    random.Random(123410).shuffle(shuffled_keys)
    shuffled_map=dict(zip(seen_keys,[labels[k] for k in shuffled_keys]))

    test_rows=[]; task_metrics=[]
    for task in heldout:
        graph=SymbolGraph(task.files)
        observed=observe_intervention(task,ACTION)
        contracts=list(zip(task.contracts,observed))
        by_contract={c.key:rec.changed for c,rec in contracts}
        # Predeclared shuffle: no access to outcome labels in any policy sort.
        order=list(range(len(contracts)))
        random.Random(int(hashlib.sha256(task.task_id.encode()).hexdigest()[:8],16)).shuffle(order)
        rows=[]
        for tie,idx in enumerate(order):
            contract,receipt=contracts[idx]
            features=graph.features(contract,task.changed_file)
            warm=loaded.recall(action_source=ACTION,features=features,now_epoch=0,target_task_id=task.task_id)
            cold=EvidenceMemory().recall(action_source=ACTION,features=features,now_epoch=0,target_task_id=task.task_id)
            try:
                reached,_,uncertain,_=graph.reachable(contract.key,task.changed_file[:-3]+'.solve')
            except Exception:
                reached=False; uncertain=True
            graph_pred='abstain' if uncertain else ('impact' if reached else 'no_impact')
            shuffled=shuffled_map.get(features,'abstain')
            row={'task_id':task.task_id, 'contract':contract.key,'features':list(features),
                 'changed':receipt.changed,'warm':warm.outcome,'warm_status':warm.status,
                 'warm_support':warm.support_tasks,'cold':cold.outcome,
                 'graph':graph_pred,'shuffled':shuffled,'pooled':pooled_prediction,'tie':tie,
                 'source_digest':receipt.before_digest,'observed_digest':receipt.receipt_digest}
            rows.append(row)
            test_rows.append(row)

        def priority(mode: str) -> list[dict]:
            if mode in ('cold','pooled'):return rows
            if mode=='graph':return sorted(rows,key=lambda r:(0 if r['graph']=='impact' else (1 if r['graph']=='abstain' else 2),r['tie']))
            if mode=='shuffled':return sorted(rows,key=lambda r:(0 if r['shuffled']=='impact' else (1 if r['shuffled']=='abstain' else 2),r['tie']))
            return sorted(rows,key=lambda r:(0 if r['warm']=='impact' else (1 if r['warm']=='abstain' else 2),r['tie']))

        counts={}
        for mode in ('cold','graph','shuffled','pooled','warm'):
            ordered=priority(mode)
            top=ordered[:3]
            first=next((i+1 for i,row in enumerate(ordered) if row['changed']),len(ordered)+1)
            counts[mode]={'impact_in_top3':sum(r['changed'] for r in top),'first_effect_probe':first}
        task_metrics.append({'task_id':task.task_id,'correct_source_file':task.changed_file,'policies':counts})

    # Drift is a new local observation in a new world epoch. The old, frozen
    # skill record is NOT overwritten, and the new branch must stop predicting.
    shifted, conditional_contract = _safe_shift(heldout[0])
    drift_graph=SymbolGraph(shifted.files)
    drift_contract=next(c for c in shifted.contracts if c.key==conditional_contract)
    before=loaded.recall(action_source=ACTION,features=drift_graph.features(drift_contract,shifted.changed_file),now_epoch=1)
    drift_receipt=next(rec for c,rec in zip(shifted.contracts,observe_intervention(shifted,ACTION)) if c.key==conditional_contract)
    branch=loaded.fork()
    branch.record(task=shifted,contract=conditional_contract,action_source=ACTION,
                  receipt=drift_receipt,capture_epoch=1)
    after=branch.recall(action_source=ACTION,features=drift_graph.features(drift_contract,shifted.changed_file),now_epoch=1)
    old_still=loaded.recall(action_source=ACTION,features=drift_graph.features(drift_contract,shifted.changed_file),now_epoch=1)
    stale=loaded.recall(action_source=ACTION,features=drift_graph.features(drift_contract,shifted.changed_file),now_epoch=6)
    shifted_action=loaded.recall(action_source='def solve(x, y):\n    return x-y\n',features=drift_graph.features(drift_contract,shifted.changed_file),now_epoch=0)
    if not drift_receipt.verify():raise AssertionError('invalid drift receipt')

    scores={}
    for mode in ('warm','cold','graph','shuffled','pooled'):
        scores[mode]=_score_one([{'prediction':r[mode],'changed':r['changed']} for r in test_rows])
        scores[mode]['mean_top3_impacts']=mean(r['policies'][mode]['impact_in_top3'] for r in task_metrics)
        scores[mode]['mean_probes_to_first_effect']=mean(r['policies'][mode]['first_effect_probe'] for r in task_metrics)
    return {
        'schema':'nomad.mnemonic.heldout.v1',
        'configuration':{'training_seeds':list(train_seeds),'calibration_seeds':list(cal_seeds),
                         'heldout_seeds':list(holdout_seeds),'train_repositories':len(training),
                         'heldout_repositories':len(heldout),'substudy':'pure Python generated repositories',
                         'task_seed_overlap':0,'action_digest':action_digest(ACTION),
                         'memory_loaded_from_separate_process':memory_file is not None},
        'saved_memory_sha256':saved_hash,'saved_memory_chain_head':loaded.head,
        'memory_event_count':len(loaded.events),'calibration':_score_one(calibration_checks),
        'scores':scores,'case_records':test_rows,'task_records':task_metrics,
        'drift':{'task':shifted.task_id,'same_coarse_features':True,
                 'prior_prediction':before.outcome,'counterexample_changed':drift_receipt.changed,
                 'after_witness':after.as_dict(),'frozen_predecessor_unchanged':old_still.outcome==before.outcome,
                 'expired':stale.as_dict(),'changed_action':shifted_action.as_dict(),
                 'witness_digest':drift_receipt.receipt_digest,
                 'branch_chain_head':branch.head},
        'scientific_boundary':'synthetic trust-controlled Python fixtures; supplied structural signatures and intervention; warmed memory is only a predictive hint, never a substitute for current WITNESS or hidden validation',
    }
