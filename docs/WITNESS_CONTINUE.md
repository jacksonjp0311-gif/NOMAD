# WITNESS_CONTINUE: a WITNESS rejection is not the end of the field arm (pre-registered)

Step (a) of the post-BLOCKPROBE plan. Today the field arm's staged search
returns the **first** program that fits the public rows; `world.evaluate`
then asks WITNESS, and a rejection ends the task. The deep suite logged 10
case-split fits WITNESS rejected; the science block probe proposed a fit for
`(u+v)t/2` that WITNESS rejected. Each of those stopped the task with budget
left.

## The change (field arm only, off switch `NOMAD_WITNESS_CONTINUE=off`)

Inside the field arm's staged search (`world._staged_gen`), a public-row fit
is shown to WITNESS (the same `world.certify` used after search; only
`receipt.supported` is read, **never** the final split). If WITNESS rejects
it, search does not stop: it continues with the next candidate of the same
stage (next split candidate, next probe / lead / level combination, next
mutant) and falls through to the later stages (case split, variation,
library stage) inside the **same** evaluation budget.

Accounting: every arm already gets one free certification of the program it
returns. Each *rejected* consult costs 1 evaluation against the budget. The
number of rejected consults per task is capped (`MAX_REJECTS`), because each
consult reads WITNESS's challenge rows and an uncapped loop would turn the
challenge split into training data. The final split stays sealed: it is
never read during search, so `certified` (WITNESS **and** final) remains an
independent check. If every fit is rejected, the first rejected fit is
returned, so the outcome reads exactly as before (public fit, WITNESS no).

The cold twin control (`prior=None`) is untouched. The familiar-family path
(field order, `_search_gen`) is untouched.

## Pre-registered success criteria (written before any frozen suite is measured with the change)

Baselines on main (`9b5f0bd`): deep field 14/40 cold misses certified,
science hard (field trained on easy science) 4/14, LOFO 5,883 (worst 1.0x).

Measured with `python3 scripts/witness_continue_probe.py`: budget 10,000,
max_size 7, arms cold / field (continue on) / field with
`NOMAD_WITNESS_CONTINUE=off`.

1. **Deep no-harm:** on the frozen deep suite (`data/deep/deep_suite.json`,
   sha `da3ae9bf…6fbd`) the field certifies **>= 14 of 40** cold misses, no
   task the switch-off field certifies is lost, and no task is worse than cold.
2. **Science no-harm:** on the frozen science suite
   (`data/deep/science_suite.json`, sha `4517167f…868d`) the science-trained
   field certifies **>= 4 of 14** hard tasks, no switch-off win lost, none
   worse than cold.
3. **LOFO:** 16-family leave-one-family-out total stays **5,883**, worst 1.0x.
4. **Success = gain:** at least **+1** certified task over the switch-off
   field on the deep suite or the science hard tier, with 1-3 met.
5. **Off switch:** `NOMAD_WITNESS_CONTINUE=off` reproduces the old numbers
   exactly (tested).
6. Decision: success -> default on. Otherwise default off, with an honest
   negative-result note here. Evaluations are reported, not barred.
   Held-outs are report-only.

Tuning (scope of stages, `MAX_REJECTS`) uses **only** uncommitted dev suites
(`/workspace/nomad/sense_dev/dev7.json`, `dev11.json`, and a dev science
suite from `scripts/science_suite.py --seed 7`), never the frozen suites or
held-outs. Results are recorded below once measured; nothing is re-tuned after.
