# NOMAD v0.18.0: Temporal Ascension qualification

November 15, 2026. **The registered persistent-controller objective failed.**
Warm state removes avoidable reconstruction, but the selected controller did not
approach always-on Bitwork quality at lower CPU cost. All four platform gates
remain HOLD. This is a development qualification snapshot, with no version
advance, production claim, main merge or GitHub release.

## Implemented and preserved

`nomad/persistent.py` adds independently versioned bounded state for the existing
frequency, conventional temporal and original native BGR predictors. It supports
incremental catchup, direct typed restoration, selective/full/cold retention,
memory-pressure eviction, logical expiry, corruption refusal, source/policy/
runtime/epoch/prefix bindings and atomic checkpoint replacement. It implements
past-only discounted credit, exploratory maturity commitments, switching costs
and a bounded selected-loss change detector. No native engine or prior frozen
controller was replaced or retuned after evaluation.

The 2,048-observation history cap is a refusal boundary. It does not silently
slide or summarize older evidence. A new bounded controller requires explicit
eligible reconstruction; indefinite lifelong state compaction remains unproved.

The [mathematical specification](PERSISTENT_TEMPORAL_V018.md) defines the actual
operational approximation. Its risk penalty is a heuristic, not a calibrated
confidence bound. The [recovery report](TEMPORAL_RECOVERY_V018.md) separates
software process-restart contracts from hostile-code and power-loss guarantees.
The optional [persistent coding path](TEMPORAL_MISSION_V018.md) changes actual
effort/ranking/continuation decisions while retaining independent WITNESS authority.
Its fixture evidence is not an authentic repair success claim.

The integration's 22 focused contracts and six independent review contracts
passed. Three accepted authored fixtures using an accelerated commitment-1,
horizon-2 test policy selected frequency, temporal and native in sequence:

| Fixture allocation | Candidate cap | Actual public probes | Actual GENESIS evaluations |
|---|---:|---:|---:|
| Frequency, cold state | 16 | 1 | 0 |
| Temporal, restored state | 32 | 2 | 1024 |
| Native, restored state | 64 | 2 (cap 3) | 4096 |

Each retained one public update; the actual native learned history was checked.
These are functional consequences under a fast contract policy, not the frozen
C32/H64 policy's coding efficacy. Worker execution is an explicit fixture double.
Mission substage timers exclude validation replay and Docker worker resources;
complete native mission cost accounting remains unqualified.

The clean starting branch/remote was `v0.18-platform` at
`3ffd46741ddb99693cd05f35153daec778a2105a`. Baseline regression reproduced 394
tests: 390 passed, zero failures/errors and four skipped. Source stayed unchanged.
The baseline archive SHA-256 is
`c8e3464dc1a2cf35aca369550f51a3c4405715e26a5571e721b12739dc1ecd89`.

The original native/frequency negative result, 0.486413 versus 0.420607 log loss
and identical candidate ordering, remains unchanged. The previous adaptive
negative result also remains unchanged:

| Earlier mechanism | Log loss | CPU seconds/trial |
|---|---:|---:|
| Frequency | 0.623104 | 0.383301 |
| Always-on native BGR | 0.488690 | 0.674072 |
| Conventional temporal | 0.532840 | 0.463623 |
| Original adaptive | 0.548275 | 0.528320 |

That older adaptive controller saved 21.62% CPU against native but failed its
joint objective. The new experiment has different streams, lengths and checkpoint
work; direct timing or score differences between studies are not improvement
estimates. The original adaptive controller already retained inactive objects
within a live process; its history-based restoration reconstructed them. Arm H
is an explicit cold-state policy, not a relabeling of that original controller.

## Prospective experiment and independent audit

The [frozen protocol](TEMPORAL_PROTOCOL_V018.md) and
[machine-readable plan](../experiments/PLAN_TEMPORAL_V018.json) were committed as
`952684387c2414b14ce76bf1cf3029254ce10e67` before reserved generation began.
Plan payload SHA-256:
`693fbdc091be0b6351acdb83786b881fdd1f1dd710e3fe1699a4934324482ecb`.
Eleven source identities, interpreter, budgets, seeds, metrics and thresholds
remained fixed. This is a local source/timestamp commitment, not external
timestamp authentication.

Three predefined profiles were compared on development seeds. The short profile
(commitment 32, credit horizon 64, detector window 16, threshold 0.25) won the
registered development objective. Eight new reserved seed blocks cover eight
regimes, with 512 observations and 64 unscored warmup observations per stream.
All arms checkpoint and restore after observation 256. No future outcome or
generator label enters a learner. Families share randomness within seed blocks;
the inferential sample is eight blocks, not individual observations.

