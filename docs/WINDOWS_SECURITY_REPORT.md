# NOMAD v0.18 Windows security qualification

**Native Docker containment: HOLD. Windows trusted-process supervision and the tested filesystem controls: PASS within the scope below. Publication remains HOLD.**

The native Windows machine had no Docker binary available and no reviewed,
digest-pinned Linux image configured. The Docker probe harness therefore executed
no repository code and wrote [an explicit HOLD receipt](../results/NATIVE_ISOLATION_V018.json).
No Docker/WSL/VM installation, elevation, virtualization change, or host security
setting change was performed. The historical [v0.17 threat model](SECURITY_THREAT_MODEL.md)
is retained as its original record; this document describes the current additions.

## What actually ran on Windows

The focused command was:

```powershell
py -3 -m unittest tests.test_security_v17 tests.test_platform_isolation_v18 -v
```

The final focused run executed 32 tests in 2.667 seconds: 30 passed and two were
explicitly skipped. The new module contains 13 tests, **five of which exercise
real Windows mechanisms**. The remaining new tests exercise intake and Docker
orchestration contracts; mocks never count as native Docker evidence.

| Native Windows experiment | Observed result |
|---|---|
| Parent exits while an ordinary subprocess descendant remains alive | PASS: Job termination and process synchronization handles confirm descendant exit |
| Wall timeout with a live target and descendant | PASS: entire observed Job tree terminates |
| Job assignment refused before requested command starts | PASS: target sentinel is never created |
| Supervisor exits abruptly with `os._exit` while target is alive | PASS: closing the last Job handle terminates target |
| Real directory junction points outside admitted source to a protected sentinel | PASS: admission rejects the junction and sentinel remains unchanged |

The inherited POSIX process-group test is skipped on Windows. The inherited
symbolic-link fixture is skipped only for Windows error 1314 (missing creation
privilege). **Native symbolic-link qualification remains HOLD.** A passing
junction test does not turn the unexecuted symbolic-link case into a pass.

Development failures are retained in
[PLATFORM_ISOLATION_ITERATIONS_V018.json](../results/PLATFORM_ISOLATION_ITERATIONS_V018.json).
One real test exposed a Windows termination race: a Job's active count reached
zero before process handles signaled termination. Cleanup now checks both.
Another exposed incomplete Windows `DirEntry.stat` identity fields; admission
now obtains identity and link counts using `lstat`.

## Enforced process contract

Windows uses an unnamed, non-inheritable Job Object with kill-on-close, a
configured aggregate commit limit of 1 GiB, and a configured active-process
limit of 64. A trusted Python launcher starts with `-I -S` and waits for a pipe
release. The supervisor assigns that launcher to the Job before releasing it
to launch the requested command. Assignment failure denies execution; no
`taskkill` or parent-only fallback is used.

Cleanup terminates the Job, verifies its active count, and waits for observed
member process handles. Receipts expose CPU user/kernel time, peak Job commit,
and process counts measured by Windows. These are measurements of the supervised
Windows process tree, **not** Docker VM or container resource consumption.
The memory/process limits are configured in the kernel; their exhaustion has
not been independently exercised by these five native tests. Wall timeout and
ordinary descendant cleanup have been exercised.

A Job Object is not a filesystem, credential, network, or hostile-code sandbox.
Service- or WMI-created processes are outside the ordinary child-process
inheritance contract. Only trusted NOMAD fixtures and the Docker client use
host supervision. Unfamiliar repository commands have no host fallback.

## Source and archive boundary

Admission rejects links, Windows reparse points, hardlinks, nonregular files,
case collisions, Windows device names, alternate-stream syntax, trailing-dot or
space aliases, credential-like paths, and `.git`. Traversal depth, entry count,
file count and byte totals are bounded. File identity and size are checked
before and after copying. ZIP parent/member spellings are checked before
extraction; extraction never overwrites an existing destination.

