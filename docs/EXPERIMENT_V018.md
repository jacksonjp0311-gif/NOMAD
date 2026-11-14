# NOMAD v0.18 PLATFORM: experiments and negative results

The original BGR runtime executed on the Windows ROG, and the platform adds enforceable controls for supported execution paths. **This evidence does not establish a coding-intelligence advantage or production readiness.** Native BGR scored worse than the frequency-only control on the frozen historical replay. Native Docker containment remains **HOLD** because Docker and a reviewed image were unavailable for this run.

The authoritative final regression record is [`PLATFORM_FINAL_V018.json`](../results/PLATFORM_FINAL_V018.json), with its matching log. The earlier [`PLATFORM_QUALIFICATION_V018.json`](../results/PLATFORM_QUALIFICATION_V018.json) is an intermediate observation. Its counts must not replace the final record after later changes.

## Evidence and scope

| Record | What it establishes |
|---|---|
| [`PLAN_BITWORK_V018.json`](../experiments/PLAN_BITWORK_V018.json) | Frozen replay inputs, source digest, native runtime identity, controls, seed and budget |
| [`BITWORK_V018.json`](../results/BITWORK_V018.json) | Actual native predictor execution, historical public-outcome metrics and measured local costs |
| [`BITWORK_INITIAL_FAILURE_V018.json`](../results/BITWORK_INITIAL_FAILURE_V018.json) | Preserved failed adapter iteration and its correction |
| [`PLATFORM_QUALIFICATION_V018.json`](../results/PLATFORM_QUALIFICATION_V018.json) | Intermediate Windows regression and trusted native-language execution results |
| [`PLATFORM_FINAL_V018.json`](../results/PLATFORM_FINAL_V018.json) | Final inherited and new regression results; consult this record for final counts |
| [`NATIVE_ISOLATION_V018.json`](../results/NATIVE_ISOLATION_V018.json) | Actual containment prerequisite HOLD; its empty case list means no Docker containment probes ran |
| [`PLATFORM_ISOLATION_ITERATIONS_V018.json`](../results/PLATFORM_ISOLATION_ITERATIONS_V018.json) | Preserved platform-control development iterations |

The original research artifacts remain historical evidence. The v0.18 replay does not relabel old failures, rerun old outcomes as new independent observations, or convert public test passes into WITNESS acceptance.

## Baseline failures and regression progression

The first inherited regression run on this machine ran **170 tests in 69.213 seconds**, with **2 failures, 8 errors and 2 skips**. The raw baseline log was retained. The failures exposed a Windows fixture materialization problem: newline translation changed on-disk source bytes from the source identity recorded by the mission. Mission checks correctly refused those unexpected bytes. Writing the intended bytes directly repaired that portability defect.

The baseline also encountered Windows error 1314 when a test tried to create a symlink without the required privilege. That case remains an explicit native qualification HOLD when the privilege is absent. The missing `baseline/NOMAD-v0.16.0.zip` caused the inherited full-lineage assertion to fail. The desktop package explicitly documents this omission; it is not evidence that the current source is corrupt. The revised test skips only when the archive is absent and the compact-package notice documents that exact omission. If the archive is present, its original hash checks still run. Whole historical lineage remains **HOLD** until the complete predecessor is supplied and verified.

An intermediate platform run subsequently recorded **212 tests: 208 passed, 0 failures, 0 errors and 4 skipped**. Its skips were the inherited POSIX ownership test, the inherited POSIX process-group test, the unavailable full predecessor archive, and the Windows symlink-privilege case. Separate Windows tests cover native mission ownership and Job Object process cleanup. These intermediate counts describe that particular source state only. The final suite record named above supersedes them for final acceptance.

Generated trusted arithmetic programs also ran in Python, JavaScript and Rust during the intermediate qualification. Each produced the independently expected values `[7, 23, -1]` for `x*x+y`. This establishes execution of those reviewed native adapters. It does not qualify hostile repository execution on the host.

## Frozen native Bitwork replay

The input is the preserved [`FRONTIER_STUDY_V014.json`](../results/FRONTIER_STUDY_V014.json), with SHA-256:

```text
00846555f1d061dfc6136a8a5cd8f0f94d4ee2edfedd97a139140d64f7118dd6
```

