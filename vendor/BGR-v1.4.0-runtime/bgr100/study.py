"""Matched heterogeneous-world, strictly prequential out-of-sample study."""
from __future__ import annotations
from math import log
from statistics import mean
from .grammar import GrammarEnsemble,BackoffKT
from .worlds import World,exogenous_actions,FAMILIES

POLICIES=('adaptive','order0','order1','order2','order3','discount0','discount1','discount2','discount3')


def run_case(seed:int,family:str,length:int=90,compact=False):
    world=World(seed,family,length)
    actions=exogenous_actions(seed,length)
    learned=GrammarEnsemble()
    experts={'order0':BackoffKT(0,1),'order1':BackoffKT(1,1),'order2':BackoffKT(2,1),'order3':BackoffKT(3,1),
             'discount0':BackoffKT(0,.82),'discount1':BackoffKT(1,.82),
             'discount2':BackoffKT(2,.82),'discount3':BackoffKT(3,.82)}
    histories=[];loss={p:0. for p in POLICIES};briers={p:0. for p in POLICIES}
    confidence={p:{'n':0,'wrong':0} for p in POLICIES}
    snapshots=[]
    for i,a in enumerate(actions):
        preds={'adaptive':learned.predict(a).probability_one}
        for name,model in experts.items():preds[name]=model.predict(a)
        # Evaluator acquires the next outcome only after all predictions.
        output=world.observe(a)
        for name,p in preds.items():
            loss[name]-=log(p if output else 1-p)
            briers[name]+=(p-output)**2
            if (p>=.95 or p<=.05):
                confidence[name]['n']+=1;confidence[name]['wrong']+=int((p>.5)!=bool(output))
        if not compact:
            snapshots.append({'step':i,'action':a,'outcome':output,'predictions':preds,
                            'grammar_weights':list(learned.weights),'grammar_likelihoods':list(learned.last[1].expert_probabilities)})
        learned.observe(a,output)
        for model in experts.values():model.observe(a,output)
    return {'seed':seed,'family':family,'steps':length,'outcomes':sum(world.previous_outputs),
            'log_loss_total':loss,'brier_total':briers,'confident_forecasts':confidence,
            'trace':snapshots,'final_grammar_weights':list(learned.weights),
            'model_evaluations':learned.telemetry,'zero_public_certifications':True}


def summarize(cases):
    families={}
    for family in FAMILIES:
        group=[c for c in cases if c['family']==family]
        count=sum(c['steps'] for c in group)
        family_result={'worlds':len(group),'observations':count,
          'log_loss':{k:sum(c['log_loss_total'][k] for c in group)/count for k in POLICIES},
          'brier':{k:sum(c['brier_total'][k] for c in group)/count for k in POLICIES},
          'high_confidence':{k:{'n':sum(c['confident_forecasts'][k]['n'] for c in group),
                                  'wrong':sum(c['confident_forecasts'][k]['wrong'] for c in group)} for k in POLICIES}}
        families[family]=family_result
    total=sum(c['steps'] for c in cases)
    return {'worlds':len(cases),'steps':total,'families':families,
            'pooled_log_loss':{k:sum(c['log_loss_total'][k] for c in cases)/total for k in POLICIES},
            'pooled_brier':{k:sum(c['brier_total'][k] for c in cases)/total for k in POLICIES},
            'incorrect_public_certifications':0,
            'family_best_baseline':{f:min(v['log_loss'].items(),key=lambda kv:kv[1]) for f,v in families.items()}}
