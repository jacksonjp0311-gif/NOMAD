# NOMAD v0.18.0 FRONTIER qualification

**Development snapshot; all four gates HOLD. No v0.19 promotion.**

This iteration starts from verified local and remote commit
`ddb5c32ea56d5c94e67fc78bdea1ad64b7b9c399` on `v0.18-platform`, with a clean tree
and zero divergence. `main` remains at `5851566`. The original archive, source
hashes, environment and 277-test baseline were captured before implementation in
`results/BASELINE_FRONTIER_V018.json` and its study receipt. That baseline was
273 passed, zero failures/errors, four skipped. Current regression counts are
recorded in `results/FRONTIER_FINAL_RECHECK_V018.json` and the companion delivery report.

Final frozen-source regression: **346 run, 342 passed, zero failures, zero errors,
four skipped**, in 102.683 seconds with 59.25 controller CPU seconds. Source
hashes were unchanged during the run. Skips are the two POSIX-specific ownership/
process-group checks, the omitted original predecessor archive and unavailable
Windows symlink privilege. Python, JavaScript and Rust trusted runtime checks
passed. These counts do not include nonexistent native Docker trials.

## Implemented capability

The new bounded function adapter extends the existing NOMAD modules. It admits
JSON contracts for named Python functions, local package/import relationships,
branches and control flow. It constructs a finite source-derived AST inventory,
including compositions across at most two modules. Actual GENESIS synthesis is
used for eligible two-integer interfaces with AST parameter binding. It is more
expressive than the previous top-level arithmetic adapter, but it is still a
bounded grammar, not arbitrary Python repair or general intelligence.

Public diagnostic calls execute through the isolated observer. Their measured
outcomes update INQUIRY's posterior and affect candidate order. The initial
likelihood is an explicitly declared reachability heuristic, not an empirically
calibrated causal model. RESONANCE encodes observed API equality without invented
numeric correlations. WORLD MODEL and MNEMONIC can influence later planning;
the original native BGR implementation remains the optional proposal ranker.
WITNESS and a separate final observer own acceptance, not the learner.

One durable mission identity binds source, policy, runtime, public cases, sealed
private partitions, candidate inventory, observations and learning. Partial
multi-file patches, ambiguous dispatches and committed memory have explicit
recovery checks. No private expected values are passed to the worker; private
failure ends a mission without becoming search feedback. The full public test
suite, when registered, is additional evidence and cannot replace independent
challenge/final checks. See [the function specification](FRONTIER_FUNCTIONS_V018.md).

The isolation adapter now supports optional complete, bounded, hash-checked UTF-8
output for parent-side comparison. It refuses truncation and inconsistent output.
The self-revision audit checks a separate candidate against its exact original,
protects tests/verifiers, requires separate full-regression receipts and preserves
rollback. It has no operation that replaces authoritative source. See
[self-revision and rollback](SELF_REVISION_FRONTIER_V018.md).

## Independent review and observed failures

Independent parse-only review found that callable aliases could bypass the new
observer's builtin allowlist, and that rebinding an imported module alias could
expose generator/frame attributes. A further review found native extension
shadowing of a parsed Python module. These were admission defects, not observed
Docker escapes. The adapter was corrected and adversarial regression cases were
added without executing the payloads on the host.

The initial full regression receipt, `FRONTIER_FINAL_V018.json`, retained 334
passes and four skips but detected source changes during execution. A final
review had added the missing complete-evidence-inventory prerequisite and its
negative regression. That receipt cannot certify the final source. The suite
was repeated under the distinct `FRONTIER_VERIFIED_V018.json` receipt; the earlier
bytes remain preserved rather than resealed or relabelled.

Recovery testing also exposed JSON integer-key roundtrip differences in diagnosis
replay; canonical comparison now preserves replay semantics. Function-memory
admission was tightened around origin, final acceptance, runtime, duplicate
observations and expiry. The review/iteration receipts retain the findings and
corrections. Software checks that mock isolation are labelled as such; they are
not native pipeline qualification.

## Intelligence results

The original negative result remains unchanged: native BGR log loss
**0.4864129774**, frequency **0.4206070942**, with identical candidate ordering.
The posthoc diagnosis separates the prior, temporal expert mixture and grammar
mixture. The old eight-event trace never reached the 24-event lag gate. Sparse
higher-order contexts pulled estimates toward uncertainty; added modeling did
not help that trace. These interventions explain a failure; they are not a new
held-out contest or a tuned replacement presented as original evidence.

