# GROW: program-language growth for integer transfer (pre-registered)

Phase 3 (A) toward general intelligence: **widen what learned memory can
build.** PORT (docs/PORT.md) and TRANSFER (docs/TRANSFER.md) showed renamed
learned blocks carry over to a never-trained domain (geometry + finance:
math+science 11/20, empty 2, cold 0). The 9 transfer tasks it could not
certify need sums of three products (`geo_box_surface`, `geo_diag3`,
`geo_open_box`, `geo_frame`), the constant 4 (`geo_box_edges`), or a halving
after a product (`geo_trap_area`, `geo_tri_prism`, `geo_diagonals`,
`geo_tri_count`). GROW adds two memory-driven organs inside PORT's block
probe, each behind its own off switch. Neither touches the DSL, the
interpreter, WITNESS, the cold control, or stage 1.

## Mechanisms (nomad/world.py)

1. **Two-block anchor** (`NOMAD_ANCHOR2`). PORT's anchor certifies
   `op(block, pool value)` by residual lookup. The two-block anchor reaches
   `a + b + c`: `a`, `b` are two of the `ANCHOR2_M = 40` bank blocks (one per
   distinct value) that lie between 0 and the goal on every public row,
   most goal-like row order first; `c = goal - a - b` is looked up among the
   probe's values. 1 evaluation per lookup; every fit is WITNESS-gated.
2. **Learned scales** (`NOMAD_SCALE`). `bank_scales`: every constant
   `k >= 2` that learned memory divides by (`div(_, k)`) or multiplies by (a
   var-free factor) is a learned scale, with its smallest tree (for the
   math+science field: 2, 3 and 9 = `mul(3, 3)`; for a math-only field: none;
   for an empty field: none). The goal is rescaled (no evaluation): `goal*k`
   is anchored and wrapped in `div(., k)`; `goal/k`, where exact, is anchored
   and wrapped in `mul(., k)`. Depth-1 anchors on each rescaled goal first,
   then (with `NOMAD_ANCHOR2`) two-block anchors on them.
