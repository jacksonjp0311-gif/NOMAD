# Persistent computation: recovery, integrity and rollback

The persistent controller is an optional v0.18.0 development capability. Its
state is computational cache, not an independently verified fact. WITNESS keeps
acceptance authority. The unchanged native BGR source and all historical
experimental results remain protected.

## What the software contracts establish

Each predictor has an explicit versioned JSON envelope. Restoration checks
source, runtime, policy, epoch and public-prefix identity, supported concrete
types, bounds and checksums before adopting its state. The controller additionally
checks chronology and reconstructs frequency counts from the recorded prefix.
An invalid state produces a reported cold fallback; it does not silently retain
old observations. Memory-pressure eviction preserves its reason and charges any
subsequent reconstruction. Expiry requires the caller's current logical epoch.

The history cap is a refusal boundary, not an indefinitely sliding window.
At 2,048 retained observations (or the configured smaller cap), further forecasts
are refused. A caller must explicitly create a new bounded controller from an
eligible prefix. Automatic lifelong compaction without changing the learner's
meaning is not implemented or demonstrated.

Forecasts settle once. An observation without a pending prediction is refused,
as is serialization of an unsettled controller. Mission recovery must bind its
settled prestate, chosen action and public receipt before replaying a pending
observation. Independent private verification remains outside the reward stream.

Checkpoint publication writes a bounded temporary JSON file, flushes it with
`fsync`, and atomically replaces the destination. Existing links, reparse points
and multiply linked destinations are refused. Partial temporary files are never
selected as authoritative state. A trusted child-process test exits before
replacement and confirms that the previous checkpoint survives. Separate fresh
Python-process tests compare restored native forecasts against uninterrupted
continuation, including a promoted native lag feature. These tests exercise real
processes and the original BGR runtime; they do not execute external code.

The registered stream experiment writes and restores every arm after observation
256. This is object restoration from a real disk checkpoint in the same worker.
It is not a process-death experiment. Exact replay compares forecasts, choices,
operation counts and deterministic state; measured clocks and timing-bearing
raw checkpoint bytes are intentionally excluded.

## Boundaries that remain unqualified

- Windows Job tests cover trusted child cleanup, timeout, resource refusal and
  supervisor death. A Job alone is not a filesystem or network sandbox.
- Actual hostile-code containment and isolated mission recovery require the
  registered Docker boundary. Their native probe counts remain zero until that
  infrastructure is available and qualified.
- The state codec and checkpoint tests do not prove recovery after physical
  power loss, race-free protection from an administrator replacing directories,
  or cryptographic authenticity against a writer that controls the trust anchor.
- Checkpoint-size and object-count limits are not strict process RSS limits.
  Process working-set and Job peak counters have separate meanings and cannot
  be summed into a simultaneous committed-memory claim.
- Unknown external effects remain fenced. A recovered computation is not
  permission to repeat a non-idempotent external action.

## Candidate rollback

The development self-revision helper writes a bounded configuration nomination,
its unchanged baseline, an exact rollback copy and source/evidence bindings.
It cannot modify authoritative implementation, WITNESS, protected contracts or
historical results. Current status is `DEVELOPMENT_NOMINATION_ONLY`.

The prospective mechanism arms compare the selected persistent profile against
other mechanisms and named ablations. They do not include the unselected standard
persistent profile as a separate held-out arm. Consequently, this experiment
cannot independently establish that the nominated short profile improves on
that standard baseline. Promotion requires a future frozen direct comparison
and native candidate acceptance; neither follows from a favorable comparison
against frequency, temporal or native controls.

## Reproduction

From a clean source package:

```powershell
py -3 -B -m unittest tests.test_persistent_v18 tests.test_persistent_process_v18 -v
py -3 -B scripts\qualify_windows_v18.py --output runs\windows-recheck.json --log runs\windows-recheck.log
```

These commands reproduce trusted software contracts. The separate qualification
report records actual counts, source hashes, failed attempts and gate statuses.
Native isolation must pass before running external repair or recovery missions.
