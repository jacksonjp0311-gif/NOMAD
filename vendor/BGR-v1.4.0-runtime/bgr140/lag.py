"""Packed-history acceleration with the v1.2 lag learner's exact semantics.

The candidate grammar, chronological validation, ranking tie breakers, and
floating-point accumulation order are inherited from ``LagFeatureLearner``.
Only repeated historical feature evaluation and repeated scores are removed.
The cache belongs to one model and one observed-history epoch. It is never
shared between streams, and its score-entry count has an explicit bound.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import log

from bgr120.lag_discovery import BASE, CANDIDATES, LagFeatureLearner


@dataclass
class _PackedEpoch:
    observations: tuple
    row_ids: tuple[int, ...]
    parameters: tuple
    full_mask: int
    outcome_mask: int
    feature_masks: dict[str, int]
    good: float
    bad: float
    weighted_terms: tuple[tuple[float, float], ...]
    scores: dict = field(default_factory=dict)


class PackedLagFeatureLearner(LagFeatureLearner):
    """Exact historical scoring using integer masks and epoch-local reuse.

    Public ``predict``, ``observe``, ``snapshot``, and promotion behavior remain
    inherited. Private scoring of an arbitrary external sequence uses the
    unchanged scalar reference. A cached epoch retains immutable binary rows
    and checks their identities, so even an equal-valued replacement of a row
    is revalidated before reuse. The supported packed vocabulary is the supplied finite
    BASE/CANDIDATES vocabulary; unfamiliar private-call programs fall back.

    ``max_cache_entries`` changes storage/work only, never score semantics.
    An entry count of zero disables score reuse while retaining packed masks.
    This bounds the score cache, not the underlying learner's history length.
    """

    def __init__(self, *, max_cache_entries=4096, **kwargs):
        if not isinstance(max_cache_entries, int) or max_cache_entries < 0:
            raise ValueError("max_cache_entries must be a nonnegative integer")
        super().__init__(**kwargs)
        self.max_cache_entries = max_cache_entries
        self._packed_epoch = None
        self.packed_cost = {
            "history_compilations": 0,
            "historical_score_evaluations": 0,
            "historical_score_cache_hits": 0,
            "packed_validation_evaluations": 0,
            "scalar_fallbacks": 0,
            "peak_score_cache_entries": 0,
        }

    def _epoch(self, observations):
        if observations is not self.history:
            return None
        snapshot = tuple(observations)
        parameters = (self.noise, self.forgetting)
        epoch = self._packed_epoch
        # The epoch owns references to validated immutable rows. Comparing
        # identities avoids treating an equal-valued float as an integer and
        # avoids repeating full per-element type validation on a cache hit.
        if (epoch is not None and epoch.parameters == parameters
                and len(epoch.observations) == len(snapshot)
                and epoch.row_ids == tuple(map(id, snapshot))):
            return epoch

        # The public API appends binary tuples. Preserve scalar behavior for
        # unusual manually supplied history rather than silently coercing it.
        if any(type(row) is not tuple or len(row) != 2 for row in snapshot):
            return None
        if any(type(a) not in (int, bool) or type(y) not in (int, bool)
               or a not in (0, 1) or y not in (0, 1) for a, y in snapshot):
            return None
        n = len(snapshot)
        action_mask = outcome_mask = 0
        for index, (action, outcome) in enumerate(snapshot):
            action_mask |= action << index
            outcome_mask |= outcome << index
        full_mask = (1 << n) - 1
        masks = {"action": action_mask}
        for name in BASE + CANDIDATES:
            if name == "action":
                continue
            source = outcome_mask if name[0] == "y" else action_mask
            masks[name] = (source << int(name[1:])) & full_mask

        good = log(1 - self.noise)
        bad = log(self.noise)
        # Keep exactly the scalar power, multiplication, and chronological
        # addition operations. A rolling recurrence or grouped sum can change
        # rounding and therefore tie-sensitive feature selection.
        terms = []
        for index in range(n):
            weight = self.forgetting ** (n - 1 - index)
            terms.append((weight * bad, weight * good))
        epoch = _PackedEpoch(
            snapshot, tuple(map(id, snapshot)), parameters, full_mask, outcome_mask, masks,
            good, bad, tuple(terms),
        )
        self._packed_epoch = epoch
        self.packed_cost["history_compilations"] += 1
        return epoch

    @staticmethod
    def _match_mask(program, epoch):
        if not isinstance(program.phase, int) or program.phase not in (0, 1):
            return None
        expected = epoch.full_mask if program.phase else 0
        for name in program.features:
            mask = epoch.feature_masks.get(name)
            if mask is None:
                return None
            expected ^= mask
        return ~(expected ^ epoch.outcome_mask) & epoch.full_mask

    def _program_log_score(self, program, observations):
        epoch = self._epoch(observations)
        if epoch is None:
            self.packed_cost["scalar_fallbacks"] += 1
            return super()._program_log_score(program, observations)
        matches = self._match_mask(program, epoch)
        if matches is None:
            self.packed_cost["scalar_fallbacks"] += 1
            return super()._program_log_score(program, observations)
        # Equivalent parity formulas can share a score if their complexity
        # penalties also agree. Rank's original syntactic tie breakers stay.
        key = (matches, len(program.features))
        found = epoch.scores.get(key)
        if found is not None:
            self.packed_cost["historical_score_cache_hits"] += 1
            return found
        score = -.45 * len(program.features)
        bits = matches
        for bad_term, good_term in epoch.weighted_terms:
            score += good_term if bits & 1 else bad_term
            bits >>= 1
        self.packed_cost["historical_score_evaluations"] += 1
        if len(epoch.scores) < self.max_cache_entries:
            epoch.scores[key] = score
            self.packed_cost["peak_score_cache_entries"] = max(
                self.packed_cost["peak_score_cache_entries"], len(epoch.scores)
            )
        return score

    def _validation_score(self, program, sequence):
        epoch = self._epoch(sequence)
        matches = self._match_mask(program, epoch) if epoch is not None else None
        if matches is None:
            self.packed_cost["scalar_fallbacks"] += 1
            return super()._validation_score(program, sequence)
        n = len(sequence)
        cut = max(12, int(n * (1 - self.validation_fraction)))
        # The scalar implementation counts actual training rows, but retains
        # the declared cut in its train_bad term even for n < 12. Preserve it.
        training_correct = (matches & ((1 << min(cut, n)) - 1)).bit_count()
        val_loss = 0.0
        bits = matches >> cut
        for _ in range(cut, n):
            val_loss -= epoch.good if bits & 1 else epoch.bad
            bits >>= 1
        self.telemetry["validation_program_evals"] += n
        self.packed_cost["packed_validation_evaluations"] += 1
        train_bad = cut - training_correct
        fit = -(training_correct * epoch.good + train_bad * epoch.bad)
        fit += .45 * len(program.features)
        return fit, val_loss, max(0, n - cut)

    def optimization_snapshot(self):
        """Implementation work/storage counters, separate from model evidence."""
        epoch = self._packed_epoch
        return {
            **self.packed_cost,
            "score_cache_limit": self.max_cache_entries,
            "current_score_cache_entries": len(epoch.scores) if epoch else 0,
            "current_packed_history_steps": len(epoch.observations) if epoch else 0,
            "current_feature_mask_count": len(epoch.feature_masks) if epoch else 0,
            "cache_scope": "one instance, one observed-history epoch",
            "physical_energy_measured": False,
        }
