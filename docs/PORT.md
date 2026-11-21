# PORT: learned blocks that travel between tasks (pre-registered)

Phase 1 toward general intelligence: **make learning count.** On main
(`ce3b893`) an empty field certifies the same 25 of 40 sealed deep tasks as
the trained field: the gains so far are search mechanisms (WITNESS_CONTINUE,
case split, SENSE), not memory. On the sealed science hard tier the field
trained on easy science certifies 5 of 14 and an empty field 0, so memory
already counts there, but only for blocks learned under the *exact* same input
signature (names and order), so `2*a*d` learned on `(u, a, d)` can never help
a task over `(u, a, t)`, and a whole certified formula (`h:m -> s`) is never
kept as a block at all (only its proper sub-trees are harvested).

## The change (field arm only; off switch `NOMAD_PORT=off`)

1. **Whole programs are remembered.** Every certified program of size >= 3 is
   kept in `WorldPrior.programs` (with its input signature and a use count,
   decayed like the library, capped at 512, persisted in the snapshot).
2. **Portable bank.** For a task, `world.port_bank` instantiates every learned
   block and every remembered program, from *any* signature, over the task's
   inputs by type-preserving renaming of its variables (identity signature
   first, at most 24 renamings per block, at most 400 bank entries, most-used
   first). Only learned memory enters: an empty field has an empty bank.
3. **Used inside the block probe** (the one place the field's blocks are tried
   on unfamiliar tasks, BLOCKPROBE, after stage 1 has spent half the budget):
   every bank block is run once on the public rows (1 evaluation each), scored
   against the goal by task features (`world.block_score`: rows already equal,
   few distinct offsets, same row ordering; no search), then
   - **anchor**: for the best-scoring blocks the residual the goal leaves for
     `add / sub / reversed sub / mul` is looked up among the probe's values
     (1 evaluation per lookup); a fit is a WITNESS-gated candidate, and anchor
     fits may use at most part of the per-task WITNESS rejection cap;
   - **atoms**: the field's own signature blocks (the plain probe's atoms) plus
     the best-scoring bank blocks enter the probe's enumeration.

Stage 1 (the exact cold search) is untouched, the cold control never reads a
bank, a task solved before the probe trigger costs exactly what it did, and
WITNESS plus the never-read final split still decide every certification.
Mechanisms from the overnight queue this covers: task-feature block selection
(scoring) and dreams-lite (whole programs recombined with renaming). Mid-search
learning is not part of it.

## Measurement: the 3-arm judge (`python3 scripts/learning_judge.py`)

Budget 10,000, the suites' max_size. Arms:

- `cold`: the twin control (`prior=None`).
- `empty`: `WorldPrior()` with every search feature on (case split, SENSE,
  WITNESS_CONTINUE, block probe, PORT); no memory.
