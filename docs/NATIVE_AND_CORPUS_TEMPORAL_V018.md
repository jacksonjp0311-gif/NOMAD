# Temporal prerequisites, history and authentic corpus

Version remains 0.18.0. The temporal work starts at `3ffd46741ddb99693cd05f35153daec778a2105a`. Existing adaptive results, including the failed registered combined quality/cost comparisons, remain unchanged. No native Docker repository repair or unseen corpus trial ran during this prerequisite refresh.

## Fresh native evidence

The [read-only inventory](../results/INFRASTRUCTURE_TEMPORAL_V018.json) again found no Docker executable, checked Docker Desktop installation, Docker engine pipe, registered alternative backend or relevant running service. The WSL command stub reports that WSL is not installed. The checked WSL, Virtual Machine Platform, Hyper-V, Hypervisor Platform and Sandbox features remain disabled. The session is not elevated. No installation, feature enablement, security-setting change or reboot was performed.

The new [Windows native receipt](../results/NATIVE_WINDOWS_TEMPORAL_V018.json) and [raw log](../results/NATIVE_WINDOWS_TEMPORAL_V018.log) record **14 passed, zero skipped, zero failures and zero errors**, with source unchanged. These are controlled trusted tests of assignment failure, junction refusal, timeouts, parent/owner death, breakaway denial, process creation limits, memory allocation refusal and budget validation. Windows Job supervision is not a hostile-code filesystem or network boundary. Process-death cleanup does not establish hard-power-loss durability.

The [Docker receipt](../results/NATIVE_DOCKER_TEMPORAL_V018.json) is **HOLD: zero of thirteen cases executed** because the engine is absent and no reviewed digest image is configured. The strict successful-memory-commit peak also remains HOLD. Allocation refusal and native high-water counters are separate observations; prior native counters can include rejected charges. No sampled counter or sum of separate peaks is relabelled a strict simultaneous peak. Source-bound native function recovery requires all twenty-one registered cases only after matching actual containment PASS; an absent backend never becomes a fixture-based pass.

## Operator setup, not actions performed

