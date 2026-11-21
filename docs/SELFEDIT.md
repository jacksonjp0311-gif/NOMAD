# SELFEDIT: a self-edit sandbox, first target the invented constants (pre-registered)

INVENT (docs/INVENT.md) gave NOMAD its own building blocks and its own constants
(4 = 2·2, 6 = 2·3, derived from the learned scales by a pairwise-product closure).
Those knobs were frozen in code. SELFEDIT makes them **bounded genome genes** and
adds a **sandbox** in which NOMAD proposes a tiny change to them, tests it, replays
what it just did under the change, and advances or rolls back -- at checkpoint
cadence, never inside a sleep. Everything is behind **`NOMAD_SELFEDIT`, default
OFF** (the sealed judge below failed two criteria, so it stays off). No transformers, no neural weights, no
LLM; WITNESS certifies every program; the sandbox edits genome *data*, never code;
the cold control is untouched.

## What is built

- **Invention genes** (`nomad/genome.py`, `INVENT_GENES`; read only while
  `NOMAD_SELFEDIT` is on; the defaults reproduce INVENT round 2 exactly):
  | gene | bounds | default | meaning |
  |---|---|---|---|
  | `inv_max_constants` | 0..8 | 2 | derived learned constants promoted (smallest first) |
  | `inv_const_depth` | 1..2 | 1 | product-closure rounds over the learned scales (2: 8 = 2·4, 12 = 2·6, ...) |
  | `inv_rounds` | 1..3 | 2 | invention rounds (composition depth) |
  | `inv_floor_fit` | 0..1 | 0 | floor-division fit by learned / derived constants |
  `genome.override(genes)` evaluates a candidate in-process without writing
  `data/genome.json`; `NOMAD_GENOME=path` measures a frozen genome file.
- **Floor-division fit** (`nomad/world.py`, INVENT phase only, gene `inv_floor_fit`):
  INVENT's rescaled targets (`goal * k` -> `block // k`) only catch exact
  division. With the gene on, a block value `v` already computed in the phase
  (an invented block over the inputs, a bank block, an invented-primitive
  application) whose `v // k` equals the goal on every public row, `k` a learned
  or derived constant, is offered as `v // k` to WITNESS. Like the rescaled-target
  test, the comparison is a lookup on a value already paid for (no extra
  evaluation); only the WITNESS-gated offer is a fit. An empty field has no
  constants, so it gains nothing.
- **Sandbox** (`nomad/selfedit.py`), one step per checkpoint when due (at most
  hourly, never while an accepted change awaits the guard):
  1. *record* the window: the world twin pairs the live body ran since the last
     self-edit attempt (families + recorded treatment outcome, `data/scoreboard.jsonl`);
  2. *propose* one bounded step of one invention gene (seeded, replayable), never a
     candidate it already rejected from the same genome (tabu list read from its log;
     without it a dev run re-proposed the same rejected moves and never found the
     floor fit in 16 steps);
  3. *test*: the committed dev benchmark `nomad.selfedit_tasks.DEV_CATALOGUE`
     (16 unit / packing formulas, dev seed 7) on the reference field (16 WORLD
     families + easy science) under the current and the candidate genome;
     then the **keep set** (the TRANSFER-4 catalogue at the dev seed 7, never the
     sealed rows);
  4. *replay* the window's tasks under both genomes on a deep copy of the live field;
  5. *analyse*: advance only if dev is strictly better (more certified, or as many
     with fewer evaluations) and loses no dev task, the keep set and the replay lose
     no task (certified -> not, or more evaluations), the full unit-test suite passes
     with the candidate genome, and the live-field files are byte-identical before
     and after (fingerprint). Advance = `data/genome.json` + a log row; the body
     commits it as `nomad-evolve: <id> selfedit <gene> a -> b (...)`, so the existing
     guard still `git revert`s it on a live twin regression. Every attempt is logged
     to `data/evolution.jsonl` (`"organ": "selfedit"`). When the sandbox runs at a
     checkpoint, the old one-gene `evolve` does not run at that checkpoint.

## Sealed suite

