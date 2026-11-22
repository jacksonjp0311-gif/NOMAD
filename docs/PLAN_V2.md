# Plan v2 — generation, abstraction, and transfer

Integrates the 22 Nov 2026 audit and the Theory of Language (v0.2.0) acceptance criteria.

## Measured gap

NOVEL: 9 solves, shuffled-memory control solves 10. One certified program wrong on 613/2000 fresh inputs. CERT implemented, default OFF, no sealed gain. Generation-first is a proposal, not a result.

The gap is not more search stages. It is the absence of structure the system was not given.

## Acceptance criteria from the theory

Three conditions for a generated abstraction to count as transfer:

1. **Identifiable hypotheses.** Remaining candidates that disagree on a probe are not certified. The learner abstains or requests a distinguishing observation.
2. **Adequate state information.** The probe family must distinguish programs that differ on the declared task. Agreement on a coarse family is not agreement on all contexts.
3. **Validated recipient map.** For a frozen field transferred to another process, the adapter must satisfy $f_B \circ T = T \circ f$ on the declared primitives, identified from paired states. Three affinely dependent anchors leave unresolved alternatives.

These are gates, not features.

## Phase A — implemented

1. **Version space.** `nomad/versionspace.py`. When domain packets disagree on operator, the decision abstains. Certification requires agreement.
2. **Portability check.** `nomad/portability.py`. Verifies that a recipient operation agrees with the source on declared examples after the adapter is applied.
3. **Probe-family distance.** Held-out records disagreement on a reserved probe set as a failure.

## Phase B — generation-first (audit move 1)

Draft candidates from the problem statement before memory. Score against examples. Fall back to recall only if nothing fits. Switch default OFF. Sealed suite with unused seed. On/off, cold, empty, real-vs-shuffled arms. Zero per-task losses.

Gate: solve at least five additional independently authored problems beyond the frozen baseline, without increasing incorrect certifications.

## Phase C — abstraction discovery (audit move 2)

Synthesize absdiff, median, and clamp without giving the solutions. Discover at least three nontrivial abstractions from training evidence. Show they improve a frozen family-held-out benchmark against equal-sized random and frequency-matched libraries.

## Phase D — active discrimination (audit move 3)

When candidates disagree, generate a probe that distinguishes them. Where a trusted oracle exists, query it. Where none exists, return an uncertainty verdict. Do not treat disagreement as evidence for either side.

## Order

Phase A is the acceptance criteria made executable. Phase B is the generation engine. Phase C is the abstraction test. Phase D is the response to CERT's failure. Moves 4–10 from the audit wait until these have sealed results.

## What is not claimed

This plan does not produce general intelligence. It produces measurable answers to the four questions at the end of the audit: why NOVEL fails, whether missing abstractions can be synthesized, whether generation-first beats equal-budget enumeration, and whether a generated abstraction survives transfer.
