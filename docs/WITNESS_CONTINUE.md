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

## Dev tuning (uncommitted dev suites only; chosen before the frozen run, committed together with the result)

`/workspace/nomad/sense_dev/wc_dev.py`: deep-style dev suites seed 7 and
seed 11 (40 tasks each, cold certifies 0) and the dev science suite
(`scripts/science_suite.py --seed 7`, 14 hard). Field trained with the
switch off, measured with it on and off, budget 10,000. Certified counts:

| Setting | dev7 on / off | dev11 on / off | sci dev hard on / off |
|---|---|---|---|
| gate after stage 1 only, cap 4 / 8 / 32 | 8 / 7 | 8 / 8 | 5 / 5 |
| gate stage 1 too, cap 8 | 18 / 7 | 19 / 8 | 5 / 5 |
| gate stage 1 too, cap 16 | 19 / 7 | 19 / 8 | 5 / 5 |
| gate stage 1 too, cap 32 | 19 / 7 | 20 / 8 | 5 / 5 |
| gate stage 1 too, cap 64 | 19 / 7 | 20 / 8 | 5 / 5 |

No dev task was worse than cold in any setting. Gating only the
post-stage-1 stages (split / probe / lead / variation / library) gained one
dev task (a case split). Most gains come from stage 1: with 5 public rows,
the cold-identical stage often stops on a small program that fits them by
accident (`div(2, x)` for `3 // max(x, 2)`); WITNESS rejects it and the
continued search reaches the right program a few hundred to a few thousand
evaluations later. Even an empty field gains these, so this is a search
mechanism, not learning, and is reported as such (`empty_on` arm).

Chosen: **gate stage 1 too (`WITNESS_GATE_STAGE1 = True`), cap
`WITNESS_MAX_REJECTS = 32`** (the dev plateau). Bars are unchanged from the
pre-registration above. Scope note: the gate lives on the staged path; the
familiar-family path and the plain field search used when a task has no
library, no split and no SENSE aim are unchanged.

## Sealed result (measured once, 2026-11-20, `python3 scripts/witness_continue_probe.py`)

| Criterion | Bar | Cold | Empty field + continue | Field, switch off | Field (continue on) | Met? |
|---|---|---|---|---|---|---|
| 1. Deep (`da3ae9bf…6fbd`): certified of 40 @10k | >= 14, none lost, none worse | 0 | 25 | 14 | **25 (62.5%)** | yes |
| 2. Science hard (`4517167f…868d`), science-trained field | >= 4, none lost, none worse | 0 | 0 | 4 | **5 (35.7%)** | yes |
| 3. LOFO total (16 families), worst | 5,883, 1.0x | 5,883 | | 5,883, 1.0x | 5,883, 1.0x | yes |
| 4. Gain over switch-off | >= +1 | | | | deep +11, science +1 | **yes** |
| 5. Off switch reproduces old search | exact | | | | tested (`tests/test_witness_continue.py`) | yes |
| Deep evaluations, all 40 (report) | | 284,839 | 240,553 | 187,678 | 240,553 | |
| Science hard evaluations (report) | | 140,000 | 140,000 | 121,445 | 122,365 | |

Decision: **default on** (`NOMAD_WITNESS_CONTINUE=off` restores the old search).

New deep certifications (11): deep_12, 13, 22, 23, 25, 32, 34, 35 (stage-1
fits rejected, search continued: e.g. deep_35 `div(2, x)` -> `div(3, x)`,
deep_25 `mod(max(x, y), 3)`), and deep_18, 31, 39 (`casesplit:d1`, a later
split candidate after the first was rejected). No switch-off win lost, no
task worse than cold. The empty-field arm certifies the same 25 deep tasks
at the same cost: on the deep suite this is a **search mechanism**, not
something the field learned. More evaluations are spent (240,553 vs
187,678) because tasks that used to stop on a wrong fit now keep searching.

New science certification (1): `sci_d_uvt`, `(u+v)t/2`, via the block probe
(`div(mul(add(v, u), t), 2)`, 9,067 evaluations). This is the fit the probe
had proposed and WITNESS had rejected in BLOCKPROBE's sealed run; the next
probe candidate is right. The empty field certifies 0 science tasks, so this
gain needs the learned blocks.

Honest reading: every certified program still passed WITNESS **and** the
final split, which search never reads. The cost is that WITNESS's challenge
rows are now consulted up to 32 times per task, so they act partly as extra
search signal; the final split is the independent check that remains. Gating
stage 1 was outside the narrowest reading of step (a) (split / probe / lead
only) and was chosen on dev data before this run; the post-stage-1-only
scope gained 1 dev task.
