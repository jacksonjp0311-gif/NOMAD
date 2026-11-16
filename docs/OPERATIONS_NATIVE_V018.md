# Operations: native prerequisite setup

Updated 2026-11-16: the authorized setup installed **WSL 3.0.5.0 and Docker Desktop 4.99.0**, without rebooting. Virtual Machine Platform is enabled, Windows records a pending restart, and WSL 2 cannot yet start. Docker is installed per-user with the WSL 2 backend and Windows-container integration disabled. Its desktop process is not running and both engine pipes are absent. The [final setup receipt](../results/SETUP_OPERATIONS_V018.json) binds installed identities, official installer checksum/signature and raw logs. Installation is complete; backend readiness and native qualification remain HOLD.

The first elevated Windows PowerShell script launch was refused with `UnauthorizedAccess` because script execution is disabled in that host, before WSL ran. Its [separate attempt receipt](../results/SETUP_ATTEMPT_OPERATIONS_V018.json) preserves Windows event 4100. The subsequent authorized direct launch of Microsoft's signed `wsl.exe` succeeded, without changing execution policy. The Docker installer matched its official SHA-256 and valid Docker Inc signature, then completed once with exit code zero. No image was pulled or run, no backend activation was requested and no reboot was initiated.

The installed absolute CLI at `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe` reports Docker 29.9.3. This already-running Codex process still has its earlier inherited `PATH`, where `docker` is not found. Thus a PATH-based prerequisite receipt can correctly report an unavailable CLI in that process while the installed absolute executable exists. No global environment edit or backend retry was made. Use a fresh terminal after the later operator-controlled restart; installation presence alone still does not satisfy the engine or image gates.

The original read-only [inventory](../results/PREREQUISITES_OPERATIONS_V018.json), preserved unchanged, records the state before setup: no Docker installation, WSL absent, and the relevant optional features disabled. It is historical evidence, not the current installation state.

Installation of WSL and Docker Desktop was authorized and completed. **A restart is not authorized in this session.** Work stopped with Windows reporting a pending restart. No image download is part of this setup authorization: an exact reviewed image digest must be selected separately first. The procedure below records the reviewed setup path; do not repeat completed installation steps. After the operator chooses a later restart, Docker's first start may still require its license prompt before engine checks.

## Minimal procedure for an authorized operator

1. Open **PowerShell as administrator** and run:

   ```powershell
   wsl --install --no-distribution
   ```

   This installs WSL and enables its required Windows components without installing a default user distribution. Let the supported installer manage the required components, including Virtual Machine Platform. Do not independently enable Hyper-V, Windows Sandbox, Windows containers, or change global security settings. Microsoft documents the administrator requirement and restart in its [installation procedure](https://learn.microsoft.com/en-us/windows/wsl/install); the [command reference](https://learn.microsoft.com/en-us/windows/wsl/basic-commands) documents `--no-distribution`.

2. If Windows requests a restart, **stop without restarting**. Only after the operator separately chooses to restart, use a normal PowerShell session to run:

   ```powershell
   wsl --version
   wsl --status
   ```

   Resolve an installation error before proceeding. The WSL 2 backend requires WSL 2.1.5 or later. No user Linux distribution is required for Docker Desktop's own backend.

3. Obtain the x86_64 Docker Desktop installer from [Docker's official Windows setup page](https://docs.docker.com/desktop/setup/install/windows-install/). Verify the release checksum against the linked official release notes, review its terms, and choose the documented **per-user installation** where available. Select **WSL 2** and **Linux containers**, then start Docker Desktop. Docker currently documents that per-user installation does not itself require administrator privileges; enabling the missing Windows prerequisites above does. Do not enable Windows containers or an alternative backend for this operation.

4. Check the local engine without pulling or running an image:

   ```powershell
   $NomadEngine = 'npipe:////./pipe/dockerDesktopLinuxEngine'
   docker --host $NomadEngine version
   docker --host $NomadEngine info --format '{{.OSType}}'
   docker --host $NomadEngine info --format '{{json .SecurityOptions}}'
   ```

   The server must respond, report Linux and expose the required seccomp support. An installed CLI alone does not qualify isolation. Do not substitute a remote engine.

5. **Stop before downloading an image.** Select and independently review an exact Linux Python image identified as `repository@sha256:<64 hexadecimal characters>`, including interpreter/dependencies and declared volumes. Only after that digest and image acquisition are authorized should it be pulled through the local engine. No `latest` tag or placeholder digest is an approved image.

After setup, NOMAD must rerun its actual thirteen containment probes against that reviewed image and exact policy. The retained twenty-one-case function recovery suite may run only after matching containment PASS. The new persistent controller's decision, pending-forecast, public-update and accepted-cache stages need separately registered native recovery coverage; twenty-one default-path passes cannot qualify them. Setup success alone is not a containment, recovery, repair or release PASS.

Official instructions were checked again on 2026-11-16. The inventory reports firmware virtualization enabled and a hypervisor present. The accompanying false CIM SLAT/VM-mode values are not treated as proof that the hardware is incompatible. Approved setup enabled Virtual Machine Platform and installed the vendor components. Legacy WSL 1, Hyper-V and Sandbox features remain disabled. No execution-policy, firewall, credential or BIOS change was issued by the agent. The Windows boot time remains unchanged from before installation.

Raw logs remain in [the task setup directory](C:/Users/jacks/Documents/Codex/2026-11-14/files-pasted-by-the-user-nomad/work/operations-native-20261116). The optional combined log-ZIP and receipt command was rejected by automatic approval review: **blocked by policy; no specific reason supplied**. It made no changes and was not retried. The final receipt was written with the dedicated file-edit tool; the installer executable and raw logs remain outside the source package. No log ZIP was created.

## Authentic task readiness

The [bounded task review](../results/AUTHENTIC_TASK_OPERATIONS_V018.json) checked two existing leads and found **no full-repository task ready to run**. The smallest retained exact function is `search()` from [pygorithm issue 38](https://github.com/OmkarPathak/pygorithm/issues/38), pinned to commit `07b46856dcdf99794396332707be89cb62a40ca6`, file `pygorithm/searching/depth_first_search.py`. Its full module is refused because `inspect` is outside the admitted function imports. The exact function-only projection remains a parse fixture, not an equivalent full-repository repair. The current generic mutation grammar also lacks a `None`-path initialization proposal; no answer-specific mutation was added.

The same commit's [public upstream test](https://github.com/OmkarPathak/pygorithm/blob/07b46856dcdf99794396332707be89cb62a40ca6/tests/test_searching.py) supplies two independently authored traversal expectations. Their original text and data-only extraction are retained in [the upstream-test receipt](../results/UPSTREAM_DFS_TEST_OPERATIONS_V018.json) and the task review. They are public development regressions, now exposed to this work, not a newly claimed private final contract. No upstream code was imported or executed. No full repository snapshot, private contract or repaired candidate was prepared. The next existing lead, `w2n` issue 74, remains refused because its full module exceeds the AST budget. The review stopped after those two leads.

The [single new archive-location search](../results/LINEAGE_LOCATION_OPERATIONS_V018.json) checked `C:\Users\jacks\OneDrive\Documents`, which is outside the roots recorded by earlier searches. It found zero ZIP paths. No cloud file was hydrated, archive extracted or history regenerated. The missing predecessor archives remain missing; this is not an exhaustive machine or cloud search.
