# AGENTS.md

This file guides any AI agent entering the NOMAD repository.

## First Read

Read `data/INDEX.md`. It is the single source of truth for all measurements: file path, timestamp, value, and status. If a number is not in the index, it does not exist for reporting purposes.

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

## Module Map

See `data/INDEX.md` Key Modules table. Core: body.py, world.py, genesis.py, invent.py, selfedit.py, dreamlog.py, organism.py.

## Current Open Signals

- Genesis held-out: field certified, cold failed (first win, unconfirmed)
- last_first_upper and sum_minus_max: none, no probe-failure receipt yet
- Selfedit: 5 consecutive no_change
- World twin informative rate: 0.109, trending down
- Genesis twin: entirely uniform

## How to Run Measurements

All sealed comparisons live in `nomad/sealed_*.py`. Trigger via `.github/workflows/sealed-*.yml` or `python3 -m nomad.sealed_*`. Results write to `data/*.json` and must be indexed.

## How to Report

One read of `data/INDEX.md` plus the relevant `data/*.json` file. No rediscovery. No re-deriving numbers from source.
