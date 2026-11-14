"""Evaluator-only binary observation worlds with randomly generated causal formulas.

A formula mask and its source AST are NEVER passed to a learner. Every trial
advances a single world under a common exogenous action sequence and no reset.
The known variable/operation DSL is deliberately restricted; four-lag and
hidden Markov cases are negative controls outside that declared DSL.
"""
from __future__ import annotations
from random import Random
from bgr100.worlds import exogenous_actions
from .synthesis import atomic_expressions,compose,context_index

FAMILIES=('triple_parity','composed_gate','nested_boolean','rule_shift','four_lag_outside','hidden_markov','action_noise')


def dependence(mask,n=5):
    return tuple(i for i in range(n) if any(((mask>>j)&1)!=((mask>>(j^(1<<i)))&1) for j in range(1<<n)))


def make_formula(rng,family):
    atom={x.code:x for x in atomic_expressions().values()}
    names=('action','y[t-1]','a[t-1]','y[t-2]','a[t-2]')
    for _ in range(250):
        chosen=rng.sample(names,4)
        x,y,z,w=(atom[q] for q in chosen)
        if family=='triple_parity':
            xy=compose(x,y,'xor');expr=compose(xy,z,'xor')
        elif family=='composed_gate':
            op=rng.choice(('xor','and','or'))
            xy=compose(x,y,op);expr=compose(xy,z,rng.choice(('xor','and','or')))
        elif family in ('nested_boolean','rule_shift'):
            xy=compose(x,y,rng.choice(('xor','and','or')))
            zw=compose(z,w,rng.choice(('xor','and','or')))
            expr=compose(xy,zw,rng.choice(('xor','and','or')))
        else:raise ValueError(family)
        if expr is None:continue
        dep=dependence(expr.signature)
        on=expr.signature.bit_count()
        if len(dep)>=3 and 5<=on<=27:return expr
    raise RuntimeError('formula generation found no diverse expression')


class StreamWorld:
    def __init__(self,seed,family,length=84):
        if family not in FAMILIES:raise ValueError(family)
        self.seed=seed;self.family=family;self.length=length
        self.rng=Random(seed*191+7)
        self.history=[];self.hidden=self.rng.randrange(2)
        self.action_prob=(.12+self.rng.random()*.15,.68+self.rng.random()*.16)
        if family in ('triple_parity','composed_gate','nested_boolean'):
            self.true_formula=make_formula(self.rng,family)
            self.alternate=None
        elif family=='rule_shift':
            self.true_formula=make_formula(self.rng,'nested_boolean')
            self.alternate=make_formula(self.rng,'nested_boolean')
            while self.alternate.signature==self.true_formula.signature:
                self.alternate=make_formula(self.rng,'nested_boolean')
        else:self.true_formula=None;self.alternate=None
        self.noise=.045 if family in ('triple_parity','nested_boolean','composed_gate','rule_shift') else None

    def observe(self,action):
        if action not in (0,1):raise ValueError('binary action required')
        i=len(self.history)
        if self.true_formula is not None:
            expr=self.alternate if self.alternate is not None and i>=self.length//2 else self.true_formula
            expected=expr.at(context_index(self.history,action))
            p=(1-self.noise) if expected else self.noise
        elif self.family=='four_lag_outside':
            lag=self.history[-4][1] if len(self.history)>=4 else 0
            expected=(action ^ lag ^ (self.history[-1][0] if self.history else 0))
            p=.95 if expected else .05
        elif self.family=='hidden_markov':
            if self.rng.random() < (.06 if action else .17):self.hidden^=1
            p=.91 if self.hidden else .09
        else:
            p=self.action_prob[action]
        y=int(self.rng.random()<p)
        self.history.append((action,y))
        return y


def trace(seed,family,length=84):
    w=StreamWorld(seed,family,length)
    actions=exogenous_actions(seed,length)
    return tuple((a,w.observe(a)) for a in actions)
