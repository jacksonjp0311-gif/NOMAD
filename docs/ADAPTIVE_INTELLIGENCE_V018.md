# Adaptive computation: measured results and limits

NOMAD now has a bounded computation selector in [`nomad/adaptive.py`](../nomad/adaptive.py). It chooses frequency, the original conventional temporal ensemble, or the preserved native Bitwork predictor. It can abstain when its available computation budget is exhausted. Selection changes actual computation: inactive temporal/native learners are neither forecast nor updated in the background. They catch up on previously observed public history only when selected, and that reconstruction is charged.

The existing negative result remains authoritative: native log loss 0.4864129774 versus frequency 0.4206070942, with identical candidate ordering. The earlier 32-stream experiment also remains unchanged: native mechanisms helped designed temporal relationships, lost on stationary data and used substantially more computation. This new study asks whether selecting when to pay that cost helps. It does not assume that selection will succeed.

The [new mechanism plan](../experiments/PLAN_ADAPTIVE_MECHANISMS_V018.json), payload SHA256 `f92d8687b27a6ec7a1f114283ae75ed6f7b21a7edfd52e6d79371bb24227be48`, and its implementation were committed at `e2cd77c03848ce13d9fe31bf32cca383835ae3b3` before held-out generation. The [source-bound development recheck](../results/ADAPTIVE_DEVELOPMENT_RECHECK_V018.json) supplied calibration. These are local source commitments, not authenticated proof against a hostile machine owner.

The measured controller reduced CPU relative to always-on native Bitwork, but its predictive loss worsened beyond the registered tolerance. It improved prediction over frequency while using more CPU, and the conventional temporal learner was both more accurate and cheaper. **None of the three registered combined quality-and-cost criteria passed.** These negative results remain frozen; no parameters were retuned after evaluation.

## Primary evaluation

All 512 registered trials completed with unchanged source: eight modes, eight regimes and eight seeds. They contain 65,536 forecasts, of which 49,152 were scored. The [primary result](../results/ADAPTIVE_MECHANISMS_V018.json) recorded 311.7933146000141 seconds wall and 280.640625 seconds CPU including Job subtrees and harness; 0.71875 CPU seconds were unallocated orchestration/analysis overhead. Final receipt serialization is outside that timer.

The [independent audit](../results/ADAPTIVE_INDEPENDENT_AUDIT_V018.json) recomputed raw forecast loss, Brier score, calibration error, input matching, output hashes, native/supervisor CPU arithmetic, paired seed blocks, bootstrap intervals and all nine Holm decisions. Its [negative audit tests](../results/ADAPTIVE_AUDITOR_REVIEW_V018.json) rejected ten altered receipts.

An [unchanged-source replay](../results/ADAPTIVE_MECHANISMS_REPLAY_V018.json) completed another 512 trials on exactly the same registered streams. The [independent replay comparator](../results/ADAPTIVE_REPRODUCIBILITY_V018.json) matched all 65,536 forecasts, choices, input hashes, final state hashes, operation counts and predictive metrics exactly. This adds no independent seeds. Confirmatory cost conclusions use the primary run only; independent auditing and light analysis ran concurrently with parts of the replay, so replay timings are not a second controlled cost experiment.

These means are over 64 streams per arm. CPU includes the worker Job plus supervisor; wall spans each complete supervised trial.

| Mechanism arm | Log loss | Brier | ECE, ten bins | CPU seconds/trial | Wall seconds/trial |
|---|---:|---:|---:|---:|---:|
| A: Frequency | 0.623104 | 0.219114 | 0.101269 | 0.383301 | 0.442131 |
| B: Always-on native | 0.488690 | 0.160760 | 0.089835 | 0.674072 | 0.736594 |
| C: Conventional temporal | 0.532840 | 0.179003 | 0.093278 | 0.463623 | 0.526595 |
| D: Adaptive | 0.548275 | 0.185936 | 0.106321 | 0.528320 | 0.586575 |

Adaptive used 21.62% less CPU than always-on native, 37.83% more than frequency and 13.95% more than temporal. The in-worker algorithm/instrumentation interval averaged 0.150391 CPU seconds for adaptive, 0.300781 for native, 0.011230 for frequency and 0.096191 for temporal. That interval includes initialization, looping, snapshot/metric construction and process-memory observation. The complete process accounting makes clear that startup, verification and transport are material parts of this small-task benchmark.

The following paired differences are adaptive minus comparator. Intervals are descriptive paired seed-block bootstrap intervals, not additional significance tests.

| Comparator | Mean log-loss difference [95% interval] | Mean CPU-second difference [95% interval] | Combined registered criterion |
|---|---|---|---|
| Native | +0.059586 [0.045451, 0.072505] | −0.145752 [−0.187012, −0.116699] | Failed |
| Frequency | −0.074829 [−0.085346, −0.065011] | +0.145020 [0.131104, 0.159424] | Failed |
| Temporal | +0.015436 [0.008153, 0.022056] | +0.064697 [0.048096, 0.082520] | Failed |

