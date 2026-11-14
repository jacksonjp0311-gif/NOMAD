# NOMAD v0.17 — Security Threat Model

**Version:** 0.17.0 | **Status:** engineering research candidate; untrusted-container kernel acceptance **HOLD** | **Audience:** operators, reviewers, and integrators

## 1. What is protected

1. **Host computer, user files, credentials and connected accounts.** Unfamiliar source code must never run as a normal host Python/Node/Rust child.
2. **Mission goal, source baseline, public tests, held-out evidence and WITNESS receipts.** A candidate repair must not edit its own evaluative evidence or forge authority from public-test success.
3. **External services and writes.** A hard crash after dispatch must not silently replay a potentially non-idempotent operation.
4. **Finite computation.** Candidate execution must have declared time, CPU, memory, process-count, filesystem and output limits.
5. **Historical research provenance.** Existing release ZIP bytes and study results remain unchanged.

## 2. Trust boundaries and reality checks

| Component | Authority | Trust requirement | Current claim |
|---|---|---|---|
| v0.16 mission path | Execute Python on host | Explicitly generated, trusted CodeWorld fixtures only | Retained for compatibility; **NOT a sandbox** |
| v0.17 `supervised.py` | Run trusted host processes | Trusted command, output/time limits, reduced inherited environment | Tested POSIX process-group termination; Windows process trees not guaranteed |
| v0.17 `isolation.py` | Create disposable source copy and request Docker execution | Trusted Docker daemon, pre-pulled digest-pinned image and functioning host/container isolation | Construction and fail-closed controls tested; real daemon **not available here** |
| v0.17 `archive_guard.py` | Read ZIP metadata and extract bounded content | Input ZIP may be hostile | Path-traversal, symlink, expansion and quota checks tested |
| v0.17 `effects.py` | Serialize local dispatch evidence and owner epochs | Operator controls effect root and independent reconciliation callback | Hard-crash HOLD tested; no exactly-once remote guarantee |
| `WITNESS` | Independent consequence observation | Evaluator must be outside worker authority | Separate process for trusted fixtures, **not a malicious-writer-proof signature** |

The Docker CLI and daemon are part of the **trusted computing base**. Having the `docker` command installed does **not** establish that the isolation policy works on a particular host. Docker or Windows kernels, mounts, daemon configuration and image contents must be evaluated separately. The Docker group/socket may confer powerful host privileges to its members; never expose the socket to the test container.

NOMAD's trusted fixture runner does use `exec` internally through the existing bounded research evaluator; a restricted `__builtins__` dictionary is not an adversarial Python sandbox. **Never feed unfamiliar source to that API or assert `--trusted-fixture` for downloaded code.** The security path accepts unfamiliar source only through `nomad.protect_cli sandbox`.

## 3. The untrusted execution contract

The new path uses a **fresh source snapshot**. Source intake refuses symlinks, multiply-linked files, special files, oversized repos, credential-looking files, and `.git` / user configuration subtrees. Snapshots are created outside the mission and WITNESS directories. No original source or private evidence directory is mounted into the container.

`nomad.isolation` generates a Docker invocation with:

- a **pre-pulled, digest-pinned trusted image** (`@sha256:...`) and `--pull=never`;
- non-root UID/GID `65534:65534`, all capabilities dropped, no-new-privileges;
- no network and no IPC sharing (`--network=none`, `--ipc=none`);
- read-only root filesystem and source bind mount;
- a small temporary scratch filesystem, no privileged mounts, no Docker socket;
- CPU, resident-memory, process-count, file-descriptor and wall-time limits;
- host-side process supervision, container removal and a positive cleanup check;
- no arbitrary host-shell invocation or host Python fallback.

A zero test exit code is **not a WITNESS receipt** and never promotes a skill, merges a patch, pushes Git, or authorizes an external action. Failed cleanup or absent isolation engine **HOLDs** the outcome.

This contract has been exercised by argument inspection and a mocked Docker client. **This release has not demonstrated that kernel-enforced restrictions defeat a malicious process.** The actual Docker host acceptance cases listed below are required before adversarial-source execution is supported on the user's Windows ROG.

### Why a container is not a silver bullet

An isolated container is still a dependency on the host kernel, Docker daemon privileges, image composition and correct runtime policy. For high-risk, untrusted binaries, a disposable VM (such as Windows Sandbox/Hyper-V) can provide a stronger separation. NOMAD does not currently implement a Windows Sandbox execution adapter and does not silently substitute host execution when Docker is unavailable.

## 4. External actions and crash ambiguity

`EffectLedger` writes `PREPARED` and then fsyncs `DISPATCHED` **before** an external call. It uses a kernel-released exclusive lock and a monotonically increased local ownership epoch. On restart:

