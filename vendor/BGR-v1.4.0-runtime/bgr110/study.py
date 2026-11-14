"""Paired, prequential synthesis study with generated hidden Boolean programs.

Every policy gets exactly the same stream of real action/observation pairs.
All loss is scored BEFORE the observed output is revealed. There are no
teacher-rule queries or arbitrary world resets inside the trial.
"""
from __future__ import annotations
from math import log
from time import perf_counter
from bgr100.grammar import GrammarEnsemble,BackoffKT
from .synthesis import GuardedGrammarLearner,GrammarSynthesizer
from .worlds import FAMILIES,trace

POLICIES=('guarded','synth_only','v1_adaptive','atomic_only','order3')


def case(seed,family,length=84,store_trace=True):
    observed=trace(seed,family,length)
    models={'guarded':GuardedGrammarLearner(),
            'synth_only':GrammarSynthesizer(),
            'v1_adaptive':GrammarEnsemble(),
            'atomic_only':GrammarSynthesizer(growth=False),
            'order3':BackoffKT(3,1.)}
    losses={k:0. for k in POLICIES};briers={k:0. for k in POLICIES}
    extreme={k:{'n':0,'wrong':0} for k in POLICIES}
    histories=[];begin=perf_counter()
    for i,(a,y) in enumerate(observed):
        forecast={}
        for name,m in models.items():
            p=m.predict(a)
            forecast[name]=p.probability_one if name=='v1_adaptive' else p
            assert 0<forecast[name]<1
        for name,p in forecast.items():
            losses[name]-=log(p if y else 1-p)
            briers[name]+=(p-y)**2
            if p>.95 or p<.05:
                extreme[name]['n']+=1;extreme[name]['wrong']+=int((p>.5)!=(y==1))
        if store_trace:
            histories.append({'step':i,'action':a,'observation':y,'probability_one':forecast,
                              'induced_candidates_before':len(models['guarded'].discovered.pool),
                              'hedge_weights_before':list(models['guarded'].weight)})
        for m in models.values():m.observe(a,y)
    learner=models['guarded'];induced=learner.discovered
    return {'seed':seed,'family':family,'steps':length,
            'log_loss_total':losses,'brier_total':briers,'confident_predictions':extreme,
            'trace':histories,'synthesis_expansions':induced.expansions,
            'synthesis_snapshot':induced.snapshot(),
            'hedge_final_weights':learner.weight,
            'computational_evaluations':induced.telemetry,
            'public_certifications':0,
            'elapsed_informational':perf_counter()-begin}


def aggregate(rows):
    result={};total=sum(c['steps'] for c in rows)
    for fam in FAMILIES:
        cs=[c for c in rows if c['family']==fam]
        n=sum(c['steps'] for c in cs)
        result[fam]={'worlds':len(cs),'steps':n,'log_loss':{p:sum(c['log_loss_total'][p] for c in cs)/n for p in POLICIES},
                     'brier':{p:sum(c['brier_total'][p] for c in cs)/n for p in POLICIES},
                     'grammar_promotions':sum(c['computational_evaluations']['structural_promotions'] for c in cs)}
    return {'worlds':len(rows),'steps':total,
            'pooled_log_loss':{p:sum(c['log_loss_total'][p] for c in rows)/total for p in POLICIES},
            'pooled_brier':{p:sum(c['brier_total'][p] for c in rows)/total for p in POLICIES},
            'by_family':result,
            'public_certifications':0,
            'total_discovered_structure_promotions':sum(c['computational_evaluations']['structural_promotions'] for c in rows),
            'candidate_signature_checks':sum(c['computational_evaluations']['candidate_signature_checks'] for c in rows),
            'candidate_scoring_calls':sum(c['computational_evaluations']['candidate_scoring_calls'] for c in rows)}