All **576 primary trials completed** with frozen source. The independent auditor
checked **294,912 forecasts, 258,048 scored forecasts**, detector decisions,
source/transport bindings, CPU arithmetic and all five primary comparisons.
An unchanged replay matched all forecasts, decisions, deterministic checkpoints,
final states and operation counts. Replay ran alongside subsequent engineering;
its costs are not a second confirmatory efficiency experiment.

| Arm | Log loss | Brier | ECE (10 bins) | CPU s/trial | Wall s/trial |
|---|---:|---:|---:|---:|---:|
| A Frequency | 0.616591 | 0.217254 | 0.038993 | 0.617676 | 0.683657 |
| B Conventional temporal | 0.510751 | 0.169282 | 0.063818 | 1.054932 | 1.132311 |
| C Always-on native BGR | 0.474825 | 0.154519 | 0.053182 | 3.229248 | 3.362223 |
| D Original adaptive | 0.501269 | 0.166523 | 0.049761 | 1.905029 | 1.997327 |
| E Persistent selective | 0.502447 | 0.165873 | 0.060114 | 3.603516 | 3.752666 |
| F No change detector | 0.490751 | 0.162090 | 0.049028 | 3.146240 | 3.279609 |
| G No delayed credit | 0.496696 | 0.164069 | 0.053884 | 3.683838 | 3.828521 |
| H Cold reconstruction | 0.502447 | 0.165873 | 0.060114 | 5.102539 | 5.275032 |
| I Fully warm | 0.501477 | 0.165372 | 0.060338 | 4.645996 | 4.818234 |

CPU includes worker Job user/kernel time and supervisor work. The whole primary
study used **1729.031250 CPU seconds** and
**1802.022101 wall seconds**. Energy and GPU cost
were not measured. ECE is descriptive and depends on the registered bins.

The objective is log loss plus `2 * CPU / 512`. All five Holm-corrected one-sided
paired sign conditions were required. Only the temporal quality-margin condition
passed; the joint conclusion is **FAIL**:

| Comparison | Condition | Favorable seed blocks | One-sided p | Holm result |
|---|---|---:|---:|---|
| E vs native | objective | 0/8 | 1.00000000 | FAIL |
| E vs native | margin_quality | 1/8 | 0.99609375 | FAIL |
| E vs native | cpu | 1/8 | 0.99609375 | FAIL |
| E vs temporal | objective | 3/8 | 0.85546875 | FAIL |
| E vs temporal | margin_quality | 8/8 | 0.00390625 | PASS |

E minus native loss was **+0.02762149** nats, exceeding the 0.02 margin; its
descriptive paired bootstrap interval was [0.02458812, 0.03043146]. E used
**11.59% more CPU** than native. E minus conventional temporal loss was
**-0.00830412**, but it cost **2.54858398 additional CPU seconds/trial** and
did not pass the combined objective. The sign test does not prove general mean
noninferiority; intervals and unregistered contrasts remain descriptive.

## Retention, delayed credit and change detection

Selective warm and cold arms made identical choices and forecasts. E replayed
26,416 historical observations versus H's 116,476, avoiding **90,060** replayed
rows. It saved **29.38% total CPU** relative to H. A separate forced-selection
development diagnostic also produced identical forecasts while replaying only
512 rows instead of 1,216. This supports state reuse, not optimal controller
selection. Catchup is reduced, not eliminated, and a discarded/invalid state
still requires cold reconstruction.

Fully warm state used **43.87% more CPU** than always-on native BGR. It also
computes inactive forecasts and earns their public credit, so E/I is not a
storage-only causal ablation. All selected E/F/G/H/I probabilities exactly match
the corresponding independently executed fixed predictor on the same prefix.
The underlying native forecasts work; choosing when to use them remains weak.

| Regime | E Persistent | C Native | B Temporal | F No detector | G No delayed credit |
|---|---:|---:|---:|---:|---:|
| delayed | 0.487601 | 0.302374 | 0.552882 | 0.302374 | 0.417969 |
| irreducible | 0.702041 | 0.711473 | 0.704220 | 0.701178 | 0.700276 |
| misleading | 0.457790 | 0.443382 | 0.460458 | 0.475016 | 0.468598 |
| shift | 0.598234 | 0.601113 | 0.597149 | 0.703944 | 0.606656 |
| sparse noisy | 0.260546 | 0.260149 | 0.260541 | 0.258616 | 0.258987 |
| stationary | 0.519140 | 0.522669 | 0.519142 | 0.515510 | 0.520563 |
| temporal | 0.324039 | 0.304607 | 0.326190 | 0.304607 | 0.313771 |
| unseen structure | 0.670184 | 0.652837 | 0.665426 | 0.664766 | 0.686747 |

