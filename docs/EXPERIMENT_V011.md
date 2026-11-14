# NOMAD v0.11 — CAUSAL ATLAS: experimental report

**Program:** Bitwork-derived evidence-guided self-coding research  
**Release:** 0.11.0  
**Research steward:** James Paul Jackson  
**Study type:** generated Python multi-file interventions, not third-party repository evaluation.

## Hypothesis and measures

A repository import graph is an overapproximation of consequence propagation. A symbol-call graph improves specificity, but can still overpredict change when a caller cancels the effect of an invoked function. We test whether a learner trained on **witnessed before/after interventions** can distinguish such situations on new, name-randomized fixtures.

For function-change intervention \(\tau\), contract \(t\) and input set \(X_t\):

\[
Y_{t}^{\rm before}=f_t^{\rm original}(X_t),\quad
Y_{t}^{\rm after}=f_t^{\tau}(X_t),\quad
I_t(\tau)={\bf1}[Y_{t}^{\rm before}\ne Y_{t}^{\rm after}].
\]

The label is **measured behavioral impact on specified finite inputs**, not proof of a semantic causal model for arbitrary inputs or environments. A hand-engineered AST feature signature includes import/call reachability, call depth, zero multiplication, cancellation and a conditional-expression indicator. The learner estimates \(P(I_t=1\mid\phi)\) using Laplace-smoothed witnessed counts; it abstains on dynamic/unknown paths and insufficient samples.

## Methods

- **Training:** 16 independently generated multi-file fixtures at seeds **907 and 947**, four arithmetic target families, two cases per family/seed. For each training world, an independent code intervention changes its shared function from `x+y` to `x*y+y`. The learner receives only the observed before/after output comparison and structural feature signature; no evaluator fault-family or filename features.
- **Held out:** the post-amendment seed set **5513, 5563, 5611**. 24 new repositories, nine public contracts each, 216 observable consequence labels.
- **Controls:** import-only connectivity; direct-call graph without learned effect boundaries; a deliberately shuffled association between training features and observed impact labels.
- **Isolation:** each fixture is authored and executed in a temporary directory. The separate audit launched two isolated Python processes per repository. This is a trusted-fixture laboratory; Python's normal interpreter is not a security sandbox.
- **Unknown code paths:** dynamic name lookups yield an explicit abstention. No such result is presented as a safe test to skip.
- **Coding integration:** four separate generated multi-file repositories; GENESIS synthesizes `solve(x,y)` expressions from visible input/output examples, WORLD MODEL-style dependency prioritization ranks candidate files, the source is physically edited, real `unittest` runs, then WITNESS and separate withheld final examples check the outcome.

### Registered result

| Method | Contracts classified | TP | FP | FN | TN | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Import-only | 216 | 120 | 72 | 0 | 24 | 0.7692 |
| Direct-call graph | 192 | 96 | 48 | 0 | 48 | 0.8000 |
| Shuffled evidence | 192 | 48 | 24 | 48 | 72 | 0.5714 |
| **CAUSAL ATLAS** | **192** | **96** | **0** | **0** | **96** | **1.0000** |

**24 dynamic contracts were abstentions** for CAUSAL ATLAS, direct-call and shuffled models. F1 is calculated only on classified examples. The learned model had no observed false positives or false negatives among the 192 classified contracts. These numbers are not a broad generalization claim: the generated grammar and the feature engineering make the underlying distinction unusually tractable.

### Small actual-code integration

| Policy | Final-correct | Files visited | Candidate vectors evaluated |
|---|---:|---:|---:|
| Flat file order + identical GENESIS | 4/4 | 7 | 28,191 |
| Call-graph guided file order + identical GENESIS | **4/4** | **4** | **17,664** |

Search cost fell **37.34% by candidate-vector count** and **42.86% by file visits** in four small matched tasks. This comparison is between the two multi-file integration policies, *not* a measured 37% CPU/energy reduction or a comparison with conventional coding agents. All four graph-guided repairs used actual Python `unittest`, WITNESS challenge, and final evaluation; the synthesis grammar is inherited unchanged from v0.10.

## Failed audit precheck and correction

The first heldout run (seeds **4321, 4357, 4397**) was completed before an audit problem emerged. The initial independent-process audit had **30 mismatches out of 216 checks**. The suspected cause was stale timestamp-based Python bytecode (`.pyc`) when changing a source file within a filesystem timestamp tick. This is an audit harness issue, not a demonstrated model failure, but the study was **demoted to a precheck** rather than called independently audited.

The first audit report is preserved at [`results/AUDIT_V011.json`](../results/AUDIT_V011.json). The corrected independent subprocess auditor disables Python bytecode writes with `-B`, and a new **post-amendment evaluation seed set** was registered and source-locked before execution. See [`experiments/AUDIT_AMENDMENT_V011.json`](../experiments/AUDIT_AMENDMENT_V011.json), [`experiments/PLAN_V011_RELEASE.json`](../experiments/PLAN_V011_RELEASE.json), and [`experiments/FREEZE_V011_RELEASE.json`](../experiments/FREEZE_V011_RELEASE.json).

The final evaluation produced **216 effect records**, independently replayed through **48 Python child processes** in three seed-scoped audit batches. Every batch is cryptographically digest-bound to its exact study fragment. Every numerical before/after contract outcome agreed with its saved record. [Aggregated audit](../results/AUDIT_V011_RELEASE.json).

The freeze covers the learning engine and experimental source. The package version declaration was updated after the freeze as release metadata; the release verifier checks that it differs only by the expected version string. No frozen learner or benchmark generator was modified after the final source lock.

## Limitations

1. Python-only, shallow generated module graphs; known library API `solve(x, y)`; finite arithmetic operations and explicitly designed impact patterns.
2. Feature design is human-specified. NOMAD learns feature-to-impact association, not a novel general representation of software causation.
3. No full external code execution sandbox; do **not** feed untrusted third-party repositories into this in-process interpreter.
4. No broad performance claim from four multi-file integration tasks. File visits and candidate-vector counts are search proxies, not wall-clock or physical energy.
5. The witnessed receipt is a content checksum, not a signature or trust root. WITNESS cannot certify arbitrary repository behavior from a finite set of tests.
6. The in-sample result of 192/192 conditioned decisions could fail under unseen call forms, mutation, side effects, aliases, concurrency or dynamic dispatch. Dynamic/unsupported cases require comprehensive validation, not blind skipping.

**Scientific interpretation:** CAUSAL ATLAS demonstrates a functional software consequence-learning prototype and clean interfaces between structural inference, typed synthesis, WITNESS and held-out tests under restricted laboratory assumptions. Its next gate is external repositories and stronger perturbation families.
