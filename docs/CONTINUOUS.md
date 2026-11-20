# Continuous cybernetic loop

Awake and sleep runners that live inside NOMAD.

## Schedule

Awake at minute 8 and 23. Sleep at minute 38. A second awake trigger exists for continuity. Times may shift to avoid scheduler drops; see the workflow files for the current cron.

Awake acts as a pair. Sleep consolidates. Control never writes the field.

## Loop

- **Pair (awake, actor)**: the proposer chooses one task. Both arms share one `pair_id`. Control runs first with a cold prior and does not persist updates. Treatment then uses the field prior, stamped with the current `field_version`. A certified treatment attempt does not write the field: it enqueues a versioned packet (with its WITNESS receipt) to `data/continuous/queue.jsonl`. Scoreboard delta is certified treatment minus certified control, paired only within one `pair_id`.
- **Sleep (single learner)**: `consolidate()` claims the queue, re-verifies every receipt (supported + checksum), drops control, uncertified, duplicate, and stale packets (lag beyond `NOMAD_MAX_LAG`, default 2), applies the rest to the grammar prior and weight packets, writes the prior atomically (keeping `prior.prev.json` as last-good), and bumps `data/continuous/field_version.json`. It then prunes unpaired scoreboard rows older than one hour into `data/scoreboard_discarded.jsonl`, reports a descriptive twin summary (pre-filter pass rate, all-pass / all-fail / informative pair rates, RLOO treatment advantage over informative pairs), merges similar packets, evaluates cellular-automaton rules on independent snapshots (preferring no-op unless a rule preserves every successful label), and proposes a rewrite that is not committed. Control is frozen.
- **Held-out probe**: after each pair, `compare_live` writes `data/continuous/heldout.json`. The held-out family is never used for training.
- **Fitness**: treatment cycle counts, with success only on certified outcomes. Fitness is not the learning meter. The paired scoreboard is.

## Fitness and learning

Public-example correctness alone is not learning. A learning measurement requires:

1. the same task identity on both arms,
2. WITNESS support and final-split correctness as the success bit,
3. a scoreboard row with both arms present.

## Balance and unlearning

Each consolidated packet also trains its acting domain's own operator counts. Treatment orders search by that domain's evidence only; a domain with no witnessed evidence keeps the cold order, so a multiply-heavy field cannot slow a subtract task below control. The never-trained held-out family still reads the global field. Every consolidation that applies packets multiplies all counts by `NOMAD_DECAY` (default 0.97) so old wins fade unless re-earned. Scoreboard rows now also carry `control_evaluations`, `treatment_evaluations`, and `evaluations_saved`, because GENESIS tasks are usually certified by both arms and the cost is the only contrast. `python -m nomad.heldout balance` reports the bar: on frozen training rows, held-out square_product is won by the field (cold misses at 2000), subtract costs 8 evaluations under the field against 29 cold (a multiply-only field cost 50), and no domain costs more than cold. Untrained domains show no transfer yet (field = cold).

## Actor / learner split

Ideas taken from NVIDIA Molt and re-implemented in pure Python (see `docs/MOLT_EXTRACTION.md`). In the current schedule awake and sleep are serialized by one concurrency group, so packet lag is normally 0; the staleness bound matters when packets survive a failed sleep, are resumed from `queue.inflight.jsonl`, or if awake is ever fanned out. `NOMAD_LEARNER=inline` consolidates right after each treatment awake (old synchronous behaviour, same checks). The staleness weight is a discount, not true importance sampling; GrammarPrior counts are integers, so it only gates.

## Data commits

Awake and sleep share the `nomad-continuous-data` concurrency group (`cancel-in-progress: false`) and retry `git pull --rebase` before push so data commits do not race.

## Boundaries

- Bounded arithmetic synthesis only (GENESIS scope).
- No unrestricted code generation.
- Field packet and prior updates require a WITNESS-supported, final-correct treatment outcome. They are not a general skill promotion. External or irreversible actions remain separately gated.
- No transformers.
- Existing platform HOLDs and claim boundaries unchanged.

The field and the receipts are the persistent geometry. The runners keep it moving.
