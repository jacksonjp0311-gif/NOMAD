# NOMAD — Change History

## Continuous loop: balance and unlearning (2026-11-19)

- `GrammarPrior` keeps per-domain operator evidence and a `decay(gamma)`; treatment orders by its domain's evidence, untrained domains keep the cold order. Held-out family still uses the global field.
- Scoreboard records per-arm evaluations and `evaluations_saved`.
- Bar (`python -m nomad.heldout balance`): held-out won, subtract 8 vs 29 cold evaluations (was 50 under a multiply-only field), no domain regresses.

## Continuous loop: actor/learner split (2026-11-19)

- Awake treatment enqueues a versioned packet instead of writing the prior; sleep (`nomad/consolidate.py`) is the single learner. Receipts are re-verified, stale packets rejected (`nomad/staleness.py`), queue bounded with crash-safe claim/ack (`nomad/field_queue.py`).
- Scoreboard pairs only within one `pair_id`; old unpaired rows are discarded, never paired with a newer arm.
- Descriptive twin statistics (`nomad/advantage.py`): pre-filter pass rate, uniform-pair rates, leave-one-out treatment advantage.
- Rust native gate only counts a rustc that answers `--version`; compile timeout raised for cold runners.
- Ideas credited to NVIDIA Molt (Apache-2.0); no Molt code copied. See `docs/MOLT_EXTRACTION.md`. No new capability claim.

## v0.18.0 — PLATFORM (2026-11-14, engineering snapshot)

- Added offline source installation, Windows command launcher, configuration, doctor, native runtime smoke checks, and explicit recovery commands.
- Replaced best-effort Windows tree cleanup with gated Job Object supervision; native timeout, descendant, owner-death, and lock tests ran on the ROG.
- Fixed Windows newline hashing and byte-range lock contention defects found in the inherited mission suite.
- Hardened source/ZIP intake for reparse points, Windows aliases, case collisions, hardlinks and credential paths; Docker uses a private client configuration, local endpoint, explicit entrypoint and pinned-image preflight.
- Added a durable Docker-only mission adapter for a strict Python arithmetic target, actual GENESIS proposals, independent WITNESS/final observations, bound receipts, unique dispatch identities and scoped learning.
- Connected original BGR through optional scoped candidate ranking; prevented duplicate evidence and relabelled observations from increasing support or renewing MNEMONIC expiry.
- Added frozen native/cold/frequency/shuffled replay, native containment probe harness, read-only manifests and deterministic source/runtime ZIP builders.
- Kept the Catalogue false-positive and all historical result files. The compact package's missing predecessor archive remains a lineage HOLD.

**Outcome:** Windows engineering controls pass their reported native tests. Docker/WSL are absent, so native containment, isolated real-repository repair and release publication remain HOLD. Native BGR loses to frequency-only log loss in the retrospective replay. No intelligence advantage or production readiness is claimed.

## v0.17.0 — SECURITY & RECOVERY (2026-11-13)

**Major capability:** a fail-closed execution boundary and durable indeterminate-effect handling around the v0.16 mission runtime.

- Added a Docker-only path for unfamiliar repository tests; requires trusted digest-pinned image and refuses fallback if the engine is missing.
- Added disposable, filtered source snapshots and hardened ZIP extraction; no private mission evidence mounted into the unknown-code container.
- Added resource restrictions, process groups, reduced host environment inheritance, output caps and cleanup checks.
- Added durable, fsynced external-effect PREPARE/DISPATCH/RECONCILE receipts and owner epochs; hard-crash ambiguity blocks replay.
- Integrated unresolved-effect HOLD checks into mission startup and inspection while retaining v0.16 journal compatibility.
- Added adversarial contract tests including negative archive, filesystem, code-execution and double-dispatch cases.
- Preserved original v0.16 archive unchanged; documented unsupported security claims and native Windows/ROG acceptance plan.

**Research outcome:** local controls tested; Docker kernel boundary and native Windows acceptance **not tested**, external Bitwork learning gains still **unproved**. No production-safety claim.

## Previous versions

The complete previous histories, including v0.16 MISSION RUNTIME, v0.15 RECURSION and earlier Bitwork/NOMAD research, remain in the exact `baseline/NOMAD-v0.16.0.zip` archive. That preserved predecessor is the reference for original studies and prior changelogs.
