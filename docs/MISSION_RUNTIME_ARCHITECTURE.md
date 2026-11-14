# NOMAD v0.16 — MISSION RUNTIME architecture

## Purpose

Connect the existing NOMAD repair and WITNESS components into a durable, restartable execution controller without broadening scientific claims. **Scope: one trusted, generated Python CodeWorld repository containing one `solution.py` and public `unittest` suite.** It is not an untrusted GitHub-repo executor.

## Identity and ownership

At mission creation, persist three independent artifacts:

- `goal.json`: task identity, public examples, source digest, withheld-evidence digest, budget, and generated-contract digest.
- `original.py`: immutable repair starting point.
- `sealed/withheld.json`: separate challenge and final examples, not passed to search. They remain readable to an adversary with filesystem access: process separation, **not** an OS secrecy boundary.

The mission ID is a digest of task identity, starting source, and public problem declaration. A nonblocking OS file lock (`flock` on POSIX and `msvcrt.locking` on Windows) grants one active controller. Recovery does not rely on process IDs or stale lockfiles.

## Durable event transitions

```
MISSION_CREATED
  ATTEMPT_PLANNED
    PATCH_APPLIED
      PUBLIC_RESULT
        ├── failed ── PATCH_REVERTED ── next candidate
        └── passed ── WITNESS_RESULT
                        ├── contradicted ── PATCH_REVERTED
                        └── supported ── FINAL_RESULT
                                         ├── contradicted ── PATCH_REVERTED
                                         └── supported ── COMPLETED
```

If all registered candidates fail or the bounded attempt budget is exhausted, source is reset to its original bytes and `EXHAUSTED` is journaled.

Each journal record has a strict schema, monotonic index, previous-record SHA-256, and own SHA-256. It is appended and fsynced. An altered, truncated, or out-of-order row causes HOLD. The origin record binds the goal's file hash. These hashes are *integrity checks*, not digital signatures or protection from a malicious actor who can rewrite every file and recompute the chain.

## Crash reconciliation

| Observed state on restart | Required behavior |
|---|---|
| Planned, no patch receipt, source still original | Apply proposed source once |
| Planned, no patch receipt, source already equals candidate | Record applied transition; do not write again |
| Applied, no public result | Rerun public test process because outcome is unknown |
| Public result already recorded | Reuse recorded result |
| WITNESS result already recorded | Reuse receipt rather than reattest |
| Final result already recorded | Commit or revert according to outcome without retesting |
| Failed attempt; rollback bytes written but not journaled | Recognize original hash and journal completion of rollback |
| Completed | Compare current source to committed hash; return previous receipt |
| Unexpected intermediate source bytes | HOLD; never overwrite unrecognized code |
| Another process currently owns workspace | HOLD; no concurrent worker race |

**Exactly-once boundary:** durable logical events and content-idempotent file edits can be reconciled. Public-test and verifier subprocesses may have already run just before a crash that prevented their receipt from being written, so their execution can repeat. The system cannot claim exactly-once effects for arbitrary tools, network calls, subprocesses or untrusted code. The v0.17 work must add sandboxed workers, effect fencing, process-tree cleanup and resource controls.

## Components reused, not replaced

`generate_python_candidates()` from NOMAD's CodeWorld repair system supplies AST transformations; `unittest` evaluates the public behavior in a fresh process; `nomad.mission_witness` runs in another process, reuses the original `Witness` attestation and evaluates a separate final split. The controller never sends `task.challenge`, `task.final`, or the evaluator's `true_family` into candidate selection.

The authentic BGR v1.4 runtime is preserved in `vendor/` and available via `nomad.native_bitwork`. It remains a **shadow observer**, not a source of privileged patch-selection claims.

## Operational limitations

No arbitrary repo checkout, network fetch, untrusted shell executor, container isolation or general-purpose filesystem permissions exist in v0.16. Linux process-lock behavior is tested; Windows-native lock and restart behavior is implemented but not verified in this environment. Test and verification timeouts constrain direct child processes; they are not full process-tree sandboxing.