3. Budget and safety: both share `GROW_CAP = 0.25` of the budget (inside the
   probe's cap) and `GROW_REJECTS = 8` WITNESS rejections per task, so they
   cannot starve the rest of the probe or the WITNESS_CONTINUE cap. When
   stage 1 finishes before the probe trigger (tasks with few inputs), the
   probe now runs once after the lead block, case split and mutants, before
   stage 2 (only when a GROW switch is on and the field has a bank).
4. Learned constants as atoms (`NOMAD_CONST`, report only): var-free
   certified sub-programs with a value outside 0-3 enter the bank as atoms.
   Dev: adds nothing over 1 + 2 (17/19/18 either way). The training curricula
   certify no program containing the constant 4 (4 is reached as `add(1, 3)`
   from the pools), so "learning 4" has no source yet. Stays **off**.

An empty field has an empty bank, so empty and cold are identical with GROW
on or off (tested).

## Design was tuned only on uncommitted dev suites

`/workspace/nomad/phase3_dev/` (not committed): first transfer catalogue,
row seeds 7 / 11 / 13 (the sealed seed 20261122 never read), math+science
field. PORT alone: 9 / 11 / 10 of 20. Two-block anchor: 12 / 14 / 13. Learned
scales: 15 / 17 / 16. Both: 18 / 20 / 19 uncapped, 17 / 19 / 18 with
`GROW_CAP = 0.25` (the cap removed the one per-task loss on dev science,
`sci_water_mol`). Dev regression (all-WORLD + science field, GROW on vs off):
deep dev 7 / 11: 19 -> 25, 20 -> 24, no per-task loss; science dev 7 / 11 /
13: 8 -> 12, 9 -> 13, 9 -> 13, no per-task loss.

## The new sealed suite (TRANSFER-2)

The first transfer suite's 9 failures shaped the design, so GROW is judged on
a **new** catalogue (`nomad/transfer2.py`, 38 families: 24 geometry, 14
finance, new formulas where possible, input names disjoint from training and
from the first catalogue), new seed 20261123, same procedure
(`scripts/grow_suite.py`: cold control at 10,000 / max_size 7 -> easy;
lookup guard against every trained arm's memory under every renaming and
against easy twins).

`data/deep/transfer2_suite.json`, sha256
`d8de7508d8d500abef5233ed9f56abd3c1b50e2797fd3aee097d6bb3c4e1f19b`: 3 easy
(never trained on, never scored), **35 sealed hard**, lookup guard dropped
none. Two hard tasks have cold public-row fits that fail the withheld rows
(`g2_kite` at 3,470 evaluations); the rest exhaust the 10k budget. Some
formulas are structurally close to first-catalogue ones (`g2_kite` ~
`geo_tri_area`, `g2_tri_area_diff` ~ `geo_trap_diff`, `g2_trap_prism` ~
`geo_trap_area` x a length); they were kept rather than chosen by outcome.

## Arms (`python3 scripts/grow_judge.py`, budget 10,000, max_size 7)

`cold`, `empty`, `math`, `math_sci`, `all_sci` (the trained fields of
`scripts/transfer_suite.py`, GROW on), `math_sci_grow_off` (PORT as in
`3d053ca`), `math_sci_port_off`. No arm trains on any transfer family.

## Pre-registered criteria (committed before any field arm is measured on TRANSFER-2)

1. **Trained beats empty (primary, `math_sci`, GROW on):** at least **+3**
   certified, or at least as many with **25% fewer** evaluations.
2. **GROW adds:** `math_sci` (GROW on) certifies at least **+2** more than
   `math_sci_grow_off` on TRANSFER-2.
3. **No harm:** no arm worse than cold on any task.
4. **No loss elsewhere (GROW on):** deep >= 25/40 trained, science hard >=
   9/14 trained (`scripts/learning_judge.py`), first transfer suite math_sci
   >= 11/20 (`scripts/grow_judge.py --suite1`, secondary report only, not
   proof); LOFO total 5,883, worst 1.0x; all tests pass.

Decision: all met -> `NOMAD_ANCHOR2` and `NOMAD_SCALE` default **on**.
Otherwise both stay **off** by default and the result is recorded here as a
negative result. Nothing is re-tuned on a sealed suite.

## Sealed result (measured once, 2026-11-21, after `19722ec`)

TRANSFER-2 (`python3 scripts/grow_judge.py`, sha `d8de7508…f19b`, 35 hard):

| Arm | Certified /35 | Geometry /21 | Finance /14 | Evaluations | vs empty |
|---|---|---|---|---|---|
| cold | 0 | 0 | 0 | 343,470 | |
| empty (no memory) | 2 | 1 | 1 | 343,394 | |
| math only | 12 | 5 | 7 | 287,217 (-16.4%) | +10 |
| **math + science (GROW on)** | **30** | 17 | 13 | 214,873 (-37.4%) | **+28** |
| all 16 WORLD + science | 30 | 17 | 13 | 214,873 | +28 |
| math + science, GROW off (PORT only) | 22 | 10 | 12 | 247,124 (-28.0%) | +20 |
| math + science, PORT off | 2 | 1 | 1 | 343,394 | 0 |

| Criterion | Bar | Result | Met? |
|---|---|---|---|
| 1. math_sci vs empty | >= +3 or 25% fewer | **+28**, -37.4% | yes |
| 2. GROW adds (math_sci on vs off) | >= +2 | **+8** (30 vs 22), no GROW-off win lost | yes |
| 3. No arm worse than cold | 0 | 0 | yes |
| 4a. Deep (learning_judge, GROW on) | trained >= 25/40 | **27/40** (empty 25, PORT-off 25, practice 28), none worse than cold, none lost | yes |
| 4b. Science hard | trained >= 9/14 | **12/14** (empty 0, PORT-off 5), -11% evals vs before | yes |
| 4c. First transfer suite (secondary, design was shaped by its failures) | math_sci >= 11/20 | 19/20 (GROW off 11, empty 2) | yes |
| 4d. LOFO | 5,883, worst 1.0x | 5,883, 1.0x | yes |
| 4e. Tests | all pass | 389 pass | yes |

Decision: **GROW passes.** `NOMAD_ANCHOR2` and `NOMAD_SCALE` now default
**on**; `NOMAD_CONST` stays off.

What the 8 GROW wins on TRANSFER-2 are (all WITNESS-certified, final split
included):

- learned halving (`scale:div2`, the 2 learned from science's
  `div(add(v, u), 2)`): `g2_handshakes` `(cnt*cnt - cnt)/2`,
  `g2_triangular` `(cnt*cnt + cnt)/2`, `g2_tri_area_diff`, `g2_kite`,
  `g2_trap_plus_rect` `(2J*Lz + J(A+D))/2`;
- learned third (`scale:div3`): `g2_rect_pyramid` `min(F,E)*max(F,E)*G/3`;
- two-block anchor: `g2_ribbon` `4G + 2(E+F)`, `f2_wage_ot`
  `rate*hr + rate*ot + (rate*ot)/2`.

Deep: for the first time the trained field beats the empty field on the
sealed deep suite (27 vs 25): the probe now runs on 2-input tasks whose stage
1 finishes early, so PORT's renamed blocks reach them.

Honest caveats: a math-only field learns no scale (its memory holds no
constant >= 2), so GROW's halving/third come from science memory; still
unsolved on TRANSFER-2: `g2_box_minus_cube` (a cube), `g2_cuboid_edges_diff`
(4(E+F-2G)), `g2_hex_number`, `g2_square_pyr_number` (/6 of a cubic),
`f2_split_bill` (two nested divisions). Several certified programs are exact
on the stated input ranges rather than symbolic identities (e.g.
`(rate*ot)/2` is exact because `rate*ot*3/2` is an integer on every row).