The plan was frozen before this replay was measured. It uses **8 public execution observations from 2 training tasks**, then **20 recorded public observations from 4 evaluation tasks**. The evaluation task IDs are `affine-rectilinear`, `affine-vector`, `catalogue-names` and `confection-merge`. The nominal budget is **12 candidate attempts per task**. Models are not updated on evaluation outcomes. Each control uses the same available historical candidates and a stable original-order tie break. Three repetitions measure execution cost; they are not three independent research datasets.

The four controls are:

- **Cold:** fixed probability 0.5 and unchanged candidate ordering.
- **Frequency:** action-conditional Laplace counts from the training observations.
- **Native:** the preserved `bgr140.GovernedBitworkV14` runtime trained on the same chronological observations.
- **Shuffled:** the same native runtime with training outcome labels permuted using seed **18018**, while retaining the action sequence. This is a label-shuffle control, not a shuffle of whole evidence rows.

The binary actions retain the historical bridge's declared meaning: relational edit versus other expression/operator edit. No hidden WITNESS outcome or final-test result is supplied to these predictors. The reported label is only whether the historical public test passed.

The runtime's original manifest verified **77 files**, and its original archive has SHA-256:

```text
93177c5cc628ac0c6426d8c612c0d769b86ed53cbd7b2a3f872d2706c601a8c2
```

This is local integrity checking of preserved bytes, not authentication against an actor who can replace both trusted code and integrity records.

## Measured replay results

These values are copied from the recorded result. Lower log loss and Brier score are better.

| Control | Mean log loss | Mean Brier score | Mean rank of first public pass |
|---|---:|---:|---:|
| Cold | 0.6931471805599453 | 0.25 | 1.5 |
| Frequency | 0.42060709421822373 | 0.12122448979591835 | 1.0 |
| Native BGR | 0.48641297739326594 | 0.14964615314873903 | 1.0 |
| Shuffled native | 0.8482314975858793 | 0.3267002827751989 | 1.0 |

The mean rank is conditional on the **2 tasks whose recorded candidate pools contain a public pass**. The other 2 tasks contain no observed public-passing candidate, so their ranks are absent, not zero. Every control therefore has the same 2 tasks with an available historical public success. The shuffled control's matching rank also shows that this small rank statistic does not establish useful learning.

**Native BGR loses to the frequency control on both predictive scores.** Its rank matches the frequency and shuffled controls. The replay establishes an executable integration and records a negative comparison. It provides no basis for a coding-intelligence or repair-success advantage. The learning gate remains **HOLD** and `external_repair_advantage` remains `NOT_ESTABLISHED`.

## Measured cost and its limits

The replay ran on Windows 11 build 26200, AMD64, using Python 3.12.10. Values below are the stored means over the three cost repetitions, except allocation, which is the maximum recorded Python allocation peak.

| Control | Mean wall seconds | Mean process CPU seconds | Maximum traced Python allocation, bytes |
|---|---:|---:|---:|
| Cold | 0.0004656333476305008 | 0.0 | 3704 |
| Frequency | 0.0003725000036259492 | 0.0 | 3472 |
| Native BGR | 0.08256299999387313 | 0.07291666666666667 | 215252 |
| Shuffled native | 0.10171533333292852 | 0.08333333333333333 | 181692 |

The zero CPU readings for the fastest controls reflect the measurement resolution; they do not mean computation was free. The measured region includes model construction, training, counterfactual scoring and evaluation, with `tracemalloc` enabled. Native module loading and manifest verification occur before that timed region. These timings are not end-to-end application startup or repository repair latency.

`tracemalloc` reports traced Python allocation, not whole-system memory. The result also preserves Windows working-set samples after each arm; those are process samples from a shared process, not isolated per-arm peak resident memory. Hardware load and instrumentation can affect the timings.

There were **0 cloud-model calls**, **0 USD of API charges**, and no GPU use in this benchmark. Energy in joules and local electricity cost were **not measured** and remain `null`. No energy saving, GPU performance, total operating-cost saving or production throughput claim follows.

## Preserved failed native integration iteration

