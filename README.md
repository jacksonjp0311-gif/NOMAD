<p align="center"><img src="assets/nomad-banner.svg" width="100%" alt="NOMAD: Bitwork-derived coding intelligence" /></p>

# NOMAD v0.18.0 — PLATFORM

**Local coding intelligence with explicit evidence and execution boundaries.**

This is a **v0.18.0 development qualification snapshot**. All four platform acceptance gates remain **HOLD**. Windows process supervision and the trusted research path run on the ASUS ROG. Docker and WSL are unavailable on this host, so native container containment and isolated external repository repair have not been demonstrated. There is no v0.19 readiness claim. See the [current qualification report](docs/QUALIFICATION_REPORT_V018.md).

## Intelligence architecture

**Bitwork → RESONANCE → WORLD MODEL → INQUIRY → GENESIS → execution → WITNESS → MNEMONIC → learning → next action.**

The original intelligence modules, BGR runtime and research records remain present. The new platform surrounds them with source admission, durable ownership, process supervision and evidence checks. No cloud model is required.

The isolated mission adapter has a deliberately bounded operating envelope: small top-level Python `solve(x, y)` arithmetic modules and transparent public import aliases, public examples and repository tests, separate private challenge/final examples, and a reviewed Docker image. Source parsing discovers the supported public target without importing unfamiliar code. The adapter connects actual RESONANCE, WORLD MODEL, INQUIRY, GENESIS, original BGR ranking, WITNESS and MNEMONIC through a durable mission journal. WITNESS and the final checker evaluate strict arithmetic syntax through a bounded interpreter. A negative private check ends that mission rather than feeding private answers into search.

The public baseline probe must precede proposal selection. Retained learning is admitted only from independently checked consequences and remains bound to source, action, runtime and receipts. INQUIRY can abstain when its available public probe has no expected information gain. This bounded implementation and its mocked execution contracts do not demonstrate general repository understanding, informative inquiry or autonomous transfer. Actual isolated integration remains HOLD. See [research qualification and claim limits](docs/RESEARCH_QUALIFICATION_V018.md).

## Start on Windows

From the extracted source root, run these commands in PowerShell or Command Prompt:

```powershell
.\NOMAD.cmd setup
.\NOMAD.cmd doctor
.\NOMAD.cmd trusted-demo
.\NOMAD.cmd runtime-smoke
.\NOMAD.cmd verify
```

`setup` creates a local `.venv` and a source link, entirely offline. It downloads no packages, changes no system security settings, and needs Python 3.11 or later. Keep the source folder in place; moving it requires rerunning setup. `doctor` reports capabilities and HOLDs without certifying containment. The `.cmd` launcher works on the tested profile where PowerShell script files are disabled. `NOMAD.ps1` is also supplied for profiles that allow scripts.

The equivalent standalone commands are:

```powershell
py -3 -B -m nomad.platform_cli doctor
py -3 -B -m nomad.platform_cli trusted-demo
py -3 -B -m nomad.platform_cli runtime-smoke
py -3 -B scripts\verify_package_v18.py
```

The supported installation is source-linked. A standalone wheel containing the vendored native runtime is not qualified in this milestone.

## What actually ran on the ROG

| Capability | Observed status |
|---|---|
| Windows 11 Pro, ROG Flow Z13 GZ302EA, Ryzen AI MAX+ 395 | Observed by native diagnostics |
| Python 3.12.10, Node 24.19.0, rustc/cargo 1.98.1 | Present; generated native programs executed successfully |
| Job Object child, timeout and supervisor-death cleanup | Native tests passed |
| NTFS mission ownership and restart | Native tests passed |
| Junction, hardlink and Windows path admission | Native tests passed |
| Native symlink behavior | HOLD: creating a symlink requires a privilege unavailable here |
| Docker Desktop / WSL | Docker absent; WSL reports not installed |
| Hypervisor and firmware virtualization | Reported enabled; CIM reports WSL, VirtualMachinePlatform, Hyper-V and Windows Sandbox features disabled |
| Malicious repository containment in Docker | HOLD: native probe cases not executed |
| Isolated external repair and interrupted isolated mission | HOLD |
| Native BGR learning advantage | HOLD: worse prediction loss than frequency-only control |

Exact current test counts, source hashes, timing, skip reasons and runtime outputs are in [the qualification receipt](results/QUALIFICATION_FINAL_V018.json). [Native Windows checks](docs/NATIVE_QUALIFICATION_V018.md) include resource refusal, breakaway denial and owner-death recovery; strict interpretation of the Job peak-memory counter remains HOLD. Original and intermediate receipts remain immutable. CPU timing has a separate scope and is not an energy measurement.

## Isolated missions

There is no host fallback for unfamiliar code. Docker must be available at the local Linux endpoint, with seccomp reported and the exact reviewed digest already present. The runner does not pull images or inherit a user's Docker credentials/context. Only a disposable source copy is mounted, read-only; journals, credentials and private examples remain outside the mount. CPU, memory, PID, time and output budgets are bounded. The container must be confirmed removed before its result can be used.

