# NOMAD v0.18.0 PLATFORM: engineering report

Date: November 14, 2026. Status: **local engineering snapshot; production and publication HOLD**.

## Implementation

Work was performed directly in the desktop NOMAD repository, on `v0.18-platform`. The source metadata is now 0.18.0; the existing folder name was retained. Original source is preserved in baseline commit `d1514f5eb1ccc1aa6a22a357524e402364aacdf5`, branch `baseline-v0.17.0`, and the original compact ZIP. The ZIP's 388 file contents match that baseline commit. The original BGR archive and all inherited results, experiment files and external-source snapshots remain unchanged.

Implemented offline Windows installation/configuration/diagnostics, a command launcher that works under the current PowerShell restriction, Job Object process-tree supervision, stricter Windows path and archive admission, isolated Docker preflight and execution, ownership-safe named-container cleanup, and a bounded durable coding mission. That mission calls GENESIS, optional original BGR ranking, independent WITNESS and final checks, then commits or restores its disposable source and retains one scoped learning record. Unknown external effects remain fenced and cannot be blindly replayed.

The bounded isolated adapter supports one strict arithmetic `solve(x,y)` target selected by the operator. It preserves but does not yet integrate WORLD MODEL/INQUIRY into arbitrary isolated repository work. Mission learning does not automatically admit MNEMONIC skills. These are explicit remaining implementation gates, not capabilities claimed by the platform label.

The preserved architecture remains **Bitwork → RESONANCE → WORLD MODEL → INQUIRY → GENESIS → execution → WITNESS → MNEMONIC → learning → next action**. The original modules remain executable and covered by inherited regression tests.

## What actually ran on the ASUS ROG

Native diagnostics identified Windows 11 Pro build 26200, ROG Flow Z13 GZ302EA, AMD Ryzen AI MAX+ 395, and 132,766,306,304 bytes reported physical memory. The hypervisor and firmware virtualization reported enabled. Optional Windows feature inspection required elevation; that inspection remains HOLD.

Python 3.12.10, Node 24.19.0, Rust/cargo 1.98.1 were present. Generated trusted arithmetic programs ran in all three native runtimes and returned `[7, 23, -1]`. Final measured elapsed times were Python 0.060994 s, JavaScript 0.121818 s, and Rust 1.034097 s including compile and run.

`NOMAD.cmd setup` installed the source link offline; `NOMAD.cmd trusted-demo` completed a generated repair with one public execution, one WITNESS observation and one final observation. Native Windows tests exercised child cleanup after parent exit, timeout tree cleanup, supervisor hard death, denied Job assignment, junction rejection and actual interprocess ownership. See `results/SUPERVISION_V018.json` for measured Job CPU, peak commit and process count. These are trusted host-process measurements, not hostile-code containment.

Docker was absent. WSL reported not installed. No Docker image or host feature was installed, and no unknown repository code ran on the host. The thirteen-case Docker qualification harness is implemented but executed zero container cases. No actual isolated external repository repair or interrupted isolated mission was demonstrated.

## Test outcomes and retained failures

| Run | Run count | Passed | Failures | Errors | Skipped | Wall seconds |
|---|---:|---:|---:|---:|---:|---:|
| Original v0.17 desktop baseline | 170 | 158 | 2 | 8 | 2 | 69.213 |
| Final v0.18 source | 219 | 215 | 0 | 0 | 4 | 86.365100 |

Final controller CPU was 41.703125 s, excluding child CPU. Source hashes were identical before and after the final run. The four skips are two POSIX-only cases, missing historical predecessor bytes and unavailable Windows symlink privilege. Separate Windows tests cover ownership and ordinary child-tree cleanup; skips never become security passes.

The baseline exposed Windows CRLF source/digest mismatch. Native follow-up exposed byte-range lock contention escaping as a raw exception. Both were fixed. Other retained development failures include BGR's predict-before-observe contract and a Job termination signaling race. Independent review also fixed stale receipt binding, duplicate container names, foreign container cleanup, Windows reparse handling and release-inventory boundaries. Full raw baseline and iteration evidence remain in `results/`.

An intermediate run recorded 9212.338825 s wall time and 39.03125 s controller CPU. Its large elapsed interval is preserved without attributing it to compute cost or claiming a measured cause. The final source run above is separately recorded.

## Benchmarks and costs

| Control | Mean log loss | Mean rank of observed public success |
|---|---:|---:|
| Cold | 0.6931471805599453 | 1.5 |
| Frequency | 0.42060709421822373 | 1.0 |
| Native BGR | 0.48641297739326594 | 1.0 |
| Shuffled native | 0.8482314975858793 | 1.0 |

The replay uses two historical training tasks and four historical evaluation tasks under matched available-candidate budgets. Rank averages only the two evaluation pools containing an observed public success. This is retrospective replay, not fresh issue solving or untouched holdout evaluation. Native BGR loses to frequency-only loss. **Learning advantage stays HOLD.** The original Catalogue false-positive remains a permanent independently rejected case.

Native BGR mean wall time was 0.082562999994 s, mean process CPU 0.072916666667 s, and maximum traced Python allocation 215,252 bytes over three cost repetitions. These are local predictor costs, not total coding-mission costs. NOMAD benchmark cloud calls and API spend were zero. Electricity, energy, GPU efficiency, hardware amortization and total dollar cost were not measured. Agent-development tool/model costs are outside the NOMAD benchmark accounting.

## Gates

PASS: offline Windows workflow, tested Job cleanup/ownership, trusted native Python/JavaScript/Rust, inherited/new engineering regressions, source admission contracts, bounded mission state transitions under mocked Docker, evidence replay/contestation checks, Catalogue rejection and original BGR integrity.

HOLD: native Docker/VM containment; native symlink qualification; actual interrupted isolated missions; real-repository repair with independent isolated validation; full WORLD MODEL/INQUIRY integration; cross-mission autonomous skill admission; BGR coding advantage; authenticated remote WITNESS; remote exactly-once effects; complete historical lineage; production and publication.

GitHub lookup returned 404/not found through the connected API and Git. An inaccessible private repository cannot be ruled out. No remote, public visibility, tag, push or release publication was created. The canonical local development history is ready for review after critical gates are satisfied.

## Artifacts and verification

The delivery includes updated source/tests/docs, original desktop-source backup, a local Git bundle, deterministic source and lightweight runtime ZIPs, SHA-256 checksums and a clean-extraction verification receipt. The source ZIP contains the complete current compact source and its retained evidence; it is not the missing full nested historical archive. Read-only package verification checks every deliverable hash and refuses extras. A separate publication check refuses the HOLD gates.

The packaging receipt supplied beside the ZIPs records exact ZIP hashes, repeated-build equality, clean extraction and rerun outcomes. Release checksums cannot authenticate a hostile replacement of both source and manifest; retain the independent delivery receipt.

## Remaining path to v1.0

Provision and qualify a reviewed local Docker/VM backend with administrator assistance where required. Run the controlled native adversarial suite, actual interrupted isolated missions, and independent real issue repair. Implement isolated WORLD MODEL/INQUIRY adapters and deliberate MNEMONIC admission without weakening evidence independence. Restore the exact full predecessor archive. Freeze a fresh issue corpus before testing learning claims. Complete image/dependency provenance, signed evidence/release anchors, long-running resource/disk limits, service recovery and supported-platform CI before considering v0.19 RC and v1.0. The detailed roadmap is `docs/NEXT_ITERATION.md`.
