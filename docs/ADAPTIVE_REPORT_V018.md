# NOMAD v0.18.0 adaptive intelligence qualification

**The controller was implemented and evaluated. Its registered combined quality
and computational-cost target failed against all three controls. All four
platform gates remain HOLD. No v0.19 promotion or intelligence-breakthrough claim.**

This iteration started from clean, matching local and remote commit
`993395f500565a392f9f117485626cad11122b0b` on `v0.18-platform`. The baseline was
342 passed, zero failures/errors, four skipped. Its source archive and tracked
file hashes are preserved. The mechanism source and protocol were committed at
`e2cd77c03848ce13d9fe31bf32cca383835ae3b3` before evaluation started.
Plan payload SHA-256:
`f92d8687b27a6ec7a1f114283ae75ed6f7b21a7edfd52e6d79371bb24227be48`.
The [registration review](../results/ADAPTIVE_PREREGISTRATION_REVIEW_V018.json)
binds local Git objects and timestamps; it is not an external timestamp service.

## Implemented changes

- A bounded controller selects existing frequency, conventional temporal or
  preserved native BGR computation, with public prequential gain, frozen
  development costs, uncertainty penalties and bounded exploration. Expensive
  predictors are lazy; initialization and history replay are charged. No vendor
  runtime or historical experiment was rewritten.
- An optional function-mission policy chooses effort before GENESIS, changes
  candidate/probe ceilings and localization, selects actual ranking and memory
  recall after public probes, and can durably abstain. Existing original A/B/C/D
  definitions remain intact. A separately frozen E design is explicitly NOT RUN.
- Accepted public forecasts and search outcomes have bounded, source/runtime/
  journal-bound memory admission. Private final values are not numeric rewards.
  Expiry, repeated sources and replay cannot manufacture fresh independent support.
- Recovery recognizes durable computation choices and abstention. Failed or
  uncertain execution retains the existing cleanup and rollback requirements.
  Software tests use disclosed worker doubles; native coding recovery is absent.
- Corrected the repository reporter's use of a nonexistent serialized WITNESS
  `supported` member. It now counts challenge/final rejection from actual fields.
  No past native repository trial was affected because none has run.
- Added three pinned authentic upstream issue/source/license bundles, two exact
  parse-only projections, a bounded development-only self-revision nomination,
  immutable evidence checks, independent arithmetic/replay tools and deterministic
  source/runtime packaging. No authoritative self-revision was installed.

The detailed [controller mathematics](ADAPTIVE_INTELLIGENCE_V018.md),
[mission and memory specification](ADAPTIVE_MISSION_V018.md),
[architecture audit](ADAPTIVE_PIPELINE_AUDIT_V018.md), and
[native/corpus report](ADAPTIVE_NATIVE_AND_CORPUS_V018.md) state the exact limits.

## Registered mechanism experiment

The primary run completed **512 of 512 trusted Windows Job trials**, with eight
regimes, eight evaluation seed blocks and eight modes. Each trial predicted 128
observations, with a 32-observation unscored prefix. Every forecast preceded its
outcome draw; models received no seed, family label or future outcome. The
held-out-only structural combination was excluded from development. Its generator
was designed and known, so this is not an independently authored coding benchmark.

The complete primary run measured **311.793315 seconds wall**
and **280.640625 seconds CPU** across worker Job trees
and the harness. Final report serialization is outside that timer. Per-trial CPU
includes worker startup/imports/verification plus supervisor CPU. The following
means cover 64 trials per mode; lower loss, Brier, ECE and cost are better.

| Main arm | Log loss | Brier | ECE10 | Total CPU seconds/trial | Wall seconds/trial |
|---|---:|---:|---:|---:|---:|
| Frequency | 0.623104 | 0.219114 | 0.101269 | 0.383301 | 0.442131 |
| Always-on native Bitwork | 0.488690 | 0.160760 | 0.089835 | 0.674072 | 0.736594 |
| Conventional temporal | 0.532840 | 0.179003 | 0.093278 | 0.463623 | 0.526595 |
| Adaptive controller | 0.548275 | 0.185936 | 0.106321 | 0.528320 | 0.586575 |

Adaptive used **21.62% less CPU than
always-on native**, but lost 0.059586 nats of predictive quality on average.
The registered 0.02-nat quality tolerance failed in all eight seed blocks.
Its CPU reduction passed the Holm-adjusted test, but its objective and quality
criteria failed. The descriptive paired 95% interval for the loss difference was
[0.045451, 0.072505]; for CPU difference it was [-0.187012, -0.116699] seconds.

Against frequency, adaptive improved mean loss by 0.074829 nats and its
cost-penalized objective passed, but required 0.145020 more CPU seconds/trial.
Against conventional temporal, adaptive had 0.015436 worse loss and used
0.064697 more CPU seconds/trial. The temporal comparator therefore dominated
the adaptive policy on these aggregate descriptive means. The policy passed
**none of its three joint comparison criteria**. Nine preregistered one-sided
paired sign tests used Holm correction; the independent unit was eight seed
blocks, not 64 supposedly independent family streams. Bootstrap intervals are
descriptive and do not increase the sample size.