The current supported path is a reviewed Docker Desktop Linux engine at `npipe:////./pipe/dockerDesktopLinuxEngine`. An operator must explicitly approve installation, privilege changes and restarts outside this task. Current Microsoft instructions require an administrator shell to install missing WSL features, and `--no-distribution` avoids adding the unrelated default distribution. Docker documents WSL 2.1.5 or later for its WSL backend. See [Microsoft installation](https://learn.microsoft.com/en-us/windows/wsl/install), [WSL command options](https://learn.microsoft.com/en-us/windows/wsl/basic-commands) and [Docker's Windows setup](https://docs.docker.com/desktop/setup/install/windows-install/), checked for this refresh.

1. In an operator-approved administrator PowerShell session, run `wsl --install --no-distribution`. Complete a requested restart. Then check `wsl --version` and `wsl --status` and resolve installation errors.
2. Obtain Docker Desktop from its official Windows setup page, review its requirements and applicable terms, select the WSL 2 backend and Linux containers, and start it. An installed executable alone is insufficient.
3. Independently review a Linux Python image and record its exact repository digest. It must supply the registered interpreter/dependencies and declare no volumes. Pre-pull only that reviewed digest through the local engine; NOMAD does not automatically fetch an image. Replace the placeholder below before running these operator commands:

```powershell
$Engine = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$Image = 'registry.example/reviewed-python@sha256:REPLACE_WITH_REVIEWED_64_HEX_DIGEST'
docker --host $Engine info --format '{{.OSType}}'
docker --host $Engine info --format '{{json .SecurityOptions}}'
docker --host $Engine pull $Image
docker --host $Engine image inspect $Image --format '{{json .RepoDigests}}'
docker --host $Engine image inspect $Image --format '{{.Os}} {{json .Config.Volumes}}'
```

The output must identify Linux, seccomp, the exact reviewed digest and no declared image volumes. Tags such as `latest`, an arbitrary remote engine or another unreviewed VM do not satisfy this interface.

4. From the current checked source or verified runtime package, select a **new** evidence directory and run the actual bounded qualifiers:

```powershell
$Evidence = 'runs\operator-temporal-native-001'
py -3 -B scripts\qualify_windows_v18.py --output "$Evidence\windows.json" --log "$Evidence\windows.log"
py -3 -B scripts\qualify_isolation_v18.py --image $Image --output "$Evidence\isolation.json"
py -3 -B scripts\qualify_function_recovery_frontier_v18.py --image $Image --isolation-receipt "$Evidence\isolation.json" --output "$Evidence\function-recovery.json" --evidence-root "$Evidence\function-recovery-evidence"
```

Containment must contain thirteen actually executed PASS cases, unchanged protected sentinel, exact host/image/policy bindings and stable sources. Function recovery refuses missing, stale or HOLD containment. The policy is ten seconds per execution, 128 MiB, 0.5 CPU and sixteen PIDs with the recorded source quotas. No broader policy, different image or changed runtime inherits a prior PASS. Preserve every failed attempt and retained journal. The retained twenty-one-case recovery registry exercises the existing function mission path. It does not qualify the new persistent controller's decision, pending-forecast, public-update or accepted-cache checkpoints. Those stages require a separately registered and actually executed native recovery qualification; even a future twenty-one-of-twenty-one PASS cannot confer that authority. Aggregate whole-mission accounting, independently curated repair evidence and other platform gates also remain separate requirements.

## Historical evidence

The [additive lineage receipt](../results/LINEAGE_TEMPORAL_V018.json) verifies **372 protected prior adaptive files** against the original seal `ce2740ce18c6e3ad1b8474e43dbf4a0e7d776bf11a42e9156eb47b2660afae31`. This includes prior results, protocols, source/license provenance, original archives, adaptive reports, controller, registered study, auditors and replay/diagnosis scripts. Earlier engineering, qualification and FRONTIER protections remain in force. A changed negative outcome, original controller, report, provenance source or seal is refused by regression tests; resealing a replacement does not preserve history.

The [differential search](../results/ARCHIVE_DIFFERENTIAL_TEMPORAL_V018.json) enumerated 203 ZIP paths, inspected twelve with a newer modification or Windows creation time, and left 191 older paths unhashed. It found no new Git archive objects and no missing authentic predecessor. No archive was extracted or regenerated. This bounded local differential can miss a copy preserving both old timestamps and does not cover cloud stores, recycle bins or other machines. Full original v0.17 and the authentic v0.16/v0.15/v0.14 predecessor chain remain unavailable; Gate D stays HOLD.

## Authentic corpus gaps

The [gap receipt](../results/AUTHENTIC_CORPUS_GAP_TEMPORAL_V018.json) preserves three independent upstream development issue/source/license bundles and two exact parse-only function projections from the previous iteration. These are not qualified full repositories or independently reproduced repairs. Current qualified counts remain **zero training repositories of two required, zero unseen evaluation repositories of eight required, and zero unseen evaluation tasks of twenty-four required** by the unchanged original four-arm protocol.

No private evaluation contract was opened, generated or rewritten; no unfamiliar source was imported on the host. No new issue examples were used to tune a learner. Only the public [SWE-bench evaluation overview](https://www.swebench.com/SWE-bench/guides/evaluation/) was reviewed as a possible future curation reference. Its full-repository Docker test harness is outside NOMAD's narrow admitted JSON-function adapter. No dataset/task was adopted; the visible documentation example concerning SymPy issue 20590 is recorded as exposure rather than unseen evidence.

An independent curator must pin upstream commit/issue/license provenance, exclude development-exposed repositories/tasks, commit disjoint public/challenge/final evidence, reproduce defects inside qualified containers, and establish the required repository counts and aggregate compute budget before a learner sees evaluation tasks. Supporting a broad external benchmark also requires an explicitly reviewed adapter. Public leads, synthetic tasks and parse-only projections cannot fill these missing qualifications.

The focused prerequisite/lineage suite passed nine tests, including six new temporal contracts and three existing adaptive-history contracts. Its mocked corruption checks test preservation logic only. The real native fourteen-test result above has its own retained receipt and log. Native containment, recovery, complete repair-corpus evidence, strict peak memory and historical completion are still separate HOLDs.
