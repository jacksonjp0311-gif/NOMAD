"""BGR 1.0: auditable online grammar selection over conditional causal predictors.

Finite supplied expert bank, not autonomous invention of a universal grammar.
All expert forecasts are probabilistic and NEVER issue categorical certificates.
Actions are externally chosen; causal intervention validity is not inferred.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from math import log,exp

EPS=1e-12


def context(history, action, order):
    """Last `order` (action, observation) pairs, newest first. No hidden truth."""
    return (action,) + tuple(v for token in history[-order:][::-1] for v in token) if order else (action,)


class BackoffKT:
    """KT/Beta-Bernoulli conditional counts with context-tree shrinkage.

    Lazy exponential forgetting is based on actual step indices. Intermediate
    contexts and the root are updated using the SAME real observations, so
    backoff priors contain no privileged future information.
    """
    def __init__(self,order:int,retention:float=1.,backoff_strength:float=2.):
        if not 0<=order<=5:raise ValueError('order outside 0..5')
        if not 0<retention<=1:raise ValueError('retention outside (0,1]')
        self.order=order;self.retention=retention
        self.backoff_strength=backoff_strength
        self.tables=[{} for _ in range(order+1)]
        self.history=[]
        self.step=0
        self.evidence=[]

    def counts(self,level,key):
        rec=self.tables[level].get(key)
        if rec is None:return 0.,0.
        zero,one,t=rec
        fade=self.retention**(self.step-t)
        return zero*fade,one*fade

    def predict(self,action):
        if action not in (0,1):raise ValueError('only two declared actions')
        estimate=.5
        for order in range(self.order+1):
            key=context(self.history,action,order)
            count0,count1=self.counts(order,key)
            strength=0 if order==0 else self.backoff_strength
            estimate=(count1+.5+strength*estimate)/(count0+count1+1+strength)
        return estimate

    def observe(self,action:int,output:int):
        if action not in (0,1) or output not in (0,1):raise ValueError('binary action and output required')
        for k in range(self.order+1):
            key=context(self.history,action,k)
            n0,n1=self.counts(k,key)
            self.tables[k][key]=(n0+int(output==0),n1+int(output==1),self.step+1)
        self.history.append((action,output));self.step+=1
        self.evidence.append((action,output))


@dataclass(frozen=True)
class Prediction:
    probability_one:float
    expert_probabilities:tuple[float,...]
    grammar_weights:tuple[float,...]
    grammar_names:tuple[str,...]
    confidence_status:str
    public_certificate:None=None


class GrammarEnsemble:
    """Fixed-share online mixture of candidate causal-observation grammars.

    p_t = sum_i w_t(i) p_i(y_t | history, action).
    After observing y_t, posterior weights are updated using likelihood,
    then mixed with original strictly positive prior by `share`.
    This is a standard switching-experts construction with an exact finite
    path-mixture log-loss bound, not a novel intelligence theorem.
    """
    def __init__(self, orders=(0,1,2,3), retentions=(1.,.82), share=.025):
        if not 0<=share<1:raise ValueError('invalid fixed share')
        self.specs=tuple((int(order),float(retention)) for order in orders for retention in retentions)
        if not self.specs or len(set(self.specs))!=len(self.specs):raise ValueError('no/duplicate experts')
        self.models=[BackoffKT(o,r) for o,r in self.specs]
        raw=[exp(-.45*o-(.25 if r<1 else 0)) for o,r in self.specs]
        self.prior=tuple(w/sum(raw) for w in raw)
        self.weights=list(self.prior)
        self.share=share;self.history=[]
        self.last=None
        self.cumulative_loss=0.
        self.expert_cumulative_losses=[0.]*len(self.models)
        self.telemetry={'forecasts':0,'observations':0,'grammar_weight_updates':0,'backoff_context_reads':0,'abstained_public_certificates':0}

    @property
    def names(self):return tuple(f'order{o}.retention{r:.2f}' for o,r in self.specs)

    def predict(self,action:int):
        if action not in (0,1):raise ValueError('action outside binary scope')
        probs=tuple(model.predict(action) for model in self.models)
        p=sum(w*x for w,x in zip(self.weights,probs))
        assert 0<p<1
        self.telemetry['forecasts']+=1
        self.telemetry['backoff_context_reads']+=sum(o+1 for o,r in self.specs)
        self.telemetry['abstained_public_certificates']+=1
        pred=Prediction(p,probs,tuple(self.weights),self.names,
            'probabilistic_model_based_not_certified')
        self.last=(action,pred)
        return pred

    def observe(self,action:int,output:int):
        if output not in (0,1):raise ValueError('binary observed output required')
        if self.last is None or action!=self.last[0]:
            # Prevent a user from accidentally updating a different prediction.
            raise RuntimeError('call predict with matching action before observe')
        pred=self.last[1]
        likelihoods=[p if output else (1-p) for p in pred.expert_probabilities]
        mixture=pred.probability_one if output else 1-pred.probability_one
        self.cumulative_loss-=log(max(EPS,mixture))
        for i,likelihood in enumerate(likelihoods):
            self.expert_cumulative_losses[i]-=log(max(EPS,likelihood))
        posterior=[weight*likely/mixture for weight,likely in zip(self.weights,likelihoods)]
        self.weights=[(1-self.share)*w+self.share*q for w,q in zip(posterior,self.prior)]
        z=sum(self.weights);self.weights=[w/z for w in self.weights]
        for model in self.models:model.observe(action,output)
        self.history.append((action,output));self.last=None
        self.telemetry['observations']+=1
        self.telemetry['grammar_weight_updates']+=len(self.models)

    def snapshot(self):
        return {'version':'1.0.0','steps':len(self.history),
                'grammar_names':self.names,'grammar_weights':[round(w,12) for w in self.weights],
                'cumulative_log_loss':self.cumulative_loss,
                'public_certifications':0,'conditional_model_families':len(self.specs),
                'model_assumptions':'binary actions and outcomes, bounded conditional histories; no external scope attestation',
                'telemetry':dict(self.telemetry)}


def fixed_share_path_bound(expert_path,model_probabilities,outputs,prior,share):
    """Exact path-code upper bound on total mixture loss for this expert path.

    Constant across time only when `share` is fixed and priors positive.
    Bound: -log pi(path) + sum_t -log p_{path_t}(observed_t).
    Applies to predictor sequence actually forecast by each expert.
    """
    seq=tuple(expert_path)
    if len(seq)!=len(outputs):raise ValueError('length mismatch')
    if not seq:return 0.
    k=len(prior)
    loss=-log(prior[seq[0]])
    for t,j in enumerate(seq):
        prob=model_probabilities[t][j];p=prob if outputs[t] else 1-prob
        loss-=log(max(EPS,p))
        if t:
            tr=(1-share if seq[t-1]==j else 0)+share*prior[j]
            loss-=log(tr)
    return loss
