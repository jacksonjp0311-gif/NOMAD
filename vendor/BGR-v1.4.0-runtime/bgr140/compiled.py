"""Exact-output execution improvements for the retained BGR Boolean grammar.

The candidate grammar, evidence discounting, approximate ranking, exact tie
guard and mixture are inherited unchanged. An evidence epoch ends whenever a
valid observation is committed. Scores are cached only inside that epoch and
inside this learner; no trained state is shared between independent streams.

Exact scores still start with the complexity penalty and add the same 32
context terms, in the original order. Precomputing those terms does not
reassociate floating-point additions. The byte-table transition constants are
data-independent integers and contain no learned evidence.
"""
from __future__ import annotations

from math import exp, log

from bgr110.synthesis import context_index
from bgr120.compiled import CompiledGrammarSynthesizer, CompiledGuardedLearner


_BYTE_TRANSITIONS = tuple(
    (byte ^ (byte & -byte), (byte & -byte).bit_length() - 1)
    for byte in range(1, 256)
)


class ExactCompiledGrammarSynthesizer(CompiledGrammarSynthesizer):
    """Preserve v1.3 grammar output while reusing work within an evidence epoch.

    Inherited telemetry counts logical scoring requests for comparability.
    ``execution_cost`` separately counts actual work and cache reuse.
    Configuration is constructor-owned, as in the retained implementation;
    directly mutating evidence arrays or hyperparameters is not a supported
    update API. Use ``predict`` followed by ``observe``.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._exact_scores = {}
        self._exact_terms = None
        self.execution_cost = {
            'exact_score_requests': 0,
            'exact_score_computations': 0,
            'exact_score_cache_hits': 0,
            'context_term_compilations': 0,
            'ranking_score_reads': 0,
            'peak_exact_cache_entries': 0,
            'evidence_epochs': 0,
        }

    def _build_lut(self):
        if self._epoch_lut is not None:
            return self._epoch_lut
        good = log(1 - self.noise)
        bad = log(self.noise)
        # Keep the reference summation and expression evaluation order.
        base = sum(self.mass0[i] * good + self.mass1[i] * bad for i in range(32))
        delta = [(self.mass1[i] - self.mass0[i]) * (good - bad) for i in range(32)]
        lut = []
        for group in range(4):
            row = [0.0] * 256
            offset = 8 * group
            for byte, (remainder, bit_index) in enumerate(_BYTE_TRANSITIONS, 1):
                row[byte] = row[remainder] + delta[offset + bit_index]
            lut.append(row)
        self._epoch_lut = (base, lut)
        self.cost['lut_compilations'] += 1
        return self._epoch_lut

    def _exact_fit(self, expression):
        self.telemetry['candidate_scoring_calls'] += 1
        self.execution_cost['exact_score_requests'] += 1
        key = (expression.signature, expression.size)
        cached = self._exact_scores.get(key)
        if cached is not None:
            self.execution_cost['exact_score_cache_hits'] += 1
            return cached
        if self._exact_terms is None:
            agree = log(1 - self.noise)
            disagree = log(self.noise)
            self._exact_terms = tuple(
                (no * agree + yes * disagree, yes * agree + no * disagree)
                for no, yes in zip(self.mass0, self.mass1)
            )
            self.execution_cost['context_term_compilations'] += 1
        score = -self.complexity * (expression.size - 1)
        signature = expression.signature
        for terms in self._exact_terms:
            score += terms[signature & 1]
            signature >>= 1
        self._exact_scores[key] = score
        self.execution_cost['exact_score_computations'] += 1
        self.execution_cost['peak_exact_cache_entries'] = max(
            self.execution_cost['peak_exact_cache_entries'], len(self._exact_scores)
        )
        return score

    def _rank_programs(self, expressions):
        self.cost['ranking_events'] += 1
        # Carry the numeric score alongside each expression. The retained
        # implementation retrieves it again for every adjacent tie check.
        scored = [(expression, self._approx_fit(expression)) for expression in expressions]
        self.execution_cost['ranking_score_reads'] += len(scored)
        scored.sort(key=lambda item: (-item[1], item[0].size, item[0].signature))
        ordered = []
        start = 0
        while start < len(scored):
            end = start + 1
            while end < len(scored) and abs(scored[end][1] - scored[end - 1][1]) <= self.tie_tolerance:
                end += 1
            group = [item[0] for item in scored[start:end]]
            if len(group) > 1:
                scores = {id(expression): self._exact_fit(expression) for expression in group}
                self.cost['near_tie_exact_evaluations'] += len(group)
                group.sort(key=lambda expression: (-scores[id(expression)], expression.size, expression.signature))
            ordered.extend(group)
            start = end
        return ordered

    def predict(self, action):
        if self.pending is not None:
            raise RuntimeError('observe pending prediction first')
        index = context_index(self.history, action)
        leaders = self._rank()
        values = leaders[:min(24, len(leaders))]
        scores = [self._exact_fit(expression) for expression in values]
        self.cost['forecast_exact_evaluations'] += len(values)
        peak = max(scores)
        weights = [exp(score - peak) for score in scores]
        total = sum(weights)
        probability = sum(weight * expression.at(index) for weight, expression in zip(weights, values)) / total
        result = self.noise + (1 - 2 * self.noise) * probability
        self.pending = (action, index, result, leaders[0].data())
        self.telemetry['forecasts'] += 1
        self.telemetry['candidate_signature_checks'] += len(values)
        return result

    def observe(self, action, outcome):
        # Validate before invalidating, so rejected API calls leave the entire
        # execution state unchanged. Exception classes match the reference.
        if self.pending is None or self.pending[0] != action:
            raise RuntimeError('prediction mismatch')
        if outcome not in (0, 1):
            raise ValueError('expected binary output')
        self._exact_scores.clear()
        self._exact_terms = None
        self.execution_cost['evidence_epochs'] += 1
        super().observe(action, outcome)

    def snapshot(self):
        result = super().snapshot()
        result['execution_cost'] = dict(self.execution_cost)
        return result


class ExactCompiledGuardedLearner(CompiledGuardedLearner):
    """The unchanged guarded mixture with an exact-output grammar executor."""

    def __init__(self, *, growth=True, share=.03):
        super().__init__(growth=growth, share=share)
        self.discovered = ExactCompiledGrammarSynthesizer(growth=growth)

    def snapshot(self):
        result = super().snapshot()
        result['version'] = '1.4.0'
        result['compiled'] = 'evidence-epoch exact term and score reuse; original numeric order'
        return result
