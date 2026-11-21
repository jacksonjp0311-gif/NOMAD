# GRAPH: a co-occurrence graph with spreading activation proposes two-block pairs (pre-registered)

Option B of docs/INTERCONNECT.md, approved by the owner. Off switch
`NOMAD_GRAPH` (default **off** until the sealed judge below passes). No
transformers, no neural weights, no LLM.

## Mechanism (`nomad/world.py`)

1. **Graph, learned only from verified receipts.** `add_witnessed` (the
   same gate as every count; in the live body: consolidation in sleep) adds,
   for each certified program, one count to every node it contains and one to
   every pair of nodes that co-occur in it. A node is a certified sub-program
   of size >= 3 up to variable renaming (`graph_key`, the ROUTE
   canonicalisation), so a bank block and its source are the same node.
   `GRAPH_NESTED = True`: a block and a sub-program of it also co-occur
   (with disjoint pairs only, the judge fields have no edges at all: their
   certified programs are too small to hold two disjoint size-3 blocks).
   Decays with the genome decay; counts below 0.01 are pruned. Persisted in
   the prior snapshot (old snapshots load with an empty graph). Learning is
   always on; only reading is switched.
2. **Seeded per task by goal match.** For each int bank block (one per
   distinct value, as in the two-block anchor), seed = scalar `block_score`
   against the current target (rows equal / n, order agreement, 1 / distinct
   offsets, averaged). Node activation = best seed of its instances +
   `GRAPH_SPREAD` (0.5) x the edge-weighted seeds of its neighbours (edge
   weight: co-occurrence Jaccard).
3. **Spreading activation proposes pairs only.** Candidate pairs are bank
   instances (best `GRAPH_PER_NODE` = 4 per node) whose nodes share a learned
   edge, scored by the goal match of the pair's sum x (1 + edge weight) x
   their activation (`GRAPH_SCORE = "fit"`); the best `GRAPH_PAIRS` = 64 are
   tried **ahead of** GROW's existing two-block loop, inside the same
   `GROW_CAP` / `GROW_REJECTS`, with the same accounting (1 evaluation per
   lookup, WITNESS-gated fit). Then the existing loop runs unchanged,
   skipping only pairs (by value) already tried. Only learned edges propose:
   an empty field proposes nothing, the cold control never reads the graph,
   stage 1 is untouched.

`GRAPH_EDGES_ONLY = False` is a dev-only probe (every pair of the best-seeded
blocks, scored by the sum's goal match, edges only boosting); it is not the
design and is not judged.

## Dev results (uncommitted suites under /workspace/nomad/graph_dev only)

Dev suites: TRANSFER-2 seeds 7 / 11, TRANSFER-1 seeds 7 / 11 / 13, TRANSFER-4
seed 7, TRANSFER-3 seed 7 (certified, 7 suites, 250 hard tasks). Fields:
math_sci (14 library blocks, 22 programs; graph 24 nodes / 14 edges) and the
**practice field** = math_sci + 1 round on the 1,000 practice tasks of
`scripts/learning_judge.py` (203 library blocks, 512 programs; graph 174
nodes / 284 edges nested, 87 disjoint-only). Rewired = degree-preserving
edge swaps, seeds 0-2.

| field | variant | off | graph | rewired 0 / 1 / 2 |
|---|---|---|---|---|
| math_sci | design (fit score) | 159 | 160 | 162 / 161 / 159 |
| math_sci | activation score | 159 | 160 | 160 / 159 / 159 |
| practice | design (fit score) | 149 | 149 | 149 / 150 / 149 |
| practice | activation score, 400 pairs | 149 | 149 | 150 / 150 / 149 |
| practice | disjoint-only edges | 149 | 149 | 150 / 150 / 149 |
| practice | dev probe: free pairs (not graph) | 149 | 149 | 149 / 150 / 149 |

Regression dev (deep 7 / 11, science 7 / 11 / 13): no changed task. LOFO with
GRAPH on: 5,883, worst 1.0x.

**Diagnosis (dev).** On the practice field the graph proposes 64 pairs per
two-block call and none hits. An oracle over the *full* (uncut) practice bank
finds that 18 of the 57 dev tasks the practice field misses are certifiable as
`a + b + c` with a, b bank blocks and c a bank block / input / constant (e.g.
geo_diag3 = L^2 + W^2 + H^2). The needed pairs are in the bank, but the graph
does not point at them: its strongest edges are a block and its own
sub-program (useless for sums), and relations such as "two squares" never
co-occurred disjointly in a certified training program; a goal-match score
of the pair's sum cannot single the pair out either (the third term still
varies), so only the residual lookup identifies it, and lookups are what
the budget charges.

**Memory-size finding (ROUTE, dev, report only).** With the practice field
the bank hits `PORT_SCAN = 400` on every task (on math_sci it never does), and
the bigger memory scores *lower* (149 vs 159). On that field ROUTE (learned
table) gives 154 vs off 149 vs three shuffled tables 148 / 149 / 138: at
large memory the learned routing evidence is real (unlike at small memory,
docs/ROUTE.md), but it also loses 7 tasks off certifies. This is the most
promising lead found here.

Expectation, written before measuring: GRAPH is unlikely to pass criteria 1-2
on either field.

## Sealed suite

TRANSFER-6 (`nomad/transfer6.py`, `scripts/graph_suite.py`, seed 20261129):
46 formulas in three new domains (music / concerts, farm / livestock,
warehouse / office), input names disjoint from every earlier catalogue
(incl. TRANSFER-5, science, text, bridge, selfedit, text-invent) and all training tasks;
cold control at 10,000 evaluations, max_size 7 splits easy / hard; lookup
guard against every trained arm's memory including the practice field.
Generated and committed (cold only) after this document, before any field
arm runs on it.

