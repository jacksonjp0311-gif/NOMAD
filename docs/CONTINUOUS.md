# Continuous cybernetic loop

Awake and sleep runners that live inside NOMAD.

## Schedule

Awake at minute 8 and 23. Sleep at minute 38. A second awake trigger exists for continuity. Times may shift to avoid scheduler drops; see the workflow files for the current cron.

Awake acts as a pair. Sleep consolidates. Control never writes the field.

## Loop

- **Pair (awake)**: the proposer chooses one task. Control runs first with a cold prior and does not persist updates. Treatment then uses the field prior. Both arms persist through a single commit. Scoreboard delta is certified treatment minus certified control.
- **Sleep**: merges similar packets, evaluates cellular-automaton rules on independent snapshots (preferring no-op unless a rule preserves every successful label), and proposes a rewrite that is not committed. Control is frozen.
- **Held-out probe**: after each pair, `compare_live` writes `data/continuous/heldout.json`. The held-out family is never used for training.
- **Fitness**: treatment cycle counts, with success only on certified outcomes. Fitness is not the learning meter. The paired scoreboard is.

## Fitness and learning

Public-example correctness alone is not learning. A learning measurement requires:

1. the same task identity on both arms,
2. WITNESS support and final-split correctness as the success bit,
3. a scoreboard row with both arms present.

## Data commits

Awake and sleep share the `nomad-continuous-data` concurrency group (`cancel-in-progress: false`) and retry `git pull --rebase` before push so data commits do not race.

## Boundaries

- Bounded arithmetic synthesis only (GENESIS scope).
- No unrestricted code generation.
- Field packet and prior updates require a WITNESS-supported, final-correct treatment outcome. They are not a general skill promotion. External or irreversible actions remain separately gated.
- No transformers.
- Existing platform HOLDs and claim boundaries unchanged.

The field and the receipts are the persistent geometry. The runners keep it moving.
