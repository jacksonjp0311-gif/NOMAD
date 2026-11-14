# Native infrastructure and memory frontier

**Native isolated execution remains HOLD. The controlled Windows memory diagnosis passed six cases. A strict historical maximum of successfully committed memory remains unproved.** This work starts at `ddb5c32`; earlier receipts and failed observations remain unchanged.

## Fresh infrastructure evidence

The [Windows receipt](../results/NATIVE_WINDOWS_FRONTIER_V018.json) refreshes CIM feature state, services, executable locations, installation registrations, privileges and Docker named pipes. The check includes Docker's current per-user installation paths and Windows Hypervisor Platform as well as the older all-users paths.

Docker, WSL distributions, Podman, Rancher Desktop, VirtualBox, VMware, containerd and QEMU were not found in the checked executable paths or relevant installation registrations. WSL's Windows command stub reports that WSL is not installed. Virtual Machine Platform, Windows Hypervisor Platform, WSL, Hyper-V and Windows Sandbox features are disabled. Firmware virtualization and a running hypervisor are reported present. The session is not elevated and lacks symbolic-link creation privilege.

The [Docker receipt](../results/NATIVE_DOCKER_FRONTIER_V018.json) records HOLD with zero of thirteen planned container cases executed. There was no installation, feature enablement, elevation, reboot or unfamiliar repository execution on the host. Existing Windows Job supervision is useful process cleanup and resource control, but it is not a hostile-code filesystem or network boundary.

## What the memory experiment establishes

[`qualify_memory_frontier_v18.py`](../scripts/qualify_memory_frontier_v18.py) runs six trusted native cases: requests of 32, 128 and 256 MiB, repeated twice, each in a fresh 96 MiB Job. It first reserves an address region, then attempts one commit. It reads the region state with `VirtualQuery`, the usual extended Job counters, `JobObjectMemoryUsageInformation` class 28, and `PROCESS_MEMORY_COUNTERS_EX2`. The [unchanged raw receipt](../results/NATIVE_MEMORY_FRONTIER_V018.json) retains every observation and cleanup result.

Both 32 MiB controls committed successfully. All four larger requests failed with WinError 1455, and the regions remained `MEM_RESERVE`, not `MEM_COMMIT`, after failure. At these before/after observation points, current Job memory and process private commit did not increase. Nevertheless, both Job peak APIs and the process peak-commit counter rose.

| First repetition | Before current Job bytes | After current Job bytes | After native Job peak bytes | Result |
|---|---:|---:|---:|---|
| 32 MiB commit | 23,773,184 | 57,393,152 | 57,393,152 | Commit succeeds |
| 128 MiB commit | 23,289,856 | 23,289,856 | 157,507,584 | Commit refused; region remains reserved |
| 256 MiB commit | 23,441,408 | 23,441,408 | 291,876,864 | Commit refused; region remains reserved |

For every rejected request, the resulting Job peak equalled the current Job charge before the request plus its requested bytes. The process peak showed the same relationship to its own current charge. This is evidence that these counters include an attempted charge that is later rejected on this build. It explains why replacing the Job peak with the process peak would not resolve the earlier discrepancy. It does not establish undocumented kernel internals or an atomic maximum of successful commitments.

