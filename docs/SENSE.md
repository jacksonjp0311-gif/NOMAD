# SENSE: classify the task before search (pre-registered)

`nomad/sense.py`. Before WORLD search starts, SENSE reads a task's declared
types and its **public rows only** and writes a deterministic, versioned
record (`nomad.sense.v1`): `domain`, `kind`, `shape`, the cheap features it
used, and a `sense_id`. It never certifies, never proposes a program and never
reads challenge or final rows. WITNESS decides every candidate as before.
`NOMAD_SENSE=off` (or `sense=False`) restores the exact prior behaviour.

## Honest classes

NOMAD holds int, string and int-list synthesis tasks, so the classes are what
a handful of input/output examples can actually show:

| Domain | When | Kinds |
|---|---|---|
| mathematics | `int` / `genesis` worlds | linear, polynomial, selection, quotient, piecewise, other |
| language | `str` world | case, reorder, measure, text_shaping |
| coding | `list` world | aggregation, ordering, list_shaping |
| science | only from an explicit task tag (`domain="science"`), never guessed | kind from the world it runs in, until a science classifier is registered |
| other | anything else | other |

`shape` (mathematics only): `negative` (every public output <= 0), `growth`
(largest |output| >= 2x the inputs' scale), `bounded`, `mixed`.

## What it aims (one place, field arm only)

On the staged path (unfamiliar family; the cold control never runs it),
right after the cold stage below `max_size` misses, the `max_size` level is
first enumerated only for the **lead top operator** the sense points at:
`sub` for `negative`, `mul` for `growth` (selection tasks and other shapes:
no lead). It runs over the cold stage's pools before library atoms enter and
leaves 20% of the budget for the case split (`SPLIT_RESERVE`). The rest of
that level later skips exactly the combinations already evaluated, so nothing
is charged twice (a block cut short by the reserve is re-covered instead).
Stage 1 is untouched: anything cold solves below `max_size` costs the same.

The record is also logged in the world loop's pair output and in the
treatment packet (`extra.sense`), so dreams, Probe-style mid-search learning
and task-feature block selection can key on `kind` / `shape` later.

## Development (never the frozen suite)

Designed and tuned only on two uncommitted dev suites generated with the same
procedure (`scripts/deep_suite.py --seed 7` and `--seed 11`, 40 tasks each,
written under /workspace, not committed). On them, at 10,000 evaluations:
field (current main) 4 + 4 = 8 of 80 cold misses certified; field + sense
7 + 8 = 15 of 80, no task lost. Variants tried there and rejected: reordering
the whole stage-2 level (no change: library levels eat the budget first),
lead block after the case split (13 of 80), lead block with no split reserve
(15 of 80 but loses two split wins), reserve 12% / 30% (13 / 14 of 80).

## Pre-registered success criteria (written before the frozen suite was measured)

Measured with `python3 scripts/sense_probe.py`, budget 10,000, max_size 7,
field trained on all 16 training families as in `scripts/casesplit_probe.py`.

1. **Deep gain:** field + sense certifies **at least 8** of the 40 deep tasks
   cold cannot certify (pre-sense field: 6), i.e. at least +2.
   Stretch: reach the DEEP_SUITE 25% bar (10 of 40).
2. **Never worse:** no deep task the pre-sense field certifies is lost, and no
   deep task is worse than cold.
3. **No LOFO regression:** 16-family leave-one-family-out total for
   field + sense <= 5,883 (cold), worst family 1.0x.
4. **Classifier:** at least 18 of the 20 families with known kind labels
   (16 training + 4 held-out, labels fixed in `scripts/sense_probe.py`)
   classified correctly. Caveat fixed in advance: the rules were written
   while looking at these families, so this is a consistency check, not a
   held-out accuracy.
5. **Off switch:** with `NOMAD_SENSE=off` every arm reproduces the pre-sense
   numbers exactly (tested).
6. Evaluations are reported, not barred. Held-outs are report-only.

Results are recorded below once measured. Nothing is re-tuned after.

## Results (2026-11-20, `python3 scripts/sense_probe.py`, frozen suite `da3ae9bf…6fbd`)

| Criterion | Bar | Cold | Field (pre-sense main) | Field + sense | Met? |
|---|---|---|---|---|---|
| 1. Deep: certified among 40 cold misses @10k | >= 8 (stretch 10) | 0 | 6 (15%) | **14 (35%)** | yes, stretch too |
| 2. Pre-sense field wins lost / tasks worse than cold | 0 / 0 | | | 0 / 0 | yes |
| 3. LOFO total (16 families), worst family | <= 5,883, 1.0x | 5,883 | 5,883, 1.0x | 5,883, 1.0x | yes |
| 4. Classifier on 20 known-label families | >= 18 | | | 20 / 20 | yes (consistency check, see caveat) |
| 5. Off switch reproduces pre-sense numbers | exact | | | tested (`tests/test_sense.py`) | yes |
| 6. Deep evaluations, all 40 tasks (report) | | 284,839 | 204,588 | 187,678 | |

New certifications by the lead block (8): deep_01, deep_07, deep_09, deep_14
(`mul` lead, growth) and deep_02, deep_28, deep_36, deep_37 (`sub` lead,
negative). deep_26 is now certified by the lead block instead of the split
(both certified). The 6 split wins are kept (deep_16 now costs 9,128
evaluations instead of 5,279: the lead block runs first; still certified).

Sense breakdown on the deep suite (all 40 are `mathematics`):

| Kind | Tasks | Field | Field + sense |
|---|---|---|---|
| quotient | 16 | 0 | 0 |
| polynomial | 13 | 2 | 7 |
| other | 7 | 3 | 5 |
| linear | 2 | 0 | 1 |
| piecewise | 2 | 1 | 1 |

| Shape | Tasks | Field | Field + sense |
|---|---|---|---|
| bounded | 18 | 1 | 1 |
| growth | 9 | 1 | 5 |
| negative | 7 | 1 | 5 |
| mixed | 6 | 3 | 3 |

Held-outs (report-only): absdiff, last_first_upper and sum_minus_max are
unchanged; quartic_sum is still certified but costs 23,054 evaluations instead
of 21,375 (+7.9%: growth shape, so the `mul` lead block runs before the
library atoms).

Honest caveats: the gain comes from the *shape* (sign and growth of the
outputs), not from the finer kind labels; `bounded` tasks (div/mod-like, 18
of 40) get nothing yet, and they are the biggest remaining block. The lead
block reorders work after the cold stage, so a task cold would solve at
exactly `max_size` within budget could cost more in the field arm (none in
LOFO, the deep suite or the held-outs). Nothing was re-tuned after this
measurement.
