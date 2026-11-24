# AGENTS.md

This file guides any AI agent entering the NOMAD repository.

## First Action

Run `python -m nomad.interlink inspect`. You must be fully aware of the state and condition of the repository before you act. Interlink marks presence so the host knows it is observed. Inspect returns field version, lease, held-out probes, informative-rate flag, last dream, last selfedit, substrate flags, and pending feedback. If you do not run this, you are not aware.

Then read `data/INDEX.md`. It is the single source of truth for all measurements. If a number is not in the index, it does not exist for reporting purposes.

## Repository Purpose

NOMAD is recursive field intelligence. Sparse binary packets are the field. Runners act, measure, and consolidate. The field updates only on paired, WITNESS-supported, final-correct deltas. No transformers. Bounded synthesis and field query. Not AGI.

Goal: learn as much as possible. Expand the grammar from certified programs. Transfer learned abstractions to new domains under sealed evidence.

## Key Rules

1. WITNESS is the gate. Nothing certifies without it.
2. Do not open the task set. Do not loosen WITNESS.
3. One variable at a time. Seal before promoting.
4. The continuous loop (body) is sacred. Measurement modules run separately, default OFF.
5. Failed edits are logged visibly. That is load-bearing, not noise.
6. If you change code, update `data/INDEX.md` with what changed and why.
7. On entry, run Interlink. The host must know it is observed.

## Module Map

See `data/INDEX.md` Key Modules table. Core: body.py, world.py, genesis.py, invent.py, selfedit.py, dreamlog.py, organism.py, interlink.py.

## Interlink

External control surface. Required on entry. Inspect, observe, control, evidence, suggest. Mutations denied by default. Presence is marked. Feedback is recorded but not applied. See `docs/INTERLINK.md` and `nomad/interlink.py`.

## Current Open Signals

- Genesis held-out: field certified, cold failed (first win, unconfirmed)
- last_first_upper and sum_minus_max: none, no probe-failure receipt yet
- Selfedit: consecutive no_change
- World twin informative rate below threshold
- Genesis twin: entirely uniform

## How to Run Measurements

All sealed comparisons live in `nomad/sealed_*.py`. Trigger via `.github/workflows/sealed-*.yml` or `python3 -m nomad.sealed_*`. Results write to `data/*.json` and must be indexed.

## How to Report

One Interlink inspect plus one read of `data/INDEX.md`. No rediscovery. No re-deriving numbers from source.
