# NOMAD v0.6 — WITNESS experiment

## Research question

Can NOMAD separate **search-time belief** from **durable consequence evidence** by routing skill promotion through an independent observer that recomputes whether a claimed transformation survived held-out evidence?

The experiment does **not** ask whether WITNESS makes search smarter. It asks whether WITNESS prevents NOMAD from converting its own search success into durable truth when a candidate has merely overfit the visible evidence.

## Core separation

NOMAD proposes a transmission. WITNESS does not choose the transmission and does not choose the goal.

WITNESS receives observable vectors and recomputes a falsifiable consequence claim:

\[
\text{candidate behavior} \stackrel{?}{=} \text{target behavior}
\]

on evidence that search did not use.

A WITNESS receipt records:

- task and transmission identity;
- world epoch;
- public and challenge match status;
- before/after RMSE;
- evidence digests;
- an effect digest;
- an integrity checksum.

The checksum is **not** a digital signature. It detects mutation when the checksum has not been recomputed. It is not an adversarial trust boundary against an actor who can rewrite both receipt and checksum.

## Evidence partition

Each evaluation task contains ten probes split into three authorities:

1. **Search evidence:** four public probes.
2. **WITNESS evidence:** three withheld probes.
3. **Final revalidation:** three additional withheld probes that are invisible to both search and WITNESS.

The final three probes measure whether WITNESS itself overfit its challenge evidence.

## Public-overfit stressor

The benchmark constructs an intentionally deceptive candidate from **public evidence only**.

Given public inputs \(x_1,\ldots,x_n\), the candidate interpolates the visible target and adds a null-space term:

\[
\hat f(x)=P(x)+\lambda\prod_i(x-x_i).
\]

The second term is exactly zero on every public input. Therefore the candidate perfectly satisfies all search-time examples while generally deviating elsewhere.

This is a deliberately adversarial laboratory stressor. It is not a claim that real program repairs fail at this rate.

## Policies

Four policies are compared:

- **public-only self-certification** — accepts the first candidate that matches all public evidence;
- **inline ECHO MAP challenge** — uses held-out challenge evidence but produces no durable independent receipt;
- **fixed WITNESS search** — fixed transformation order, with WITNESS controlling evidence admission;
- **ECHO MAP + WITNESS** — v0.5 learned ranking chooses candidate order, while WITNESS controls evidence admission.

## Study size

Four held-out substrates are rotated:

- code;
- math;
- data;
- workflow.

Five deterministic seeds are used. Each held-out domain contributes 50 evaluation tasks per seed, for **1,000 evaluation tasks per protocol**.

Two protocols are run:

### Adversarial stress

The public-overfit candidate appears on every task.

### Mixed contamination

The public-overfit candidate appears deterministically on approximately 25% of tasks. The realized rate in this frozen study was **22.9%**.

## Frozen results

### Adversarial stress

| Policy | Mean attempts | Final correctness | False certifications |
|---|---:|---:|---:|
| Public-only self-certification | **1.000** | **0.0%** | **100.0%** |
| Inline ECHO MAP challenge | 2.244 | 100.0% | 0.0% |
| Fixed WITNESS | 4.000 | 100.0% | 0.0% |
| **ECHO MAP + WITNESS** | **2.244** | **100.0%** | **0.0%** |

ECHO MAP reduced witnessed search attempts by **43.9%** relative to fixed witnessed search while preserving the same final correctness.

### Mixed contamination

| Policy | Mean attempts | Final correctness | False certifications |
|---|---:|---:|---:|
| Public-only self-certification | **1.193** | **77.1%** | **22.9%** |
| Inline ECHO MAP challenge | 1.473 | 100.0% | 0.0% |
| Fixed WITNESS | 3.229 | 100.0% | 0.0% |
| **ECHO MAP + WITNESS** | **1.473** | **100.0%** | **0.0%** |

ECHO MAP reduced witnessed search attempts by **54.38%** relative to fixed witnessed search.

## Provenance tests

For every final supported WITNESS receipt in the experiment, two additional checks were performed:

1. **stale replay:** attempt to authorize the exact receipt at a later world epoch;
2. **field mutation:** alter the transmission identity without updating the receipt checksum.

Observed rates:

- stale receipt rejection: **100%**;
- checksum field-mutation detection: **100%**.

Again, the second result is integrity detection, not digital-signature security.

## Interpretation

The experiment supports three bounded conclusions.

### 1. Self-certification is structurally unsafe

A learner can satisfy all evidence it used for search while remaining wrong on unseen evidence. This is true even when the search itself is functioning exactly as designed.

### 2. Independent factual witnessing can separate belief from evidence

WITNESS receives observations and recomputes the consequence claim. Durable skill memory no longer accepts a caller-provided `success=True` at the promotion boundary.

### 3. Evidence authority and search intelligence can remain separate

WITNESS does not replace ECHO MAP. ECHO MAP still reduces the amount of search. WITNESS controls whether the resulting claim is admissible as durable evidence.

That division is the intended architecture:

\[
\text{NOMAD proposes} \quad\neq\quad \text{WITNESS attests}.
\]

## What this does not establish

This study does not establish:

- cryptographic or Byzantine trust;
- resistance to a process that can rewrite both WITNESS code and receipts;
- universal truth detection;
- moral judgment;
- correctness outside the supplied evidence;
- independence equivalent to an external organization or human auditor;
- arbitrary real-world software verification.

WITNESS is an **architectural authority separation inside the research system**. Future releases can place the witness in a separate process, machine, evaluator, or externally maintained verifier.

## Next research gate

v0.7 should use WITNESS receipts to learn **causal skill envelopes**:

\[
K=(P,\tau,\Delta,\mathcal E,F)
\]

where a skill stores its learned preconditions, transformation, expected consequence, evidence and known failure boundary. Counterexamples should narrow scope rather than merely decrement a success score.