## Pre-registered criteria (budget 10,000, every other switch at its default)

Arms (`scripts/graph_judge.py`): cold / empty / empty_graph; for each of the
two fields F in {trained (math_sci), practice}: F (GRAPH off) / F_graph /
F_graph_rw0..2.

1. **Graph beats off:** on at least one field F, F_graph certifies >= 1 more
   TRANSFER-6 hard task than F.
2. **Graph beats every rewired control:** on that same field, F_graph
   certifies >= 1 more than each of F_graph_rw0, rw1, rw2.
3. **Gain vanishes with an empty field:** empty_graph equals empty on every
   task (certified and evaluations).
4. **No losses on TRANSFER-6:** on neither field does F_graph lose a task F
   certifies, and no new worse-than-cold task appears.
5. **Zero per-task losses on every existing frozen suite** (`--secondary`,
   each suite's own trained field): deep (27/25/0 of 40), science hard
   (12/0/0 of 14, incl. sci_water_mol), TRANSFER-1 (19 of 20), TRANSFER-2 (32
   of 35), TRANSFER-3 (27 of 40), TRANSFER-4 (18/2/0 of 35), TRANSFER-5
   (26/8/0 of 33), TEXT (3/0/0 of 24 before INVENT_TEXT; 10 now) , BRIDGE (6/0/0 of 22 before
   INVENT_TEXT; 13 now; current main 17fb8ad defaults INVENT_TEXT on, so the
   judge's own GRAPH-off `trained` arm is the bar): trained_graph
   certifies every task trained certifies, and at least as many.
6. **LOFO** (`--lofo`): trained_graph total <= 5,883, worst ratio <= 1.0x.

All six pass: `NOMAD_GRAPH` defaults to on in a separate commit. Otherwise it
stays off, and the code and the result are committed here as they are.

## Sealed result (TRANSFER-6, sha256 07561e10...c6158fa2, 33 hard): FAIL

Judged 2026-11-21 against the suite committed in e1f05c3; raw output in
`results/graph/graph_sealed_{primary,secondary,lofo}_20261121.json`.

| arm | certified / 33 | evaluations |
|---|---|---|
| cold | 0 | 310,961 |
| empty | 6 | 295,206 |
| empty_graph | 6 | 295,206 |
| trained (GRAPH off) | 23 | 228,059 |
| trained_graph | 23 | 228,272 |
| trained_graph_rw0 / rw1 / rw2 | 23 / 23 / 23 | 228,294 / 228,280 / 228,295 |
| practice (GRAPH off) | 23 | 240,802 |
| practice_graph | 23 | 241,047 |
| practice_graph_rw0 / rw1 / rw2 | 23 / 23 / 23 | 241,102 / 241,088 / 241,089 |

By domain, trained arms: music 10/11, farm 6/12, warehouse 7/10 (identical
for off, graph and every rewired graph); practice arms: 9/11, 7/12, 7/10.
The same 23 tasks are certified by every trained-field arm; the graph changes
only which block pairs are tried first (+213 evaluations on trained, +245 on
practice, within noise of the rewired controls).

| criterion | result |
|---|---|
| 1. graph beats off (either field) | **FAIL** (23 = 23 on both) |
| 2. graph beats every rewired control | **FAIL** (23 = 23 / 23 / 23 on both) |
| 3. empty_graph == empty | pass (6 = 6, identical evaluations) |
| 4. no TRANSFER-6 losses, no new worse-than-cold | pass |
| 5. zero losses on existing suites | pass: deep 27->27 (empty 25, cold 0, of 40); science hard 12->12 (sci_water_mol kept, of 14); TRANSFER-1 19->19 /20; TRANSFER-2 32->32 /35; TRANSFER-3 27->**28** /40; TRANSFER-4 18->18 /35; TRANSFER-5 26->26 (empty 8, cold 0, of 33); TEXT lang 7->7 /24; BRIDGE trained 13->13 /22 |
| 6. LOFO | pass: cold 5,883, trained 5,883, trained_graph 5,883; worst 1.0x |

Verdict: **FAIL** on criteria 1-2, as expected before measuring.
`NOMAD_GRAPH` stays **off**; the code stays in tree behind the switch.

**Memory-size note.** The 1,000-task practice field again does not help on
its own (23 vs 23, and it loses m6_choir_risers and w6_top_and_rest that the
math_sci field certifies, gaining one farm and one warehouse task): a bigger, uncurated memory
is not better under the fixed `PORT_SCAN = 400` cut.

**Honest reading.** A co-occurrence graph learned from WITNESS-certified
programs encodes "which blocks were used together before". On held-out
domains the missing programs need relations that never co-occurred in
training (dev oracle: 18 of 57 practice misses are bank-pair sums), so the
graph's proposals are no better than a randomly rewired graph's. Proposal
order is not the bottleneck; selection of *which* blocks survive the 400-cut
at large memory is.

**Most promising next step.** ROUTE-style learned selection *before* the
`PORT_SCAN` cut at large memory (dev on the practice field: learned 154 vs
off 149 vs shuffled 148 / 149 / 138), with loss protection (e.g. learned
order fills only the tail of the 400 after the usage-order head, or a
two-pass fallback) to remove its 7 dev losses, pre-registered on a fresh
sealed suite.
