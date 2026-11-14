"""Bounded evidence-guided compositional grammar induction for binary streams.

This is NOT unrestricted invention of mathematical primitives. The DSL's
atoms and operators are supplied, but candidate programs are composed,
filtered, and promoted from action/observation evidence at runtime.
All forecasts remain probabilities; no categorical certificate is issued.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, log
from collections import Counter
from bgr100.grammar import GrammarEnsemble

BITCOUNT=5
SIGNATURE_BITS=(1 << (1 << BITCOUNT))-1
ATOM_NAMES=('action','y[t-1]','a[t-1]','y[t-2]','a[t-2]')
EPS=1e-12


def context_index(history,action):
    if action not in (0,1):raise ValueError('expected binary action')
    def pair(n,i):return history[-n][i] if len(history)>=n else 0
    inputs=(action,pair(1,1),pair(1,0),pair(2,1),pair(2,0))
    return sum(x<<i for i,x in enumerate(inputs))


@dataclass(frozen=True)
class Expression:
    signature:int
    code:str
    size:int
    depth:int
    operator:str
    def at(self,index):return (self.signature>>index)&1
    def data(self):return {'signature':self.signature,'code':self.code,'size':self.size,'depth':self.depth,'operator':self.operator}


def atomic_expressions():
    allmask=SIGNATURE_BITS
    result=[]
    for i,n in enumerate(ATOM_NAMES):
        sig=sum(((j>>i)&1)<<j for j in range(1<<BITCOUNT))
        result.extend((Expression(sig,n,1,0,'atom'),
                       Expression(sig^allmask,'!'+n,2,1,'not')))
    result.extend((Expression(0,'0',1,0,'constant'),Expression(allmask,'1',1,0,'constant')))
    return {x.signature:x for x in result}


def compose(x:Expression,y:Expression,op:str,max_size=13,max_depth=4):
    if op=='xor':signature=x.signature^y.signature
    elif op=='and':signature=x.signature & y.signature
    elif op=='or':signature=x.signature | y.signature
    else:raise ValueError(op)
    size=x.size+y.size+1;depth=1+max(x.depth,y.depth)
    if size>max_size or depth>max_depth:return None
    left,right=sorted((x,y),key=lambda e:e.code)
    return Expression(signature,f'({left.code} {op} {right.code})',size,depth,op)


class GrammarSynthesizer:
    """Batched beam expansion from the accumulated *observed* prefix.

    Candidate ranking is a regularized, exponentially discounted noisy-program
    likelihood, not a proof of causal correctness. The beam deliberately keeps
    a small set of atomic anchors and uses periodic re-proposals to recover
    from earlier pruning. Internally generated programs contain no teacher
    rule or environment-family label.
    """
    def __init__(self,*,growth=True,beam=20,max_pool=105,
                 growth_every=5,max_depth=4,max_size=13,
                 forgetting=.975,noise=.075,complexity=.55):
        if not 0<noise<.5 or not 0<forgetting<=1:raise ValueError('calibration parameters')
        if beam<1 or max_pool<12 or growth_every<1:raise ValueError('beam/pool/budget')
        self.growth=growth;self.beam=beam;self.max_pool=max_pool
        self.growth_every=growth_every;self.max_depth=max_depth;self.max_size=max_size
        self.forgetting=forgetting;self.noise=noise;self.complexity=complexity
        self.atoms=atomic_expressions()
        self.pool=dict(self.atoms)
        self.contexts=[];self.outputs=[];self.history=[]
        self.mass0=[0.]*32;self.mass1=[0.]*32
        self.pending=None;self.expansions=[];self.proposals_tested=0
        self.telemetry={'forecasts':0,'observations':0,'candidate_scoring_calls':0,
                        'candidate_signature_checks':0,'compositions_attempted':0,'unique_proposals':0,
                        'structural_promotions':0,'high_confidence_public_certificates':0}

    def _fit(self,candidate):
        self.telemetry['candidate_scoring_calls']+=1
        agree=log(1-self.noise);disagree=log(self.noise)
        score=-self.complexity*(candidate.size-1)
        for idx in range(32):
            yes=self.mass1[idx];no=self.mass0[idx]
            score+=(yes*agree+no*disagree) if candidate.at(idx) else (no*agree+yes*disagree)
        return score

    def _rank(self):
        return sorted(self.pool.values(),key=lambda c:(-self._fit(c),c.size,c.signature))

    def _propose(self):
        anchors=list(self.atoms.values())
        strongest=self._rank()[:self.beam]
        best=dict(self.pool);created=0;unique=0
        # Unary additions are already part of the atom grammar. Binary
        # compositions build new syntax trees from retained programs.
        for left in strongest:
            for right in anchors:
                for op in ('xor','and','or'):
                    created+=1
                    expression=compose(left,right,op,self.max_size,self.max_depth)
                    if expression is None:continue
                    old=best.get(expression.signature)
                    if old is None or (expression.size,expression.code)<(old.size,old.code):
                        best[expression.signature]=expression;unique+=int(old is None)
        self.telemetry['compositions_attempted']+=created
        self.telemetry['unique_proposals']+=unique
        self.proposals_tested+=created
        ranked=sorted(best.values(),key=lambda c:(-self._fit(c),c.size,c.signature))
        keep={x.signature:x for x in ranked[:self.max_pool]}
        keep.update(self.atoms)
        newly=[x for x in keep if x not in self.pool and x not in self.atoms]
        self.pool=keep
        self.telemetry['structural_promotions']+=len(newly)
        if newly:
            self.expansions.append({'after_observations':len(self.history),'new_structures':len(newly),
                                    'pool_size':len(self.pool),'best':ranked[0].data()})

    def predict(self,action:int):
        if self.pending is not None:raise RuntimeError('observe pending prediction first')
        idx=context_index(self.history,action)
        ranked=self._rank()
        best=ranked[0]
        candidate_top=ranked[:min(24,len(ranked))]
        scores=[self._fit(x) for x in candidate_top]
        peak=max(scores)
        weights=[exp(s-peak) for s in scores]
        total=sum(weights)
        support=sum(w*c.at(idx) for w,c in zip(weights,candidate_top))/total
        forecast=self.noise+(1-2*self.noise)*support
        assert 0<forecast<1
        self.pending=(action,idx,forecast,best.data())
        self.telemetry['forecasts']+=1
        self.telemetry['candidate_signature_checks']+=len(candidate_top)
        return forecast

    def observe(self,action:int,outcome:int):
        if self.pending is None or self.pending[0]!=action:raise RuntimeError('prediction mismatch')
        if outcome not in (0,1):raise ValueError('expected binary output')
        _,idx,_,_=self.pending
        self.contexts.append(idx);self.outputs.append(outcome)
        for i in range(32):
            self.mass0[i]*=self.forgetting;self.mass1[i]*=self.forgetting
        (self.mass1 if outcome else self.mass0)[idx]+=1.
        self.history.append((action,outcome));self.pending=None
        self.telemetry['observations']+=1
        if self.growth and len(self.history)>=6 and len(self.history)%self.growth_every==1:
            self._propose()

    def snapshot(self):
        leaders=self._rank()[:6]
        return {'observations':len(self.history),'candidate_programs':len(self.pool),
                'best_discovered_programs':[x.data() for x in leaders],
                'expansions':self.expansions,'telemetry':dict(self.telemetry),
                'all_predictions_conditional':True,'public_certifications':0}


class GuardedGrammarLearner:
    """Online hedge between v1.0 supplied adaptive expert and an induced DSL.

    The learner never accesses the teacher's latent formulas. Mixed-model
    forecasts remain strictly inside (0,1) and authorize no categorical claim.
    """
    def __init__(self,*,growth=True,share=.03):
        self.base=GrammarEnsemble()
        self.discovered=GrammarSynthesizer(growth=growth)
        self.prior=(.75,.25)
        self.weight=list(self.prior)
        self.share=share
        self.last=None
        self.history=[];self.loss=0.;self.induced_loss=0.;self.base_loss=0.
        self.telemetry={'forecasts':0,'observations':0,'hedge_updates':0,'public_certifications':0}

    def predict(self,action):
        if self.last is not None:raise RuntimeError('observe pending prediction')
        p0=self.base.predict(action).probability_one
        p1=self.discovered.predict(action)
        p=self.weight[0]*p0+self.weight[1]*p1
        assert 0<p<1
        self.last=(action,(p0,p1),p)
        self.telemetry['forecasts']+=1
        return p

    def observe(self,action,output):
        if self.last is None or self.last[0]!=action:raise RuntimeError('predict first')
        if output not in (0,1):raise ValueError('binary output')
        _,probs,p=self.last
        self.loss-=log(p if output else 1-p)
        self.base_loss-=log(probs[0] if output else 1-probs[0])
        self.induced_loss-=log(probs[1] if output else 1-probs[1])
        likelihoods=[x if output else 1-x for x in probs]
        weights=[x*y for x,y in zip(self.weight,likelihoods)]
        z=sum(weights)
        assert z>0
        self.weight=[(1-self.share)*w/z+self.share*pi for w,pi in zip(weights,self.prior)]
        self.base.observe(action,output)
        self.discovered.observe(action,output)
        self.last=None;self.history.append((action,output))
        self.telemetry['observations']+=1;self.telemetry['hedge_updates']+=1

    def snapshot(self):
        return {'version':'1.1.0','steps':len(self.history),'mixture_weights':tuple(self.weight),
                'model_generation':self.discovered.snapshot(), 'cumulative_log_loss':self.loss,
                'base_loss':self.base_loss,'induced_loss':self.induced_loss,
                'certifications':0,'scope':'supplied finite compositional Boolean DSL; no AGI or external tools'}
