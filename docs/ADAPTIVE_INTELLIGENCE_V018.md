# Adaptive computation: registered mechanism study

NOMAD now has a bounded computation selector in [`nomad/adaptive.py`](../nomad/adaptive.py). It chooses frequency, the original conventional temporal ensemble, or the preserved native Bitwork predictor. It can abstain when its available computation budget is exhausted. Selection changes actual computation: inactive temporal/native learners are neither forecast nor updated in the background. They catch up on previously observed public history only when selected, and that reconstruction is charged.

The existing negative result remains authoritative: native log loss 0.4864129774 versus frequency 0.4206070942, with identical candidate ordering. The earlier 32-stream experiment also remains unchanged: native mechanisms helped designed temporal relationships, lost on stationary data and used substantially more computation. This new study asks whether selecting when to pay that cost helps. It does not assume that selection will succeed.

## Controller and objective

Every 16 observed events, the controller compares a bounded utility estimate. For mechanism \(m\), it uses the latest 128 available paired public log-loss gains against its own action-conditional frequency forecast. Gains are clipped to [-8, 8] for selection only; reported predictive loss is not clipped. Only selected mechanisms receive these observations. There is no fabricated counterfactual native outcome and no continuously running expensive shadow model.

The selection approximation is

\[
S_m=\bar g_m-\lambda\left[\frac{\hat c_{m,\mathrm{setup}}\,1_{\mathrm{not\ resident}}+\hat c_{m,\mathrm{step}}(B+d_m)}{B}-\hat c_{\mathrm{frequency},\mathrm{step}}\right]
-\mu\left[\frac{s_m}{\sqrt{\max(1,n_m)}}+\frac1{\sqrt{4+n_m}}\right].
\]

Here \(B\) is the next block length, \(d_m\) is actual pending replay work, and \(n_m\) is the available quality-observation count. Frequency's relative gain and risk term are zero. The registered weights are \(\lambda=2\), \(\mu=0.15\). Setup and step costs are fixed development measurements; noisy live clocks cannot change decisions. Actual initialization, original runtime integrity verification, inference, updates, replay, feature screening and controller overhead remain part of measured runtime cost.

This is an experimentally testable heuristic, not an optimal-computation theorem or a confidence guarantee. Selective feedback and distribution changes can bias its estimates. A positive public prediction gain is not proof that invoking the mechanism caused an independently correct repair.

The inexpensive structural screen examines 16 conditional contingency tables: past action or outcome at lags 1–8, conditioned on the current action. It uses at most 64 past observations and the score

\[
\max_Z\widehat I(Y;Z\mid A)-[\log n+\log(16)]/n.
\]

After at least 32 observations, a score above 0.015 can permit exploration. At most one exploration block occurs per four decision intervals. The screen prioritizes a least-observed eligible mechanism; a longer lag breaks a tie toward native Bitwork. It supplies neither a forecast nor a causal certificate. The no-structure ablation explores on the same bounded schedule without that screen.

All original predictors are accessed through the verified BGR loader. The controller does not reimplement the native learner. Frequency uses two Beta(1,1) counts; temporal uses the original `GrammarEnsemble`; native uses unchanged `GovernedBitworkV14` defaults. The native learner's own grammar and lag discovery remain intact.

Snapshot restoration preserves settled public history, utility evidence, decision indices and previously recorded decisions. It does not pretend that a live native object survived a restart. A new decision after restart includes initialization and full historical reconstruction debt and can therefore differ from an uninterrupted decision. The mission runtime reuses an already durable decision rather than making it again.

## Registered study

[`scripts/experiment_adaptive_v18.py`](../scripts/experiment_adaptive_v18.py) compares eight modes: frequency, always-on native, conventional temporal, adaptive, and four adaptive ablations. No-history permits frequency only; no-structure removes the contingency screen; no-memory resets selector utility history at each decision while retaining predictors' public histories; no-selection fixes the native choice while retaining controller bookkeeping. The no-memory arm is not a persistent MNEMONIC transfer experiment.

Eight regimes cover stationary data, previous-outcome dependence, delayed action dependence, a distribution shift, rare actions with noisy outcomes, a temporal relationship that later disappears, a previously untested temporal combination, and an independent fair coin. “Sparse” means rare action support, not missing outcome labels. The held-out-only combination is current action XOR (outcome at lag two AND action at lag five), with registered noise. Its outcomes are excluded from development; its generator is deliberately designed and known, so this is not an independently authored discovery task.

One development seed is used for seven regimes. All development receipts, including failed validation attempts, are preserved. Eight disjoint evaluation seeds are registered for all eight regimes. Every arm receives the same stream for a seed/regime and predicts before the next outcome is drawn. Each stream has 128 events; the first 32 are unscored, followed by 96 prequential forecasts. The predictor receives no family name, seed or future observation. Evaluation order is shuffled using a separate fixed schedule seed, including arm order within each seed/regime group.