The new experiment froze implementation hashes, generators, eight evaluation
seeds, scoring and four statistical contrasts before generating evaluation
outcomes. Thirty-two synthetic streams ran through the actual original native
BGR runtime. Each predictor saw the same prefix and current action; the first
32 observations were unscored and the next 96 were scored prequentially.

| Mean natural-log loss | Frequency | Native BGR | Conventional temporal |
|---|---:|---:|---:|
| Stationary | 0.478565 | 0.487530 | 0.489977 |
| Boolean history | 0.702128 | 0.292385 | 0.358759 |
| Three-step lag | 0.702936 | 0.412302 | 0.680390 |
| Distribution switch | 0.769760 | 0.650146 | 0.644287 |

The four registered contrasts passed their Holm-adjusted one-sided paired sign
tests. Frequency beat native on seven of eight stationary seeds (p=0.03515625).
Native without lag beat frequency on Boolean history; native beat its no-lag
ablation on lag-three; conventional temporal beat frequency after switching
(each eight of eight, p=0.00390625). Other table comparisons are descriptive.
The study consumed 154.061 seconds wall and 142.719 controller CPU seconds.
The measured Python allocation peak was 5,878,213 bytes, not whole-process RSS.
Native computation was substantially more expensive than frequency and the
conventional temporal control. Equal information and observations are not equal
CPU work. There is no efficiency, energy, GPU, coding or general intelligence claim.

An unchanged-source replay reproduced all 28,672 forecasts and model snapshots,
excluding nondeterministic cost measurements. A separate arithmetic-only auditor
recomputed all 21,504 scored forecasts, aggregates and Holm decisions. Replaying
the same streams does not increase the independent sample size.

The new real-repository design uses A cold, B frequency, C native Bitwork, and D
native plus verified memory/full pipeline. It preserves the earlier protocol
unchanged. It remains **NOT RUN**: a curated repository-disjoint corpus, verified
native function recovery and matched controller-plus-worker resource accounting
are missing. The public keon/algorithms issue 2733 lead has pinned upstream source,
license and an AST-preserving function projection for development inspection;
neither the projection nor this exposed repository is unseen evaluation or a
completed authentic whole-repository repair. No genuine cross-task coding benefit
or isolated self-improvement has been demonstrated. See
[mechanism mathematics and protocol](FRONTIER_BITWORK_V018.md).

## Qualification matrix

| Gate | Status | Evidence and precise blocker |
|---|---|---|
| A: native containment | HOLD | 14 trusted native Windows supervision checks pass; Docker absent and WSL/required features disabled. Zero of 13 container probes executed. Strict peak committed-memory accounting remains unproved. |
| B: real-repository repair | HOLD | Broader adapter and provenance lead implemented; zero independently accepted authentic isolated missions. Curated disjoint task corpus and execution backend absent. |
| C: full pipeline and transfer | HOLD | Real module wiring and replay contracts exercised in software tests with mocked isolation; actual isolated function pipeline, interruption/recovery and cross-task benefit unverified. |
| D: historical lineage | HOLD | Compact v0.17 and original BGR validate; 196 historical, 211 original engineering and 241 prior qualification evidence files remain unchanged. Original full v0.17 and v0.16-v0.14 archives remain unavailable. |

All release and production gates remain HOLD. A source-integrity PASS checks the
delivered bytes; it does not override this matrix. The machine-readable matrix is
`results/GATES_FRONTIER_RECOVERY_V018.json`.

## Windows, recovery and provenance

Six native memory cases distinguish current commit from reported peaks. Both
32 MiB controls succeeded inside a 96 MiB Job. Four 128/256 MiB attempts failed
with WinError 1455; regions remained reserved and observed current commitment did
not increase, while both peak counters rose by the attempted charge. This
supports an explanation of the measured anomaly on this build, not a strict
historical maximum. No counter is relabelled to manufacture a PASS.

Docker, WSL, alternative backend registrations, privilege and feature state were
checked without installation or system changes. Exact privileged provisioning
and subsequent probe commands are in [native instructions](NATIVE_FRONTIER_V018.md).
Windows Job cleanup is not filesystem/network isolation. Unfamiliar code was
never executed directly on the host as a substitute.

