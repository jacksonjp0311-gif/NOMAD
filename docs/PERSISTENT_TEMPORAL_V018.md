# Persistent temporal computation: implementation and mathematical scope

`nomad/persistent.py` adds a bounded controller and explicit JSON codecs around
the preserved frequency, temporal, and native BGR implementations. It does not
modify `nomad/adaptive.py` or the original BGR vendor tree. A saved native state
retains actual learned counts, grammar pool, mixture weights, lag proposals,
forward-validation progress, and observation histories. Persistence itself is
not evidence of improved prediction, coding, or autonomous self-improvement.

The separate prospective temporal experiment owns its source freeze, development
selection, reserved outcomes, measured costs, and acceptance decisions. The
previous adaptive experiment and its negative results remain unchanged.

Before opening any new development outcomes, the experiment design selected
selective warm state as primary arm E and full warm state as arm I. The class's
default remains full warm; the harness explicitly applies the arm policy. This
pre-outcome design choice makes the primary computational policy capable of
avoiding inactive native work. It is not a result of measured development wins.

## Learners and bounded state

The frequency learner keeps two Laplace count pairs. The temporal learner is the
original eight-expert `GrammarEnsemble`: orders 0 through 3, retentions 1 and
0.82, conditional KT counts with backoff, and fixed-share likelihood updates.
The native learner is the actual `GovernedBitworkV14`, including its guarded
compiled Boolean grammar and evidence-gated lag-feature learner. Their priors,
operator set, promotion gates, and update rules are inherited unchanged.

Each learner has a separate `nomad.persistent-predictor.v18.1` envelope and an
integer state version. Each envelope binds the local implementation hashes,
verified original BGR manifest, Python version/implementation/cache tag,
mechanism, policy digest, logical creation epoch, and public-prefix digest.
Controller state has its own schema and checksum and records all three states
independently. This is local integrity, not authentication against someone who
can replace both state and checksums or executable source and its trust anchor.

The controller permits at most three resident learners, at most 2,048 observed
rows, 512 decision records, 512 verified admission IDs, and bounded native
grammar/cache collections. Checkpoints are capped at 16 MiB, with a configurable
smaller `max_state_bytes`. Those are object and storage bounds, not a strict RSS
claim. Native allocator overhead and transient JSON encoding are included in the
worker's measured process resources. The experiment's OS Job is the outer
resource boundary.

`trim_resident(maximum)` persistently lowers the resident learner count. It evicts
expensive states deterministically by oldest cursor and then mechanism name;
frequency is retained. A cap of one permits frequency only. A cap of two permits
frequency plus the selected expensive learner. Full-warm operation consequently
degrades to the permitted subset under pressure. `evict` also supports explicit
expiry and policy-change reasons. Reusing an evicted learner reconstructs it
from the bounded eligible observed prefix and charges the reconstruction.

## State policies and their comparison

| Policy | Inactive state | Observation work | Reactivation |
|---|---|---|---|
| `fullwarm` | All three learners remain current | Forecast and update all three, including inactive learners | Direct reuse |
| `selectivewarm` | Dormant states retain their last cursor | Frequency and selected learner only | Replay missing observed rows into retained state |
| `cold` | Expensive state discarded when switching away | Frequency and selected learner only | Rebuild and replay the complete observed prefix |

Cold here means cold computational state, not an information-deprived learner:
the same past public observations remain available for reconstruction.
Full-warm also obtains actual inactive forecasts and their public losses. It
therefore differs from selective/cold in both paid computation and available
measured predictor credit. An aggregate comparison cannot attribute a quality
change solely to persistence. A matched forced-selection microbenchmark is
needed to isolate retained-state execution from reconstruction.

An abstention decision produces probability 0.5 and performs only frequency
bookkeeping. It does not instantiate or update expensive learners. Budget
estimates determine admission; all actual process work is separately charged.

## Delayed credit and deterministic selection

For an observed row `t`, let `p_f,t` be the frequency forecast and `p_m,t` an
actually computed forecast from mechanism `m`. Only after the public binary
outcome `y_t` is observed do we append

```
g_m,t = clip(logloss(p_f,t, y_t) - logloss(p_m,t, y_t), -8, 8).
```

No uncomputed counterfactual forecast receives credit. Full-warm computes all
three forecasts; other policies compute only their active set. Inactive
missing rows earn no fabricated gain. This relative predictive score is not a
causal estimate of the benefit of running a learner.

At settled prefix length `n`, delayed mode releases credit at complete horizon
boundaries `e = floor(n/H) H`. Its registered window is `[e-H,e)`, truncated by
the most recent detector credit reset. An observation's weight is
`w_t = gamma^(e-1-t)`. Available rows yield

```
gain_m = sum(w_t g_m,t) / sum(w_t)
n_eff  = sum(w_t)^2 / sum(w_t^2)
risk_m = min(1, 1/sqrt(max(1, n_eff))).
```

An empty window has gain zero and risk one. The effective-count penalty is a
bounded heuristic. It is not a calibrated confidence interval or a theorem
about delayed rewards. Credit is released using past horizon blocks; the
controller never inspects outcomes beyond the current prefix.

The no-delayed-credit ablation uses the current prefix and a last-16-observation
window, capped by `H`, and retains the base commitment length. Delayed mode also
extends an initial exploratory commitment to the first completed horizon after
at least that base number of observations: `ceil((n+C)/H) H`. This is capped by
the history limit and any explicit remaining-step budget. Its prospective cost
estimate charges the extended interval. This prevents normal commitment expiry
from discarding a new learner before its initial credit can be released. Budget
restrictions and detector alarms may still interrupt it. The ablation removes
both delayed release and this associated initial waiting rule; it does not
isolate the discount factor alone.

