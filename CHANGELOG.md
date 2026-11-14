# NOMAD — Change History

## v0.17.0 — SECURITY & RECOVERY (2026-11-13)

**Major capability:** a fail-closed execution boundary and durable indeterminate-effect handling around the v0.16 mission runtime.

- Added a Docker-only path for unfamiliar repository tests; requires trusted digest-pinned image and refuses fallback if the engine is missing.
- Added disposable, filtered source snapshots and hardened ZIP extraction; no private mission evidence mounted into the unknown-code container.
- Added resource restrictions, process groups, reduced host environment inheritance, output caps and cleanup checks.
- Added durable, fsynced external-effect PREPARE/DISPATCH/RECONCILE receipts and owner epochs; hard-crash ambiguity blocks replay.
- Integrated unresolved-effect HOLD checks into mission startup and inspection while retaining v0.16 journal compatibility.
- Added adversarial contract tests including negative archive, filesystem, code-execution and double-dispatch cases.
- Preserved original v0.16 archive unchanged; documented unsupported security claims and native Windows/ROG acceptance plan.

**Research outcome:** local controls tested; Docker kernel boundary and native Windows acceptance **not tested**, external Bitwork learning gains still **unproved**. No production-safety claim.

## Previous versions

The complete previous histories, including v0.16 MISSION RUNTIME, v0.15 RECURSION and earlier Bitwork/NOMAD research, remain in the exact `baseline/NOMAD-v0.16.0.zip` archive. That preserved predecessor is the reference for original studies and prior changelogs.
