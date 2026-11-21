# MERGE: observationally equivalent bank blocks are one idea (pre-registered)

Switch: `NOMAD_MERGE` (default **off** until the sealed judge below passes). Code:
`nomad/world.py` (`merge_enabled`, `_probe_rows`, `probe_fingerprint`, `MergedBank`,
`_merge_bank`, `merge_ranked`, and in the PORT probe `vev`, `merge_extra`, `merge_settle`).
No transformers, no neural weights, no LLM; CPU-only and deterministic; WITNESS certifies
every program; the cold control is untouched.

## Why

Three ranking experiments (ROUTE, GRAPH, ROUTE_CUT) tied their scrambled controls. ROUTE_CUT's
best next step: make the portable bank's duplicates stop costing slots and evaluations. On the
1,000-task practice field the big memory scores lower than the small one (dev: practice 149 vs
math_sci 159 on the seven TRANSFER-1..4 dev suites).

**Measured before building (dev only).** The practice field's bank for a TRANSFER-3 task is 2,238
instances (1,972 distinct by behaviour) cut at `PORT_SCAN = 400`; 715 memory sources fall in 488
behaviour classes up to variable renaming. But for 31 dev tasks math_sci solves and practice does
not, the blocks math_sci's program uses are **inside** practice's 400-block cut (positions 30-275).
So the scan cut is not what loses them; the crowded downstream cuts are (`PORT_ANCHOR_N = 100`
anchors, `PORT_K` atoms) plus the evaluations spent on equivalent blocks. Merging the sources
(summed usage) or skipping equivalent instances in the scan changes main's bank order and lost
tasks on dev (sci_d_rest, t3_fuel_cost, t3_cost_per_head; merging the atom choice lost
`sci_water_mol` on two science dev suites). Those variants are not built.

## Design (frozen before the sealed suite)

