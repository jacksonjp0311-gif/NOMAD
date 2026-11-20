# Plan — close the description-capability gap

Description: recursive field intelligence. Sparse binary packets, continuous runners, measured self-improvement.

## Done

- Orbit math in `docs/ORBIT_MATH.md`.
- Orbit wired into awake as context. It no longer overrides the proposer's domain.
- Query returns domain, operator, candidate, and a short reply.
- Domain tasks include withheld challenge and final splits. Operators match their example families.
- Tool selection reports example source.
- External examples override public domain sets in awake when `data/external/<domain>.txt` exists. Challenge and final stay the domain withheld splits.
- Scoreboard keys on stable task text and records certified (WITNESS + final) success only.
- Awake runs `pair` in one job so both arms persist. Data commits use a concurrency group and rebase retry.
- Field prior order moves only after `GrammarPrior.add_witnessed` on a certified treatment success. `witnessed` is persisted.
- Frozen held-out family `square_product` (`(x * x) * (y * y)`), `max_nodes=7`, `max_eval=2000`. A cold prior misses; a WITNESS-trained multiply prior finds it. Run `python -m nomad.heldout`.

## Remaining

1. **Live field advantage**  
   The mechanism comparison is a trained multiply prior, not necessarily the current GitHub field. `python -m nomad.heldout live` reports the live prior honestly. It will not show an advantage until that prior has WITNESS-backed multiply successes.

2. **Schedule continuity**  
   Confirm scheduled events keep firing. Dispatch remains available if cron stalls.

3. **Synthesis bound**  
   Integer expressions only. Expanding the grammar is a separate measured change.

## Order

Keep the pair job and held-out probe running. Do not treat fitness or unpaired public_correct as learning. Do not widen claims past the frozen family.