Cost calibration is mechanical: arithmetic means of development baseline initialization wall time and full-loop wall time divided by 128. The selector uses these frozen runtime estimates. The evaluation cost objective separately uses measured whole-process CPU, including supervision. Neither cost measurement is inferred from log loss.

The independent statistical unit is a seed block, averaging its eight regimes. The 64 regime/seed streams are not treated as 64 independent samples. For adaptive versus native, frequency and temporal, the protocol registers three directional criteria: cost-penalized loss improvement, a 0.02-nat margin-shifted quality sign criterion, and lower total CPU. The nine exact one-sided paired sign tests receive Holm correction at alpha 0.05. A comparator passes the complete registered quality/cost criterion only if all three tests pass. The cost-penalized endpoint is log loss plus \(2\times\mathrm{total\ CPU}/128\). This uses CPU for all observations, including the unscored training prefix.

The shifted-margin sign test concerns directional seed-block evidence; it does not establish equality of population means or unrestricted correctness. Paired bootstrap intervals resample eight seed blocks 4000 times with a fixed registered seed and are descriptive. Family tables, calibration diagnostics and unregistered ablation comparisons are descriptive. Predictive quality includes natural-log loss, Brier score and ten fixed-bin expected calibration error.

## Complete computation accounting and limits

Each arm/regime/seed is a new trusted subprocess tree under a Windows Job. Limits are 30 seconds wall, 512 MiB configured Job memory and four processes. CPU is measured; an independent CPU-time kill limit is not claimed. These are trusted authored generators and verified native code, not unfamiliar repository code and not evidence that native repository containment is qualified.

Per-trial CPU is the Job's user plus kernel CPU **plus** parent supervisor CPU. It includes worker startup, imports, native integrity verification and initialization. Algorithm-only initialization/loop timings and adaptive decision, bookkeeping, native build and catch-up timings are also retained, so process startup cannot silently hide inside or disappear from a predictive-efficiency claim. Unallocated harness and analysis CPU is reported separately. Final JSON serialization is outside the recorded run timer.

Worker-process peak working set and native Job high-water counters are reported separately from the parent harness's lifetime peaks. They are not added: independent process peaks need not occur simultaneously. The native commit counters can include attempted charges on this Windows build; strict committed-memory peak qualification remains HOLD. Microsoft's [process-counter definition](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters) distinguishes working-set and commit counters. No energy, GPU saving or electricity cost is measured.

Every attempted trial is retained. A raised execution failure records its identity and observed parent cost; unknown worker CPU stays null and total CPU remains incomplete, with an explicitly labeled measured lower bound. Failed or missing arms prevent complete paired assessment. Calibration admission checks the exact development inventory, source stability, complete native receipts, output hashes and recomputed metrics/cost summaries. Checksums detect changed local records; they do not authenticate a hostile host administrator.

The first 56-trial development execution completed, but calibration intake reconstructed LF output while Windows emitted CRLF. The original result and [validation failure](../results/ADAPTIVE_DEVELOPMENT_VALIDATION_FAILURE_V018.json) remain preserved. The transport reconstruction was corrected, and a new source-bound development calibration is required before evaluation. No policy threshold or quality parameter was tuned from held-out outcomes.

## Coding transfer boundary

The optional mission integration uses this controller to allocate actual existing planning, probing, synthesis, ranking and retrieval work. Durable public observations may update within-task evidence. Cross-mission admission requires independently accepted provenance; numeric utility comes from public forecasts and outcomes, never hidden final labels. A final acceptance verdict authorizes admission but is not a numeric training target. WITNESS retains authority.

The original real-repository A/B/C/D comparison remains unchanged. Any adaptive repository arm is separately registered. Authentic repair, cross-repository learning transfer and complete controller-plus-container cost accounting remain unproved while corpus and native prerequisites are absent. A synthetic mechanism result cannot pass those gates or authorize promotion.

To reproduce after checking the frozen source and registered environment, use new output paths:

```powershell
py -3 -B scripts\experiment_adaptive_v18.py develop --output runs\adaptive-development.json
py -3 -B scripts\experiment_adaptive_v18.py freeze --calibration runs\adaptive-development.json --output runs\adaptive-plan.json
py -3 -B scripts\experiment_adaptive_v18.py run --plan runs\adaptive-plan.json --confirm-preregistered-evaluation --output runs\adaptive-result.json
```

Evaluation is a prospective one-time source-bound experiment. Altering its code, generator, calibration rule or acceptance after examining held-out outcomes requires a new study; the exposed outcomes cannot become unseen again.
