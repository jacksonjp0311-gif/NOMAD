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
