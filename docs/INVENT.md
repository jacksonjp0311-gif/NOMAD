# INVENT: NOMAD invents its own building blocks (pre-registered)

Phase 4 toward general intelligence. PORT (docs/PORT.md) remembers whole
certified programs and renames their variables onto a new task's inputs;
GROW (docs/GROW.md) sums two learned blocks and rescales by learned
constants. Both only *reuse* what was certified. INVENT makes **new
primitives** out of certified experience: lambda-abstractions with holes
that recur across certified programs, and constants derived from the
constants memory uses, and lets the field arm's enumerator use each one as
a single node. Off switch `NOMAD_INVENT` (default **off** until a sealed
judge below passes). No transformers, no neural weights, no LLM.

## Mechanism (`nomad/invent.py`, hooks in `nomad/world.py`)

1. **Abstraction by compression (Stitch / DreamCoder-style MDL).** Corpus:
   the field's whole certified programs (PORT memory). Candidates: every
   sub-program with its variables turned into typed holes (first-occurrence
   order), and the least general generalisation (anti-unifier) of every pair
   of sub-programs from different programs with the same root (the same
   differing pair maps to the same hole, so `x·x` and `u·u` give `λa. a·a`).
   A candidate's *uses* are the distinct certified programs that contain an
   instance of it (holes bind any sub-program, a repeated hole binds equal
   sub-programs, commutative operators match in either order). Rewriting a
   use saves `size - holes - 1` nodes; the primitive costs `size - holes`;
   **utility = uses x saving - cost**. Promoted: at least `MIN_USES = 2`
   uses, utility >= 0, saving >= 1 (at least two operator nodes, or a
   repeated hole), at most 3 holes, best utility first, deduplicated by
   behaviour on seeded synthetic rows (hole order ignored), at most
   `MAX_INVENTIONS = 8`. Cached per field by memory content.
2. **Learned constants.** The constants learned memory divides or multiplies
   by (`world.bank_scales`, GROW) are closed under pairwise products
   (4 = 2·2, 6 = 2·3, ...), smallest first, `MAX_CONSTANTS = 2` new ones.
   They join GROW's rescaled anchors as extra targets.
3. **First-class use in the field arm's block probe.**
   - *Single nodes.* In the probe's levels, at every size the inventions are
     enumerated first: an application of an arity-k invention costs one node
     plus its arguments' sizes (so the probe reaches one size further,
     `INVENT_SIZE = 1`), arguments are any probe pool entries, the
     invention's own symmetric argument orders and all-constant argument
     tuples are skipped, a new value enters the pools (later levels combine
     it) and, for int goals, gets PORT's residual lookup (add / sub /
     reversed sub / mul against the probe's values). All invention work in a
     task shares `INVENT_CAP = 0.15` of the budget and PORT's per-task
     WITNESS rejection cap.
   - *Invented blocks.* Each invention instantiated over the task's own
     inputs (repeats allowed, so `λa b c. a·b·c` gives the cube `G·G·G`;
     symmetric duplicates skipped; at most `MAX_INSTANCES = 160`) joins
     PORT's bank for the anchors (not its atoms).
   An application is expanded to plain operators the moment it is built:
   search trees never contain a hole, and the interpreter, WITNESS and the
   never-read final split see ordinary programs. Stage 1 (the exact cold
   search) is untouched and the cold control never sees an invention. An
   empty field has no memory, hence no inventions and no learned constants:
   empty with INVENT on is identical to empty with INVENT off (tested).
4. **Dreams** (sampling compositions of library pieces) were considered and
   not built in this phase; the only "dreamed" objects are the derived
   constants. Synthetic rows (seeded random integers) are used only for
   behavioural dedup and symmetry detection; no task row, held-out or
   sealed suite is read to invent anything.

Invented primitives (`python3 scripts/invent_judge.py --inventions`):

| Field | Abstractions (readable) | Learned scales | Derived constants |
|---|---|---|---|
| math only | `λa. a·a` (3 nodes -> 1 + arg; uses 2) | none | none |
| math + science | `λa b c. a + b·c` (uses 4, utility 2), `λa. a·a` (uses 3), `λa b c. a·b·c` (uses 2: `mul(gH, mul(3, 3))`, `mul(I, mul(I, R))`) | 2, 3, 9 | 4 = `mul(2, 2)`, 6 = `mul(2, 3)` |
| all 16 WORLD + science | the three above + `λa. concat(a, a)` | 2, 3, 9 | 4, 6 |

## Design was tuned only on uncommitted dev suites

