# NOMAD v0.10 — GENESIS: Predeclared experiment and results

**Research question.** Can a Bitwork-failure-state-conditioned production policy improve the search for verified Python expressions that are not reachable by v0.9's fixed one-edit operator vocabulary, while maintaining challenge/final correctness?

## Registered design

- Frozen synthesis and audit source hashes: [`experiments/FREEZE_V010.json`](../experiments/FREEZE_V010.json). Held-out evaluation seeds: `17011`, `17047`, `17101`; training seeds: `313`, `337`, `359`. Original plan [`PLAN_V010.json`](../experiments/PLAN_V010.json).
- The fixture author generates target outputs for 8 arithmetic expression structures. Four are training-only (`square_plus`, `sum_times_y`, `times_shift`, `shift_times_y`). Four structures are withheld from training (`difference_product`, `sum_times_x_shift`, `bilinear_plus`, `shifted_product`). Each evaluation seed contains 2 cases per withheld structure, giving **24 held-out tasks**.
- Every task starts from `def solve(x,y): return x+y`. Test fixtures include negative inputs, zero cases, and mixed signs. A public set of 12 input/output pairs is visible to search; 10 withheld challenges and 10 final examples are not accessible to the synthesis loop.
- The candidate grammar is `E := x | y | 0 | 1 | 2 | 3 | (E + E) | (E - E) | (E * E)`. Expression complexity is capped at 7 AST nodes; each task has at most 65,000 computed candidate output vectors. Results are compared with exact integer arithmetic.
- The CEGIS loop starts with three public examples. If a candidate fits the active subset but not the remainder of the **public** cases, the first public counterexample becomes active and the search restarts. The WITNESS challenge **cannot** become a search counterexample.
- Baselines: unchanged original v0.9 fixed one-edit generator (exhaustively enumerated), uninformed grammar enumeration, global witnessed operator prior, shifted-context negative control, and the contextual Bitwork policy. Prior training uses only WITNESS-supported, final-correct solutions on training-only tasks.
- Freeze means the candidate grammar, task families, seeds, budgets and thresholds are locked before the original canonical held-out run. Reproductions must write to separate destinations.

## Frozen outcomes

| Policy | Public passes | WITNESS-supported | Final correct | Mean candidate output-vector computations |
|---|---:|---:|---:|---:|
| v0.9 fixed one-edit | 0/24 | — | — | Five possible sources; all unreachable |
| Uninformed grammar | 24/24 | 24/24 | 24/24 | 6,693.00 |
| Global witnessed prior | 24/24 | 24/24 | 24/24 | 3,083.25 |
| Rotated-context control | 24/24 | 24/24 | 24/24 | 3,083.25 |
| **Bitwork-contextual witnessed prior** | **24/24** | **24/24** | **24/24** | **1,203.25** |

Contextual ordering saved **81.99%** of computed candidate vectors against uninformed enumeration and **60.97%** against global learning. The rotated-context control retained all trained operator totals but assigned them to different failure states; it lost the contextual advantage.

**Independent internal audit:** `96/96` selected programs independently interpreted from the AST; `0` result disagreements; `0` false WITNESS-supported outcomes; all candidate budgets respected. The reference auditor is a separate source implementation, but the test worlds were created by the same research package, not by an external evaluator.

**Real file execution:** eight generated Python repositories had their `solution.py` replaced by a newly synthesized function, then ran a real `python -m unittest discover -s tests` process, a WITNESS challenge and a separate final evaluation. These are not externally sourced GitHub issues.

## Negative experiments and constraints

1. **Public-only overfit trap:** when all visible rows make `x+y` indistinguishable from `x*x+y`, the cheapest public candidate is accepted by synthesis but contradicted by WITNESS. This prevents a false learned skill. The system does not quietly modify the hidden set to salvage the candidate.
2. **Visible counterexample:** a different public set starts with insufficient examples and later adds a discriminating case. GENESIS refines its search and finds the correct composition, without accessing WITNESS's challenge.
3. **Operator absence:** the v0.9 generator's complete candidate list from the initial source cannot match any public target in this study. That establishes a precise *fixed-vocabulary* limit, not novelty relative to all synthesis methods.
4. **Budget and syntax restrictions:** search refuses budget exhaustion and rejects function calls, imports, attribute accesses, arbitrary statements and unsupported operators.
5. **Learning ablation:** preserving global witnessed frequencies while shifting context keys increases candidate evaluations. This is evidence for the role of the compact observed failure state *in this dataset*, not proof of human-level reasoning.

## Scope / limitations

- Targets are integer arithmetic functions of exactly two named variables, with short expressions and fully specified public I/O examples. There is no natural-language specification understanding or open-ended patch generation.
- The grammar is hand-authored. NOMAD learns priorities **within** it; it does not invent the mathematical operators `+`, `-`, or `*`.
- Candidate vector evaluation is a proxy for inner-loop search work, not measured CPU, energy, wall time or economic cost. Grammatical prior training has a cost that is not included in per-task mean evaluation counts; end-to-end economics require subsequent experiments.
- WITNESS validation is a separate set of examples, but the research harness itself provides those examples and recomputes the readings. Integrity hashes are checksums, not adversarial authentication.
- Held-out families share arithmetic primitives and some algebraic structural similarities with training. This tests transfer to new compositions, not arbitrary programming paradigms.
- The prior uses NOMAD's existing Bitwork-style failure encoding, but **does not directly call the standalone BGR-v1.4 predictor**. Avoid claiming verified native BGR coupling.

## Reproduction

From the extracted root (Python 3.11+):

```bash
python scripts/verify_package_v10.py
python -m unittest discover -s tests -q
python scripts/audit_v10.py
python scripts/run_simulation_v10.py --output runs/reproduction-v010.json
python scripts/genesis_demo.py
```

Reproduction is deterministic in its scientific result data. Timings and Python-process resource use are not reported as fixed scientific outcomes. Never overwrite `results/study-v010.json` or existing receipt files.

## Next gate: CAUSAL ATLAS

Integrate typed synthesis with multi-file WORLD MODEL and INQUIRY. The next evaluation must predict blast radius and effects across modules using observed evidence, then show that synthesis improves *real* multi-file repairs against patch-only and discovery-only controls without leaking hidden validation outcomes.
