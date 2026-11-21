# ROUTE_CUT: learned relevance fills the tail of the PORT_SCAN cut

Switch: `NOMAD_ROUTE_CUT` (default **off**). Code: `nomad/world.py`
(`route_cut_enabled`, `CUT_HEAD`, `CUT_MIN_REL`, `_port_instances`, `port_bank(..., cut_key)`).

## Why

GRAPH (docs/GRAPH.md) failed, but its dev work found the memory-size effect:
on the 1,000-task practice field the portable bank overflows `PORT_SCAN = 400`
on every task (on the math_sci field it never does), and the big memory scores
lower (149 vs 159 on the dev suites). Ordering the *whole* bank by ROUTE's
learned relevance (docs/ROUTE.md) gave 154 vs off 149 vs shuffled 148/149/138
there, but lost 7 tasks off certifies. ROUTE_CUT keeps the learned evidence
and protects main's order.

## Design (frozen before the sealed suite)

- Only when the bank built in main's usage order would exceed `PORT_SCAN`
  (a bank within the cut is main's bank exactly, element for element).
- The first `CUT_HEAD = 350` instances are main's (usage order, unchanged).
- The remaining `PORT_SCAN - CUT_HEAD = 50` slots go to sources whose learned
  ROUTE relevance for the task's SENSE key is above `CUT_MIN_REL = 0.5` (the
  uniform Beta(1,1) prior mean: groups with net positive evidence), in
  relevance order, usage breaking ties; slots they leave are filled by main's
  usage order.
- Nothing else changes: same scan cost (1 evaluation per bank block, at most
  `PORT_SCAN`), same downstream ranking, anchors, GROW, INVENT, WITNESS.
- Needs ROUTE evidence for the key; no evidence (empty field, unknown key) =
  main. Inactive when `NOMAD_ROUTE` itself is on. The ROUTE table is learned
  only from WITNESS-certified receipts (unchanged, docs/ROUTE.md).

## Dev tuning (uncommitted dev suites only)

Seven uncommitted dev suites of the TRANSFER-1/2/3/4 catalogues (seeds 7,
11, 13), practice field (math_sci + 1 round on the 1,000 practice tasks) and
math_sci field; arms off / on / three shuffled ROUTE tables (shuffled within
each SENSE key, `route_judge.permuted`, seeds 0-2). Certified totals:

| variant | off | on | shuffled 0/1/2 | tasks lost |
|---|---|---|---|---|
| CUT_HEAD 200 | 149 | 154 | 152 / 154 / 151 | 2 |
| CUT_HEAD 250 | 149 | 155 | 150 / 154 / 149 | 2 |
| CUT_HEAD 300 | 149 | 155 | 152 / 153 / 153 | 1 |
| CUT_HEAD 325 | 149 | 154 | 149 / 152 / 153 | 1 |
| CUT_HEAD 350 | 149 | 151 | 148 / 149 / 150 | 0 |
| CUT_HEAD 300, MIN_REL 0.5 | 149 | 154 | 149 / 150 / 151 | 1 |
| CUT_HEAD 300, MIN_REL 0.7 | 149 | 151 | 149 / 150 / 149 | 0 |
| **CUT_HEAD 350, MIN_REL 0.5 (chosen)** | 149 | **151** | **146 / 148 / 149** | **0** |
| extend: 400 of main + 100 learned | 149 | 147 | 149 / 148 / 149 | 4 |
| extend: 400 of main + 200 learned | 149 | 151 | 151 / 150 / 149 | 5 |
| math_sci field (bank never overflows) | 159 | 159 (0 evaluation difference) | - | 0 |

The single recurring loss at smaller heads (g2_kite) is not a budget loss:
a learned-tail block yields a public-row fit WITNESS accepts that then fails
the final split; the final split is never read by search, so no fallback
pass can detect it. A second pass (re-run with main's bank on leftover
budget) was therefore not built; the protection is the 350-instance head.
Part of the smaller-head gain is plain tail diversity (shuffled tables also
beat off there); the chosen setting is the one where learned beats every
shuffled table with no loss.