`/workspace/nomad/invent_dev/` (not committed): TRANSFER-2 catalogue at row
seeds 7 and 11 and the first transfer catalogue at seeds 7 and 11 (the
sealed seeds never read), deep / science / text dev suites
(`sense_dev`, `phase3_dev/text`). Field math_sci (transfer) / all_sci
(regression). INVENT off -> on:

| Dev suite | off | on | Notes |
|---|---|---|---|
| TRANSFER-2 seed 7 | 27/35 | **30/35** (-3.7% evals) | cube via `λabc. a·b·c`, `mul4`, `div6` |
| TRANSFER-2 seed 11 | 26/34 | **29/34** (-3.8%) | same three |
| first transfer seed 7 / 11 | 17/20, 19/20 | 17/20, 19/20 (+1% evals) | nothing left to reach |
| deep dev 7 / 11 | 25, 24 | 26, 24 | no per-task loss |
| science dev 7 / 11 / 13 | 12, 13, 13 | 12, 13, 13 | no per-task loss (+0.6-1.8% evals) |
| text dev 7 / 11 | 2, 3 | 3, 4 | `λa. concat(a, a)` as a node |
| LOFO (16 families) | 5,883 | 5,883, worst 1.0x | |

Choices the dev suites decided: inventions interleaved by size inside the
probe (an invention pass run *before* PORT's atoms, or in lockstep with the
probe's levels, reached 2 more TRANSFER-2 dev tasks but pushed
`sci_water_mol`, which main certifies at 88-96% of the budget, over budget
on two science dev seeds); invented blocks feed the anchors but are not
probe atoms (as atoms they displaced the stoichiometry blocks); symmetric
argument orders skipped. `INVENT_CAP` 0.15 vs 0.25, `MAX_CONSTANTS` 2 vs 4,
`MAX_INVENTIONS` 8 vs 20 made no dev difference.

## The new sealed suite (TRANSFER-3)

TRANSFER-2's misses are known, so INVENT is judged on a **new** catalogue
(`nomad/transfer3.py`, 46 families: building / materials, games /
tournaments, travel / logistics; ordinary textbook and everyday formulas;
input names disjoint from training and both earlier catalogues), new seed
20261125, same procedure (`scripts/invent_suite.py`: cold control at 10,000
evaluations / max_size 7 -> easy; lookup guard against every trained arm's
memory under every renaming and against easy twins; 5 public / 3 challenge
/ 3 final rows, the final split never read by search or WITNESS). Honest
caveat: the catalogue was written by the same author after seeing which
kinds of blocks INVENT can build (squares, cubes, quarter and sixth
scalings appear because building and counting formulas contain them); it
was fixed and committed before any field arm was measured on it at any
seed, and is not re-tuned.

`data/deep/transfer3_suite.json`, sha256
`5a8dab572468551d557558bea6ba2c004b90b254aa68c2878f3e91a9bb4f10e9`: 6 easy
(`g3_cube_count`, `g3_points`, `t3_fuel_saving`, `t3_arrival_minute`,
`t3_vehicles`, `t3_empty_seats`; recorded, never scored), **40 sealed hard**
(building 15, games 11, travel 14), lookup guard dropped none. One hard task
has a cold public-row fit that fails the withheld rows (`t3_last_vehicle`
at 2,886 evaluations); the rest exhaust the 10k budget.

## Arms (`python3 scripts/invent_judge.py`, budget 10,000, max_size 7)

`cold` (twin control), `empty` (no memory, INVENT off), `empty_invent` (no
memory, INVENT on), `trained` (math_sci field, INVENT off = main),
`trained_invent` (math_sci, INVENT on), `math_invent` (math-only field,
INVENT on; report only). No arm trains on any transfer family.

## Pre-registered criteria (committed before any field arm is measured on TRANSFER-3)

1. **INVENT adds (primary):** `trained_invent` certifies at least **+3**
   more than `trained` on TRANSFER-3 hard, or at least as many with **25%
   fewer** evaluations.
2. **It is learning, not search:** the gain disappears with an empty field:
   `empty_invent` certifies no more than `empty` and saves < 5% of its
   evaluations.