Microsoft documents the Job memory limit as a committed-memory limit and its peak fields as continuously maintained counters. The process EX2 API distinguishes private commit, peak private commit and shared commit. Class 28's structure and identifier are present in Microsoft's container implementation, while the public `QueryInformationJobObject` reference does not list that class. The diagnostic records unavailable APIs explicitly; it does not make the production supervisor depend on them. See [extended Job limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information), [process EX2 counters](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex2), [Microsoft hcsshim definitions](https://github.com/microsoft/hcsshim/blob/main/internal/winapi/jobobject.go), and [the query API](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject).

No sampled value is relabelled a strict peak. Allocation refusal and the observed region states pass their finite test; the strict peak gate remains HOLD. Repeat with a new receipt path:

```powershell
py -3 -B scripts\qualify_memory_frontier_v18.py --output runs\operator-check\memory.json
```

## Small containment corrections

The existing isolation adapter now offers `include_output=True`. It returns `output_utf8` only after confirmed cleanup, complete capture within 8192 bytes, strict UTF-8 decoding, and agreement with the recorded SHA-256 and total byte count. Truncated, malformed or inconsistent observations HOLD. Existing callers receive no new output field. Output combines stdout and stderr and is untrusted; the parent verifier must parse an exact protocol and compare against separately held expectations. An exit code or candidate-authored report never establishes correctness.

The native supervisor-death probe now receives the exact serialized qualification policy instead of silently substituting a 30-second timeout. All source quotas and resource settings remain bound to the declared policy. These paths have explicit mocked contract tests; Docker availability is still required for native qualification.

## Operator provisioning instructions

The following steps are instructions only. They were not performed by this task. A privileged operator must decide when to install software, enable required features and restart. The code currently supports Docker's local Linux engine at `npipe:////./pipe/dockerDesktopLinuxEngine`; another installed VM or container tool does not automatically satisfy that interface.

1. In an administrator PowerShell session, install WSL without an unrelated default distribution using `wsl --install --no-distribution`. Restart when Windows requests it. After restart, check `wsl --version` and `wsl --status`; resolve installation errors before proceeding. Microsoft documents this option and the required installation workflow in [WSL commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands) and [WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install).
2. Obtain and review Docker Desktop from its [official Windows installation page](https://docs.docker.com/desktop/setup/install/windows-install/). Choose its WSL 2 backend and Linux containers, complete any operator-approved restart, and start Docker Desktop. Current Docker requirements include WSL 2.1.5 or later. Its per-user installer cannot itself supply every required privileged Windows feature; the earlier Windows setup must be complete.
3. Independently review a Linux Python image that supplies the required interpreter and dependencies. Record its exact repository digest. The image must not declare volumes. Pull that reviewed digest through the local Linux engine as an explicit operator provisioning action; no NOMAD harness fetches an image. Replace the placeholder below with the actual reviewed 64-hex digest:

```powershell
$Image = 'registry.example/reviewed-python@sha256:REPLACE_WITH_REVIEWED_64_HEX_DIGEST'
$Engine = 'npipe:////./pipe/dockerDesktopLinuxEngine'
docker --host $Engine info --format '{{.OSType}}'
docker --host $Engine info --format '{{json .SecurityOptions}}'
docker --host $Engine pull $Image
docker --host $Engine image inspect $Image --format '{{json .RepoDigests}}'
docker --host $Engine image inspect $Image --format '{{.Os}} {{json .Config.Volumes}}'
```

The output must identify Linux, seccomp support, the exact reviewed digest and no configured volumes. Tags such as `latest` do not satisfy the policy. Local readiness is still not qualification.

4. From the checked checkout, choose a new evidence directory and run the real bounded probes:

```powershell
$Evidence = 'runs\operator-native-check-001'
py -3 -B scripts\qualify_windows_v18.py --output "$Evidence\windows.json" --log "$Evidence\windows.log"
py -3 -B scripts\qualify_isolation_v18.py --image $Image --output "$Evidence\isolation.json"
py -3 -B scripts\qualify_recovery_v18.py --image $Image --isolation-receipt "$Evidence\isolation.json" --output "$Evidence\recovery.json" --evidence-root "$Evidence\recovery-evidence"
py -3 -B scripts\qualify_function_recovery_frontier_v18.py --image $Image --isolation-receipt "$Evidence\isolation.json" --output "$Evidence\function-recovery.json" --evidence-root "$Evidence\function-recovery-evidence"
```

The isolation receipt must contain thirteen actually executed PASS cases, stable source bindings and an unchanged protected sentinel. Recovery refuses a missing, stale, inconsistent or HOLD isolation receipt. A failed probe remains a failed probe; preserve its directory and use a new path after a reviewed correction. The qualified policy is 10 seconds per execution, 128 MiB, 0.5 CPU and 16 PIDs with the declared source quotas. A PASS does not authorize broader settings or a different image. Preserve all journals and hashes for independent review before advancing any gate.

The separate [function recovery qualifier](../scripts/qualify_function_recovery_frontier_v18.py) declares 21 native cases: a reference and terminal replay, twelve interruption boundaries, observed live-container owner death and cleanup, an actual mixed two-file patch followed by recovery, final rejection and source restoration, and five corrupted-evidence refusals. Its receipt binds the function adapter, complete runtime source, host, image, policy, original source and retained evidence files. Native execution has not been performed here: the [current receipt](../results/FUNCTION_RECOVERY_FRONTIER_RECHECK_V018.json) remains HOLD with zero cases and no mission initialized. The earlier receipt remains unchanged at its earlier runtime identity. The six qualifier unit tests use explicit controlled doubles only for controller contracts; they do not establish a Docker pass. Aggregate whole-mission compute limits, power loss and service restart remain outside this qualifier.

## Original archive search

The [bounded archive search](../results/ARCHIVE_SEARCH_FINAL_FRONTIER_V018.json) hashes ZIPs and reads central directories under Downloads, both desktop locations, Documents/Codex and Codex attachments, then examines reachable Git archive blobs. It does not extract archives or regenerate historical results. It finds compact v0.17 copies but no recovered v0.16/v0.15/v0.14 originals or verified full v0.17 archive. One malformed ZIP remains unreadable. This is a scoped local search, not proof that no original exists in cloud storage, a recycle bin or another machine. Gate D remains HOLD until the authentic bytes are supplied and checked against the pinned original hashes.
