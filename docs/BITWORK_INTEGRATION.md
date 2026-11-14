# Bitwork Integration Strategy — NOMAD v0.2

NOMAD exists to make the Bitwork research program operate on software.

## What is already Bitwork-native

v0.2 now implements a genuine temporal evidence loop:

```text
program state -> action -> execution outcome -> new compact state -> next action
```

The current contextual learner is still a small Bayesian-style operator policy rather than the full BGR temporal engine, but the interface boundary is now stable enough to define a direct bridge without inventing arbitrary bit meanings.

## Why code operators are not BGR action bits

BGR v1.4's present interface is a binary temporal predictor. NOMAD has several distinct transformation families. Encoding `root_operator`, `constant`, `variable`, and so on directly as arbitrary binary sequences would make the representation depend on our encoding choice instead of the software evidence.

The bridge should instead operate one level above individual mutations.

## Proposed binary control experiment for v0.3

At each repair state, BGR chooses between two real meta-actions:

- `0 = exploit`: continue expanding the best currently supported local repair region;
- `1 = explore`: return to a structurally different frontier region / broaden evidence collection.

A delayed binary outcome can represent whether the meta-action produced preregistered forward progress within the next `k` executed candidates.

This makes the BGR question meaningful:

> Given the recent sequence of repair decisions and outcomes, when should NOMAD keep exploiting a repair hypothesis and when should it deliberately move elsewhere?

## Required comparison

A future direct-coupling study should freeze tasks and compare:

1. fixed frontier policy;
2. NOMAD contextual operator policy;
3. BGR meta-controller with non-contextual operator policy;
4. hierarchical NOMAD + BGR.

The bridge is promoted only if it improves a registered objective such as executed candidates, test runs, CPU time, or solve rate while preserving withheld challenge correctness.

## Authority boundary

BGR may influence search allocation. It cannot certify a patch or promote a skill. Those remain verification-plane responsibilities.


## v0.9 INQUIRY integration boundary

INQUIRY builds on the Bitwork *research method* of compact evidence, transformations and observation updates, but **does not directly execute the standalone BGR v1.4 runtime**. Its fault posterior and query likelihoods are local Python implementations. A direct BGR adapter must be bench-tested on identical frozen tasks, with identical cost budgets, before labeling this release native BGR inference. WITNESS acceptance remains unchanged and cannot be overwritten by a model suggestion.


## v0.10 GENESIS integration checkpoint

GENESIS uses the actual `nomad.bitstate.encode_failure` function from the earlier NOMAD research lineage, rather than an invented `operator_id` bit. It then uses WITNESS-trained `ContextualOperatorLearner` probabilities to order safe AST productions. The frozen comparison tests whether this observed state helps search versus global and context-shuffled controls.

**Not claimed:** direct integration with the standalone BGR v1.4 temporal inference runtime. A native adapter and matched-budget ablation must precede that claim. WITNESS remains separate from every learning/expansion policy.
