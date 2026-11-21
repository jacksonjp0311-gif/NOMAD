# TRANSFER: cross-domain transfer test (pre-registered)

Phase 2 toward general intelligence: **prove transfer.** Phase 1 (PORT,
`3d053ca`, docs/PORT.md) showed memory counts *within* a domain: trained on
easy science, the field certifies 9 of 14 sealed hard science tasks, an empty
field 0. The question here is whether what the field learns in mathematics
(and science) helps in a domain it has **never trained on**, and whether more
training domains give more transfer.

## The transfer domain (chosen from evidence)

`nomad/transfer.py`: integer **geometry** (rectangles, boxes, triangles,
trapezoids, polygons) and **finance** (simple interest, prices with
percentages, profit). Why these and not strings / lists:

- The field's learned memory is int-typed (8 WORLD math families, 14 easy
  science families); the WORLD string and list families are 4 each and
  their held-out probes already exist. An int domain with *different
  quantities, input names and arities* tests whether structure (products,
  halves, sums of products, percent-of) carries over, which is the honest
  "structure transfers" question; a string domain would test mostly the DSL.
- Exact checkable truth exists (Fraction ground truth, integer-only rows),
  no DSL / interpreter / WITNESS change, the same `int` opset and constants
  0-3. Stated constants (100 for percent, 180 degrees) are constant input
  columns, like science's 60 s/min.
- Input names (`L W H`, `B T Z`, `n q`, `P r Y C`, `S K N X`) are disjoint
  from every training signature, so no learned block applies under its own
  names: reuse must come through renaming (PORT) or composition.

Catalogue: 34 families, fixed before any field arm was measured on them
(21 geometry, 13 finance; formulas in `nomad/transfer.py`). Transfer tasks
carry no domain tag: SENSE classifies them by features, as a genuinely new
domain would arrive.

## The sealed suite (`scripts/transfer_suite.py`, seed 20261122)

`data/deep/transfer_suite.json`, sha256
`f27adf3cbe3dbec76b7904c5311de6cc46e453ba1426706281f895e0104e872c`
(`data/deep/transfer_suite.sha256`). 5 public / 3 challenge / 3 final rows
(final never read by search).

1. Cold control at 10,000 evaluations, max_size 7: certified -> `easy`
   (14 families; recorded, **never trained on, never scored**); not
   certified -> candidate `hard`.
2. **Lookup guard** (transfer must be more than retrieval): a candidate is
   dropped if any whole program or library block remembered by any trained
   arm, instantiated over the task's inputs by every type-preserving
   renaming, certifies it outright; or if an easy transfer family's
   reference tree does. Dropped: none.
3. Sealed `hard`: **20 tasks** (13 geometry, 7 finance): `geo_box_lateral`
   2H(L+W), `geo_box_surface` 2(LW+LH+WH), `geo_open_box` LW+2H(L+W),
   `geo_box_edges` 4(L+W+H), `geo_diag2` L²+W², `geo_diag3` L²+W²+H²,
   `geo_frame` (L+2H)(W+2H)-LW, `geo_square_pyramid` L²H/3,
   `geo_trap_area` (B+T)Z/2, `geo_tri_prism` BZT/2, `geo_trap_diff`
   (B-T)Z/2, `geo_diagonals` n(n-3)/2, `geo_tri_count` (n-2)+n(n-3)/2,
   `geo_ext_angle` 360/n, `fin_simple_interest` PrY/100, `fin_amount`
   P+PrY/100, `fin_discounted` P-Pr/100, `fin_taxed` P+Pr/100,
   `fin_installment` (P+PrY/100)/Y, `fin_net_profit` (S-K)N-X.
   Every one is cold-unsolvable at 10k (`geo_ext_angle`: cold stops at 918
   evaluations on a public-row fit that fails the withheld rows).

The suite is not modified after measuring. The deep suite (`da3ae9bf…6fbd`)
and the science suite (`4517167f…868d`) are not modified.

## Arms (`python3 scripts/transfer_judge.py`, budget 10,000, max_size 7)

- `cold`: the twin control (`prior=None`), untouched.
- `empty`: `WorldPrior()`, every search feature on (case split, SENSE,
  WITNESS_CONTINUE, block probe, PORT); no memory.
- `math`: trained only on the 8 WORLD mathematics families
  (`variation_probe.train`, 2 rounds).