The initial targeted run contained 20 tests and produced **3 errors** with `RuntimeError: observation pending`. The adapter had tried to predict two counterfactual actions on the same stateful BGR object. The original predictor reserves a pending observation after `predict`; another prediction before `observe` violates its contract.

The correction scores each counterfactual action on a separate deep copy of the trained predictor. It neither supplies invented outcomes nor changes the preserved runtime. The initial failure is retained in [`BITWORK_INITIAL_FAILURE_V018.json`](../results/BITWORK_INITIAL_FAILURE_V018.json). Later targeted tests passed, and the final regression record supplies the final validation result.

## Evidence admission and the Catalogue negative case

Native ranking has no acceptance authority. Evidence must come from the trusted controller's independent observation path. Duplicate source/candidate observations and reused receipts cannot multiply support or renew expiry. Contradictory reports about the same source/candidate exclude that observation. Stale and future observations are ineligible. Persisted checksums detect changed records but are not signatures.

The arithmetic mission's optional `genesis-vs-ast` action scope distinguishes GENESIS synthesis from registered AST transformations. It starts cold without eligible observations in that scope. Historical relational-edit evidence is rejected when supplied to that scope. Tests show that the original native predictor can change an enumerated candidate ordering when supplied matching evidence; no prospective mission-level gain has been established.

MNEMONIC retains its distinct role and skill-admission boundary. Replaying a receipt at a later capture epoch, or relabelling the same source as another task, cannot refresh positive support. Distinct task labels alone do not establish independent sources. Genuine contradictory receipts, including those captured in the same epoch, remain visible and cause abstention. A stored preference never authorizes skipping fresh final validation or promoting a skill.

The v0.14 Catalogue failure remains a permanent regression: a conjunction change in namespace handling could pass incomplete upstream tests while violating the additional namespace contract. Both the inherited regression and the new platform regression require that bad patch to be rejected by the independent contract. Its preservation is separate from the historical `catalogue-names` replay row. An ordinary public test pass cannot erase this negative finding or establish broader correctness.

## Containment and recovery interpretation

`NATIVE_ISOLATION_V018.json` records `docker_binary_present=false`, no configured reviewed image, an empty probe list and **HOLD**. No native Docker attack, isolated repository repair or isolated interruption/restart result is claimed from that record. Fail-closed refusal and mocked driver tests establish software contracts; they do not substitute for the missing native containment experiment.

Mission tests exercise source-bound execution receipts, independent bounded arithmetic WITNESS and final observations, rollback, durable interruption checkpoints, ownership and uncertain-dispatch refusal. These controller tests do not prove isolated execution on this host. Unknown external effects remain blocked until independently reconciled; the local ledger does not claim distributed exactly-once delivery.

## Reproduction

From the source package, run the frozen replay into a new result path. The script refuses to overwrite a prior result or accept a changed plan/input/runtime identity.

```powershell
py -3 -B scripts\benchmark_platform_v18.py --plan experiments\PLAN_BITWORK_V018.json --output runs\replay\bitwork-v018.json
py -3 -B -m unittest tests.test_platform_bitwork_v18 tests.test_mnemonic tests.test_recursion_v15 -v
py -3 -B scripts\study_platform_v18.py --output runs\qualification\platform-new.json
py -3 -B scripts\qualify_isolation_v18.py --output runs\qualification\isolation-new.json
```

Without a reviewed digest-pinned local image, the last command records HOLD without executing repository code. Native qualification with such an image uses the script's `--image` argument and must retain its actual result, including any failure. Do not regenerate the archived plan to conceal a changed input, or overwrite negative results to obtain a cleaner report.

## Remaining research gate

The replay uses outcomes that existed before the new adapter was designed. Freezing a retrospective replay does not make it a prospective held-out study. The candidate pools were truncated by prior search policies and exclude unexecuted repairs. The defects in the original FRONTIER corpus were evaluator-injected into independently authored packaged code, not newly resolved authentic upstream bug reports. There are too few tasks to support a generalization or significance claim.

The next learning experiment needs fresh independently selected tasks, frozen matched search budgets, real permitted execution, separate final validation, independence controls and complete failed outcomes. It must compare cold, frequency, native and declared shuffled controls on actual accepted repairs and cost. Until then, verified native execution is an engineering result; an intelligence advantage remains unproven.