- **Equivalence**: a block's probe fingerprint = its values on `MERGE_PROBES = 16` fixed synthetic
  rows per input signature (fixed int / string pools, seeded shuffle per input position; never a
  task's rows, never the final split). With the switch on, `port_bank` returns main's bank element
  for element (int goals only; not when ROUTE or ROUTE_CUT re-orders it), annotated with `dup_of`:
  index -> the earlier probe-equivalent block. Dev check: 24,842 duplicate pairs over three fields and
  nine dev suites, **0** differ on the public rows.
- **Skips** (main's search, cheaper): a duplicate's public values are copied from its class head
  (no evaluation); an anchor lookup `(target, op, block values)` that already missed is not repeated
  (same table, same residual: it cannot produce a candidate). Main's stages see the virtual count
  `vev()` = real evaluations + unspent skips, so they try exactly main's candidates and stop exactly
  where main stops.
- **Merged anchors** (`merge_extra`, after every one of main's int anchors, GROW anchors, scales and
  LET missed): the ranked bank merged by public values (one block per value class) is anchored on the
  goal and on each learned scale target; only blocks main's top-`PORT_ANCHOR_N` cut never reached are
  tried. Paid **only from the skips** (1 evaluation per lookup), WITNESS-gated, at most
  `MERGE_REJECTS = 4` rejections, skipped when the task's rejection cap could be reached.
- **Settle** (`merge_settle`): the skips the merged anchors did not spend are charged before the
  next stage, so every later stage (atoms, INVENT, the probe's levels, stage 1) starts at main's count
  and runs main's search. A task main certifies can therefore only change if a merged anchor is
  accepted first, or its rejections push the task's global WITNESS cap.
- Empty field: empty bank, nothing runs. Cold control: never reads a bank. String goals: untouched.
- **Judge-only control** `NOMAD_MERGE_CONTROL=rewired:<seed>`: every duplicate re-pointed to a random
  earlier block that is *not* probe-equivalent (same number of skips, wrong merges).

## Dev tuning (uncommitted dev suites only, `/workspace/nomad/merge_dev`)

Seven TRANSFER-1..4 dev suites (seeds 7 / 11 / 13, `graph_dev/dlist`), fields rebuilt on current
main; guards: science dev seeds 7 / 11 / 13 (all_sci and math_sci; each holds `sci_water_mol`),
TRANSFER-5 / -6 dev seed 7, SELFEDIT dev seeds 7 / 11, MEANING dev seeds 7 / 11 (meaning_judge
`--suite`, every arm byte-compared off / on).

| variant (dev) | practice off -> on | math_sci off -> on | losses |
|---|---|---|---|
| source merge (summed usage) + scan dedup + merged ranking | 149 -> 159 | 159 -> 162 | 2 (dev) + 3 (science dev, incl. sci_water_mol) |
| merged ranking only, atoms merged too | 149 -> 158 | 159 -> 162 | 2 + sci_water_mol |
| merged anchors after main, funded by skips (skips extend capped stages) | 149 -> 157 | 159 -> 163 | s5_court_margin (TRANSFER-5 dev: invent starved) |
| **chosen: + virtual count + settle** | **149 -> 153** | **159 -> 163** | **0** |

Chosen design, guards: science dev 38 = 38 (all_sci and math_sci, `sci_water_mol` kept on all
three seeds); TRANSFER-5/6 + SELFEDIT dev: math_sci 62 = 62, all_sci 62 = 62, practice 57 -> 60;
MEANING dev: every arm identical. `MERGE_REJECTS` 2 / 4 / 8 and `MERGE_PROBES` 8 / 16 give the same
totals. Scanning distinct blocks past the cut with the skips added nothing (dev 157 = 157) and is not
built (consistent with the needed blocks being inside the cut).

**Rewired control on dev** (seeds 0-2): practice 153 / 154 / 154, math_sci 163 / 163 / 162, science
dev 35 / 36 / 37 (vs merge 38); rewired lost 1 (practice), 1 (math_sci) and 6 (science dev) tasks
main certifies, MERGE lost 0. Stated before measuring: **the certified gain is not attributable to
correct equivalence** (wrong merges re-spend the same skips on the same extra anchors); what correct
equivalence buys is that the re-spending is loss-free. Criterion 2 is written for that claim.

Expectation, written before measuring: a small effect (+0 to +2 on a ~30-task sealed suite).

## Sealed suite

TRANSFER-8 (`nomad/transfer8.py`, `scripts/merge_suite.py`, seed **20270203**, unused by any
earlier suite): 52 formulas in three new domains (brewery, railway, laundry), input names disjoint
from every earlier catalogue and training task (grep over nomad/, scripts/, data/deep/, tests/);
cold control at 10,000 evaluations, max_size 7 splits easy / hard; lookup guard against every trained
arm's memory including the practice field. Generated and committed (cold only) with this document,
before any field arm runs on it.

Generated (`python3 scripts/merge_suite.py`, cold control only): `data/deep/transfer8_suite.json`,
sha256 `1d5cd94d8290a2a2595d969f8655e37aeaa5d876f457ee46e369abf2c08980ca`; 52 families, 26 easy,
**23 hard**, 3 lookup drops (r8_fence, r8_inner, l8_hem: memory already holds the formula).

## Pre-registered criteria (budget 10,000, every other switch at its default)

Arms (`scripts/merge_judge.py`): cold / empty / empty_merge; for each field F in {trained (math_sci),
practice}: F (MERGE off) / F_merge / F_rw0..2. Control part: `merge_judge.py --science` (science-hard
sealed suite, its trained field: trained / trained_merge / trained_rw0..2).

1. **Merge helps:** on at least one field F, F_merge certifies >= 1 more TRANSFER-8 hard task than F.
2. **Correct merges are what make it safe:** summed over TRANSFER-8 (both fields) and the science-hard
   suite, F_merge loses **0** tasks F certifies, while the three rewired controls together lose
   **>= 1**. (Rewired certified counts are reported; on dev they tie.)
3. **Empty gain 0:** empty_merge equals empty on every task (certified and evaluations).
4. **No TRANSFER-8 losses:** on neither field does F_merge lose a task F certifies; no new
   worse-than-cold task.
5. **Zero per-task certification losses on every existing frozen suite**, every arm, switch on vs
   off (`SWITCH=NOMAD_MERGE scripts/switch_regress.py run`, every judge except `merge`: learning (deep,
   science hard incl. sci_water_mol, LOFO), TRANSFER-1..4, secondary, TEXT, BRIDGE, INVENT_TEXT,
   TRANSFER-5, TRANSFER-6, SELFEDIT-2, TEXT_CHAIN, MEANING, INFLECT, LET, and TEXTPAT / ROLES where
   on main). Evaluation changes are reported, not judged.
6. **LOFO** (`--lofo`): MERGE-on total <= 5,883, worst ratio <= 1.0x; the full test suite passes.

All six pass: `NOMAD_MERGE` defaults to on in a separate commit. Otherwise it stays off, and the
code and the result are committed as they are.

### Addendum to criterion 5 (before any MERGE measurement)

COMBINE (8ae25e1) and CEIL (c7cc8d0) were pre-registered by other steps while this one was being
written; their owners have not run their single sealed measurements, so their judges are **not**
run here (running them off / on would measure their sealed suites first). Criterion 5 covers every
other judge in `scripts/switch_regress.py` except `merge` itself: learning, transfer1-4, secondary4,
text, bridge, text_invent, route5, transfer6, selfedit2, text_chain, meaning, inflect, let, textpat,
roles. Measured from a snapshot of `81063e0`.

## Sealed result, part 1 (measured once from a snapshot of 81063e0; regressions pending)

TRANSFER-8 (sha 1d5cd94d, 23 hard; `results/merge/transfer8_sealed.json`):

| arm | certified | evaluations |
|---|---|---|
| cold | 0 | 230,000 |
| empty / empty_merge | 6 / 6 (identical per task) | 201,430 / 201,430 |
| trained (math_sci) off / merge | 14 / 14 | 171,182 / 170,252 |
| trained rewired 0 / 1 / 2 | 14 / 14 / 14 | 170,339 / 170,354 / 170,329 |
| practice off / merge | 14 / 14 | 172,254 / 171,501 |
| practice rewired 0 / 1 / 2 | 14 / 14 / 14 | 171,698 / 171,686 / 172,476 |

Science hard (`results/merge/science_hard.json`): trained 12, trained_merge 12 (0 lost); rewired 11 / 11 / 11
(each loses `sci_water_mol`). LOFO (`results/merge/lofo.json`): 5,883 / 5,883, worst 1.0x.

- Criterion 1 **FAIL** (merge = off on both fields, 14 = 14; the dev gain of +4 did not transfer).
- Criterion 2 pass (merge loses 0; the rewired controls lose 3 in total).
- Criterion 3 pass, criterion 4 pass, criterion 6 LOFO pass.
- Criterion 5: running (adds COMBINE and CEIL, now measured by their owners, as extra judges).

`NOMAD_MERGE` stays **off** whatever criterion 5 shows.

## Sealed result, part 2: existing suites (criterion 5)

`SWITCH=NOMAD_MERGE scripts/switch_regress.py` from the 81063e0 snapshot over 20 judges (learning, transfer1-4,
secondary4, text, bridge, text_invent, route5, transfer6, selfedit2, text_chain, meaning, inflect, let, textpat,
roles, plus COMBINE and CEIL, now measured by their owners): **0 per-task losses** on every judge, counting
both certification losses and evaluation increases; 794 per-task records with fewer evaluations; certified
totals unchanged (`results/merge/regress_compare.json`). Criterion 5 passes.

**Verdict: FAIL** (criterion 1 only). MERGE is safe (zero losses everywhere, LOFO unchanged) but adds no
certified task on the sealed suite, so `NOMAD_MERGE` stays **off**. Its skip machinery is reused by LET2
(docs/LET2.md).
