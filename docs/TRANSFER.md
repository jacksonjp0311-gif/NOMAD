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

## Sealed result

(Recorded after the single sealed measurement.)
