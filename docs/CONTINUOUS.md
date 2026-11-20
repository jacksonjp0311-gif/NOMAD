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

## WORLD organ

Each pair also runs a WORLD twin pair (typed ints/strings/lists, curriculum, library primitives); sleep probes never-trained families. See `docs/WORLD.md`.

## Balance and unlearning

Each consolidated packet also trains its acting domain's own operator counts. Treatment orders search by that domain's evidence only; a domain with no witnessed evidence keeps the cold order, so a multiply-heavy field cannot slow a subtract task below control. The never-trained held-out family still reads the global field. Every consolidation that applies packets multiplies all counts by `NOMAD_DECAY` (default 0.97) so old wins fade unless re-earned. Scoreboard rows now also carry `control_evaluations`, `treatment_evaluations`, and `evaluations_saved`, because GENESIS tasks are usually certified by both arms and the cost is the only contrast. `python -m nomad.heldout balance` reports the bar: on frozen training rows, held-out square_product is won by the field (cold misses at 2000), subtract costs 8 evaluations under the field against 29 cold (a multiply-only field cost 50), and no domain costs more than cold. Untrained domains show no transfer yet (field = cold).

## Actor / learner split

Ideas taken from NVIDIA Molt and re-implemented in pure Python (see `docs/MOLT_EXTRACTION.md`). In the current schedule awake and sleep are serialized by one concurrency group, so packet lag is normally 0; the staleness bound matters when packets survive a failed sleep, are resumed from `queue.inflight.jsonl`, or if awake is ever fanned out. `NOMAD_LEARNER=inline` consolidates right after each treatment awake (old synchronous behaviour, same checks). The staleness weight is a discount, not true importance sampling; GrammarPrior counts are integers, so it only gates.

## Data commits

Awake and sleep share the `nomad-continuous-data` concurrency group (`cancel-in-progress: false`) and retry `git pull --rebase` before push so data commits do not race.

## Boundaries

- Bounded synthesis only: GENESIS integer expressions plus the WORLD typed operator table (programs of at most 7 nodes).
- No unrestricted code generation.
- Field packet and prior updates require a WITNESS-supported, final-correct treatment outcome. They are not a general skill promotion. External or irreversible actions remain separately gated.
- No transformers.
- Existing platform HOLDs and claim boundaries unchanged.

The field and the receipts are the persistent geometry. The runners keep it moving.

## Heartbeat (self-sustaining schedule)

GitHub throttles scheduled runs, so NOMAD keeps its own pulse (`scripts/heartbeat.sh`):

- A successful **awake** dispatches **continuous-sleep** right away.
- A successful **sleep** dispatches the next **continuous-awake**, but not before `NOMAD_CHAIN_GAP_MIN` minutes (repo variable, default 15) after the last awake was created, so the chain cannot spin.
- Only one chain lives: both run in the `nomad-continuous-data` concurrency group, and the script skips dispatch when the target is already queued or running.
- **nomad-watch** runs after every awake/sleep completion and on its own cron. If no awake succeeded in `NOMAD_STALE_MIN` minutes (default 90) and nothing is queued or running, it re-dispatches awake and logs the gap to `data/organism_events.jsonl`. It is not in the data group, so it can never cancel a pending run.
- The original crons stay as a fallback restart. Set repo variable `NOMAD_HEARTBEAT=off` to stop chaining.
- `data/organism.json` (written by `python -m nomad.organism status` every awake and sleep) is the organism-level health view: last pulses, curriculum levels, twin summaries, field version, queue, held-out probes, evolution and heartbeat events.

## Long-lived body (primary runtime)

`python -m nomad.body` (`nomad/body.py`) runs the whole organism in one process: proposer → GENESIS and WORLD twin pairs → packet queue → sleep learner every 3 cycles → checkpoint every 10 minutes (retention trim, organism health, lease heartbeat, evolve guard and maybe one gene mutation, commit `data/`, pull --rebase, push). It is host-agnostic; `nomad-body.yml` is the GitHub wrapper (~5.5 h, `timeout-minutes: 350`, `nomad-body` concurrency group, dispatches its successor). A single-body lease (`nomad/lease.py`, `data/lease.json`) means only one host writes; others stand by until the lease is released or stale (30 min). The awake/sleep workflows check the lease and no-op while a body is alive; `nomad-watch` restarts the body when the heartbeat is stale. Append-only logs are trimmed by `nomad/retention.py` (counts kept in `data/retention.json`).

## Self-evolution

`nomad/evolve.py` evolves **parameters, not code**: the genome (`data/genome.json`: decay, library_k, patience, max_lag, all bounded). When due (every 2 h, nothing awaiting verification) it mutates one gene, runs a fixed offline benchmark (frozen training families + never-trained probes), and keeps the change only if the benchmark is strictly better (more held-out wins, or equal wins and less search, with no loss of certified training families) **and** the full unit-test suite passes. The accepted change is committed to main as `nomad-evolve: <id> …`. After at least 6 live WORLD pairs, the guard compares the live treatment/control cost ratio with the value before the change; if it worsened by more than 15%, the body (or fallback sleep) runs `git revert` on that commit (`nomad-revert: <id> …`).

### Revert drill

`python3 scripts/revert_drill.py` exercises the self-revert path end to end without touching live main. It clones the repo and the current live `data/` into a temp directory, with a throwaway bare repo as `origin`. Then it writes an accepted genome change exactly as the body does (`nomad-evolve: <id>` commit), appends 8 world twin rows, and runs the real `python -m nomad.body evolve-step --push`. It runs two scenarios. With regressed rows (3x the pre-change treatment/control cost ratio) the guard must revert: `nomad-revert: <id>` commit, genome restored, evolution log resolved, both pushed to the throwaway origin. With healthy rows it must keep. The script exits non-zero if any check fails.

