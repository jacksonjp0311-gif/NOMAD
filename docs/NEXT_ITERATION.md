# NOMAD v0.18 — PLATFORM INTEGRATION (Next major version)

The product path remains: **v0.17 Security & Recovery → v0.18 Platform → v0.19 Release Candidate → v1.0**.

## Mandatory v0.18 gates

1. **Actual isolated execution on target hardware.** Docker/VM on Windows 11 Pro ROG, digest-pinned image, filesystem/network/process/memory/resource adversarial test cases; no undocumented host fallback.
2. **Native Windows recovery.** Windows process-tree kill using reviewed Job Objects/container isolation, NTFS file locking, restart after worker and supervisor crashes, source durability, trusted independent verification.
3. **Approved external side effects.** Integrate caller-supplied external idempotency and authoritative receipt reconciliation; uncertain payments/GitHub actions or deployments must HOLD, not repeat.
4. **Trustworthy WITNESS.** Move challenge evidence out of worker reach and require authenticated attestation/integrity anchors in an independently protected store.
5. **Coding capability.** End-to-end multi-file tasks on unfamiliar real projects with sandboxed tests; do not invent learning wins. Native BGR vs cold and frequency baselines must be measured under matched compute.
6. **Platform packaging.** Repeatable installer, clean CLI/API, recoverable updater, rollback, explicit secrets policy, observability and published resource budgets.

Patch releases are only for severe correctness, security, provenance or deployment defects. A version is a capability gate, never a license to claim production before testing.

## Explicit holds carried forward

- Native Docker/Windows kernel containment has not been performed in the current Linux evaluation environment.
- Native Bitwork's incremental benefit on real programming work has not been demonstrated.
- Broad autonomous coding, external-skill transfer, permanent self-improvement, and safe irreversible external operations remain research goals.
