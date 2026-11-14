# Bitwork v1.4 execution changes

This release reduces repeated scoring work while retaining two existing
learning policies. `GovernedBitworkV14` preserves the selected v1.3 policy in
`bgr130/governed.py`; `FullBitworkV14` preserves the always-on v1.2 policy in
`bgr120/lag_discovery.py`. Both use the new execution components in `bgr140/`.

The supplied rule vocabulary, discounting, promotion thresholds, chronological
validation, and mixture arithmetic remain inherited. A faster implementation
does not establish a new reasoning capability, broader generalization, or
better learning decisions. The release evidence compares each implementation
with the appropriate unchanged policy reference.

## 1. Reuse exact grammar scores within an evidence epoch

The compiled grammar scores candidate Boolean expressions over 32 observable
contexts. Its approximate lookup-table ranking is followed by exact rescoring
of near ties, and exact scores are also needed for the forecast mixture.
Previously, the same candidate could be scored repeatedly against unchanged
evidence during those operations.

`ExactCompiledGrammarSynthesizer` now:

1. Computes the two possible likelihood contributions for each context once
   per evidence epoch.
2. Caches exact scores by expression truth signature and expression size.
3. Carries approximate scores alongside ranked candidates rather than
   repeatedly fetching them for adjacent tie comparisons.
4. Reuses data-independent integer byte-transition constants while building
   the approximate lookup tables.

The exact scorer starts with the same complexity penalty and adds all 32
context contributions in the original order. It does not regroup additions or
replace them with a numerically different recurrence. This matters because a
small rounding difference can change a tie, which can change the selected
program and later learning behavior.

A successfully observed outcome invalidates the epoch's exact score and term
caches. A rejected observation is checked before that invalidation. No trained
score cache is shared between model instances; the shared byte-transition
constants contain no learned observations.

## 2. Pack observed history for lag scoring

`PackedLagFeatureLearner` inherits the original predictor, proposer, and
two-stage validation policy. It replaces the expensive historical scoring
helpers used inside that policy.

Let bit `i` of an integer represent observation `i`, with the earliest
observation at the least significant bit. For a history of length `n`, define:

- `A`: action bits already observed.
- `Y`: outcome bits already observed.
- `M = (1 << n) - 1`: the mask selecting the observed history.
- A lagged action feature `aL`: `(A << L) & M`.
- A lagged outcome feature `yL`: `(Y << L) & M`.

The output mask of a supplied XOR program is the XOR of its feature masks,
plus the phase mask when appropriate. Agreement with observed outcomes is
computed as `~(program_mask ^ Y) & M`. These masks contain only recorded past
evidence. They do not provide a teacher formula or an unseen outcome.

### Illustrative four-observation example

For recorded pairs `[(1,0), (0,1), (1,1), (1,0)]`:

| Quantity | Four-bit representation |
| --- | --- |
| Action mask `A` | `1101` |
| Outcome mask `Y` | `0110` |
| Previous-outcome mask `y1` | `1100` |
| Program `action XOR y1` | `0001` |
| Agreement mask | `1000` |

Only the last observation agrees with that illustrative program. Binary
strings here place observation 3 at the left and observation 0 at the right.

### Exact weighted accumulation still matters

For historical program likelihoods, discount powers and their good/bad
likelihood products are computed once for the epoch. Each program still adds
the selected terms **in chronological order**, beginning with its original
complexity penalty. A rolling-score recurrence or a grouped sum could produce
different floating-point values, so neither is substituted.

An exact score can be reused when both the agreement mask and complexity
penalty agree. The original syntactic tie breakers still determine ranking.
For validation, training matches are counted with `int.bit_count()`, while
validation losses retain the original sequential subtraction order. The
candidate-selection and later forward-validation code is inherited unchanged.

This removes repeated feature-name interpretation, historical XOR evaluation,
discount-power calculation, and duplicate scoring. Work proportional to history
length still remains; this release does not turn arbitrary long-history
learning into constant-time inference.

## 3. Cache ownership, invalidation, and limits

The lag cache belongs to one model and one observed-history epoch. The epoch
retains validated immutable binary rows and checks their identities before
reuse. A replaced row must be revalidated even if Python considers its values
equal, such as integer `0` and float `0.0`. This avoids stale cached results
that would bypass the original scalar evaluator's type behavior.

Scoring a separately supplied sequence or an unsupported private-call program
uses the unchanged scalar reference. Those fallbacks protect internal
differential comparisons; they do not make arbitrary edits to private model
state a supported application API. Applications should use the interface in
[API.md](API.md).

The lag score cache has a default cap of **4,096 entries**. Reaching the cap
skips further score insertion; it does not truncate evidence or change scores.
A zero-entry cache is supported by the component for validation purposes.
The cap is specific to lag scores:

- It is not a limit on retained history length.
- It is not a limit on the compiled grammar's separate epoch cache.
- It is not a total RAM, CPU, wall-clock, or electrical-energy budget.

The engine retains its growing history, and packed masks and weighted terms
grow with that history. A fresh instance starts a new independent stream.

## 4. Governed activation remains prospective

The default governed policy keeps its compiled grammar active and checks
recent predictive surprise at the inherited checkpoints. If the gate
activates, it reconstructs the lag learner and its mixture weights by replaying
only actions, outcomes, and baseline probabilities that have already been
recorded. The reconstructed lag learner uses the packed implementation.

The selected default checkpoints are observations 24, 30, 36, 48, and 60. The
default recent-loss window is 24 observations and the activation threshold is
0.66 nats. Historical replay is refused when it exceeds the configured
`max_replay` value, default 100. These are retained policy choices, not a new
theorem that surprise always identifies useful discovery work.

Full mode runs lag discovery continuously, as the v1.2 policy did. Optimizing
both policies supports separate comparisons without confusing savings from
faster execution with savings from skipping a learning operation.

## 5. Telemetry and serialization

Inherited telemetry continues to count logical learning/scoring requests for
comparison with historical records. New counters describe implementation work:

| Counter group | Examples |
| --- | --- |
| `base.discovered.execution_cost` | Exact-score requests, actual score computations, cache hits, compiled context terms, ranking score reads, and peak exact-cache entries. |
| `lags.optimization_snapshot()` | History compilations, historical score computations/cache hits, packed validation evaluations, scalar fallbacks, and lag-cache occupancy/limit. |

Counters distinguish a requested score from a newly computed score. They are
operation accounting, not elapsed time measurements. Runtime comparisons
must measure the complete relevant workload under a stated environment.

The model can retain the reference's `-inf` diagnostic sentinel when no
candidate qualifies. `serialization.json_safe` represents it as
`{"nonfinite_float":"-inf"}` at the JSON boundary while preserving the
internal learning value. This changes serialization, not the candidate
selection rule. Version, policy, and implementation labels likewise describe
the new executor without claiming that all diagnostic metadata is byte
identical to an older release.

## 6. Interpretation of resource measurements

Python process CPU time measures processor time charged to that process.
Wall time measures elapsed time and includes effects such as scheduling.
Neither directly measures physical energy. Peak resident memory, operation
counts, cache entries, and CPU seconds also describe different quantities.

Electrical claims require suitable instrumentation and a stated measurement
scope. No conversion from these counters or CPU seconds to watts or joules is
provided. BitWatts accounting remains separate from actual electrical energy
measurement. Consult the release's validation results for measured performance
and its limits; this implementation note supplies no assumed speedup.