Removing delayed credit improved average loss by 0.00575114; on delayed streams
it improved loss by 0.06963235. Removing change detection improved average loss
by 0.01169557, and on delayed streams it matched native at 0.30237356 instead
of E's 0.48760105. Detection helped the changing regime relative to detector-off
(0.59823410 versus 0.70394443), but this did not offset its other losses.

E emitted **316 alarms**. Under the preregistered matching rule it detected
29 of 32 known changes, with mean matched delay 31.38 observations, and emitted
**287 false alarms**, including 50 on stationary streams and 48 on delayed
streams without registered changes. Predictor switching itself changes selected
loss. This detector does not reliably distinguish changing relationships from
learning or selection effects. The [diagnosis](TEMPORAL_DIAGNOSIS_V018.md)
records policy consequences without claiming a causal proof from trace inspection.

## Complete cost scope and memory limits

Mean E CPU scopes include construction 0.141602 s, catchup 0.933838 s, active
forecast/update 0.520020 s, checkpoint publication/restoration 0.839111 s, and
final state materialization 0.523926 s. Selection and detector arithmetic each
used about 0.001953 s. These are nested diagnostic scopes, not disjoint costs
to add to the 3.603516 s whole-worker total. Persistent state serialization and
validation are material costs. Fixed scheduling estimates underprice that work.

| Arm | Maximum worker working set (MiB) | Maximum final state bytes | Mean switches |
|---|---:|---:|---:|
| A Frequency | 28.508 | 1063 | 0.000 |
| B Conventional temporal | 35.727 | 249033 | 0.000 |
| C Always-on native BGR | 39.684 | 378707 | 0.000 |
| D Original adaptive | 30.465 | 43319 | 5.734 |
| E Persistent selective | 54.219 | 686784 | 7.672 |
| F No change detector | 45.727 | 460055 | 2.594 |
| G No delayed credit | 54.535 | 658124 | 10.844 |
| H Cold reconstruction | 41.227 | 403871 | 7.672 |
| I Fully warm | 55.410 | 679732 | 7.859 |

The [machine-readable accounting](../results/TEMPORAL_COST_ACCOUNTING_V018.json)
includes parent overhead, active/inactive work, checkpoints, storage and Job
counters. Allocation/deallocation are paid in process totals but not individually
traced; eviction has event counts, not a separate stopwatch. Original adaptive
telemetry resets on restoration; retained segments and whole-worker costs must
be used instead of interpreting its final segment as the full run.

All trials have the same 60-second wall, 512-MiB and four-process Job ceilings.
CPU is measured without a separate hard CPU-time kill limit. Process working set
and Job peaks are nonadditive. Strict successful committed-memory accounting
remains HOLD. The final parent JSON publication lies outside the study timer.

## Engineering verification and preserved failed attempts

Final source regression: **473 run, 469 passed, 0
failures, 0 errors and 4 skipped**, source unchanged.
The skips concern POSIX ownership/process groups, the missing full predecessor
archive and unavailable native symlink privilege. Trusted Windows supervision
checks passed 14/14. Native state continuation, corrupted-state rejection,
duplicate-observation refusal, epoch/runtime mismatches and interrupted checkpoint
publication are covered by real software/process tests. Mission execution doubles
are labeled separately from actual Docker containment.

The first 98-trial development attempt completed its workers but received
`INTERRUPTED_HOLD` because the independent auditor's source inventory was corrected
while it ran. Exact prior source bytes were recovered against recorded hashes;
that attempt was preserved and excluded from selection. The current-source
98-trial recheck completed successfully before registration. Predevelopment codec
failures/fixes remain documented. After primary completion a descriptive exporter
failed on a string telemetry label; its focused correction/test and successful
recheck are recorded separately. No frozen mechanism or outcome was changed.

Independent mission review corrected repeated decisions after restart,
misbinding a later public success to an earlier candidate, trusted diagnostic
posteriors/recall without recomputation, and omission of prediction-affecting
native caches from semantic comparison. A native-activation test also corrected
an adapter horizon that could retain the initial cheap mechanism for a short
mission. A bounded memo now reuses only fully validated exact content, with
complete/selected flags, fresh source/vendor/runtime checks and defensive copies.
One independent test initially expected the inner refusal message rather than
its public wrapper; the rejection was already correct, and the assertion-only
failure and recheck are both retained. An intentionally stopped expensive fixture
attempt has its exact journals preserved in the companion interrupted-run archive.

The first full regression ran 473 tests with 468 passes, one failure and four
skips. Its existing post-commit immutability test exposed a diagnostic compatibility
regression: the generic runtime handler wrapped an intentional MissionHold.
The handler now propagates that domain refusal unchanged. The focused original
test passes and the final full recheck above covers the corrected source.
Both full-run receipts remain retained; 235 exact Python source/test/script files
from the failed run were recovered and hash-verified in a separate source archive.
Source-bound repository and recovery receipts were reissued under RECHECK names;
their originals were not overwritten.

