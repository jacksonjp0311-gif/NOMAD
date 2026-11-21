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
