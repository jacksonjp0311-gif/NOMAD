# NOMAD v0.17 — Security & Recovery Experiment

**Release:** NOMAD 0.17.0 | **Design:** adversarial engineering/control checks, NOT a blind external exploit study | **Results:** `results/SECURITY_V017.json`, `results/GATES_V017.json`

## What was tested

The threat model separates (1) host execution of *trusted generated fixtures*, (2) arbitrary source that must enter an independent OS isolation boundary, (3) archive intake, (4) mission restart under uncertain external side effects, and (5) the independence of WITNESS acceptance from ordinary test results.

All locally runnable tests use Python's standard `unittest` on Linux with no Docker daemon. The targeted suite contains **19 tests**, all passing, including:

1. Unfamiliar source is denied when a reviewed Docker runtime is unavailable. A mock verifies that the denied path never calls a host runner.
2. Filesystem intake rejects symlinks to outside files, hardlinks, credential-like files, `.git` material, and source-size overruns.
3. A valid source is copied into a disposable read-only source snapshot, without mounting evidence or the original repository.
4. ZIP traversal and ZIP symlink attacks are rejected. An ordinary archive extracts without overwrite.
5. The digest-pinned Docker argv includes no networking, a read-only source mount, non-root UID, dropped capabilities, no-new-privileges, and resource ceilings; unapproved entrypoints/images are refused.
6. Mocked Docker execution records only a **test outcome**, not a WITNESS certification. Uncertain container cleanup changes a nominally successful test into HOLD.
7. A trusted test subprocess omits a host fake API-key environment variable, bounds output, and terminates on timeout.
8. POSIX process-group cleanup terminates a descendant that attempts to remain alive after its parent exits.
9. A separately launched process uses `os._exit` immediately after fsyncing `DISPATCHED`. A new owner sees the exact unresolved effect and is refused a duplicate dispatch.
10. Truncated/tampered effect evidence, stale owner epochs, permanently reused effect IDs, absent independent readback and missing mission ledgers all cause HOLD.

## Result table

| Gate | Observation | Status |
|---|---|---|
| Local security contract tests | 19/19 passed | **PASS** |
| Untrusted source without Docker | No host fallback; action refused | **PASS for fail-closed design** |
| POSIX supervised timeout / child cleanup | Tested, passed | **PASS within restricted local threat model** |
| Hard-crash external-effect uncertainty | Dispatch journal survived, restarted owner refused replay | **PASS for local HOLD behavior** |
| Portable release provenance | v0.16 predecessor and BGR runtime exact hashes preserved | **PASS when package verifier succeeds** |
| Real Docker kernel isolation/escape resistance | Docker not available | **HOLD** |
| Native Windows sandbox/process-tree/NTFS acceptance | This run used Linux | **HOLD** |
| Authenticated off-worker WITNESS | Not implemented | **HOLD** |
| External service exactly-once semantics | No remote idempotency/readback test | **HOLD** |
| Real software transfer or BGR cognitive advantage | Not retested; earlier gates remain open | **HOLD** |

## What changed from v0.16

The trusted fixture's ordinary `subprocess.run` testing path was replaced with supervised child execution and a minimal environment. A process-group cleanup runs after completion or timeout; this covers ordinary descendants on POSIX but is not a complete defense against malicious processes that create new sessions. A Windows `taskkill` fallback is included, but it is not a Job Object and is not claimed to be comprehensive.

The mission controller now creates a separate effects ledger on new missions and refuses to resume if that ledger is missing or unresolved. The original v0.16 event journal schema remains readable, allowing old accepted mission evidence to remain interpretable.

## Null results and risk disclosures

**Docker:** no container was run, so it would be inaccurate to call this a secure sandbox demonstration. The mocked driver tests validate construction and cleanup logic only. No authenticated verifier has been deployed outside worker control. No irreversible external service is used; journal fencing cannot itself stop a stale worker from reaching an external service that ignores its epoch.

**Coding intelligence:** This release is execution hardening. It provides no new matched benchmark proving that learned NOMAD beats cold search on independently authored software, nor that BGR improves the current coding policy. Those gates remain HOLD.

## Reproduction

```bash
python -m unittest tests.test_security_v17 -q
python -m nomad.protect_cli doctor
python scripts/verify_package_v17.py --security --smoke
python scripts/verify_package_v17.py --tests
```

The verifier checks existing hashes **before** optionally executing any tests. It does not rewrite study data, manifests or sources. The canonical engineering study record is never overwritten by the recorder.

## Next experiment

On the target Windows ROG, execute the adversarial container and process-tree tests under an operator-controlled VM/Docker installation using a trusted pinned image. Require independent WITNESS attestation with no worker access to holdouts, and demonstrate remote-operation idempotency/readback before any irreversible action is permitted. Until then **production promotion is HOLD**.
