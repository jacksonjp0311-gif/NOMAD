# NOMAD v0.17.0 — SECURITY & RECOVERY

**Engineering result:** PROTECTION LAYER IMPLEMENTED. Local admission, process supervision, effect-recovery and clean-package checks to be reported from the final verification record.

**Adversarial execution authorization:** **HOLD** until the Docker/VM boundary is natively exercised on the deployment host. The source launcher is intentionally fail-closed when Docker is not available.

## What shipped

- `isolation.py`: digest-pinned, pre-pulled Docker-only execution, unprivileged user, no network, readonly snapshot, limited processes/memory/CPU, no Docker socket or private WITNESS bind, and cleanup confirmation.
- `supervised.py`: trusted subprocess output/time limits, minimal environment, POSIX process-group cleanup, best-effort Windows termination (not a guarantee).
- `archive_guard.py`: ZIP entry validation, traversals/symlink/duplicate/size checks.
- `effects.py`: fsynced pre-dispatch journal, process ownership epochs, unconfirmed-effect hold, mandatory independent readback and never-reused effect IDs.
- Mission start now checks the external-effect journal. Prior mission states remain readable; the v0.16 event schema is deliberately retained for restart compatibility.
- Security-specific adversarial tests and verified-vs-untested research records.

## Scientific and production boundaries

- No measured external coding gain over cold search; no native BGR coding advantage claimed.
- No live Docker kernel isolation test or Windows Job Object support in this release; Windows native behavior not verified here.
- No encrypted/authed WITNESS remote attestation or irreversible remote operation integration.
- A Docker test passing does **not** complete a coding mission or certify a patch. Verification remains independent.
- The previous v0.16 full archive is preserved unchanged. Production qualification remains held.

## Next release

**v0.18 — PLATFORM:** native Windows/ROG containment acceptance, process trees, Docker/VM contract verification, external-effect idempotency/readback, authenticated WITNESS, and measured real coding tasks. No superficial patch-version ladder.
