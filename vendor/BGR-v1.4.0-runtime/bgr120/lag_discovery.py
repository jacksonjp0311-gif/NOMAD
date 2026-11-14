"""Bounded feature proposal from evidence, not pre-supplied formula identities.

Programs are XORs of <=3 binary features; lag candidates are proposed from
past action/observation sequences (3..6) and promoted only when held-out
prefix evidence distinguishes them from all current programs. This discovers
missing lag VARIABLES, not a new logical operator or arbitrary concept.

Each target step is predicted BEFORE observing its output. This model issues
no certificates. A supplied finite feature generator is an explicit limit.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from math import exp,log
from bgr120.compiled import CompiledGuardedLearner

BASE=('action','y1','a1','y2','a2')
CANDIDATES=tuple(name for delay in range(3,7) for name in (f'y{delay}',f'a{delay}'))


def feature(history,action,name):
    if name=='action':return action
    dtype=name[0]; lag=int(name[1:]);idx=1 if dtype=='y' else 0
    return history[-lag][idx] if len(history)>=lag else 0


def program_output(history,action,features,phase=0):
    value=phase
    for name in features:value^=feature(history,action,name)
    return value


def program_output_at(sequence,index,action,features,phase=0):
    """Indexed form equivalent to `program_output(sequence[:index],...)`.

    Avoid allocating history prefixes in every hypothesis evaluation.
    """
    result=phase
    for name in features:
        if name=='action':result^=action
        else:
            lag=int(name[1:]);pos=index-lag
            if pos>=0:result^=sequence[pos][1 if name[0]=='y' else 0]
    return result


@dataclass(frozen=True)
class XorProgram:
    features:tuple[str,...]
    phase:int=0
    def at(self,history,action):return program_output(history,action,self.features,self.phase)
    def data(self):return {'features':list(self.features),'phase':self.phase,'operators':['xor']}


def generate_programs(features, max_terms=3, must_use=None):
    out=[]
    for size in range(0,min(max_terms,len(features))+1):
        for select in combinations(features,size):
            if must_use is not None and must_use not in select:continue
            out.extend((XorProgram(select,phase) for phase in (0,1)))
    return out


class LagFeatureLearner:
    """Search missing lag variables using held-out segments of prior history.

    No access to environment family, true formula, future states or reset.
    Deterministic program prior: shorter formulas preferred. Unlike a proof,
    this is regularized noisy likelihood over a hand-specified grammar.
    """
    def __init__(self,*,proposal_period=12,min_history=36,validation_fraction=.30,
                 promote_gain=.5,noise=.075,max_terms=3,forgetting=.985):
        self.history=[];self.pending=None;self.proposal_period=proposal_period
        self.min_history=min_history;self.validation_fraction=validation_fraction
        self.promote_gain=promote_gain;self.noise=noise;self.max_terms=max_terms
        self.forgetting=forgetting
        self.features=list(BASE);self.programs=generate_programs(self.features,max_terms)
        self.promotions=[];self.proposal_traces=[];self.awaiting_validation=None
        self.telemetry={'proposals_evaluated':0,'validation_program_evals':0,
                        'prediction_program_evals':0,'public_certifications':0,
                        'deferred_proposals':0,'deferred_rejections':0}

    def _program_log_score(self,pr,observations):
        good=log(1-self.noise);bad=log(self.noise)
        score=-.45*len(pr.features)
        size=len(observations)
        for i,(action,out) in enumerate(observations):
            expected=program_output_at(observations,i,action,pr.features,pr.phase)
            score+=(self.forgetting**(size-1-i))*(good if expected==out else bad)
        return score

    def _rank(self):
        return sorted(self.programs,key=lambda p:(-self._program_log_score(p,self.history),len(p.features),p.features,p.phase))

    def predict(self,action:int):
        if action not in (0,1) or self.pending is not None:raise RuntimeError('expected new binary action')
        ranked=self._rank()[:24]
        scores=[self._program_log_score(p,self.history) for p in ranked]
        shift=max(scores);weights=[exp(v-shift) for v in scores];norm=sum(weights)
        q=sum(w*p.at(self.history,action) for w,p in zip(weights,ranked))/norm
        pred=self.noise+(1-2*self.noise)*q
        self.telemetry['prediction_program_evals']+=len(self.programs)
        self.pending=(action,pred)
        return pred

    def _validation_score(self,program,sequence):
        n=len(sequence)
        cut=max(12,int(n*(1-self.validation_fraction)))
        good=log(1-self.noise);bad=log(self.noise)
        train=sequence[:cut]
        training_correct=sum(program_output_at(sequence,i,a,program.features,program.phase)==y for i,(a,y) in enumerate(train))
        # Validation is forward in time after training, and uses only PREVIOUS
        # history at each point. The structural rule is fixed during scoring.
        val=sequence[cut:]
        val_loss=0.0
        for i in range(cut,n):
            a,y=sequence[i]
            val_loss-=good if program_output_at(sequence,i,a,program.features,program.phase)==y else bad
        self.telemetry['validation_program_evals']+=n
        train_bad=cut-training_correct
        fit=- (training_correct*good+train_bad*bad) + .45*len(program.features)
        return fit,val_loss,len(val)

    def _propose(self):
        observed=self.history
        # Stage 2: require a SEPARATE forward-time validation interval after
        # the candidate was chosen. This guards against proposing and
        # promoting a feature on the same cherry-picked holdout block.
        if self.awaiting_validation is not None:
            candidate,baseline,proposed_at,initial_gain=self.awaiting_validation
            good=log(1-self.noise);bad=log(self.noise)
            diff=0.0
            for i in range(proposed_at,len(observed)):
                action,y=observed[i]
                match_c=program_output_at(observed,i,action,candidate.features,candidate.phase)==y
                match_b=program_output_at(observed,i,action,baseline.features,baseline.phase)==y
                diff+=(good if match_c else bad)-(good if match_b else bad)
            future_n=len(observed)-proposed_at
            future_gain=diff/future_n if future_n else 0.0
            newvar=next(x for x in candidate.features if x not in self.features)
            accepted=future_n>=self.proposal_period and future_gain>=.25
            self.proposal_traces.append({'after':len(observed),'kind':'forward_validation',
                'feature':newvar,'forward_gain':future_gain,'initial_gain':initial_gain,
                'forward_observations':future_n,'accepted':accepted})
            if accepted:
                self.features.append(newvar)
                self.programs=generate_programs(self.features,self.max_terms)
                self.promotions.append({'after_observations':len(observed),'feature':newvar,
                           'evidence_gain':initial_gain,'forward_gain':future_gain,
                           'witness':candidate.data()})
            else:self.telemetry['deferred_rejections']+=1
            self.awaiting_validation=None
            return
        if len(observed)<self.min_history:return
        baseline=min((self._validation_score(p,observed)+(p,) for p in self.programs),
                     key=lambda x:(x[0],x[1],len(x[3].features)))
        best_train,best_val,count,_=baseline
        best_gain=-float('inf');winner=None
        for candidate in CANDIDATES:
            if candidate in self.features:continue
            # Include one new feature in a parity formula, with up to two of
            # the initial observed variables (no teacher-specific formula).
            proposals=[]
            other=list(self.features)
            for size in (0,1,2):
                for bits in combinations(other,size):
                    all_features=tuple([*bits,candidate])
                    proposals.extend([XorProgram(all_features,0),XorProgram(all_features,1)])
            for p in proposals:
                fit,validation,_=self._validation_score(p,observed)
                self.telemetry['proposals_evaluated']+=1
                # Validation improvement controls inclusion, rather than
                # training fit alone. Training fit must also be competitive.
                gain=(best_val-validation)/count
                if fit<best_train+3.0 and gain>best_gain:
                    best_gain=gain;winner=p
        proposed=winner is not None and best_gain>=self.promote_gain
        self.proposal_traces.append({'after':len(observed),'kind':'candidate_generation',
                  'best_gain_nats_per_step':best_gain,'validation_steps':count,
                  'deferred_candidate':winner.data() if proposed else None})
        if proposed:
            self.awaiting_validation=(winner,baseline[3],len(observed),best_gain)
            self.telemetry['deferred_proposals']+=1

    def observe(self,action:int,outcome:int):
        if self.pending is None or self.pending[0]!=action or outcome not in (0,1):
            raise RuntimeError('pending binary prediction required')
        self.history.append((action,outcome));self.pending=None
        if len(self.history)>=self.min_history and len(self.history)%self.proposal_period==0:
            self._propose()

    def snapshot(self):
        return {'steps':len(self.history),'candidate_features':list(self.features),
                'promotions':list(self.promotions),'proposals':list(self.proposal_traces),
                'awaiting_forward_validation':self.awaiting_validation is not None,
                'telemetry':dict(self.telemetry),'public_certifications':0,
                'scope':'bounded XOR feature-lag proposal, not universal feature/operator invention'}


class AdaptiveBitworkV12:
    """Combines equivalent compiled synthesis and evidence-gated lag proposals."""
    def __init__(self,*,promote_gain=.5):
        self.base=CompiledGuardedLearner()
        self.lags=LagFeatureLearner(promote_gain=promote_gain)
        self.weight=[.80,.20];self.prior=(.80,.20);self.pending=None
        self.history=[];self.loss=0;self.telemetry={'public_certifications':0}

    def predict(self,action):
        if self.pending is not None:raise RuntimeError('pending observation')
        pbase=self.base.predict(action)
        plag=self.lags.predict(action)
        # No newly proposed feature yet: remain EXACTLY on tested v1.1 core.
        if not self.lags.promotions:pr=pbase
        else:pr=self.weight[0]*pbase+self.weight[1]*plag
        self.pending=(action,(pbase,plag),pr)
        return pr

    def observe(self,action,outcome):
        if self.pending is None or self.pending[0]!=action or outcome not in (0,1):
            raise RuntimeError('matching prediction required')
        _,parts,p=self.pending
        self.loss-=log(p if outcome else 1-p)
        self.base.observe(action,outcome)
        self.lags.observe(action,outcome)
        likelihood=[x if outcome else 1-x for x in parts]
        post=[w*q for w,q in zip(self.weight,likelihood)]
        denom=sum(post)
        self.weight=[.98*z/denom+.02*prior for z,prior in zip(post,self.prior)]
        self.history.append((action,outcome));self.pending=None

    def snapshot(self):
        return {'version':'1.2.0','observations':len(self.history),
                'compositional_discovery':self.base.snapshot(),
                'new_history_feature_discovery':self.lags.snapshot(),
                'mixture_weights':list(self.weight),'log_loss':self.loss,
                'public_certifications':0,'model_adequacy':'unverified for unrestricted worlds'}