The first clean source extraction subsequently exposed two intermittent Windows
`Access is denied` errors during final mission-directory publication. It recorded
332 passes, two errors and four skips. Both affected tests passed on an unchanged
targeted replay; the holder or system component behind those original refusals
was not identified. The failed archive/receipt and exact logs are retained in
`FRONTIER_EXTRACTION_INITIAL_V018.*` and `FRONTIER_DELIVERY_INITIAL_V018.json`.

The correction retains atomic same-parent publication and retries only Windows
errors 5/32, at most six attempts with 1.55 seconds of total scheduled delay.
Every attempt requires the original non-reparse directory identity and an absent
destination. Existing or newly appearing destinations, unknown errors, changed
source identity and ambiguous results are refused; persistent refusal remains
HOLD. There is no copy-over or delete-and-replace fallback. An actual Windows
directory-handle sharing refusal and later successful retry are tested alongside
the injected error contracts. This does not identify the original handle holder
or establish general concurrent-filesystem isolation. The corrected snapshot
uses a separate source seal; the first FRONTIER seal and archives are unchanged.

The separate function recovery qualifier registers 21 native cases: terminal
replay, durable interruption points, observed live-container owner termination,
a true mixed two-file patch, negative final rollback and tampered evidence.
It requires the current host/image/policy containment PASS before initialization.
Its current receipt is HOLD with zero executed cases. Independent harness review
removed nondeterministic unittest timing from semantic equivalence and ensured
source/evidence read failures remain visible in a FAIL/HOLD receipt. Raw execution
receipts remain retained. This tool makes future native verification reproducible;
its unexecuted positive path is not qualified by controller tests.

```powershell
py -3 -B scripts\qualify_function_recovery_frontier_v18.py --image $Image --isolation-receipt runs\native-qualification.json --output runs\function-recovery.json --evidence-root runs\function-recovery-evidence
```

The local archive search hashed 174 ZIPs, read 173 and examined reachable Git
archive objects. Fourteen compact predecessor copies were found; original full
predecessors were not recovered. The malformed archive and scoped search limits
remain in the receipt. Historical results were not regenerated or overwritten.

## Reproduce

Run from the extracted source root, using new output paths:

```powershell
py -3 -B -m unittest discover -s tests -q
py -3 -B scripts\study_platform_v18.py --output runs\new-frontier-study.json
py -3 -B scripts\audit_frontier_metrics_v18.py --output runs\new-frontier-audit.json
py -3 -B scripts\qualify_memory_frontier_v18.py --output runs\new-memory.json
py -3 -B scripts\verify_lineage_v18.py --output runs\new-lineage.json
py -3 -B scripts\verify_package_v18.py
py -3 -B scripts\build_release_v18.py --mode source --output dist\new-frontier-source.zip
py -3 -B scripts\build_release_v18.py --mode runtime --output dist\new-frontier-runtime.zip
```

The lineage check deliberately returns HOLD while originals are missing.
`verify_package_v18.py --require-release` must also refuse this snapshot. Native
experiment replay and new-protocol commands are in the mechanism report. Source
and runtime archives use deterministic timestamps, ordering and permissions;
exact compressed bytes reproduce with the recorded Python/zlib toolchain.
The separate delivery receipt records clean extraction, offline Windows setup,
runtime execution, fresh remote checkout, artifact SHA-256 and CI status.

## Next iteration, in priority order

1. Operator provisions WSL2/Docker and a reviewed digest-pinned image, then runs
   all 13 probes under the exact policy. Keep every failure and cleanup receipt.
2. Run an interrupted/uninterrupted function mission through the actual observer
   and compare source, journal, WITNESS, memory and duplicate-effect outcomes.
3. Bound and account for controller plus worker CPU, peak memory and wall time.
   Worker limits alone do not support the required matched-compute comparison.
4. Curate independently sourced authentic tasks in disjoint repositories, with an
   independent custodian freezing private contracts. Public development leads
   cannot be recycled into unseen evaluation. Freeze a new complete plan only
   after these prerequisites pass, then run the A/B/C/D transfer experiment once.
5. Recover the original full historical archives and verify their pinned hashes.
6. Advance to v0.19 only after all gates pass; production additionally needs
   broader supported tasks, longer recovery stress, reproducible clean install,
   independently accepted transfer and a documented security operating envelope.

The highest-value intelligence experiment is the qualified A/B/C/D authentic
repository comparison with matched whole-mission resources. The next executable
prerequisite is native containment and function-mission recovery qualification.