The standalone state checksum is not authentication. A valid-shaped, deliberately
rehashed native numerical cache can change a future forecast without changing
the public prefix. The independent review reproduced that limitation. Mission
admission now compares those prediction-affecting caches against public replay;
it does not treat arbitrary serialized state as verified knowledge. A hostile
writer controlling all source and trust anchors remains outside this local
integrity guarantee.

Clean extraction, byte-identical source/runtime rebuilding, offline Windows
setup/demo/native BGR execution, fresh remote checkout and CI state are recorded
in the companion delivery receipts. Archive checksums are in `SHA256SUMS.txt`.
GitHub billing restrictions, if reported there, are separate from software failures.

## Qualification matrix and scientific answers

| Gate | Status | Evidence and unresolved requirement |
|---|---|---|
| A Containment | HOLD | Docker/WSL unavailable; 0/13 container probes; trusted Jobs pass, strict peak accounting unresolved. |
| B Authentic repairs | HOLD | No qualified disjoint corpus or independently accepted isolated repairs; prospective repository comparison NOT_RUN. |
| C Complete pipeline | HOLD | Persistent decisions and recovery contracts implemented; 0/21 native function-recovery cases; no isolated end-to-end transfer proof. |
| D Historical lineage | HOLD | 372 protected prior adaptive files and available originals verify; full v0.17 and original v0.16/v0.15/v0.14 archives remain missing. |

1. **Does persistent state eliminate reconstruction?** It avoids repeated work
   for retained states and restores actual native state, but missing-prefix
   catchup and cold fallback remain necessary.
2. **Does longer credit improve delayed tasks?** Not in this frozen comparison;
   the no-delayed ablation has lower delayed-regime loss. Individual horizon and
   discount effects are not separately identified.
3. **Does detection recognize useful temporal reasoning?** Some real changes
   were detected, with too many false alarms and harmful delayed-task resets.
4. **Does E outperform conventional temporal learning?** Slightly lower loss,
   much higher CPU; the registered combined claim fails.
5. **Does it approach native quality at lower cost?** No: worse loss and higher CPU.
6. **Is it efficient on stationary/irreducible tasks?** No advantage over the
   simpler frequency control; extra exploration, alarms and state work remain.
7. **Does any benefit survive held-out evaluation?** Warm state preserves exact
   forecasts and saves cost against matched cold reconstruction; overall policy
   success does not survive. Native has the lowest aggregate loss among these
   designed controls, at higher cost than frequency/temporal, without a coding claim.
8. **Does it change coding decisions?** Yes in explicit integration contracts;
   improved authentic coding outcomes remain unproved without isolation.
9. **Is cross-repository learning demonstrated?** No. Synthetic stream state,
   retained metadata and mocked mission tests cannot establish it.
10. **What remains unproved?** Effective cost-aware selection, reliable change
    detection, candidate self-improvement, general coding benefit, hostile-code
    containment, long-running recovery and complete historical lineage.

The bounded self-revision configuration remains a development nomination.
The selected short profile was not compared with the standard persistent profile
as a held-out arm, so no self-revision promotion is justified. WITNESS and protected
evaluation files remain outside candidate authority.

## Highest-value next experiment and reproducibility

Use this completed study only as development evidence. On new reserved seeds,
compare a predictor-specific residual detector against the current selected-loss
detector and detector-off control, while holding retention and exploration fixed.
Record alarms caused by switching, native commitment interruption, and all state
serialization/catchup costs. Include genuinely stationary and irreducible controls
and freeze thresholds before outcomes. Separately compare nominated and baseline
persistent profiles if self-revision promotion is sought. Do not retrofit a win
onto this study. Native coding experiments still depend on Gate A and an independent
corpus; [the v0.19 blocker plan](V019_READINESS_PLAN.md) remains conditional.

Exact audit, replay, regression and packaging commands are in
[TEMPORAL_REPRODUCTION_V018.md](TEMPORAL_REPRODUCTION_V018.md). Retained evidence:

| Receipt | SHA-256 |
|---|---|
| `TEMPORAL_MECHANISMS_V018.json` | `30f8995aa1371d18ad575c4f7697c3bb770192e0168df7866aa9b5f47ca59e8b` |
| `TEMPORAL_INDEPENDENT_AUDIT_V018.json` | `125d22e86f9fc82351711cb7c6943254590bc3a94004e59744cb490a4db01335` |
| `TEMPORAL_REPRODUCIBILITY_V018.json` | `16f5e5620e1b5cedb76cc36979841fe31681a4257d450036d4afe4120637f115` |
| `TEMPORAL_FINAL_RECHECK_V018.json` | `b9e5a9107a0901549d2a38868e0fa50f63cf995e17f970d65c7e395be85d5588` |
