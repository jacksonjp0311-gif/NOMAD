# INVENT_TEXT: string goals use invented and remembered blocks (pre-registered)

BRIDGE (docs/BRIDGE.md) let INVENT run on string goals, and it added nothing
(`trained_binvent_off` = `trained`). Two reasons, found on the bridge dev suites:
(1) the string INVENT phase is always *deferred* -- it only gets the budget the
regular levels leave, which on a hard task is none; (2) INVENT's residual anchors
(goal = block + b, block - b, block * b) are integer-only, so a string goal never
gets the "half of it is a block I know" move. The field *does* hold string
inventions (rotate = `concat(drop(a, b), take(a, b))`, `itos(strlen(a))`, composed
rotations); they had no way in. Everything below is behind **`NOMAD_INVENT_TEXT`,
default ON since the sealed judge below passed** (off switch: `NOMAD_INVENT_TEXT=off`). No transformers, no neural weights;
WITNESS certifies every program; the cold control is untouched.

## What is built (`nomad/world.py`, `nomad/invent.py`)

- **Concat residual anchors**: a string block value `v` that is a proper prefix
  (suffix) of the goal on every public row leaves a remainder per row; if a pool
  value, a bank block or an invented block equals the remainder, `concat(v, b)`
  (`concat(b, v)`) is offered to WITNESS. Longest matching blocks first, at most
  `TEXT_ANCHOR_N` = 24 per pass. Cost accounting: the remainder lookup is free (a
  comparison on values already computed, like INVENT's rescaled targets and the
  SELFEDIT floor fit); an assembled candidate costs 1 evaluation. (INVENT's
  integer residual anchors charge 1 evaluation per lookup; this is a deliberate,
  documented difference.)
- **Where**: (a) an *early pass* right after the PORT block probe, over the bank
  blocks' string values (already computed) -- it costs nothing unless a remainder
  is found; (b) inside the (still deferred) INVENT phase, over invented blocks
  instantiated on the task's inputs plus the bank blocks. The integer path is
  unchanged; the switch off changes nothing; an empty field has no bank, so it
  gains nothing; with NOMAD_INVENT off there is no kit and no anchor.
- A first dev version ran the whole INVENT phase early on string goals whenever a
  bank block was a prefix / suffix; it lost ~1,600 evaluations on a dev task the
  regular levels solve, so it was replaced by the free early pass (dev only).

## Sealed suite

`nomad/text_invent_tasks.py` (22 formulas: string and mixed int/str compositions,
two integer-output controls, a few non-concatenation shapes; new inputs `xw xv xk
xj xq` disjoint from every catalogue; separator "_"), written before any field arm
was measured on it; `scripts/text_invent_suite.py` (the BRIDGE generator: cold at
10,000 -> easy / hard, lookup guard on every trained arm's memory), seed
**20261130**: `data/deep/text_invent_suite.json`, sha256
`cef71e021555c8897e352a240c735a9e3f4feff3e31542de72747e0d5f46e5a4`: 7 easy
(never scored), **15 sealed hard**, none dropped by the guard.

## Judge (`python3 scripts/text_invent_judge.py`, budget 10,000, max_size 7, NOMAD_BRIDGE on)

Fields = `scripts/bridge_suite.fields()` (trained = 16 WORLD families + easy science
+ the 16 bridge training tasks). Arms: `cold`, `empty_off`, `empty_on`,
`trained_off`, **`trained_on`** (scored); report: `world_only_on`, `bridge_only_on`,
`trained_on_invent_off`.

## Pre-registered criteria (committed before any sealed measurement)

All must hold to flip `NOMAD_INVENT_TEXT` on by default:

1. **It helps**: `trained_on` certifies >= **+3** over `trained_off`, or >= 0 more
   with >= **25% fewer** evaluations.
2. **Gains vanish with an empty field**: `empty_on - empty_off <= 1` (the switch's own
   effect on an empty field; `empty_on - cold` is reported -- SELFEDIT's criterion 2
   copied `empty - cold` and so measured the base search, not the switch).
3. **No sealed task worse**: `trained_on` loses no task to `trained_off` (certified
   lost or more evaluations); neither `trained_on` nor `empty_on` is worse than cold.
4. **No per-task loss on the existing sealed suites** with the switch on vs off: deep,
   science hard, transfer 1-4 and the INVENT secondary re-runs, text, bridge; every arm
   of every judge (`scripts/switch_regress.py`, SWITCH=NOMAD_INVENT_TEXT).
5. **LOFO total <= 5,883, worst 1.0x** with the switch on; **the full test suite passes**.

Decision rule: all five pass -> default on in a follow-up commit with the results;
otherwise it stays off and an honest negative-result note is committed here.

## Dev expectations (bridge dev suites, seeds 7 and 11, uncommitted)

`trained` 9 -> **15** (seed 7) and 8 -> **15** (seed 11) of 21 hard with the switch on;
evaluations -22% / -25%; empty 0 / 0, cold 0; no per-task loss on any arm. The gains
are concatenations of two remembered blocks (`b_pick_two`, `b_split_at`,
`b_split_upper`, `b_swap_split`, `b_stretch_first`, `b_echo_sep`, `b_two_drops`), found
in the early pass. Expectation for the sealed suite: criterion 1 passes with a smaller
margin (15 hard tasks, several are not concatenations or need three parts); 2-5 pass.
Honest framing: this is *composition of remembered and invented blocks on strings*,
not new string abstractions -- the abstraction step itself is unchanged.

## Sealed result (measured once, 2026-11-21, code `38f434d`; `results/invent_text/`): **PASS -> default ON**

Sealed suite sha `cef71e02...e5a4`, 15 hard:

| arm | certified | evaluations |
|---|---|---|
| cold | 0 | 150,000 |
| empty_off | 0 | 150,000 |
| empty_on | 0 | 150,000 |
| trained_off | 6 | 134,722 |
| **trained_on** | **13** | **85,724** |
| world_only_on (report) | 1 | 145,024 |
| bridge_only_on (report) | 13 | 88,208 |
| trained_on_invent_off (report) | 6 | 134,722 |

7 new certifications (`x_word_sep_len`, `x_stutter_initial`, `x_rev_head`, `x_double_kth`,
`x_cross_tail`, `x_len_pair`, `x_rest_stutter`), 3 cheaper (~9,500-9,980 -> ~5,030), all via
`port:invent:text:pre|suf`; not reached: `x_last_sep_first` (three parts), `x_digits_then_word`.

| criterion | result |
|---|---|
| 1 helps (>= +3) | **pass**: +7 certified, 36.4% fewer evaluations |
| 2 empty field gains nothing | **pass**: empty_on - empty_off = 0 (empty_on - cold = 0) |
| 3 no sealed task worse | **pass**: no loss vs trained_off; nothing worse than cold |
| 4 existing suites, every arm | **pass**: 0 losses. Gains: TEXT all_sci 6 -> **10**, lang 3 -> 7, all_grow_off 3 -> 7; BRIDGE trained 6 -> **13**, bridge_only 9 -> 12; INVENT secondary text trained_invent 3 -> 7; deep, science, transfer 1-4 byte-identical |
| 5 LOFO, tests | **pass**: LOFO 5,883, worst 1.0x; 444 passed, 6 skipped |

Honest reading: the gain is real and memory-borne (empty field 0; world_only 1 -- it needs the
bridge-trained blocks), but it is *composition* of remembered / invented blocks by concatenation,
not new string abstractions. Two-part concatenations only; three-part strings still fail. The free
remainder lookup is an accounting choice (see above); every certified program is WITNESS-checked
and final-split-correct like any other.