`scripts/selfedit_suite.py`, catalogue `nomad.selfedit_tasks.CATALOGUE` (24 formulas,
domains music / sport / travel, inputs `zp..zw` disjoint from every catalogue,
written before any field arm was measured on it: some constants derivable from the
learned scales (4, 6, 8, 12, 16, 18, 24, 36), some not (7, 60), three answers are
ceilings, which a floor fit cannot produce), seed **20261128** (20261127 is TRANSFER-5's):
`data/deep/selfedit_suite.json`, sha256
`a7d061beab9da1e5de21a351295e14e8f6c1640f72843a58e4f9a261d82756a5`:
1 easy (cold certifies at 10k; never scored), **23 sealed hard**; the lookup guard
dropped none.

## Judge (`python3 scripts/selfedit_judge.py`, budget 10,000, max_size 7, PORT / ANCHOR2 / SCALE on)

1. The sandbox runs **K = 24** steps offline from the default genome (base seed
   20261128): dev benchmark + keep set on the reference field; the window is the 16
   WORLD training families replayed on a copy of that field; no unit tests inside
   the loop (criterion 5 runs them once); `data/` is fingerprinted before and after.
2. The final genome **G\*** is frozen and the sealed suite is scored once: `cold`,
   `empty_default`, `empty_tuned` (G\*), `trained_off` (NOMAD_SELFEDIT=off),
   `trained_default` (on, default genome), **`trained_tuned`** (on, G\*; scored),
   `math_sci_tuned` (report).

## Pre-registered criteria (committed before any sealed measurement)

All must hold to flip `NOMAD_SELFEDIT` on by default:

1. **Self-edit helps**: `trained_tuned` certifies >= **+3** over `trained_default`,
   or >= 0 more with >= **25% fewer** evaluations.
2. **Gains vanish with an empty field**: `empty_tuned - empty_default <= 1` and
   `empty_tuned - cold <= 1`.
3. **No sealed task worse**: `trained_tuned` loses no task to `trained_default`
   (certified lost or more evaluations), and neither `trained_tuned` nor
   `empty_tuned` is worse than cold on any task.
4. **No per-task loss on the existing sealed suites** (deep, science hard,
   transfer 1-4 and the INVENT secondary re-runs, text, bridge; every arm of every
   judge; `scripts/switch_regress.py`, SWITCH=NOMAD_SELFEDIT), switch on vs off,
   **(a)** with the default genome and **(b)** with `NOMAD_GENOME` = G\*.
5. **LOFO total <= 5,883, worst 1.0x** with the switch on and G\*; **the full test
   suite passes**.
6. **Safety**: `trained_off` equals `trained_default` on every task (certified and
   evaluations), and the offline sandbox left the live data fingerprint unchanged.

Decision rule: all six pass -> default on in a follow-up commit with the results.
G\* is **not** written to `data/genome.json`: the live sandbox must earn every edit
itself, through its own dev / keep / replay / tests / guard. Otherwise the switch
stays off and an honest negative-result note is committed here. Nothing under
`results/` is overwritten.

## Dev expectations (stated before the sealed run; uncommitted dev suites only)

On the dev catalogue (rows of seeds 11 and 13, never the sandbox's own seed-7 rows)
the default genome certified 6 / 5 of 16 with the reference field, 0 empty, 0 cold.
On dev seed 13, with the judge's base seed and tabu list, 16 offline steps accepted 3
edits (floor fit on; constants 2 -> 6; closure depth 1 -> 2, at step 16 -- hence
K = 24), rejected `inv_rounds` 2 -> 3 on the keep set (six TRANSFER-4 dev tasks cost
more), and the tuned genome certified **12** vs 5 for the default genome, 0 for both
empty arms, no task worse (another base seed without the tabu list accepted nothing
in 16 steps). On the dev suites of earlier
rounds (TRANSFER-1 dev 7 / 11, science dev 7 / 11, TRANSFER-2 dev 7 / 11, TRANSFER-4
dev 7) the tuned genome changed nothing (byte-identical certified and evaluations).
Expectation for the sealed suite: criterion 1 passes with a smaller margin than dev
(the sealed constants and shapes differ; 7, 60 and the ceilings are out of reach);
criteria 2-6 pass.

## Sealed result (measured once, 2026-11-21, code `6690d61`; `results/selfedit/`): **FAIL -> NOMAD_SELFEDIT stays OFF**

Sandbox (K = 24, base seed 20261128): 4 edits accepted -- `inv_floor_fit` 0 -> 1
(dev 6 -> 8), `inv_max_constants` 2 -> 6 (8 -> 9), `inv_const_depth` 1 -> 2 (9 -> 12),
`inv_max_constants` 6 -> 8 (12 -> 12, fewer evaluations); `inv_rounds` 2 -> 3 was
rejected by the keep set. **G\*** = {max_constants 8, const_depth 2, rounds 2,
floor_fit 1} (`results/selfedit/genome_tuned.json`). data/ fingerprint unchanged.

Sealed suite (sha `a7d061be...56a5`, 23 hard), certified / evaluations:

| arm | certified | evaluations |
|---|---|---|
| cold | 0 | 221,117 |
| empty_default | 2 | 214,273 |
| empty_tuned | 2 | 214,273 |
| trained_off | 8 | 189,521 |
| trained_default | 8 | 189,521 |
| **trained_tuned** | **17** | **165,279** |
| math_sci_tuned | 17 | 165,279 |

All 9 gains are floor-division fits by learned constants (`port:invent:...:floor8 /
floor12 / floor16 / floor18`: phrases of 8, sets of 12, warm-up // 16, relay // 4,
six-a-side // 6, balls // 12, straps // 12, slots // 8, legs // 36). Out of reach as
expected: // 7, 60·zu, the three ceilings, // 16 bracket, (zu zv + zw) // 6.

| criterion | result |
|---|---|
| 1 self-edit helps (>= +3) | **pass**: +9 certified, 12.8% fewer evaluations |
| 2 gains vanish with an empty field | **FAIL as written**: `empty_tuned - empty_default` = 0, but `empty_tuned - cold` = 2 > 1 (the empty field's own SENSE / case-split wins on `se_m_beats44`, `se_m_stands`, identical without the self-edit) |
| 3 no sealed task worse | **pass**: no loss vs trained_default, nothing worse than cold |
| 4a existing suites, default genome | **pass**: 0 losses, 0 gains on every arm of deep, science, transfer 1-4, secondary, text, bridge (byte-identical) |
| 4b existing suites, G\* | **FAIL**: 1 loss -- TEXT `t_line_len`, arm `all_sci`, evaluations 3,817 -> 4,089 (still certified); 1 gain (TRANSFER-2 `g2_kite`, `math_sci_grow_off`, 5,900 -> 5,887) |
| 5 LOFO, tests | **pass**: LOFO 5,883, worst 1.0x; 441 passed, 6 skipped |
| 6 safety | **pass**: trained_off == trained_default on every task; sandbox left data/ untouched |

Decision (pre-registered rule): two criteria fail, so **`NOMAD_SELFEDIT` stays OFF**.
Nothing in the live body changes (switch off: invent ignores the genome, the body never
runs the sandbox, the old evolve organ runs as before).

Honest reading:
- The mechanism works where it was aimed: a self-edit loop that only touches genome
  data found, on its own dev benchmark, a genome that more than doubles the trained
  field on blind sealed tasks (8 -> 17 of 23), and the gain is memory (an empty field
  gains 0 from it).
- Criterion 2 was mis-specified: copying earlier rounds' `empty - cold <= 1` measured
  the empty field's base search features, not the self-edit. It is recorded as a fail
  anyway; a corrected criterion would have to be pre-registered on a fresh sealed suite.
- Criterion 4b is a real cost. Diagnosed after the measurement (diagnosis only, no
  change made): the extra 272 evaluations come from **`inv_const_depth` = 2** alone
  (more derived-constant targets -> more residual anchors before the hit); floor fit
  alone, or more constants at depth 1, leave `t_line_len` at 3,817. The keep set
  (TRANSFER-4 dev rows) did not cover string-length tasks, so the sandbox could not see
  this cost.
- Next step, not attempted here: widen the keep set (TEXT / BRIDGE dev rows) or charge
  derived-constant targets only after the learned-scale ones, then a fresh sealed suite
  with a corrected criterion 2.
