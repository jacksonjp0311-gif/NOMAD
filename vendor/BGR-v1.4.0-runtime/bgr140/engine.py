"""BGR 1.4 engines: identical learning policies with less repeated scoring.

``GovernedBitworkV14`` retains the selected v1.3 surprise gate.
``FullBitworkV14`` retains the v1.2 always-on policy. Their underlying model
families, numerical evaluation order, and prospective validation are unchanged.
"""
from __future__ import annotations

from bgr120.lag_discovery import AdaptiveBitworkV12
from bgr130.governed import GovernedBitworkV13
from .compiled import ExactCompiledGuardedLearner
from .lag import PackedLagFeatureLearner


class GovernedBitworkV14(GovernedBitworkV13):
    """Optimized, drop-in binary predictor for the selected v1.3 branch.

    Call ``predict(action)`` before the corresponding ``observe(action, y)``.
    Each model owns its learning state and caches. Start a fresh instance for
    each independent stream. Probabilities describe the supplied model family.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base = ExactCompiledGuardedLearner()

    def _activate(self):
        if self.lags is not None:
            raise AssertionError("already activated")
        if len(self.history) > self.max_replay:
            self.telemetry["fallback_due_budget"] += 1
            return False
        learner = PackedLagFeatureLearner(promote_gain=self.promote_gain)
        weights = [.80, .20]
        for action, outcome, pbase in self.history:
            plag = learner.predict(action)
            likelihood = (pbase if outcome else 1-pbase,
                          plag if outcome else 1-plag)
            post = [w*v for w, v in zip(weights, likelihood)]
            denominator = sum(post)
            weights = [.98*p/denominator + .02*r
                       for p, r in zip(post, self.prior)]
            learner.observe(action, outcome)
        self.lags = learner
        self.weight = weights
        self.telemetry["lag_activation"] += 1
        self.telemetry["lag_replay_steps"] += len(self.history)
        return True

    def snapshot(self):
        result = super().snapshot()
        result["version"] = "1.4.0"
        result["policy"] = "v1.3 surprise-gated lag discovery"
        result["implementation"] = "exact score reuse and packed observed history"
        return result


class FullBitworkV14(AdaptiveBitworkV12):
    """Optimized v1.2 policy, retaining its always-on feature discovery."""

    def __init__(self, *, promote_gain=.5):
        super().__init__(promote_gain=promote_gain)
        self.base = ExactCompiledGuardedLearner()
        self.lags = PackedLagFeatureLearner(promote_gain=promote_gain)

    def snapshot(self):
        result = super().snapshot()
        result["version"] = "1.4.0"
        result["policy"] = "v1.2 always-on lag discovery"
        result["implementation"] = "exact score reuse and packed observed history"
        return result


Bitwork = GovernedBitworkV14
