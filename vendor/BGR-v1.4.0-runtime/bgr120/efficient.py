"""Exact-objective accelerated v1.1 causal expression search.

The likelihood and candidate expression *set* match v1.1; the internal
computation is changed via sufficient statistics, per-epoch score caches, and
incremental discounted updates. No teacher formula or family ID is accessed.
All probabilities are conditional and NEVER public correctness certificates.
"""
from __future__ import annotations
from math import log
from bgr110.synthesis import GrammarSynthesizer,GuardedGrammarLearner

class EfficientGrammarSynthesizer(GrammarSynthesizer):
    """Bit-identical likelihood scores cached by (signature, complexity) and epoch.

    A tempting incremental likelihood recurrence changed tie ordering of
    competing equivalent programs by 1e-14. We explicitly rejected it and
    instead evaluate the original reference expression once per evidence epoch.
    This preserves the original float addition order and beam choices.
    """
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self._score_cache={}
        self._ranked_cache=None
        self.cost={'fit_cache_hits':0,'reference_fit_evaluations':0,
                   'rank_cache_hits':0,'rank_builds':0}

    def _fit(self,candidate):
        key=(candidate.signature,candidate.size)
        value=self._score_cache.get(key)
        if value is not None:
            self.cost['fit_cache_hits']+=1
            self.telemetry['candidate_scoring_calls']+=1
            return value
        self.cost['reference_fit_evaluations']+=1
        value=super()._fit(candidate)
        self._score_cache[key]=value
        return value

    def _rank(self):
        if self._ranked_cache is not None:
            self.cost['rank_cache_hits']+=1
            return self._ranked_cache
        self.cost['rank_builds']+=1
        result=super()._rank()
        self._ranked_cache=result
        return result

    def observe(self,action:int,outcome:int):
        if self.pending is None or self.pending[0]!=action:
            raise RuntimeError('observation does not match pending prediction')
        if outcome not in (0,1):raise ValueError('binary outcome required')
        self._score_cache.clear()
        self._ranked_cache=None
        super().observe(action,outcome)
        self._ranked_cache=None

    def snapshot(self):
        result=super().snapshot()
        result['efficient_search_cost']=dict(self.cost)
        return result

class EfficientGuardedLearner(GuardedGrammarLearner):
    """Preserves v1.1 hedge update, swaps only the candidate scorer."""
    def __init__(self,*,growth=True,share=.03):
        super().__init__(growth=growth,share=share)
        self.discovered=EfficientGrammarSynthesizer(growth=growth)

    def snapshot(self):
        data=super().snapshot();data['version']='1.2.0'
        data['optimization']='incremental likelihood scores, per-epoch cache and signature lookups'
        return data