Eligible mechanism scores are

```
score_m = gain_m - risk_weight * risk_m
          - cost_weight * estimated_cost_m / planned_steps
          - switch_penalty * [m differs from current mechanism].
```

Estimated cost includes fixed registered per-step work, missing-prefix catchup,
and setup when a model is absent. Full-warm charges the estimate for its whole
active set, so choosing among its forecasts has equal marginal execution cost.
Measured clocks never feed selection. Estimates are approximate scheduling
inputs; realized whole-worker costs remain the experiment's cost outcome.

The controller initially selects frequency. Thereafter bounded exploration
visits temporal and native, subject to budget and resident-state constraints.
An admitted choice is retained for the registered commitment unless a public
change alarm or a resource restriction interrupts it. Replayed decisions and
snapshots preserve chronological prefix indices. A detector reset makes the
bounded exploratory visit available again; it does not reset native evidence.

## Public change detector

After each selected forecast's public outcome, the detector appends the selected
log loss clipped to `[0,4]`. It compares the means of two consecutive windows of
registered length `W`. An alarm occurs when their absolute difference reaches
the registered threshold and the cooldown has elapsed. The alarm records its
settled prefix, both means, and their difference. It expires selector credit
and permits a new decision. The learned models retain their own original
forgetting mechanisms and state.

This is a bounded deterministic diagnostic, not a statistical change-point
certificate. Switching predictors can itself change the selected-loss series.
False alarms and detection delays must be measured using evaluator-only change
times; those times never enter the controller. The no-detector ablation still
maintains the bounded diagnostic loss buffer but disables alarms and resets.

## Safe restoration and operational limits

The codec admits a finite list of exact concrete classes and fields. JSON tags
never become module names or executable import targets. Expression text is
data used by the original engine for display/tie ordering; it is never evaluated
as Python. Integer bounds, finite numbers, collection sizes, configuration,
counter schemas, cache shapes, source identity, chronology, and nested public
histories are checked before adoption. Boolean values are refused as version
integers. The original lag diagnostic `-infinity` for no eligible proposal has
one explicit string representation; arbitrary JSON nonfinite numbers are
refused.

The packed lag cache contains process-local row identities. It is intentionally
invalidated on restoration. The next forecast reconstructs that derived cache
from retained observations and charges the work. Other declared finite caches
are preserved. A native process test restores a 256-row state with a promoted
lag feature into a fresh Python process and compares the next 32 forecasts
exactly. Separate 512-row tests compare all three learners through periodic
restoration. These establish bounded fixture behavior, not arbitrary power-loss
recovery or general semantic equivalence.

`snapshot()` accepts settled state only. `predict(action)` creates one pending
forecast, and `observe(action,outcome)` settles it exactly once. Calling observe
again without a new forecast is refused. `peek_probabilities()` forecasts on
copies and leaves the live learner settled. A mission can therefore persist its
settled prestate and planned public forecast, dispatch one worker, and after a
crash restore the prestate and repeat predict/observe once from its bound public
receipt. This mechanism does not itself implement mission exactly-once I/O.

Logical epoch expiry requires an externally supplied current `expected_epoch`.
The default stored epoch is useful for a same-epoch local round trip and does
not provide autonomous wall-clock expiry. Cross-mission consumers must also
provide the exact eligible accepted public-prefix digest and expected policy.
An expired or otherwise ineligible prefix must not leave latent old evidence in
a cached model. `restore_or_cold` reports `COLD_FALLBACK`, a reason, and zero
retained observations instead of silently treating rejected state as valid.
Rebuilding from any new eligible prefix is the caller's explicit, charged work.

Standalone temporal/native helpers compare the actual decoded model history to
the expected prefix hash. Standalone frequency counts cannot prove chronological
order; its prefix field is an external binding only. Controller restoration
checks the explicit ordered history and independently recomputes its frequency
counts. `record_verified` deduplicates admission IDs and refuses contradictory
reuse; admission metadata cannot manufacture time-indexed stream credit.

Checkpoint files use bounded JSON, duplicate-key rejection, fsync of a temporary
file, and atomic replacement. Leftover partial files are never selected as state.
Existing symbolic links, Windows reparse/junction ancestors, and multiply linked
checkpoint files are refused. These checks do not claim race-free defense
against a concurrent administrator replacing directories after inspection.

## Cost interpretation and contract verification

Stage timers expose build, catchup, active forecast/update, inactive
forecast/update, decision, detector, bookkeeping, serialization, and restoration
work. They are diagnostics, not an alternative to whole-worker Job CPU plus
supervisor CPU. Snapshot's internal serialization timer covers model encoding
and identity checks before final envelope encoding; the harness's surrounding
checkpoint timer also includes canonical encoding, disk publication, parsing,
and restoration. Do not add inclusive checkpoint totals to their nested stage
totals. Deterministic state hashes omit timing values, while preserving state
and operation counters. Raw storage hashes retain the serialized timing values.

Run the mechanism contracts with:

```
python -B -m unittest tests.test_persistent_v18 -q
```

The contracts cover real forecast continuation, a fresh native process, pending
state refusal, typed corruption, source/runtime/policy/prefix mismatch, logical
expiry and cold fallback, duplicate evidence, memory-pressure eviction,
abstention cost behavior, atomic failure preservation, partial/duplicate JSON,
and a controlled native Windows junction. Contract passes are software evidence;
they do not establish a favorable held-out quality/cost result.
