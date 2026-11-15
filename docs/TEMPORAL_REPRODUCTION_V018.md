# Reproducing the temporal development snapshot

Use Python 3.11 or later from a clean source extraction. The measured native
cost study used Windows and the interpreter identity frozen in the plan. It
runs reviewed synthetic predictors in Windows Jobs. It never imports an external
repository on the host. The packages contain the original native runtime; no
cloud model, package download or extra agent framework is required.

Keep new outputs under `runs/` and choose unused names. The tools refuse to
overwrite retained evidence. Replaying reserved seeds is a reproducibility
check, not a new prospective confirmation or permission to retune the controller.

## Inspect source, software and arithmetic

```powershell
py -3 -B scripts\verify_package_v18.py
py -3 -B scripts\verify_package_v18.py --require-release
py -3 -B scripts\verify_lineage_v18.py
py -3 -B scripts\study_platform_v18.py --output runs\temporal-regression.json
py -3 -B scripts\audit_temporal_metrics_v18.py --plan experiments\PLAN_TEMPORAL_V018.json --result results\TEMPORAL_MECHANISMS_V018.json --output runs\temporal-audit.json
py -3 -B scripts\summarize_temporal_v18.py --result results\TEMPORAL_MECHANISMS_V018.json --output runs\temporal-summary.json
py -3 -B scripts\account_temporal_cost_v18.py --result results\TEMPORAL_MECHANISMS_V018.json --output runs\temporal-cost-accounting.json
```

Source integrity should pass. `--require-release` and historical lineage return
exit code 3 while their recorded qualification gates remain HOLD. This is an
explicit qualification refusal, not a successful production release check.
The independent arithmetic audit imports no predictor and executes no study
trial. Read its own status and the separate registered scientific conclusion.

## Replay the fixed experiment

```powershell
py -3 -B scripts\experiment_temporal_v18.py run --plan experiments\PLAN_TEMPORAL_V018.json --output runs\temporal-replay.json --confirm-preregistered-evaluation
py -3 -B scripts\verify_temporal_replay_v18.py --plan experiments\PLAN_TEMPORAL_V018.json --original results\TEMPORAL_MECHANISMS_V018.json --replay runs\temporal-replay.json --output runs\temporal-replay-check.json
```

The nine arms receive identical observations in each of 64 streams. The
experiment contains 576 worker trials, 512 forecasts per trial, a 64-observation
unscored prefix and one checkpoint restoration after observation 256. Match
the frozen source and interpreter; a mismatch is a refusal to reproduce this
particular registration. Exact comparison excludes clocks, resource peaks and
timing-bearing raw checkpoint bytes. Cost findings belong to the original
primary run; rerun costs depend on host load and are not new seed evidence.

## Build deterministic packages

From the complete source checkout, which already includes its immutable seal:

```powershell
py -3 -B scripts\build_release_v18.py --mode source --output runs\temporal-source.zip
py -3 -B scripts\build_release_v18.py --mode runtime --output runs\temporal-runtime.zip
Get-FileHash runs\temporal-source.zip -Algorithm SHA256
Get-FileHash runs\temporal-runtime.zip -Algorithm SHA256
```

Compare with the companion delivery checksum file. Do not reseal edited source
under the old snapshot identity. The runtime package intentionally omits most
tests and authoring tools; run the full regression suite from the source package.
Its offline setup, trusted demo and runtime smoke commands are described in the
README. Source-linked installation requires keeping the extracted folder.

## Native qualification and authentic tasks

Follow [the prerequisite report](NATIVE_AND_CORPUS_TEMPORAL_V018.md) before
executing the registered 13 container probes or 21 function-recovery cases.
Administrator installation, feature changes and a restart have not been
performed by this work. A Windows Job cannot substitute for that isolation.
The authentic repository experiment remains NOT_RUN until its independent
corpus, private contracts, budgets and boundary are qualified and frozen.
