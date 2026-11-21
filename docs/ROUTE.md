# ROUTE: a learned routing table over the portable bank (pre-registered)

Phase 5 toward general intelligence: replace PORT's fixed bank order with
evidence. Off switch `NOMAD_ROUTE` (default **off** until the sealed judge
below passes). No transformers, no neural weights, no LLM.

## What it replaces

`port_bank` (docs/PORT.md) collects learned blocks and whole certified
programs from any input signature, renames them onto the task's inputs and
orders them by **raw usage count** before the `PORT_SCAN = 400` cut; the
probe then ranks the evaluated blocks by the fixed `block_score` (rows equal,
fewest distinct offsets, row-order agreement) and cuts again: the first
`PORT_ANCHOR_N = 100` anchor, the best `PORT_K = 24` foreign blocks become
atoms, the best `ANCHOR2_M = 40` pair. Ties inside `block_score` are broken
by the block's hash name. Nothing in that order ever learns.

**Measured before building (dev only):** in every field the judges train
(math, math_sci, all_sci, lang) and in the live body's
`data/continuous/world_prior.json`, the bank for a TRANSFER-4 task has at most
129 entries (live: at most 57). The `PORT_SCAN` cut never bites today, so
"popularity truncation drops a far-domain fitting block unseen" is not an
active failure yet; the cuts that do bite are the atom (`PORT_K`) and
two-block (`ANCHOR2_M`) cuts and the order in which budget-capped anchors are
tried. ROUTE acts on all of them, and on the scan order for when the bank
grows past 400.

## Mechanism (`nomad/world.py`)

1. **Provenance.** Every library block and whole program remembers the SENSE
   key of the task whose certified solution put it in memory
   (`library_src`, `programs_src`). SENSE key = I/O feature kind + output
   shape, domain-free (`polynomial/growth`, `quotient/bounded`,
   `aggregation/n/a`, ...), so a science and a mathematics task of the same
   shape share evidence.
2. **Routing table** `route[task_key][group] = [s, f]`, a group being memory
   kind x source key (`prog:polynomial/growth`, `lib:quotient/bounded`, ...).
   Updated **only in `add_witnessed`**, i.e. only from a verified WITNESS
   receipt (the same gate as every other count; in the live body that is
   sleep / consolidation): for the certified tree, every group that has a
   block occurring in it (up to variable renaming) gets s += 1, every other
   known group f += 1. Decays with the genome decay like the operator counts.
   Persisted in the prior snapshot (old snapshots load with an empty table).
   Learning is always on; only reading is switched.
3. **Reading (NOMAD_ROUTE on).** Relevance r = (s + 1) / (s + f + 2) for the
   task's own SENSE key. If the table has no evidence for that key (an empty
   field, a new kind of task) nothing changes: the search is exactly main's
   (tested). Otherwise: (a) bank sources are scanned in relevance order
   (usage breaks ties) before the `PORT_SCAN` cut; (b) the ranked bank is
   ordered by `block_score`, then r, then name (`ROUTE_MODE = "tie"`); (c)
   the `PORT_K` foreign atoms are chosen by rows-equal, then r, then the rest
   of the score (`ROUTE_ATOMS`); (d) the two-block anchor's top list breaks
   ties by r. The cold control never reads the table; stage 1 is untouched.

