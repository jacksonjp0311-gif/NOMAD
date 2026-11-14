# NOMAD v0.18 native qualification follow-up

**Gate A, native isolated execution: HOLD. Tested Windows process supervision: PASS. Strict interpretation of the native peak-memory counter: HOLD.**

This follow-up starts from Git commit `58515665dcccfdaa1c046907b51189a19e48c5aa`.
It preserves the original v0.18 receipts and the earlier security report. It
does not install software, enable Windows features, elevate privileges, reboot,
or execute unfamiliar repository code on the host.

## Current host evidence

The [current native receipt](../results/NATIVE_QUALIFICATION_WINDOWS_POST_REVIEW_V018.json)
contains fresh read-only CIM, executable, service, privilege and pipe checks.

| Check | Observed result |
|---|---|
| Operating system | Windows 11 Pro, build 26200, 64-bit |
| Hardware | ASUS ROG Flow Z13 GZ302EA; Ryzen AI MAX+ 395 |
| Firmware virtualization / hypervisor present | Both reported true |
| VirtualMachinePlatform / WSL / Hyper-V / Windows Sandbox features | Disabled, `InstallState=2` |
| WSL status | Exit 50, explicitly reports not installed |
| WSL distribution listing | Exit 1, explicitly reports not installed |
| Docker CLI and standard Desktop installation files | Absent |
| Docker Desktop Linux and default engine pipes | Absent, WinError 2 |
| Docker, WSL and VM compute services | None returned |
| Podman, nerdctl, containerd, VirtualBox, VMware and QEMU commands | Not found on PATH |
| Elevated administrator / symbolic-link privilege | Not available in this session |

The WSL executable is an installed Windows command stub, not evidence of an
installed Linux runtime. Read-only CIM feature inspection succeeded without
elevation; this improves the earlier feature-inspection HOLD. SLAT and VM
monitor extension flags reported false while a hypervisor is present. That
combination is retained as observed; it is not evidence that this processor
cannot support virtualization.

The [current Docker receipt](../results/NATIVE_QUALIFICATION_DOCKER_POST_REVIEW_V018.json)
records `DOCKER_BINARY_UNAVAILABLE` and `REVIEWED_IMAGE_UNCONFIGURED`. It declares
13 planned controlled cases and **zero executed container cases**. The native
Python command returned 3 for HOLD. No alternate reviewed VM was available.

## Changes and measured native outcomes

Windows Job budgets now reject booleans, fractional counts, zero limits and
out-of-range values before making native calls. Trusted supervision permits
explicit bounded Windows memory/process settings while refusing to imply those
settings are enforced on another platform. Sandbox count types and subprocess
timeout/output types are also validated before execution.

The final Windows qualification executed 14 tests in 4.093 seconds, with no
failures, errors or skips. Ten tests exercise native Windows mechanisms or
controlled process-death/assignment faults; four check parameter or receipt
contracts. Source hashes were unchanged across that run.

| Experiment | Observation |
|---|---|
| Explicit process breakaway | Denied with WinError 5; escaped-process marker absent |
| Job process count capped at six | Four children start in addition to launcher/target; next creation denied with WinError 1816 |
| Memory commit under a 96 MiB Job budget | 80 MiB of explicit allocations succeed; the next allocation is refused with WinError 1455 |
| Private commit around the rejected allocation | 91,222,016 bytes before and after; no increase at these measurement points |
| Supervisor death before Job assignment | Waiting launcher exits; requested target never starts |
| Three repeated supervisor deaths after target launch | Every recorded live Job member exits before fixture cleanup |
| Inherited Windows probes | Parent-exit cleanup, timeout tree cleanup, assignment denial, owner-death cleanup and junction rejection pass |

Native process and memory limits are tested on controlled trusted commands.
They do not establish a hostile-code filesystem/network boundary or VM
containment. Job supervision does not cover service/WMI-mediated execution.

## Preserved failures and limits of the measurements

[The initial memory result](../results/NATIVE_QUALIFICATION_INITIAL_FAILURE_V018.json)
failed an assertion that the native peak counter must never exceed the
configured Job limit. Allocation refusal was observed, but the peak counter was
100,675,584 bytes in the first run and 100,864,000 bytes in a repeat, above the
100,663,296-byte limit. The earlier final direct-allocation probe reported a raw
peak of 108,683,264 bytes. The post-review repeat reported 108,638,208 bytes while
rejecting the allocation and leaving the worker's measured private commit
unchanged. Both original receipts remain intact.

The Windows API documents commit refusal at the limit and separately reports a
peak counter. These observations do not establish how this Windows build
accounts for rejected allocation attempts. The implementation retains the raw
counter, adds an explicit counter-scope label, and does not claim an atomic
historical maximum of successfully committed bytes. **The strict peak-counter
gate stays HOLD.** The test now checks direct allocation refusal and measured
private commit before/after the failed call; it does not hide the old result or
raise the allowed memory budget to obtain a pass.

[A repeated owner-death run](../results/NATIVE_QUALIFICATION_OWNER_DEATH_FAILURE_V018.json)
also exposed a fixture cleanup error: the target had exited, but its temporary
directory was still in use. The old observation tracked only the target. The
new probe records every live Job member immediately before controlled owner
death and waits for all observed members, including the launcher, before
cleaning the fixture. Cleanup errors are not ignored.

Independent review of the recovery qualifier found that an exception during a
Docker observation could kill the owner but skip daemon-container cleanup. The
same pattern was found and fixed in the containment qualifier: cleanup now runs
even when observation or owner waiting fails, and it retains ownership-label
checks. Both qualifiers also preserve a FAIL receipt if the protected sentinel
is deleted or unreadable. Twelve explicit mocked contract tests cover these
failure paths and prerequisite/output integrity; they are not native Docker
qualification. The post-review native receipts above bind the corrected source.
All earlier receipts, including earlier HOLDs, are preserved.

Process-death tests do not demonstrate hard-power-loss durability, and a
passing three-repetition probe is not a long-duration service reliability
claim. Native symbolic-link qualification remains HOLD because its required
Windows privilege is unavailable.

## Repeatability and future qualification binding

```powershell
py -3 scripts\qualify_windows_v18.py --output <new-windows-receipt.json> --log <new-log.txt>
py -3 scripts\qualify_isolation_v18.py --image <reviewed-image@sha256:digest> --output <new-docker-receipt.json>
```

Both commands refuse to overwrite prior evidence. The Docker harness binds a
receipt to backend, exact policy, image, current host identity and source hashes
before/after execution. A self-checksum covers the full receipt. These hashes
are integrity checks, not signatures or authentication; a later experiment
must pin an operator-owned trusted receipt and independently require matching
host, policy, image and current source. Archived HOLD receipts authorize no
experiment or hidden-evidence access.

The current Docker probe policy is timeout 10 seconds, 128 MiB memory, CPU share
0.5 and 16 PIDs, with the existing source limits. A future PASS under that
configuration does not qualify a different budget or image. Actual isolated
restart equivalence also needs its own native receipt; mocked mission tests
cannot supply it.

The remaining prerequisite is an operator-provisioned, reviewed local Linux
Docker/VM backend and reviewed image. Feature enablement may require elevation
and a restart. No such system change was attempted by this follow-up.

## References

- [Win32 optional feature states](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-optionalfeature)
- [Job Object committed-memory limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)
- [Job Object extended limits and peak counters](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)
- [Process private commit measurement](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex)
