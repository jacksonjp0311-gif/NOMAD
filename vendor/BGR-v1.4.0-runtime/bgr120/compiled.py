"""A bounded, bit-signature likelihood compiler for the v1.1 grammar.

This is a performance experiment, not a new learning theorem. A 32-context
truth signature is scored with four byte lookup tables; near-tied score
clusters are recalculated in the reference summation order before beam
selection. Selected forecasts use the original exact scorer. If an ambiguous
ranking remains, the caller must fall back to the reference learner.
"""
from __future__ import annotations
from math import exp,log
from bgr110.synthesis import GrammarSynthesizer, GuardedGrammarLearner, compose,context_index,atomic_expressions

class CompiledGrammarSynthesizer(GrammarSynthesizer):
    def __init__(self,*,tie_tolerance=1e-8,**kwargs):
        super().__init__(**kwargs)
        self.tie_tolerance=tie_tolerance
        self._epoch_lut=None
        self._rank_cache=None
        self._approx_scores={}
        self.cost={'lut_compilations':0,'compiled_candidate_evaluations':0,
                   'near_tie_exact_evaluations':0,'forecast_exact_evaluations':0,
                   'ranking_events':0,'compositions_attempted':0}

    def _build_lut(self):
        if self._epoch_lut is not None:return self._epoch_lut
        good=log(1-self.noise);bad=log(self.noise)
        base=sum(self.mass0[i]*good+self.mass1[i]*bad for i in range(32))
        delta=[(self.mass1[i]-self.mass0[i])*(good-bad) for i in range(32)]
        lut=[]
        for group in range(4):
            row=[0.0]*256
            for byte in range(1,256):
                bit=byte & -byte
                row[byte]=row[byte^bit]+delta[8*group+bit.bit_length()-1]
            lut.append(row)
        self._epoch_lut=(base,lut)
        self.cost['lut_compilations']+=1
        return self._epoch_lut

    def _approx_fit(self,expr):
        key=(expr.signature,expr.size)
        found=self._approx_scores.get(key)
        if found is not None:return found
        base,lut=self._build_lut()
        m=expr.signature
        s=base+lut[0][m&255]+lut[1][(m>>8)&255]+lut[2][(m>>16)&255]+lut[3][m>>24]
        score=s-self.complexity*(expr.size-1)
        self.cost['compiled_candidate_evaluations']+=1
        self._approx_scores[key]=score
        return score

    def _rank_programs(self,expressions):
        self.cost['ranking_events']+=1
        items=sorted(expressions,key=lambda p:(-self._approx_fit(p),p.size,p.signature))
        if not items:return []
        # Approximation may perturb order when evidence signatures are tied.
        # Every connected cluster within tolerance is sorted by the EXACT
        # prior v1.1 numeric score to preserve the original beam selection.
        ordered=[];a=0
        while a<len(items):
            b=a+1
            while b<len(items) and abs(self._approx_fit(items[b])-self._approx_fit(items[b-1]))<=self.tie_tolerance:
                b+=1
            group=items[a:b]
            if len(group)>1:
                scores={id(expr):GrammarSynthesizer._fit(self,expr) for expr in group}
                self.cost['near_tie_exact_evaluations']+=len(group)
                group.sort(key=lambda p:(-scores[id(p)],p.size,p.signature))
            ordered.extend(group)
            a=b
        return ordered

    def _rank(self):
        if self._rank_cache is None:
            self._rank_cache=self._rank_programs(self.pool.values())
        return self._rank_cache

    def _propose(self):
        anchors=list(self.atoms.values())
        strongest=self._rank()[:self.beam]
        best=dict(self.pool);created=unique=0
        for left in strongest:
            for right in anchors:
                for op in ('xor','and','or'):
                    created+=1
                    expr=compose(left,right,op,self.max_size,self.max_depth)
                    if expr is None:continue
                    old=best.get(expr.signature)
                    if old is None or (expr.size,expr.code)<(old.size,old.code):
                        best[expr.signature]=expr;unique+=int(old is None)
        self.telemetry['compositions_attempted']+=created
        self.telemetry['unique_proposals']+=unique
        self.cost['compositions_attempted']+=created
        self.proposals_tested+=created
        ranked=self._rank_programs(best.values())
        keep={p.signature:p for p in ranked[:self.max_pool]}
        keep.update(self.atoms)
        newly=[s for s in keep if s not in self.pool and s not in self.atoms]
        self.pool=keep
        self._rank_cache=None
        self.telemetry['structural_promotions']+=len(newly)
        if newly:
            self.expansions.append({'after_observations':len(self.history),'new_structures':len(newly),
                                    'pool_size':len(self.pool),'best':ranked[0].data()})

    def predict(self,action):
        if self.pending is not None:raise RuntimeError('observe pending prediction first')
        idx=context_index(self.history,action)
        leaders=self._rank()
        # The reference forecast evaluates its top 24 programs with the
        # original score. This guards numerical output equivalence.
        values=leaders[:min(24,len(leaders))]
        scores=[GrammarSynthesizer._fit(self,p) for p in values]
        self.cost['forecast_exact_evaluations']+=len(values)
        peak=max(scores)
        weights=[exp(s-peak) for s in scores]
        total=sum(weights)
        prob=sum(w*p.at(idx) for w,p in zip(weights,values))/total
        result=self.noise+(1-2*self.noise)*prob
        self.pending=(action,idx,result,leaders[0].data())
        self.telemetry['forecasts']+=1
        self.telemetry['candidate_signature_checks']+=len(values)
        return result

    def observe(self,action,outcome):
        self._rank_cache=None;self._epoch_lut=None;self._approx_scores.clear()
        super().observe(action,outcome)
        self._rank_cache=None

    def snapshot(self):
        result=super().snapshot();result['compiled_cost']=self.cost.copy()
        return result

class CompiledGuardedLearner(GuardedGrammarLearner):
    def __init__(self,*,growth=True,share=.03):
        super().__init__(growth=growth,share=share)
        self.discovered=CompiledGrammarSynthesizer(growth=growth)
    def snapshot(self):
        snap=super().snapshot();snap['version']='1.2.0';snap['compiled']='truth signature lookup with exact tie and forecast guard'
        return snap