Callers pass `sense_key=task_route_key(task)`: `scripts/variation_probe.py`,
`scripts/science_probe.py`, `nomad/evolve.py`, `nomad/consolidate.py` (live
sleep, key from the family's training task).

## Dev results (uncommitted suites under /workspace/nomad/route_dev only)

Dev suites: TRANSFER-2 catalogue seeds 7 / 11, TRANSFER-1 seeds 7 / 11 / 13,
TRANSFER-4 seed 7, TRANSFER-3 seed 7 (math_sci field); regression dev: deep
seeds 7 / 11, science seeds 7 / 11 / 13 (all_sci), text seeds 7 / 11 (lang).

| variant | dev certified (7 suites) | losses |
|---|---|---|
| ROUTE off | 159 | - |
| tie (r breaks block_score ties) | 161 | 0 |
| eqr (r before offsets/order) | 161 | 4 |
| mult ((eq+1) x r) | 161 | 4 |
| **tie + routed atoms (chosen)** | **162** | **0** |
| block-grain table (per block, not per group) | 160 | 1 |

Regression dev: identical certified counts on all 7 deep / science / text dev
suites (0 changed tasks). LOFO with ROUTE on: 5,883, worst 1.0x (unchanged).

**Control that changed the protocol.** The same field with each routing
table's counts shuffled among its groups (seeds 0-3) scored 161 / 159 / 163
/ 163 on the same dev suites, mean 161.5 vs 162 for the learned table. On dev
the gain is therefore re-sorting (a different tie order lands a fitting block
inside a capped anchor or atom set), **not** the learned evidence. The
"gain vanishes with an empty field" test cannot catch this here, because an
empty field has no table and so is identical by construction. So the sealed
judge adds a permuted-table criterion (4 below). Expectation, written before
measuring: criterion 4 is likely to fail.

## Sealed suite

TRANSFER-5 (`nomad/transfer5.py`, `scripts/route_suite.py`, seed 20261127):
49 formulas in three new domains (sport / tournaments, transit / parking,
venue / stage) with input names disjoint from every earlier catalogue and
training task; cold control at 10,000 evaluations, max_size 7 splits easy /
hard; lookup guard against every trained arm's memory. Generated and
committed (cold only) after this document, before any field arm runs on it.

## Pre-registered criteria (budget 10,000, every other switch at its default)

Arms (`scripts/route_judge.py`): cold / empty / empty_route / trained
(math_sci, ROUTE off) / trained_route / trained_route_perm0..2 (table counts
shuffled among groups, seeds 0-2); report only: math_route.

1. **ROUTE beats off on TRANSFER-5:** trained_route certifies >= 1 more
   hard task than trained, and loses none trained certifies.
2. **Gain vanishes with an empty field:** empty_route equals empty on every
   task (certified and evaluations).
3. **No new worse-than-cold task:** no task where trained_route is worse than
   cold (lost or more evaluations) unless trained already is.
4. **The gain needs the learned table:** trained_route certified minus the
   mean of the three permuted-table arms >= 1.
5. **Zero per-task losses on every existing frozen suite** (deep, science
   hard, TRANSFER-1, -2, -3, -4, TEXT; `--secondary`): trained_route certifies
   every task trained certifies, and at least as many.
6. **LOFO** (`--lofo`): trained_route total <= 5,883 and worst ratio <= 1.0x.

All six pass: `NOMAD_ROUTE` defaults to on in a separate commit. Otherwise it
stays off, and the code and the result are committed here as they are.

## Sealed result (2026-11-21): FAIL. `NOMAD_ROUTE` stays **off**

TRANSFER-5 sha256 `1db6039e7c4a495c6bb3cb9a28ca62cd0d955d19e213c5a5d16af866a8d86df4`,
33 hard tasks (16 easy). Raw output: `results/route/`.

| TRANSFER-5 arm | certified / 33 | evaluations |
|---|---|---|
| cold | 0 | 310,581 |
| empty | 8 | 272,791 |
| empty_route | 8 | 272,791 |
| trained (ROUTE off) | 26 | 206,361 |
| trained_route | 26 | 206,385 |
| trained_route_perm0 / 1 / 2 | 26 / 26 / 26 | 206,357 / 206,377 / 206,313 |
| math_route (report only) | 16 | 229,742 |

Existing frozen suites (trained ROUTE off -> on; empty, cold): deep 27 -> 27
of 40 (25, 0); science hard 12 -> **11** of 14 (0, 0), **lost
sci_water_mol** (certified by trained at 9,890 of 10,000 evaluations; the
re-ordered anchors push it over budget); TRANSFER-1 19 -> 19 of 20 (2, 0);
TRANSFER-2 32 -> 32 of 35 (2, 0); TRANSFER-3 27 -> 27 of 40 (1, 0);
TRANSFER-4 18 -> 18 of 35 (2, 0); TEXT 3 -> 3 of 24 (0, 0). The ROUTE-off
arms reproduce every earlier baseline exactly (the bookkeeping changes no
decision). LOFO: 5,883 with ROUTE on and off, worst 1.0x.

| criterion | result |
|---|---|
| 1 ROUTE beats off (>= +1, no loss) | **fail** (+0) |
| 2 gain vanishes with an empty field | pass (identical by construction) |
| 3 no new worse-than-cold task | pass |
| 4 gain needs the learned table (vs permuted mean) | **fail** (0.0) |
| 5 zero per-task losses on frozen suites | **fail** (science hard: sci_water_mol) |
| 6 LOFO <= 5,883, worst <= 1.0x | pass |

**What this says.** A coarse routing prior (task shape x source shape)
carries no information the fixed `block_score` does not already have: on
sealed data the learned and three shuffled tables give the same 26, and on
dev the learned table (162) is inside the shuffled spread (159-163). The
small dev wins were tie-order luck, and the sealed loss is the same luck the
other way. Two structural reasons: (1) the judge fields are tiny (math_sci:
14 library blocks, 22 programs; banks <= 129, so `PORT_SCAN` never cuts and
there is little to route between), and (2) a group-level prior can only
re-order blocks that already tie on the goal-match score, while what decides
a hit is the specific block's fit to this goal. The table, its persistence
and the off switch stay in the code (learning is cheap and always on), so a
later, finer interconnect (docs/INTERCONNECT.md) can use the evidence; the
permuted-table control is now part of the protocol for any learned routing.
