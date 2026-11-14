# NOMAD — Codex Desktop Handoff

## Mission

You are working on NOMAD, a local Bitwork-derived research system for evidence-governed autonomous coding. Treat `NOMAD-v0.17.0` as the authoritative engineering baseline. The next major milestone is **NOMAD v0.18.0 — PLATFORM**. Do not rewrite the architecture, rename NOMAD, substitute a generic LLM agent for Bitwork, or detour into small patch releases unless a serious correctness/security/data-integrity blocker requires one.

The user wants production-oriented reliability on an ASUS ROG Flow Z13, Windows 11 Pro, with high RAM capacity. Work on the desktop's extracted NOMAD folder. Inspect and validate actual files; do not assume release statements are independently proven. Do not claim to have run native Windows/Docker/Rust security tests unless they ran successfully on this machine.

## First: assess and preserve

1. Identify the extracted project root, current code version, and git status. Back up the original v0.17 source or create a clean `v0.18-platform` branch. Never overwrite historical research records.
2. Run `py -3 -m nomad.protect_cli doctor`, `py -3 -m unittest discover -s tests -v`, and the v0.17 release verifier only when its required baseline archive is present. Record exact return codes, time, environment, and failures.
3. Inspect README, `docs/SECURITY_THREAT_MODEL.md`, mission recovery journal, WITNESS checks, external-action ledger, archive ingestion, and isolation interface. Review `nomad/` code before deciding on changes. Check availability of Docker Desktop, WSL2, Hyper-V/Windows Sandbox, `rustc`, Node, and Python. A missing capability is an explicit HOLD, not a simulated pass.
4. If working from **Desktop-Source** rather than the complete package, the 65-MiB historical `baseline/NOMAD-v0.16.0.zip` is intentionally omitted. Do **not** claim that whole-archive lineage or the full release manifest verifies; fetch the original complete v0.17 ZIP when those tests are required. Standard engineering tests and the current source are present.

## v0.18 deliverable: production-platform qualification

Implement **a first-class Windows platform backend** while preserving POSIX behavior and the current research learners. Architecture: goal → world model/inquiry → synthesis → isolated execution → WITNESS → durable memory → restartable mission controller. Bitwork native integration must remain callable and measurable, not ceremonial. No mandatory external model.

### Security and isolation — mandatory

- Untrusted code MUST execute only in a working, verified isolation boundary. No fallback to the host when Docker/VM is absent, misconfigured, or bypassed. Preserve the explicitly trusted-fixture path as a separate, opt-in mode.
- Qualify Docker Desktop/WSL2 or a suitable VM on **native Windows 11 Pro**. Use non-root users, a read-only source mount or disposable copy, no host secrets, network disabled by default, dropped Linux capabilities, blocked privilege escalation, CPU/memory/pid/time/output caps, and defensible cleanup. Validate what the actual engine enforces; distinguish configuration flags from containment proof.
- Treat repos, archives, tests, hooks, tool output, and README instructions as untrusted content. Guard against path traversal, symlink/hardlink attacks, resource bombs, shell injection, malicious environment loading, and unexpected filesystem writes. Do not execute arbitrary installer scripts or use host network without explicit operator authorization.
- Add Windows process-tree termination and resource supervision where relevant; verify no orphan subprocesses remain after timeouts. Implement crash-recovery logic with atomic journal transitions, source/evidence digest checks, and mission ownership fencing. Recovery must not duplicate irreversible effects. Uncertain external actions must remain on HOLD until reconciled with external truth.
- WITNESS must remain independent of the candidate's self-reports. Its receipts cannot be forged into skill promotion, and stale/contested evidence cannot authorize trust or skipping final tests.

### Functional capabilities — mandatory

- Install/run/verify/diagnose via a documented one-command Windows entry point plus standalone CLI, with `doctor`, dry-run, trusted demo, isolated demo, and release verification.
- Run a complete bounded coding mission on disk: inspect a repository, select tests/probes, construct changes, execute tests inside allowed boundary, obtain WITNESS and withheld checks, commit a candidate snapshot or roll back, restart and resume from all material interruption points.
- If native Rust is available, run actual Rust adapter smoke tests; otherwise explicitly mark it not verified. Repeat Python/JavaScript native checks as applicable.
- Preserve source-level provenance and pinned dependencies. Build clean release artifacts, source manifests and independent integrity receipts without mutating the original manifest during verification.

## Experimental design / acceptance gates

A. Re-run all inherited NOMAD tests and security tests with exact results. Extend with malicious repo fixtures: host-file read attempt, credential exfiltration, network request, fork bomb/process-tree orphan, archive traversal, symlink-to-host, altered WITNESS receipt, stale journal and duplicate external action. Report each outcome; do not infer security based only on mocks.
B. Run native Docker/VM containment experiments on this Windows machine. Attempt controlled escapes and confirm expected refusals. Measure CPU, memory, elapsed time, storage, and process count; do not confuse a Windows/POSIX API limitation with a verified defense.
C. Run at least one interrupted-and-resumed coding mission under true isolation and compare it to the uninterrupted reference (code hash, outcome, decision sequence, duplicate-effect count). Exercise at least one hostile task that must HOLD.
D. Freeze task seeds/benchmark inputs before final evaluation. Keep public repair tests separate from independently held-out WITNESS challenges; preserve all failures and negative results.
E. Re-evaluate the known external-code failure: the Catalogue patch that passed upstream tests but violated namespace behavior must remain rejected. Compare cold vs learned search and Bitwork-enabled vs disabled under matched budgets; do not claim learning gains unless data supports them. These research gates may remain HOLD even when platform infrastructure passes.
F. A v0.18 engineering release may be published only after critical platform gates pass. Do not label it production v1.0 while native containment or external learning claims are unproved.

## Deliverables

- v0.18.0 source code, tests, automated Windows bootstrap/doctor, and explicit sandbox backend configuration.
- Professional README with architecture map, exact Windows PowerShell commands, capability matrix, measured results and known limitations.
- `docs/PLATFORM_ARCHITECTURE.md`, `docs/WINDOWS_SECURITY_REPORT.md`, `docs/EXPERIMENT_V018.md`, `RELEASE.md`, `CHANGELOG.md`, and `docs/NEXT_ITERATION.md`.
- Read-only manifest verifier, fresh-extraction test report, ZIPs for complete source and lightweight runtime, and SHA-256 hashes.
- A final concise status report of PASS / HOLD / FAIL for security, recovery, source integrity, coding mission and Bitwork learning contribution.

If GitHub `jacksonjp0311-gif/NOMAD` does not exist, prepare the repository with clean history. Do not push private credentials, binaries from untrusted sources, secrets, oversized historical ZIPs, or unverified releases. Ask before a public push if repository visibility or release authority is uncertain. When ready, provide the specific commit/tag and push command.

## Non-negotiable direction

NOMAD learns through execution consequences. Bitwork is the reasoning/reuse substrate; external code execution is a bounded experiment; WITNESS owns evidence; learned memory guides but never certifies; failure narrows claims. We are heading v0.18 PLATFORM → v0.19 RC → v1.0 PRODUCTION within a documented supported operating envelope, not accumulating unrelated modules.