The original negative result remains unchanged: native BGR **0.4864129774**
versus frequency **0.4206070942**, identical candidate ordering. The newer
32-stream study is also intact. Different experiments have different data and
timing instrumentation; this study cannot retroactively convert either result
into a success or support a cross-study speedup claim.

## Ablations, memory and failure analysis

| Descriptive ablation | Log loss | Brier | ECE10 | Total CPU seconds/trial | Wall seconds/trial |
|---|---:|---:|---:|---:|---:|
| No temporal history | 0.623104 | 0.219114 | 0.101269 | 0.387207 | 0.446256 |
| No structural screen | 0.531644 | 0.178544 | 0.105349 | 0.737793 | 0.802936 |
| No selector utility memory | 0.586305 | 0.203067 | 0.109320 | 0.504395 | 0.562906 |
| No adaptive selection | 0.488690 | 0.160760 | 0.089835 | 0.695068 | 0.756875 |

No-history exactly reproduced frequency predictions. No-selection exactly
reproduced native predictions with additional controller overhead. Removing the
structural screen improved adaptive loss but raised CPU above always-on native.
Removing selector utility memory worsened loss while saving some CPU. This
supports a descriptive within-stream memory effect in this implementation; it
does **not** establish persistent MNEMONIC value, repository transfer, or a
registered superiority result for the ablations.

| Regime, descriptive log loss | Frequency | Native | Temporal | Adaptive |
|---|---:|---:|---:|---:|
| delayed | 0.707270 | 0.394498 | 0.669728 | 0.660154 |
| irreducible | 0.704377 | 0.712645 | 0.706975 | 0.704614 |
| misleading | 0.680755 | 0.506223 | 0.528671 | 0.538299 |
| shift | 0.778083 | 0.626558 | 0.620134 | 0.755338 |
| sparse_noisy | 0.289732 | 0.295394 | 0.296625 | 0.289732 |
| stationary | 0.476975 | 0.490772 | 0.488776 | 0.476975 |
| temporal | 0.714604 | 0.287667 | 0.348956 | 0.349088 |
| unseen_structure | 0.633035 | 0.595761 | 0.602854 | 0.612003 |

Observed decisions expose the immediate failure mode. Adaptive stayed on
frequency for 944/1024 observations in the shift regime and 704/1024 in the
delayed regime. It used native for only 176 delayed observations. The screen
detects conditional lag association, so it can miss a changing marginal
distribution. In seven of eight delayed seeds, native was tried at step 32 and
dropped at step 48 after only 16 scored observations with little gain. The native
control's gains emerged later, but stale selector utility and growing replay
cost discouraged returning to it; later least-observed exploration chose temporal.
All 8192 adaptive forecasts exactly matched their selected full-prefix control,
so approximate native inference is not the cause. This is a short credit-horizon
failure with replay overhead. These are posthoc trace explanations, not a tuned
replacement experiment; see the retained adaptive diagnosis.

Across adaptive trials, native supplied 768/8192 forecasts and temporal 1408;
frequency supplied 6016. Mean decision overhead was
0.001969 wall seconds/trial.
Mean model construction and catch-up were
0.073102 and
0.045497 seconds respectively.
Controller selection arithmetic was cheap relative to rebuilding/replaying
models; that fact did not rescue its failed quality/cost objective.

Maximum adaptive worker peak working set was
26,963,968 bytes; maximum reported
Job peak was 28,491,776 bytes. Parent
harness lifetime peak working set was 57,688,064
bytes. These are separate, noncontemporaneous counters and must not be summed.
Strict committed-memory peak remains HOLD because this Windows build's native
peak counters can include rejected charges. No energy or GPU saving was measured.

## Independent checks and exact regression results

The arithmetic auditor imported no predictor. It verified all **65,536 forecasts**,
**49,152 scored forecasts**, raw worker-output hashes, loss/Brier/ECE, measured
CPU arithmetic, matched inputs, decision-block consistency, seed-block aggregates,
bootstrap intervals and nine Holm decisions. Ten altered-evidence checks were
correctly refused, including changed forecasts, policy, CPU, decision prefixes,
missing/duplicate arms and relabelled conclusions.

An unchanged-source replay matched all **65,536 forecasts**,
choices, input identities, final state hashes, predictive metrics and deterministic
operation counts across **512 trials**. Timing fields were
excluded. Replay is reproducibility evidence, not additional independent seeds;
confirmatory cost claims use the primary run only.

The final regression suite ran **394 tests: 390 passed,
0 failed, 0 errors, 4 skipped** in
107.760 wall seconds, with source unchanged. Its
64.125 CPU seconds cover the test controller only. Skips remain
two POSIX-specific cases, missing historical predecessor bytes and unavailable
Windows symlink privilege. Trusted Python/JavaScript/Rust runtime smoke checks
are retained in the study receipt. Clean archive extraction and offline Windows
setup/run checks are recorded separately in the delivery receipt.

The initial development run's CRLF transport-validation failure is preserved.
The correction required a fresh calibration and source freeze before held-out
evaluation. No controller threshold, weight or predictor changed after opening
held-out outcomes. Auditor consistency corrections did not change those outcomes
or the frozen scoring procedure.

