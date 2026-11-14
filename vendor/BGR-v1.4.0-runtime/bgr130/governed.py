"""Lazy bounded history-feature discovery, preserving prior causal semantics.

The v1.2 lag search is not run until cheap out-of-sample surprise justifies
paying for it. On activation it is reconstructed by replaying *past* data only,
so no future observations are used in earlier forecasts.  Model probabilities
remain conditional and all public categorical certifications stay disabled.

This does NOT create unseen causal primitives or guarantee optimum use of CPU.
"""
from __future__ import annotations
from collections import deque
from math import log
from bgr120.compiled import CompiledGuardedLearner
from bgr120.lag_discovery import LagFeatureLearner

class GovernedBitworkV13:
    def __init__(self,*,surprise_threshold=.66,checkpoints=(24,30,36,48,60),
                 monitor_window=24,max_replay=100,promote_gain=.5):
        if not 0 < surprise_threshold < 2:raise ValueError('invalid surprise threshold')
        if monitor_window<=0 or max_replay<monitor_window:raise ValueError('invalid replay budget')
        if sorted(set(checkpoints))!=list(checkpoints):raise ValueError('checkpoints must be increasing and unique')
        self.base=CompiledGuardedLearner()
        self.lags=None
        self.history=[] # (a,y,p_base) already observed, no future leakage
        self.losses=deque(maxlen=monitor_window)
        self.threshold=surprise_threshold;self.checkpoints=frozenset(checkpoints)
        self.max_replay=max_replay;self.promote_gain=promote_gain
        self.weight=[.80,.20];self.prior=(.80,.20)
        self.last=None;self.loss=0.0
        self.gate_events=[];self.public_certifications=0
        self.telemetry={'monitor_evaluations':0,'lag_live_steps':0,'lag_replay_steps':0,
                        'lag_activation':0,'fallback_due_budget':0,'public_certifications':0,
                        'lag_trigger_reason':'rolling predictive surprise on compiled v1.1 base'}

    def predict(self,action):
        if self.last is not None:raise RuntimeError('observation pending')
        pbase=self.base.predict(action)
        plag=self.lags.predict(action) if self.lags is not None else None
        active=self.lags is not None and bool(self.lags.promotions)
        result=self.weight[0]*pbase+self.weight[1]*plag if active else pbase
        if not 0<result<1:raise AssertionError('invalid probability')
        self.last=(action,pbase,plag,result)
        return result

    def _activate(self):
        if self.lags is not None:raise AssertionError('already activated')
        if len(self.history)>self.max_replay:
            self.telemetry['fallback_due_budget']+=1
            return False
        m=LagFeatureLearner(promote_gain=self.promote_gain)
        weights=[.80,.20]
        # Replay only previously observed actions/outputs. This exactly
        # reconstructs the dormant lag learner and mixture weights that
        # v1.2 would have maintained up to the same time.
        for action,y,pbase in self.history:
            plag=m.predict(action)
            likelihood=(pbase if y else 1-pbase,plag if y else 1-plag)
            post=[w*v for w,v in zip(weights,likelihood)];denom=sum(post)
            weights=[.98*p/denom+.02*r for p,r in zip(post,self.prior)]
            m.observe(action,y)
        self.lags=m;self.weight=weights
        self.telemetry['lag_activation']+=1
        self.telemetry['lag_replay_steps']+=len(self.history)
        return True

    def observe(self,action,outcome):
        if outcome not in (0,1) or self.last is None or action!=self.last[0]:
            raise RuntimeError('pending prediction required')
        _,pbase,plag,p=self.last
        self.loss-=log(p if outcome else 1-p)
        self.losses.append(-log(pbase if outcome else 1-pbase))
        self.base.observe(action,outcome)
        if self.lags is not None:
            self.telemetry['lag_live_steps']+=1
            li=(pbase if outcome else 1-pbase,plag if outcome else 1-plag)
            new=[w*v for w,v in zip(self.weight,li)]
            denom=sum(new)
            self.weight=[.98*v/denom+.02*r for v,r in zip(new,self.prior)]
            self.lags.observe(action,outcome)
        self.history.append((action,outcome,pbase))
        self.last=None
        steps=len(self.history)
        if steps in self.checkpoints and self.lags is None:
            surprise=sum(self.losses)/len(self.losses)
            self.telemetry['monitor_evaluations']+=1
            trigger=surprise>=self.threshold
            event={'at':steps,'mean_recent_base_log_loss':round(surprise,12),
                   'activation_requested':trigger,'activated':False}
            if trigger:event['activated']=self._activate()
            self.gate_events.append(event)

    def snapshot(self):
        return {'version':'1.3.0','steps':len(self.history),'lag_search_active':self.lags is not None,
                'lag_promotions':list(self.lags.promotions) if self.lags is not None else [],
                'feature_set':list(self.lags.features) if self.lags is not None else [],
                'cumulative_log_loss':self.loss,'monitor_events':list(self.gate_events),
                'telemetry':dict(self.telemetry),'conditional_model_only':True,
                'public_certifications':0}
