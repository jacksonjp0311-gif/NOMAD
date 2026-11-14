# NOMAD v0.7 — CAUSAL SKILLS / CODEWORLD experiment

## Question

Can WITNESS-bound repair outcomes be converted into conservative applicability rules that reduce search on unseen repository fixtures **without increasing false skill application**, and can the resulting learner drive a real file-edit + unittest loop?

## Hypothesis

A transformation family conditioned on a learned conjunction of observable code/execution predicates will require fewer candidate attempts than fixed or global-frequency ordering while preserving final correctness. Counterexample evidence should narrow the learned rule and cause abstention outside its observed validity envelope.

## Evidence partitions

Every solvable CODEWORLD task has:

- four public examples used by search;
- three challenge examples visible only to WITNESS after a candidate is proposed;
- three final examples invisible to search and WITNESS.

The integration gate also materializes `solution.py` and `tests/test_public.py` and launches the public unittest suite in a separate Python process.

## Training

Three deterministic seeds are used. Each training set contains five examples per supported repair family plus unsupported boundary counterexamples. `CausalSkillRegistry` accepts observations only through valid WITNESS receipts.

A rule is promoted only when:

- at least four supported observations match;
- no witnessed negative observation matches;
- its preconditions are a conjunction of at most three supplied predicates.

## Evaluation

Registered repair families:

- binary operator;
- constant adjustment;
- comparison;
- zero guard;
- unknown identifier;
- return negation.

Unsupported boundary cases include power-expression, comparison-to-numeric, nonlinear constant, unresolved identifier, alternate zero semantics and negation-plus-offset tasks.

## Frozen result

Across seeds 17, 29 and 41:

- registered evaluation tasks: **54**;
- causal final correctness: **54/54**;
- fixed mean attempts: **1.8888888889**;
- global mean attempts: **1.8888888889**;
- causal mean attempts: **1.3888888889**;
- causal attempt reduction vs fixed: **26.4705882353%**;
- causal attempt reduction vs global: **26.4705882353%**;
- causal skill predictions: **54**;
- false causal skill predictions: **0**;
- unsupported tasks: **18**;
- causal abstentions on unsupported tasks: **18/18**.

Separate file/test integration:

- repositories: **6**;
- public unittest process passed after repair: **6/6**;
- WITNESS-supported: **6/6**;
- final hidden-correct: **6/6**.

## Interpretation

This is evidence that a conservative, witnessed precondition learner can improve search within this generated repair family while preserving abstention on explicitly represented boundary counterexamples.

It is **not** evidence of arbitrary causal program understanding. The predicate vocabulary and operator vocabulary are supplied, training and evaluation share the same fixture generator, and the repositories are intentionally small.