- `PREPARED` with no dispatch is conservatively on hold until accounted for.
- `DISPATCHED` without authoritative confirmation becomes `UNCERTAIN` and cannot be reissued as the same operation.
- A missing receipt cannot be guessed from timing, a PID, or a log filename.
- Reconciliation requires an **independent trusted readback callback** and a digest of its evidence; there is no default auto-approve path.
- A resolved effect ID cannot be reused. Another action needs a new ID and a new independently authorized decision.

**No exactly-once delivery claim:** an external service must itself enforce idempotency tokens and fencing or supply authoritative state readback. A local epoch file does not fence an unaware payment API, website, or repository server. This release **blocks uncertain operations** instead of pretending to solve distributed exactly-once semantics.

The chain and epoch checksums protect against accidental alteration and unsynchronized local writers. An adversary who can rewrite all journal files can recompute them. For production, the verifier and operator should maintain independent trusted storage or signatures.

## 5. Adversarial test matrix

| Test case | Local outcome | Remaining issue |
|---|---|---|
| Unknown code with Docker missing | DENIED before execution | Native Docker installation, daemon readiness and containment untested |
| Source symlink to an outside secret | REJECTED | Filesystem race resistance on Windows needs separate inspection |
| Hardlinks, special files, credentials, `.git`, quota overruns | REJECTED | Broader secret scanning and repository archive formats untested |
| ZIP traversal, symlink entry, duplicate extraction target | REJECTED in unit tests | Third-party archive format fuzzing pending |
| Trusted command inherits host API-key env | Credential key omitted | Host process is still trusted and not an isolation boundary |
| Trusted process survives after parent exit | POSIX process-group cleanup verified | Double-fork/session escape, native Windows Job Objects unverified |
| Trusted process exceeds wall time | Terminated | Windows orphan tree behavior not guaranteed |
| Large output | Captured output is bounded | Total bytes are counted; OS pipe still drains until timeout |
| Docker arguments attempt broader authority | Unapproved command/flags rejected by builder | Real daemon policy and adversarial escape test pending |
| Docker CLI says success but cleanup cannot be confirmed | Outcome HOLD | Docker runtime acceptance pending |
| Hard process death after external dispatch | Recovery HOLD, no duplicate dispatch | Remote service idempotency not integrated |
| Stale owner or tampered local journal | Refused | Checksums are not signatures |
| Mission has unresolved effects or missing effect ledger | Refuses to resume | Legacy mission compatibility intentionally retained |

## 6. Required native Windows/ROG deployment qualification

**Do not run arbitrary internet repositories until the first five checks pass under an operator-controlled test plan.**

1. Validate Docker Desktop (Linux containers) or another reviewed VM backend on the exact host; use a trusted image verified by content digest. Run `py -3 -m nomad.protect_cli doctor --image <digest-pinned-image>`.
2. Execute malicious-but-controlled fixtures inside the container: try reading a host sentinel file, looking for host credentials, resolving outbound DNS, connecting to a blocked endpoint, writing to the protected source mount, accessing host processes, spawning beyond the PID limit, allocating beyond memory budget and exhausting CPU. All must fail within the declared budget. Keep the host sentinel outside every mount.
3. Kill the Python supervisor and Docker client while a container is running. Confirm the orphaned container is forcibly removed before any result is admitted; simulate an unavailable daemon and require HOLD.
4. Exercise native Windows filesystem links, reparse points, case-folding and path races in snapshot intake. Verify the file lock and durable journal on actual NTFS.
5. Demonstrate trusted-procedure termination of whole Windows process trees (ideally a **Job Object** or a reviewed container/VM runtime). The current `taskkill` fallback is not an enforced boundary.
6. Establish a restricted Docker daemon/service account, pre-pulled image and consistent image-digest policy. Verify source privacy and no secret/credential mounts.
7. Run independent WITNESS against the resulting proposed patch from a **separate trusted verifier**. Never let the untrusted test container edit or view private challenge inputs or witnesses.
8. Repeat hard-power-loss and service-restart external-effect reconciliation with genuine idempotency/readback semantics before enabling irreversible integrations.

**Current verdict:** Engineering control implementation **PASS** for the tested local contracts. **Adversarial kernel isolation, Windows native acceptance, authenticated WITNESS and remote exactly-once effects: HOLD.**

## 7. Source references

- [Docker CLI `container run` security and resource options](https://docs.docker.com/reference/cli/docker/container/run/)
- [Python subprocess security considerations](https://docs.python.org/3/library/subprocess.html#security-considerations)
- [Microsoft AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)
- [Microsoft Windows Sandbox overview](https://learn.microsoft.com/en-us/windows/security/threat-protection/windows-sandbox/windows-sandbox-overview)