- `trained`: trained only on training families (the 16 WORLD families via
  `variation_probe.train`; for science also the suite's 14 *easy* families),
  never on a sealed task. PORT on.
- `trained_port_off` (report): the same field with `NOMAD_PORT=off` = main.
- `trained_practice` (deep, report only): `trained` plus 1,000 generated
  practice tasks (`deep_suite.sample`, seed 101, sizes 5-12) with any task
  whose row behaviour equals a sealed deep task excluded. Shows whether more
  same-distribution training moves the deep suite.

Sections: LOFO (16 families), deep (`data/deep/deep_suite.json`, sha
`da3ae9bf…6fbd`), science hard (`data/deep/science_suite.json`, sha
`4517167f…868d`). Neither suite is modified.

## Pre-registered criteria (written before the sealed suites are measured with PORT)

1. **Learning counts:** on a sealed suite, `trained` certifies at least **3
   more** tasks than `empty` (or at least 25% fewer evaluations at the same
   count).
2. **The mechanism adds memory value:** on science hard, `trained` certifies
   at least **+2** over `trained_port_off`, or the same count with at least 25%
   fewer evaluations.
3. **No drop:** `trained` deep >= **25/40**, science hard >= **5/14**. Wins of
   `trained_port_off` that PORT loses are reported (dev suggests `d_uvt`, a
   9,600-9,900-evaluation probe win, may be pushed over budget), not barred.
4. **None worse than cold** on either suite.
5. **LOFO** total stays **5,883**, worst 1.0x.
6. **Off switch:** `NOMAD_PORT=off` reproduces main exactly (tested); all
   tests pass.

Decision: 1-6 met -> default on. Otherwise default off with an honest note.
Expected and reported, not targeted: on the deep suite PORT should not fire
(stage 1 finishes below the probe trigger for `(x, y)` tasks), so `trained`
= `empty` there.

## Dev tuning (uncommitted dev suites only, before the sealed run)

Science dev suites `scripts/science_suite.py --seed 7 / 11 / 13` (14 hard
each, 42 total; same formulas as the sealed suite, different rows: a known
limit of the science generator, so tuning was kept to a few global knobs on a
plateau) and deep dev suites seed 7 / 11 (`/workspace/nomad/sense_dev/`).
Field trained as in the judge. Science hard certified (empty field: 0 on all):

| Setting | dev7 | dev11 | dev13 | total /42 | PORT-off wins lost |
|---|---|---|---|---|---|
| PORT off (main) | 5 | 5 | 4 | 14 | |
| renaming bank in probe only, no anchors | 5 | 8 | 5 | 18 | |
| anchors only, exact signature | 5 | 5 | 4 | 14 | |
| bank + anchors, 12 atoms (bank replaces own atoms) | 7 | 9 | 7 | 23 | d_rest x2, d_uvt x2 |
| + keep own atoms, 24 bank atoms, 100 anchors | 8 | 8 | 10 | **26** | d_uvt x2 |

Chosen: the last row (`PORT_K = 24`, `PORT_ANCHOR_N = 100`). Anchor-fit
rejection cap 4 / 8 / 32 changed nothing on dev; 16 kept as a safety margin.
Deep dev (seed 7 / 11): empty 19 / 20, trained 19 / 20 with PORT on or off,
also with 1,000 practice tasks (19 / 20): PORT does not fire there.

Negative results on the way (dev only, not committed):

- Ranking blocks by features for stage 2 (after the cold stage): no change.
- An anchor stage right after stage 1 on the deep suite (learned blocks as
  anchors, residual looked up in stage 1's values): trained 31 / 25 vs empty
  19 / 20 on deep dev. But the same lookup with stage-1 programs as anchors
  and **no memory** gives 31 / 25 too: it is a search mechanism, so it is not
  counted as learning and not part of PORT.
- Harvesting whole programs into the library itself, larger practice
  curricula (100 / 400 / 1,000 tasks, hard-only practice at 10k and 100k
  training budgets): no deep gain over the matched no-memory control. The
  deep suite is uniform random programs; the blocks it shares with practice
  are small, and stage 1 already enumerates every program up to size 6.

Results are recorded below once measured; nothing is re-tuned after.

## Sealed result (measured once, 2026-11-21, `python3 scripts/learning_judge.py`)

| Criterion | Bar | Cold | Empty | Trained, PORT off (main) | Trained (PORT on) | Met? |
|---|---|---|---|---|---|---|
| Science hard (`4517167f…868d`): certified of 14 @10k | | 0 | 0 | 5 | **9 (64%)** | |
| Science hard evaluations | | 140,000 | 140,000 | 122,365 | **103,397 (-15.5%)** | |
| Deep (`da3ae9bf…6fbd`): certified of 40 @10k | | 0 | 25 | 25 | 25 | |
| Deep evaluations | | 284,839 | 240,553 | 240,553 | 240,553 | |
| 1. Learning counts: trained - empty on a sealed suite | >= 3 | | | science +5, deep 0 | **science +9**, deep 0 | yes |
| 2. PORT adds memory value (science hard vs PORT off) | >= +2 | | | | **+4** | yes |
| 3. No drop: deep >= 25, science >= 5 | | | | | 25, 9 | yes |
| 4. Tasks worse than cold | 0 | | 0 | 0 | 0 | yes |
| 5. LOFO total (16 families), worst | 5,883, 1.0x | 5,883 | | 5,883, 1.0x | 5,883, 1.0x | yes |
| 6. Off switch exact, all tests pass | | | | | 370 tests (+7) | yes |
| Deep, trained + 1,000 practice tasks (report) | | | | | 26 (236,902 evals) | |

Decision: **default on** (`NOMAD_PORT=off` restores main).

New science certifications (5), every one built from a block learned on an
easy family under a different signature or a whole remembered program:

- `sci_vsq` u^2 + 2ad: anchor = the easy `2*a*d` program, renamed;
  residual `u*u` from stage 1 (`port:anchor`).
- `sci_hms_to_s` h:m:s -> s: anchor = the easy `h:m -> minutes` / `m:s -> s`
  programs, renamed (`port:anchor`).
- `sci_ke_v`, `sci_ke_u` m v^2 / 2: probe atoms from the easy `P = I^2 R`
  program renamed to `m, v` / `m, u` (`port:probe`).
- `sci_water_mol` min(gH/2, 2gO/32): `min` of the two easy stoichiometry
  programs (`port:probe`).

Lost (1), as dev predicted: `sci_d_uvt` (u+v)t/2. Main certified it at 9,067
of 10,000 evaluations; PORT's bank costs push the plain probe's hit past the
budget. Faster on four main wins (`sci_energy` 6,172 -> 5,133,
`sci_hm_to_s` 5,443 -> 5,329, `sci_vmean_uat`), slower on one
(`sci_d_rest` 6,544 -> 6,820).

Deep: trained = empty = 25, identical evaluations. PORT does not fire there:
for `(x, y)` tasks the cold stage finishes (about 4,150 evaluations) below the
block-probe trigger (5,000), so the probe never runs. 1,000 extra
same-distribution practice tasks move the deep suite by one task (26). On the
deep suite **memory still does not count**; on science it now does, by 9
tasks over an empty field.

Honest reading: the science dev suites share their formulas with the sealed
suite (only the rows differ), so dev tuning on science is closer to the sealed
suite than the deep dev suites are to theirs. Tuning was three global knobs on
a plateau (12-32 atoms, 50-all anchors gave 22-26 of 42 on dev), never a
per-formula choice, and the sealed result (+4) is in line with dev (+4 per
suite on average). The transfer shown here is within one domain (easy
science -> hard science, renamed variables); cross-domain transfer is not yet
tested.