- `math_sci`: `math` + the 14 easy science families
  (`science_probe.train_more`, the PORT judge's science curriculum).
- `all_sci` (report): all 16 WORLD families (math, language, coding) + easy
  science = the `trained` arm of `scripts/learning_judge.py`.
- `math_sci_port_off` (report): `math_sci` with `NOMAD_PORT=off`.

No arm trains on any transfer family, easy or hard.

## Pre-registered criteria (written and committed before any arm is measured on the suite)

1. **Transfer (primary, `math_sci`):** `math_sci` certifies at least **3
   more** sealed transfer tasks than `empty`, or at least as many with at
   least **25% fewer** evaluations.
2. **Math-only transfer (reported separately, same bar):** `math` vs `empty`.
3. **No harm:** no arm worse than cold on any task (cold certifies none, so
   this means no arm is broken), and no field arm certifies fewer than
   `empty` (reported).
4. **More domains = more transfer?** `math_sci - math` (and `all_sci`)
   reported; a positive difference is the "yes".
5. Unchanged: deep and science suites and the cold control untouched; LOFO
   total 5,883, worst 1.0x; all tests pass.

Decision: criterion 1 and 3 met -> **transfer passes**. Otherwise **fails**,
and the cause is investigated on uncommitted dev transfer suites only (other
seeds of `scripts/transfer_suite.py`, plus new dev-only formulas); at most a
couple of principled fixes, each behind an off switch, kept only if it passes
on dev first, then confirmed once on the sealed suite. Results are recorded
below whether positive or negative; nothing is re-tuned on the sealed suite.

## Sealed result (measured once, 2026-11-21, `python3 scripts/transfer_judge.py`, after `5d729d2`)

Correction to the prose above, not to the suite: the sealed section has
**14 geometry + 6 finance** tasks (the list above is right; "13 / 7" was a
miscount). The suite file and sha are exactly as committed in `5d729d2`.

| Arm | Certified /20 | Geometry /14 | Finance /6 | Evaluations | vs empty |
|---|---|---|---|---|---|
| cold | 0 | 0 | 0 | 190,918 | |
| empty (no memory) | 2 | 2 | 0 | 188,241 | |
| math only | **7** | 2 | 5 | 162,028 (-13.9%) | **+5** |
| math + science | **11** | 5 | 6 | 147,457 (-21.7%) | **+9** |
| all 16 WORLD + science (report) | 11 | 5 | 6 | 147,457 | +9 |
| math + science, PORT off (report) | 2 | 2 | 0 | 188,241 | 0 |

| Criterion | Bar | Result | Met? |
|---|---|---|---|
| 1. Transfer, math+science vs empty | >= +3 | **+9** (11 vs 2) | yes |
| 2. Transfer, math only vs empty (reported, same bar) | >= +3 | **+5** (7 vs 2) | yes |
| 3. No arm worse than cold | 0 tasks | 0 | yes |
| 3b. No field arm below empty (count) | | math 7, math_sci 11 >= 2 | yes (one per-task loss, below) |
| 4. More domains = more transfer? | > 0 | math_sci - math = **+4**; all_sci adds 0 over math_sci | yes |
| 5. Suites, cold, LOFO, tests | 5,883, 1.0x | 5,883, 1.0x; deep / science / cold untouched | yes |

Decision: **transfer passes.** No fix was needed or tried.

Where it comes from: every one of the 9 extra certifications is
`port:anchor` or `port:probe`; with PORT off the trained field scores exactly
the empty field (2, identical evaluations). So the transfer is carried by
renamed learned memory, not by search. Examples (certified programs):

- math only -> finance: `fin_amount` `(P/C)*(C + r*Y)`, `fin_simple_interest`,
  `fin_discounted`, `fin_taxed`, `fin_installment` `P/Y + r*(P/C)`. The bank
  pieces in these programs are small renamed math programs: `div(P, C)`,
  `div(P, Y)` (the WORLD `div_pair` program `x // y` renamed), `max(C, P)`,
  `min(r, P)`.
- math + science -> geometry and finance: the bank adds larger renamed science
  blocks: `mul(sub(S, K), N)` and `mul(sub(B, T), Z)` (a difference times a
  quantity, as in impulse `m*(v-u)`), `mul(L, mul(L, H))` (a square times a
  quantity), `mul(r, div(P, C))`, `add(C, mul(r, Y))`. They give
  `fin_net_profit` `(S-K)*N - X`, `geo_trap_diff` `(B-T)*Z/2`,
  `geo_square_pyramid` `L*L*H/3`, `geo_box_lateral` `2WH + 2LH`.
- Language / coding training adds nothing (all_sci = math_sci): their blocks
  are str / list typed and cannot be renamed onto int inputs.

Per-task loss: `geo_square_pyramid` is certified by empty (6,940, SENSE lead
`mul`) and by math+science (6,573), but not by math-only (bank work pushes it
past the budget), the same kind of loss as `sci_d_uvt` under PORT.

Honest caveats:

- WITNESS certifies programs that are exact on the domain the rows come from,
  not symbolic identities: `fin_discounted` was certified as
  `max(C, P) - r*(P/C)` (P >= 100 = C on every row of that range) and
  `fin_simple_interest` (math-only) as `min(r, P)*(Y*(P/C))` (r <= 20 < P).
  Both are correct on every row of the stated ranges, final rows included.
- The transfer is of small blocks (products, halves, percent-of, a difference
  times a quantity). The 9 unsolved tasks need sums of three products
  (`geo_box_surface`, `geo_diag3`, `geo_open_box`, `geo_frame`), the constant
  4 (`geo_box_edges`), or a halving placed after a product that a learned
  "half of a sum" block cannot provide under integer division
  (`geo_trap_area`, `geo_tri_prism`, `geo_diagonals`, `geo_tri_count`).
- Dev replication (uncommitted, other row seeds of the same 34 formulas,
  measured *after* the sealed run, no tuning): seed 7: empty 3, math 7,
  math+science 9; seed 11: 3 / 7 / 11; seed 13: 1 / 7 / 10. Pass on all
  three, math+science > math on all three.