The supported input is a **source-only directory**, not an arbitrary working
checkout containing credentials, dependency caches or Git metadata. The
container receives a disposable copy rather than the original repository.
Private mission partitions, effect journals and learning records are outside
that mount.

These controls assume the operator controls the host. They do not provide a
transactional filesystem snapshot against a malicious concurrent process
running under the same Windows account. A same-user attacker can also rewrite
NOMAD itself or recompute local checksums. Those threats require independent
storage/authentication and stronger host separation.

## Docker implementation and qualification gap

Metadata preflight requires the local Linux Docker engine, seccomp support, and
an already-present image with the exact requested repository digest. It rejects
image-declared volumes. Docker uses a fresh empty client configuration and a
fixed local endpoint: the Docker Desktop Linux named pipe on Windows, or the
local Docker socket on POSIX. User contexts, remote daemon selection, registry
credential helpers and inherited Docker environment settings are not used.

Execution overrides the image entrypoint and specifies a non-root user,
read-only root and source mount, disabled networking/IPC, private cgroup
namespace, all capabilities dropped, no privilege escalation, disabled image
healthchecks, no restart policy, bounded tmpfs, PID/memory/swap/CPU/file-descriptor
limits, wall timeout and bounded captured output. Images are never pulled
automatically. These settings are implemented contracts, not proof that this
machine's absent daemon enforces them.

Container names are recorded before mission dispatch. Cleanup inspects NOMAD
ownership labels and removes the inspected immutable container ID, refusing
foreign name collisions. Missing or uncertain cleanup keeps the result on HOLD.
An interrupted mission discards a lost execution outcome; it requires explicit
confirmed cleanup before a fresh experiment. This is not exactly-once remote
execution. Irreversible external actions remain governed by the separate effect
ledger and independent reconciliation.

## Repeatable native qualification

After an operator provisions and reviews Docker Desktop and a suitable image:

```powershell
py -3 scripts\qualify_isolation_v18.py --image <reviewed-image@sha256:digest> --output <new-receipt.json>
```

The image placeholder must be replaced by a real, reviewed digest reference.
The harness refuses to overwrite an existing receipt. It has 13 controlled
cases, all **unexecuted on this host**:

| Controlled case | Required observation |
|---|---|
| Non-root | Effective user and group are non-root |
| Protected host | Synthetic sentinel outside mounts and Docker socket cannot be read |
| Environment | Synthetic host environment marker is absent |
| Read-only mounts/root | Writes to source and root filesystem fail |
| Networking | Loopback-only interfaces, no default IPv4 route, refused outbound TCP, DNS UDP and IPv6 |
| Namespaces | Controlled entrypoint is PID 1; kernel control file is not writable |
| Resource configuration | cgroup v2 reports the declared memory/PID/CPU limits |
| PID exhaustion | Bounded process creation stops below the declared cap |
| CPU budget | Controlled CPU loop stays below the declared share with tolerance |
| Memory exhaustion | Allocating child is killed and the cgroup `oom_kill` counter increases |
| Output budget | Large controlled output is truncated with a retained digest |
| Wall timeout | Sleeping command is terminated and container removal confirmed |
| Supervisor death | A live container is observed, owner killed, and the recorded container independently removed |

Any changed host sentinel forces FAIL. An exit code of 137 alone is not treated
as evidence of OOM enforcement. Missing prerequisites or ambiguous cleanup
produce HOLD. Even a future complete pass qualifies these bounded fixtures on
that engine/image/host; it is not proof against all container escapes.

## Remaining gates

Native Docker/VM containment, isolated interrupted mission equivalence, real
third-party repository repair with independent final validation, native
symbolic-link qualification, power-loss durability, remote WITNESS
authentication and externally fenced irreversible actions remain unqualified.
The new mission verifier supports a strict arithmetic `solve(x, y)` contract;
it does not certify general Python behavior or arbitrary repository repairs.
No security test establishes a Bitwork intelligence advantage.

## Technical references

- [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [Microsoft AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)
- [Docker container run options](https://docs.docker.com/reference/cli/docker/container/run/)