First provision the host using the official [WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install) and [Docker Desktop Windows setup](https://docs.docker.com/desktop/setup/install/windows-install/) instructions. Feature changes may need an administrator and restart. This task did not install those system components. Review an image and its dependencies, then pre-pull it through an operator-controlled workflow.

Copy `platform.example.json` to ignored `platform.local.json` and replace `null` with that real digest reference. Do not invent a digest or use `latest`.

```powershell
.\NOMAD.cmd --config platform.local.json doctor
# $image must contain the same independently reviewed full image@sha256 reference.
py -3 -B scripts\qualify_isolation_v18.py --image $image --output runs\native-qualification.json
.\NOMAD.cmd --config platform.local.json dry-run --source .\reviewed-source-only-copy
.\NOMAD.cmd --config platform.local.json isolated-demo --root runs\isolated-demo
```

The qualification harness contains controlled host-file, environment, network, namespace, read-only filesystem, resource-exhaustion and owner-death probes. A probe PASS qualifies only that stated check on that image/host. It does not prove arbitrary kernel escapes impossible. The current native receipt is HOLD with no executed container cases.

For a supported repository, prepare a separate JSON contract with `goal_text`, optional `target` and `entry_module`, and `public`, `challenge`, `final` arrays of `{ "x": 1, "y": 2, "expected": 3 }`. All three input partitions must be disjoint. The source copy must contain a `tests` directory; `.git`, credentials, links and unsupported Windows path names are refused. Ambiguous or unsupported public interfaces produce HOLD.

```powershell
.\NOMAD.cmd --config platform.local.json init --source .\source-only --root runs\mission --contract .\contract.json
.\NOMAD.cmd run --root runs\mission
.\NOMAD.cmd status --root runs\mission
.\NOMAD.cmd recover --root runs\mission
```

A completed mission commits only its disposable snapshot. It does not alter the original repository, commit to Git, publish, deploy or perform irreversible external actions. A crash after dispatch causes HOLD; `recover` must independently confirm that specific container is gone before a fresh attempt. Unknown external effects remain fenced by the inherited `EffectLedger` and require authoritative reconciliation. Checksums are integrity checks, not signatures against a hostile host administrator.

## Bitwork and evidence

`nomad.platform_bitwork.NativeDecisionRanker` executes the original vendored `bgr140.GovernedBitworkV14`. The archive and runtime manifest are checked. Candidate ranking has no acceptance authority. The arithmetic mission's `genesis-vs-ast` scope starts cold until matching independent observations exist; historical relational-edit evidence cannot be silently transferred into it.

The frozen historical replay compared four controls under the same candidate budget:

| Control | Mean log loss (lower is better) | Mean rank of observed public success |
|---|---:|---:|
| Cold | 0.6931471806 | 1.5 |
| Frequency only | 0.4206070942 | 1.0 |
| Native BGR | 0.4864129774 | 1.0 |
| Shuffled evidence | 0.8482314976 | 1.0 |

Native BGR loses to the frequency control. These are retrospective public-trace predictions from the preserved study, not fresh repository repairs, untouched holdout evidence or a demonstrated coding advantage. The original Catalogue false-positive remains rejected by its separate namespace contract. See [experiment and costs](docs/EXPERIMENT_V018.md) and [machine-readable results](results/BITWORK_V018.json).

An [independent arithmetic audit](docs/RESEARCH_QUALIFICATION_V018.md) reproduces that negative loss result and shows identical candidate ordering under BGR and frequency learning. The [prospective four-arm protocol](docs/INTELLIGENCE_PROTOCOL_V018.md) fixes comparison rules and enforces isolation preflight before opening private contracts. No admissible held-out corpus has been frozen and no prospective trial has run. Known upstream repair candidates are explicitly unsupported by the current arithmetic adapter; synthetic fixtures are not counted as authentic repairs.

## Reproduce and inspect

```powershell
py -3 -B -m unittest discover -s tests -v
py -3 -B scripts\study_platform_v18.py --output runs\new-platform-study.json
py -3 -B scripts\verify_package_v18.py
py -3 -B scripts\build_release_v18.py --output .\dist\NOMAD-v0.18.0-source.zip --mode source
py -3 -B scripts\build_release_v18.py --output .\dist\NOMAD-v0.18.0-runtime.zip --mode runtime
```

Results and archive outputs must be new paths. The verifier never rebuilds expected hashes. Builds use deterministic ordering, timestamps and file modes; bytes reproduce with the same Python/zlib toolchain. The shared boundary excludes Git internals, virtual environments, working runs and local credentials while preserving `.github`. Both ZIPs carry the platform, original BGR and retained research records; the source ZIP additionally carries the tests and development tooling. Both are engineering artifacts with release publication HOLD. The new qualification seal preserves the first v0.18 engineering manifest unchanged.

## History and release gates

The original desktop source is preserved in the `baseline-v0.17.0` Git branch and the original ZIP; development is on `v0.18-platform`. Historical experiment/results files and the original BGR archive were not rewritten. This compact source omits `baseline/NOMAD-v0.16.0.zip` by design. Its absence is a lineage HOLD, not corrupted current source. Do not present this source ZIP as the complete nested historical archive.

The [GitHub repository](https://github.com/jacksonjp0311-gif/NOMAD) is private. Development uses [v0.18-platform](https://github.com/jacksonjp0311-gif/NOMAD/tree/v0.18-platform); `main` remains at the earlier engineering commit `5851566`. Initial reconciliation found that only `main` had been pushed. The artifact delivery receipt records the verified development synchronization. GitHub Actions was blocked before jobs started by the account billing/spending limit; local tests do not substitute for the unrun CI matrix. No release, main merge, force push or visibility change is part of qualification.

- [Current qualification report](docs/QUALIFICATION_REPORT_V018.md)
- [Native security qualification](docs/NATIVE_QUALIFICATION_V018.md)
- [Original engineering report](docs/PLATFORM_QUALIFICATION_REPORT.md)
- [Release notes](RELEASE.md)
- [Conditional v0.19 readiness plan](docs/V019_READINESS_PLAN.md)

**Protect the system. Preserve the intelligence. Advance verified capability.**
