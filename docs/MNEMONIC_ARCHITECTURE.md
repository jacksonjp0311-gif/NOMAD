# MNEMONIC Architecture — v0.12

## Claim and contract

MNEMONIC is an evidence memory for *outcome hypotheses*, not a solver that can confer independent verification or production authority. Existing NOMAD components remain responsible for source generation, repo structure, test execution, and WITNESS.

A portable record is:

\[
R_i = (A, B, T, C, D_0, D_1, E_i, y_i, t_i)
\]

- **A**: normalized transformation AST digest; different action → no transfer.
- **B**: packed sparse Bitwork-style binary structural state, one bit per category.
- **T**: source task ID, used to count distinct supporting tasks.
- **C**: observed contract identifier, for provenance only; never included in transfer lookup.
- **D₀/D₁**: before/after complete source digests, binding observed evidence to the specific task snapshot.
- **Eᵢ**: source intervention receipt checksum. It is not a signature.
- **yᵢ**: observed Boolean output-change label on finite rows.
- **tᵢ**: memory capture epoch.

The feature space is fixed for v0.12: import usage (2), call usage (2), call distance (5), zero mask (2), self-cancellation (2), and conditional presence (2) = **15 binary coordinates**. A valid state has six 1-bits, one in each partition. An unknown state is *unrepresentable* and forces abstention.

Transfer lookup uses **(A,B)** only. Source task IDs are counted to prevent repeated contracts on the same task from artificially multiplying support.

## Recall algorithm

Given current action and structural features, gather matching records within the epoch horizon. If no records, too few distinct source tasks, an unknown signature, an expired history, or conflicting outcomes are present, **abstain**. Otherwise issue `impact` or `no_impact`, always tagged `authority=prediction_only`.

At least **three distinct source tasks** with consistent labels are required before a prediction is considered promoted. Contradictory evidence is never silently averaged away: the applicable cell becomes `contested`.

A retained memory is never allowed to skip independent final validation or authorize a new code change. It is used only to **prioritize the next execution budget**.

## Integrity and replay

The ledger is append-only within a candidate epoch. Each record contains `sha256 = H({evidence, previous})`; the snapshot has an outer checksum and is written with atomic replacement. A new experiment starts as a fork, keeping the frozen predecessor unchanged. The loader recomputes the chain, checks schema and state bits and rejects malformed records.

**Threat model:** This detects accidental or noncoordinated local corruption. A malicious writer controlling the entire file can recompute hashes; this is not an authenticated, remote-adversarial memory system. A recorded receipt's checksum is not equivalent to independently witnessed execution. Trust comes from the separate execution study and current WITNESS gate.

## Counterexample behavior

The deliberately drifted conditional changes `if x > 0` to `if x > 999`. Its coarse binary structure remains the same, but the measured effect flips. Under v0.12 the appropriate response is **abstention**, not inventing an additional feature after seeing the release holdout. Learning a finer causal predicate is a future research task.

## Reproducibility boundaries

The training and evaluation processes are disjoint. Train/calibration/heldout seeds are separate. The evaluator computes correct labels after recalling memory. The fixed action, bounded generated modules and provided features make the experiment internally meaningful but unsuitable for a general intelligence claim.