Package review also found that the runtime's Windows qualifier depended on two
test modules absent from the runtime inventory. The packaging boundary now
includes those modules and their package initializer; a dependency-closure
regression and native qualification from the clean runtime extraction check the
fix. The earlier 389-pass source receipt is retained; the final receipt below
includes the packaging correction and its additional regression.

## Qualification and readiness

| Gate | Status | Current evidence and blocker |
|---|---|---|
| A: native containment | HOLD | Docker/WSL unavailable, 0/13 probes; strict successful-commit peak accounting unresolved. Trusted Windows Job trials are not hostile-code filesystem/network containment. |
| B: authentic isolated repair | HOLD | Zero native authentic repairs. Three new provenance bundles and two parse-only projections are exposed development material, not the missing disjoint evaluation corpus. |
| C: full isolated pipeline and transfer | HOLD | Actual modules and optional policy are connected; software contracts pass. Native function recovery is 0/21; no independently verified cross-repository learning or whole-mission cost advantage. |
| D: historical lineage | HOLD | Available compact v0.17/BGR and 303 protected FRONTIER evidence/code files verify; original full v0.17 and v0.16-v0.14 archives remain missing. |

The archive differential examined 17 recent ZIPs and left 174 older-timestamp
paths to the preserved prior search. It found no missing originals. This is a
scoped local search, not proof about cloud storage, recycle bins or other machines.
No installation, privileged feature change, reboot or unfamiliar host execution
was performed. Exact operator steps are in [native instructions](NATIVE_FRONTIER_V018.md).

The development-only self-revision nomination selected the existing
`semantic_then_prior` ranking production: six versus four attempts across four
public synthetic tasks. No independent held-out corpus exists; its digest is
explicitly null. There were no native candidate executions, independent gains
or authoritative source replacement. The original projection remains available
for rollback. This is neither a whole-engine self-repair nor a verified improvement.

Genuine coding transfer, persistent-memory efficacy, memory-reset/shuffled-evidence
repository comparisons and verified self-improvement are **NOT ESTABLISHED**.
Source integrity and passing software regressions do not promote the platform.
Version stays **0.18.0**. v0.19 requires all four gates; v1.0 additionally needs
sustained native operation, authenticated evidence anchors, broader supported
semantics, installation/update/rollback qualification and external-effect recovery.

## Reproduce

Use the supplied Windows/Python environment and new output paths. The committed
plan binds Python identity and the exact predictor/harness sources. Regenerating
a plan from exposed outcomes would not reproduce an independent preregistration.

```powershell
py -3 -B -m unittest discover -s tests -q
py -3 -B scripts\verify_package_v18.py
py -3 -B scripts\audit_adaptive_metrics_v18.py --plan experiments\PLAN_ADAPTIVE_MECHANISMS_V018.json --result results\ADAPTIVE_MECHANISMS_V018.json --output runs\adaptive-audit.json
py -3 -B scripts\summarize_adaptive_v18.py --result results\ADAPTIVE_MECHANISMS_V018.json --output runs\adaptive-summary.json
py -3 -B scripts\experiment_adaptive_v18.py run --plan experiments\PLAN_ADAPTIVE_MECHANISMS_V018.json --output runs\adaptive-replay.json --confirm-preregistered-evaluation
py -3 -B scripts\verify_adaptive_replay_v18.py --plan experiments\PLAN_ADAPTIVE_MECHANISMS_V018.json --original results\ADAPTIVE_MECHANISMS_V018.json --replay runs\adaptive-replay.json --output runs\adaptive-replay-audit.json
py -3 -B scripts\build_release_v18.py --mode source --output dist\adaptive-source.zip
py -3 -B scripts\build_release_v18.py --mode runtime --output dist\adaptive-runtime.zip
```

`verify_package_v18.py --require-release` must refuse this snapshot.
The current seal is `results/RELEASE_MANIFEST_ADAPTIVE_V018.json`; earlier seals
are unchanged. Source/runtime archives are deterministic for the recorded
Python/zlib toolchain. Their exact hashes, clean extraction, remote commit and
current CI result are in the companion delivery folder. GitHub billing/spending
restrictions, if still present, are reported as pre-execution CI blockage rather
than a software test failure. No main merge, visibility change or GitHub release.

## Highest-value next experiment

The next executable intelligence experiment should test whether a cheap public
change-point/surprise signal, a credit horizon long enough to observe native lag
learning, and episode-length-aware initialization cost improve
selection against the conventional temporal learner on **new, independently
reserved streams**. Register that new policy and budgets first; use this failed
study only as exposed development evidence. Do not tune and rescore these held-out
streams as a new win. Continue to test both missed temporal gains and wasted
reasoning on irreducible data.

For coding, the shortest critical path remains operator-provisioned native
containment, all 13 probes, all 21 function recovery cases plus the new optional
controller's interruption cases, complete controller/worker cost accounting, and
an independently curated repository-disjoint A/B/C/D comparison with a separately
registered E policy and memory controls. See the [prioritized readiness plan](V019_READINESS_PLAN.md).