CPU reduction versus native, and objective improvement plus the shifted quality criterion versus frequency, each won all eight seed blocks with one-sided p=0.00390625 and passed Holm correction. Native quality failed the 0.02-nat criterion on all eight blocks. The other registered tests did not pass. In particular, the chosen cost penalty does not turn reduced CPU into an overall improvement when predictive quality degrades too much.

Family results are descriptive:

| Regime | Frequency loss | Native loss | Temporal loss | Adaptive loss |
|---|---:|---:|---:|---:|
| Stationary | 0.476975 | 0.490772 | 0.488776 | 0.476975 |
| Previous-outcome dependency | 0.714604 | 0.287667 | 0.348956 | 0.349088 |
| Delayed action relationship | 0.707270 | 0.394498 | 0.669728 | 0.660154 |
| Distribution shift | 0.778083 | 0.626558 | 0.620134 | 0.755338 |
| Sparse/noisy | 0.289732 | 0.295394 | 0.296625 | 0.289732 |
| Misleading temporal relationship | 0.680755 | 0.506223 | 0.528671 | 0.538299 |
| Held-out-only structure | 0.633035 | 0.595761 | 0.602854 | 0.612003 |
| Irreducible fair coin | 0.704377 | 0.712645 | 0.706975 | 0.704614 |

The ablations were also completed, with descriptive mean loss/CPU seconds: no-history 0.623104/0.387207; no-structure 0.531644/0.737793; no-selector-memory 0.586305/0.504395; fixed-native/no-selection 0.488690/0.695068. Removing the structural screen improved prediction but spent more CPU; retaining selector utility improved prediction over resetting it but also cost more. These comparisons do not establish persistent cross-repository memory value.

## Why the adaptive policy failed its combined objective

The [posthoc decomposition](../results/ADAPTIVE_DIAGNOSIS_V018.json) is computed from frozen traces without running new predictors. All 8192 adaptive forecasts exactly match the corresponding existing learner on the same observed prefix: 6016 frequency, 1408 temporal and 768 native forecasts. Lazy reconstruction introduced no forecast approximation. Among 6144 scored adaptive forecasts, frequency choices contributed +0.042667 nats to the mean loss gap versus native, temporal choices +0.016918, and native choices zero.

The strongest failure was the delayed regime. The [delayed-trace review](../results/ADAPTIVE_DELAYED_TRACE_REVIEW_V018.json) shows the same pattern on seven of eight seeds: native exploration begins at zero-based step 32, then the controller returns to frequency at step 48. Its first 16-event native gain ranges from −0.034606 to +0.027070, below the frozen risk/cost threshold. That estimate remains unchanged while native is inactive, and the estimated cost of catching up grows. At step 96, least-observed exploration selects temporal instead. The separately measured native arm then shows substantial later advantage that the earlier controller could not know. This identifies a short credit-assignment horizon and stale utility estimate in the observed decisions; it is not evidence that changing those rules after seeing these streams would generalize.

Distribution-shift handling also under-allocated temporal computation: 688 of 768 scored forecasts in that regime used frequency. The structural screen's local contingency evidence did not reliably justify timely exploration. In stationary and sparse/noisy streams, frequency was selected for every forecast and matched the simpler baseline exactly.

Direct adaptive timing totals across 64 streams were 0.126005 seconds for decisions, 0.031648 for observation bookkeeping, 4.678543 for lazy model construction, 2.911799 for catch-up and 1.418279 for selected prediction/update work. Catch-up processed 4336 historical observations; 33 native and 30 temporal objects were built. Timed decision arithmetic was small, but initialization and replay were substantial. The complete measured algorithm and process costs also include uninstrumented checks, shared input generation, trace recording and serialization. The controller cannot claim efficiency by reporting decision arithmetic alone.

Mean native Job high-water counters were 27,249,216 bytes for adaptive, 27,456,768 for native, 26,835,840 for frequency and 26,860,928 for temporal. Adaptive's largest Job counter was 28,491,776 bytes; the parent's separate lifetime peak working set was 57,688,064 bytes. These are measured counter values, not a proved reduction in strict simultaneous committed peak memory.

A future prospective mechanism study should test longer evaluation credit windows or renewed exploration of previously unpromising mechanisms, using new untouched seeds and preregistered costs. The present data must not be reused as unseen validation. Authentic coding benefit still requires the separately qualified repository experiment.

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

# Exact frozen-study reproduction; retain a distinct output and audit it.
py -3 -B scripts\experiment_adaptive_v18.py run --plan experiments\PLAN_ADAPTIVE_MECHANISMS_V018.json --confirm-preregistered-evaluation --output runs\adaptive-replay.json
py -3 -B scripts\verify_adaptive_replay_v18.py --plan experiments\PLAN_ADAPTIVE_MECHANISMS_V018.json --original results\ADAPTIVE_MECHANISMS_V018.json --replay runs\adaptive-replay.json --output runs\adaptive-replay-audit.json
```

Evaluation is a prospective one-time source-bound experiment. Altering its code, generator, calibration rule or acceptance after examining held-out outcomes requires a new study; the exposed outcomes cannot become unseen again.