3. **No harm:** no arm worse than cold on any task.
4. **No loss on any existing sealed suite** (`--secondary`, INVENT on vs
   off, each suite's own trained field): deep `da3ae9bf…6fbd` >= 27/40,
   science hard >= 12/14, TRANSFER-2 `d8de7508…f19b` >= 30/35, TEXT
   `08a826a3…4a02` >= 3/24; on every suite no task the INVENT-off field
   certifies is lost and no arm is worse than cold.
5. **LOFO** total 5,883, worst 1.0x (INVENT on); **all tests pass**.

Decision: all met -> `NOMAD_INVENT` default **on**. Otherwise it stays
**off** and the result is recorded here as a negative result. Nothing is
re-tuned on a sealed suite.

## Sealed result (measured once, 2026-11-21, after `d43ae99`)

TRANSFER-3 (`python3 scripts/invent_judge.py`, sha `5a8dab57…10e9`, 40 hard):

| Arm | Certified /40 | Building /15 | Games /11 | Travel /14 | Evaluations | vs empty |
|---|---|---|---|---|---|---|
| cold | 0 | 0 | 0 | 0 | 392,886 | |
| empty (no memory, INVENT off) | 1 | 0 | 0 | 1 | 395,311 | |
| empty, INVENT on | 1 | 0 | 0 | 1 | 395,311 (identical) | 0 |
| trained (math + science, INVENT off = main) | 20 | 8 | 4 | 8 | 309,010 (-21.8%) | +19 |
| **trained, INVENT on** | **24** | 11 | 5 | 8 | 290,998 (-26.4%) | **+23** |
| math only, INVENT on (report) | 7 | 1 | 3 | 3 | 346,101 | +6 |

Secondary (`--secondary`, each suite's own trained field, INVENT off -> on):

| Suite | cold | empty | trained (off) | trained (INVENT on) | Per-task changes |
|---|---|---|---|---|---|
| deep `da3ae9bf…6fbd` | 0 | 25 | 27 | 27 (235,425 vs 235,421 evals) | none |
| science hard `4517167f…868d` | 0 | 0 | 12 | 12 (-2.0% evals) | **+`sci_dist_m`**, **-`sci_water_mol`** |
| TRANSFER-2 `d8de7508…f19b` | 0 | 2 | 30 | **33** (-3.7% evals) | +3, no loss |
| TEXT `08a826a3…4a02` (lang field) | 0 | 0 | 3 | 3 | none |

LOFO with INVENT on: 5,883, worst 1.0x. Tests: 404 pass (6 skipped).

| Criterion | Bar | Result | Met? |
|---|---|---|---|
| 1. INVENT adds on TRANSFER-3 | >= +3 or 25% fewer evals | **+4** (24 vs 20), -5.8% evals, no trained win lost | yes |
| 2. Gain vanishes with an empty field | empty_invent <= empty, < 5% fewer evals | 1 = 1, identical evaluations | yes |
| 3. No arm worse than cold | 0 | 0 (all six arms) | yes |
| 4. No loss on existing sealed suites | counts >= 27 / 12 / 30 / 3 and no per-task loss | counts 27 / 12 / 33 / 3, but science hard **loses `sci_water_mol`** (main certifies it at 9,890 of 10,000 evaluations; INVENT's extra anchors push it over budget) while gaining `sci_dist_m` | **no** |
| 5. LOFO, tests | 5,883, 1.0x; all pass | 5,883, 1.0x; 404 pass | yes |

Decision: **INVENT does not pass as pre-registered** (criterion 4: one
per-task loss on the sealed science suite). `NOMAD_INVENT` stays **off** by
default; nothing is re-tuned on a sealed suite. This is a near miss with a
real positive signal, recorded honestly:

- The primary test passes cleanly and the gain is learning, not search: the
  same mechanism over an empty field changes nothing (identical
  evaluations), and a math-only field, which can invent only `λa. a·a` and
  learns no constants, certifies 7, not 24.
- What the 4 TRANSFER-3 wins are (WITNESS-certified, final split included):
  - invented block `λa b c. a·b·c` instantiated as a cube (`ht·ht·ht`,
    `wd·wd·wd`), then PORT's anchor: `b3_two_cubes` wd^3 + ht^3,
    `b3_room_minus_cube` wd·ln·ht - ht^3;
  - learned constant 4 = `mul(2, 2)` rescaling the goal: `b3_slab`
    pa·pb·pc/4 -> `div(pa·(pb·pc), mul(2, 2))`;
  - invented primitives as single nodes in the probe, with a residual
    lookup: `g3_star_number` 6n(n-1)+1 ->
    `add(add(1, mul(3, mul(nl, nl))), mul(nl, mul(sub(nl, 2), 3)))`.
- On TRANSFER-2 INVENT reaches 3 of its 5 known misses (cube via
  `λabc. a·b·c`, `mul4`, `div6`); on science it adds `sci_dist_m` via the
  derived 6 = `mul(2, 3)`.
- The loss is a budget-edge effect, not a wrong answer: `sci_water_mol` was
  certified by main with 110 evaluations to spare, and dev had flagged the
  same task as fragile (it is why the lockstep / invention-first variants
  were rejected on dev).

Still unsolved on TRANSFER-3 by every arm: `b3_path_around`, `b3_two_beds`,
`b3_cube_shell`, `g3_tetra_stack`, `g3_squares_on_board`,
`g3_groups_then_final`, `g3_points_pct`, `g3_win_pct`,
`t3_fuel_plus_toll`, `t3_litres_two_legs`, `t3_distance`,
`t3_cost_per_head` (nested division, products of shifted terms, n(n+1)(n+2)).
Some certified programs are exact on the stated input ranges rather than
symbolic identities (e.g. `t3_hire_cost` via `hire·(pax div cap) + hire`).

---

# Round 2: budget-safe INVENT phase + iterated invention (pre-registered)

Round 1 failed only criterion 4: on the frozen science suite main certifies
`sci_water_mol` at 9,890 of 10,000 evaluations and INVENT's extra anchors
(derived-constant targets inside GROW, invented instances in PORT's bank)
pushed it over budget. Round 2 changes *where* INVENT spends and lets
invented primitives compose. Off switch unchanged (`NOMAD_INVENT`, default
off until the judge below passes).

## Mechanism changes

1. **Main's path is untouched up to one INVENT phase.** Invented instances no
   longer join PORT's bank and derived constants no longer join GROW's
   targets: stage 1, SENSE, BLOCKPROBE trigger, PORT (bank run, anchors,
   atoms), GROW (two-block and rescaled anchors) and the atoms offered to the
   probe are exactly main's. Then a single capped **INVENT phase**
   (`invent_phase` in `world.py`, at most `INVENT_CAP = 0.15` of the budget
   and PORT's per-task rejection cap) runs before the probe's regular levels:
   (a) invented blocks over the task's inputs (1 evaluation each; constants
   and plain inputs such as `min(a, a·a) = a` skipped) are anchored on the
   goal and on the goal rescaled by every learned and derived constant;
   derived constants also rescale the bank blocks' anchors; (b) invented
   primitives as single nodes over the probe's pools, size by size up to
   max_size + 1, with direct and residual fits on the same targets
   (applications that return one of their arguments are skipped).
2. **Evidence gate (the budget edge).** When some bank block already equals
   the goal on `INVENT_EQ_GATE = 2` or more public rows, the regular levels
   are likely to finish the task, so the phase is **deferred** and runs only
   on the budget the regular levels leave. (`INVENT_AT = "after"`, always
   deferring, is the strict guarantee; on dev it leaves INVENT no budget and
   no gain, so it is not the default.) This is a heuristic, not a proof: an
   already-solvable task without such a block can still be pushed over
   budget; the sealed judge checks per-task losses on every frozen suite.
3. **Iterated invention (rounds >= 2, `ROUNDS = 2`).** Parts: the round-1
   primitives and **learned operator frames** (each binary int operator used,
   with a non-constant argument, by >= 2 certified programs). A round-r
   candidate fills one hole of a round-(r-1) primitive (or frame) with a
   round-1 primitive or frame (two different frames never compose alone; a
   frame may compose with itself, e.g. nested division), or wraps a round-1+
   primitive by a learned / derived constant (`// k`, `* k`). Kept: <= 3
   holes, saves >= 1 node per application (a learned constant counts as one
   node), not degenerate (constant or a bare hole on the synthetic rows),
   behaviourally new against every earlier primitive and frame; ranked by
   evidence x saving (evidence = the smaller use count of its parts), at most
   `PER_HEAD = 2` per outer part and `MAX_COMPOSED = 6` per round. Synthetic
   rows are now log-uniform in 1..1000 so division is not all zeros.

Invented primitives with round 2 (`python3 scripts/invent2_judge.py --inventions`):

| Field | Round 1 | Round 2 (built from) |
|---|---|---|
| math only | `λa. a·a` | `λa. a·a·a·a` (sq∘sq), `λa b. min(a,b)·min(a,b)` (sq∘min), `λa b. min(a, b·b)`, `λa b. a·b·b`, `λa b. a - b·b`, `λa b. a·a - b` |
| math + science | `λa b c. a + b·c`, `λa. a·a`, `λa b c. a·b·c` | `λa b c. (a + b·c)·(a + b·c)` (sq∘fma), `λa. a·a·a·a`, `λa b c. (a + b·c) // 2`, `λa b c. (a + b·c) // 3` (fma under a learned constant), `λa b c. (a + b) + c`, `λa b. a + b·b` |
| all + science | as math + science, + `λa. concat(a, a)` | as math + science with `λa. concat(concat(a,a), concat(a,a))` |

## Dev tuning (uncommitted dev suites only; trained = INVENT off)

TRANSFER-2 catalogue at seeds 7 / 11 (math_sci field), TRANSFER(-1)
catalogue at seeds 7 / 11, deep dev 7 / 11, science dev 7 / 11 / 13 and text
dev 7 / 11 (all_sci field). Net extra solves, per-task losses:

| Setting | T2 dev 7 / 11 | T1 dev | deep dev | sci dev | text dev | losses |
|---|---|---|---|---|---|---|
| chosen settings but no gate | +3 / +2 | 0 | +2 | 0 | +3 / +3 | **water_mol x2** |
| `INVENT_AT = "after"` (early settings) | 0 / 0 | 0 | . | . | . | 0 |
| gate 1 (early settings) | +3 / +1 | . | . | . | . | 0 |
| **gate 2 (chosen)**, rounds 2, frames, constant wraps, 2 per head | +3 / +2 | 0 | +2 | 0 | +3 / +3 | 0 |
| chosen, rounds 1 only | +4 / +3 | 0 | +1 | 0 | +1 / +1 | 0 |
| chosen, rounds 3 | +3 / +3 | 0 | +2 | 0 | +1 / +1 | 0 |
| gate 4 / 5 / 6 (early settings) | +3 / +2 | . | +2 | **water_mol x2** | . | 2 |

"Early settings": 1 composition per head, no constant wraps (the first
round-2 build); "." = not run with that setting. The gate and the round-2
settings were picked on these dev numbers only.
Gate 3 is the edge (the water_mol dev tasks have a block equal on 3 rows),
so 2 was chosen. Round 2 beats round 1 on dev in total (+13 vs +10 extra
solves) but loses on the TRANSFER-2 dev seeds (+5 vs +7), so the fresh suite
decides; round 1 alone is a report-only arm.

## The new sealed suite (TRANSFER-4)

`nomad/transfer4.py`, `scripts/invent2_suite.py`, seed **20261126**, 47
families in three new domains (kitchen / baking, garden, workshop / crafts),
input names disjoint from every earlier catalogue, the science catalogue and
all training tasks (tested). By the owner's brief it deliberately includes
the round-2 target shapes (products of shifted terms such as `(cb - 2)^3`,
`(tw + 1)(tl + 1)tk`; n(n+1)(n+2)-type products; nested floor / ceiling
division) next to ordinary formulas. Same procedure as TRANSFER-3: cold
control at 10,000 evaluations, max_size 7 -> easy / hard, lookup guard,
WITNESS challenge rows, a disjoint never-read final split. Generated (cold
only) and committed with its sha256 **after** this pre-registration and
with the INVENT code frozen; no field arm, and no INVENT run, ever touched
the TRANSFER-4 catalogue before the single sealed measurement.

## Arms (`python3 scripts/invent2_judge.py`, budget 10,000, max_size 7)

cold / empty / empty_invent / trained (math_sci, INVENT off) /
trained_invent (math_sci, INVENT on), and report only: trained_invent_r1
(round 1 only) and math_invent. Secondary (`--secondary`): cold / empty /
trained / trained_invent on deep, science hard, TRANSFER(-1), TRANSFER-2,
TEXT and TRANSFER-3, each with its own trained field.

## Pre-registered criteria (round 2; all required to turn INVENT on)

1. **INVENT adds** on TRANSFER-4 hard: trained_invent certifies >= 3 more
   than trained, or as many with >= 25% fewer evaluations.
2. **The gain vanishes with an empty field:** empty_invent certifies no more
   than empty and spends within 5% of its evaluations.
3. **No decision arm worse than cold** on any TRANSFER-4 task.
4. **No per-task loss on any existing sealed suite:** on each of deep,
   science hard, TRANSFER(-1), TRANSFER-2, TEXT and TRANSFER-3,
   trained_invent certifies every task trained certifies, at least the
   recorded baseline (deep 27, science 12, TRANSFER-2 30, TEXT 3), and no
   arm is worse than cold.
5. **LOFO** stays 5,883 / worst 1.0x (with INVENT on).
6. **All tests pass**; CI green.

If every criterion passes, `NOMAD_INVENT` defaults to on. Otherwise INVENT
stays off and the result is committed as measured.
