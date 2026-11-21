# INVENT: NOMAD invents its own building blocks (pre-registered)

Phase 4 toward general intelligence. PORT (docs/PORT.md) remembers whole
certified programs and renames their variables onto a new task's inputs;
GROW (docs/GROW.md) sums two learned blocks and rescales by learned
constants. Both only *reuse* what was certified. INVENT makes **new
primitives** out of certified experience: lambda-abstractions with holes
that recur across certified programs, and constants derived from the
constants memory uses, and lets the field arm's enumerator use each one as
a single node. Off switch `NOMAD_INVENT` (default **off** until the sealed
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