Expectation, written before measuring: a small effect (dev +2 of 149, +2..+5
over shuffled), so a sealed pass is far from certain.

## Sealed suite

TRANSFER-7 (`nomad/transfer7.py`, `scripts/route_cut_suite.py`, seed
20261213, unused by any earlier suite): 51 formulas in three new domains
(clinic / pharmacy, print shop / bindery, harbour / port), input names
disjoint from every earlier catalogue and training task (checked by grep
over nomad/, scripts/, data/, tests/); cold control at 10,000 evaluations,
max_size 7 splits easy / hard; lookup guard against every trained arm's
memory including the practice field. Generated and committed (cold only)
after this document, before any field arm runs on it.

## Pre-registered criteria (budget 10,000, every other switch at its default)

Arms (`scripts/route_cut_judge.py`): cold / empty / empty_cut; for each
field F in {trained (math_sci), practice}: F (ROUTE_CUT off) / F_cut /
F_cut_sh0..2 (shuffled ROUTE tables).

1. **Cut beats off:** on at least one field F, F_cut certifies >= 1 more
   TRANSFER-7 hard task than F.
2. **Cut beats every shuffled table:** on that same field, F_cut certifies
   >= 1 more than each of F_cut_sh0, sh1, sh2.
3. **Empty gain 0:** empty_cut equals empty on every task (certified and
   evaluations).
4. **No losses on TRANSFER-7:** on neither field does F_cut lose a task F
   certifies; no new worse-than-cold task.
5. **Zero per-task losses on every existing frozen suite**, every arm, switch
   on vs off (`SWITCH=NOMAD_ROUTE_CUT scripts/switch_regress.py`; loss =
   certified off but not on): learning (deep, science hard incl.
   sci_water_mol, LOFO), TRANSFER-1..4, secondary, TEXT (lang 17, all_sci 20
   on current main), BRIDGE (trained 15), INVENT_TEXT (15), TRANSFER-5 (26),
   TRANSFER-6 (23), SELFEDIT-2 (14), TEXT_CHAIN (22). Evaluation changes are
   reported, not judged (the switch only acts when a bank overflows, which on
   these suites happens only on practice-field arms).
6. **LOFO** (`--lofo` and the learning judge): ROUTE_CUT-on totals <= 5,883,
   worst ratio <= 1.0x.

All six pass: `NOMAD_ROUTE_CUT` defaults to on in a separate commit.
Otherwise it stays off, and the code and the result are committed as they are.

Not measured here: MEANING's sealed suite (59f6add), whose owner has not yet
run its single sealed measurement.

Generated (`python3 scripts/route_cut_suite.py`, cold control only):
`data/deep/transfer7_suite.json`, sha256
`f8906d60f56e03dcc1205ec1e73aa1fe8ece00dbce548d258b4b8816233ae175`; 51
families, 19 easy, **31 hard**, 1 lookup drop (p7_waste: memory already
holds `mod(sub(ups, lfs), ups)`).

### Addendum to criterion 5 (before any MEANING measurement with ROUTE_CUT)

MEANING was measured by its owner (sealed PASS 7e299b3, default ON ceb4b7b)
after this document was written, so its sealed suite joins criterion 5:
`meaning` in `scripts/switch_regress.py` (trained_on 19 of 19 on current
main), zero per-task losses on every arm, switch on vs off. This only adds a
suite; nothing else in the criteria changes. All ROUTE_CUT judges run with
MEANING at its default (on).

## Sealed result, primary (TRANSFER-7, sha256 f8906d60...e175, 31 hard): criteria 1-2 FAIL

Measured once, 2026-11-21, with every other switch at its current default
(TEXT_CHAIN, MEANING on); raw output `results/route_cut/route_cut_sealed_primary_20261121.json`.

| arm | certified / 31 | evaluations |
|---|---|---|
| cold | 0 | 310,000 |
| empty | 7 | 276,936 |
| empty_cut | 7 | 276,936 |
| trained (math_sci, ROUTE_CUT off) | 15 | 240,200 |
| trained_cut / sh0 / sh1 / sh2 | 15 / 15 / 15 / 15 | 240,200 each (the bank never overflows: identical) |
| practice (ROUTE_CUT off) | 19 | 238,254 |
| practice_cut | 19 | 235,581 (-1.1%) |
| practice_cut_sh0 / sh1 / sh2 | 19 / 19 / 19 | 238,359 / 238,036 / 238,178 |

By domain: trained clinic 5/9, print 6/12, harbour 4/10; practice 6/9, 7/12,
6/10 (identical for off, cut and every shuffled table). No task lost on
either field; nothing worse than cold; empty_cut identical to empty.
Criteria 3 and 4 pass; 1 and 2 fail (19 = 19 = 19/19/19).
The secondary regression and LOFO follow below.

## Sealed result, regression and LOFO: criterion 5 FAIL, criterion 6 pass

`SWITCH=NOMAD_ROUTE_CUT scripts/switch_regress.py` (each judge with the
switch off and on, every arm); raw output in `results/route_cut/regress/`,
comparison in `results/route_cut/regress_compare_20261121.json`.

| suite | certified records off -> on | lost certification (task, arm) |
|---|---|---|
| learning (deep, science hard) | 94 -> 93 | **sci_water_mol, trained** |
| secondary (invent2 --secondary) | 275 -> 273 | **sci_water_mol, trained and trained_invent** |
| MEANING | 158 -> 161 | **ms_nurse_weeks (trained_off, shuffled_1, shuffled_3); ms_cake_split2 (words_only_on)**; trained_on 19 unchanged |
| TRANSFER-6 | 242 -> 247 | none (w6_floor_tiles gained on every practice arm) |
| TRANSFER-1..5, TEXT, BRIDGE, INVENT_TEXT, SELFEDIT-2, TEXT_CHAIN | unchanged (50, 107, 58, 61, 162, 56, 60, 51, 44, 89) | none, no evaluation changes |

The switch acts wherever a field's bank overflows PORT_SCAN: besides the
practice field, that is the science-hard field (math + science easy) and
the MEANING fields, which the dev tuning never saw. There it costs
sci_water_mol (the task ROUTE also lost, docs/ROUTE.md) and four MEANING arm
records, while gaining others (MEANING 7 records, TRANSFER-6 5).

LOFO (`route_cut_judge.py --lofo`): cold 5,883, trained 5,883, trained_cut
5,883; worst ratio 1.0x for both (also 5,883 / 1.0x in the learning judge).

## Verdict: FAIL (criteria 1, 2 and 5)

| criterion | result |
|---|---|
| 1. cut beats off | **FAIL**: practice 19 = 19, trained 15 = 15 |
| 2. cut beats every shuffled table | **FAIL**: 19 = 19 / 19 / 19 |
| 3. empty gain 0 | pass (7 = 7, identical evaluations) |
| 4. no TRANSFER-7 losses | pass |
| 5. zero losses on existing suites | **FAIL**: sci_water_mol (science hard, 3 arm records), MEANING 4 arm records |
| 6. LOFO | pass: 5,883, worst 1.0x |

`NOMAD_ROUTE_CUT` stays **off**; the code stays behind the switch.

**Reading.** At large memory, which 50 blocks fill the tail of the cut
matters (dev: any tail change moved 2-6 tasks, and on TRANSFER-6 / MEANING
it moves records both ways), but the learned ROUTE relevance is no better a
chooser than a shuffled table on a new catalogue (19 = 19/19/19), and it is
not loss-free. Three experiments (ROUTE, GRAPH, ROUTE_CUT) now agree that
the SENSE-key-level relevance learned so far does not carry to new domains.

**Most promising next step.** Stop re-ordering the cut and make the cut
unnecessary: deduplicate the portable bank by behaviour (blocks whose public
values coincide on this task's rows are one scan, so 400 evaluations cover
more distinct blocks), or let the practice-scale memory consolidate (merge
equivalent library blocks in sleep) so the bank fits within PORT_SCAN; both
are measurable on the same practice field against the 149 -> 159 memory-size
gap, with sci_water_mol and MEANING in the dev guard from the start.
