# INTERCONNECT: how NOMAD's domains mix today, and learned interconnects that could replace the fixed wiring

Analysis document (2026-11-21). No code changes are proposed here without a
sealed judge; everything marked *speculative* is untested.

## 1. The path from task to certified program (as of main 0d198eb + ROUTE)

1. **Type picks the world** (`opset_of`, `nomad/world.py`). int, str, list
   and (with `NOMAD_BRIDGE`, default on since 90fbdfc) the bridge opset with
   int<->str conversion operators. Operators outside the task's opset are
   never enumerated: this is the first, hard partition between domains.
2. **Cold control** (`prior=None`): exact enumeration in the opset order.
   Never reads memory. Every arm is measured against it.
3. **Familiar family** (`familiar()`: the field holds operator counts for
   this family): the family's own Beta-ordered operators plus up to
   `library_k` library blocks *of the same input signature*
   (`primitives_for`), then the variation fallback. **No cross-domain input
   at all**: the portable bank, SENSE, INVENT and GROW are never consulted.
   This is deliberate (LOFO: cross-family order and atoms cost 13x on the
   worst family) and is why LOFO is 5,883 with worst 1.0x.
4. **Unfamiliar family** -> `_staged_gen`, in this order:
   - stage 1: the exact cold search below max_size (cannot lose to cold);
   - SENSE lead block (`sense.lead_ops`): shape `negative` -> `sub`,
     `growth` -> `mul` at the max_size level over stage 1's pools;
   - case split (int + `ite`), then variation mutants;
   - **block probe -> PORT** (`port_body`): the portable bank
     (`port_bank`: every library block and whole certified program, any
     signature, any source family, renamed onto this task's inputs by type),
     one evaluation per block on the public rows;
   - **block_score** (rows equal, fewest distinct offsets, row-order
     agreement) ranks the blocks: this is the only goal-conditioned
     "attention" in the system (query = the goal's public values, key = a
     block's values, a fixed similarity, no learning);
   - anchors: for the top `PORT_ANCHOR_N` blocks, residual lookups (goal
     minus / over the block) in the table of pool values; GROW two-block
     anchors (`ANCHOR2_M` = 40 blocks paired) and learned-scale rescaling;
   - `PORT_K` = 24 foreign blocks become probe atoms;
   - **INVENT phase** (`invent.kit`): MDL abstractions over *all* certified
     programs regardless of domain, plus derived constants, used as single
     nodes and as anchors (capped at 15% of budget);
   - the probe's regular levels, stage 2 (library atoms), the max_size level.
5. **WITNESS** gates every fit on challenge rows (a rejection costs 1
   evaluation and search continues); certification also needs the final
   split, which search never reads.
6. **Learning** happens only from a verified receipt (`add_witnessed`, in the
   live body via consolidation in sleep): operator Beta counts (global and per
   family), library harvest of sub-programs, whole programs (cap 512), and
   since ROUTE, the routing table and block provenance. `decay` forgets.

### Where domains actually mix

- **One shared memory**, read cross-domain in exactly two places: the
  portable bank (step 4, PORT/GROW anchors and atoms) and INVENT's
  abstraction corpus. Both only on unfamiliar families.
- **One shared type bridge**: the bridge opset lets a text task use integer
  sub-programs through conversion operators.
- Nothing else: the global operator table is used only when no family is
  given; SENSE only aims the max_size level.

### Where it fails to mix (measured, not guessed)

- **The bank is small.** In every judge field and in the live
  `world_prior.json`, a TRANSFER-4 task's bank has <= 129 entries (live <= 57)
  against `PORT_SCAN = 400`. The "popularity cut drops a fitting far-domain
  block unseen" failure is **not active today**; the cuts that bite are the
  24 atoms, the 40 two-block candidates, and the order budget-capped anchors
  are tried in.
- **block_score never learns**, and it only compares single blocks to the
  goal: it cannot see that two mediocre blocks combine into the answer
  (GROW's two-block anchor tries pairs blindly among the top 40).
- **Familiar families are sealed off** (by design, for the LOFO guarantee).
- **ROUTE result (docs/ROUTE.md):** a learned table of how often a memory
  group (source shape x kind) appears in certified solutions of a task shape
  ranks blocks no better than the same table shuffled (sealed: 26 = 26 = 26 =
  26 of 33; dev: 162 vs 159-163) and lost one budget-edge science task.
  Lesson: **coarse priors over groups carry no information beyond
  block_score**; a useful learned interconnect has to be (a) block-level and
  (b) conditioned on the current goal, and needs (c) a memory big enough to
  route through. Any learned routing must be judged against a permuted-
  evidence control, because an empty field is identical by construction and
  re-ordering alone moves budget-edge tasks either way.

## 2. Learned interconnects with attention-like behaviour (no transformer)

The analogy: attention = each element weighs every other element by a
learned compatibility, recomputed per input. Here the elements are memory
blocks and primitives; "per input" is per task (its goal values); "learned"
must mean updated only from WITNESS-certified receipts so that nothing
uncertified can steer search; every option below keeps stage 1 exact and
spends only a capped share of budget after it, which is what protects the
cold guarantee and LOFO.

### Option A: learned routing counts (built: ROUTE, off)

- *Mechanism:* Beta counts per (task SENSE key, memory group); rank by
  block_score then relevance; routed atoms.
- *Cost:* negligible (one subtree canonicalisation per receipt).
- *Risk:* re-ordering moves budget-edge tasks (sealed: sci_water_mol lost).
- *Judged:* done; failed criteria 1, 4 and 5.
- *Keep:* the table and provenance are cheap evidence, always learned, for
  B-D.

### Option B: sparse co-occurrence graph + spreading activation (recommended)

- *Mechanism:* nodes = canonical blocks (up to renaming), invented
  primitives and operator frames; an edge (u, v) gets a Beta count each time
  u and v occur together in one certified program (s), or one occurs without
  the other (f); decays with the genome. Per task: seed activation =
  block_score of each bank block against the goal (and against each residual
  / rescaled target); spread one or two steps along edges weighted by the
  edge posterior; the activated *pairs* (u, v) go to GROW's two-block anchor
  and the activated nodes to the atom set, in activation order. Every block
  weighs every other through the graph, freshly per task: that is the
  attention, but sparse, inspectable (an edge is a count you can print) and
  O(edges) per task.
- *Co-evolution:* the graph is built from certified programs, and INVENT's
  new primitives become nodes; option D closes the loop.
- *Cost:* tiny today (tens of nodes, hundreds of edges); bounded by the
  512-program cap.
- *Risk:* the same budget-edge re-ordering as ROUTE if it replaces the
  current top-40 pairing. Mitigation: *add* graph pairs ahead of the existing
  pair loop inside GROW's existing cap rather than replacing it, or charge
  the graph phase to its own small cap after main's anchors.
- *Judged:* fresh sealed suite, 3-arm judge, plus a degree-preserving
  rewired-graph control (the ROUTE lesson), zero per-task losses on all
  frozen suites, LOFO unchanged.
- *Honest prior:* the judge fields hold 22-30 programs, so the graph would
  be very sparse; a positive result likely needs the larger practice field
  (`learning_judge.practice_tasks`, 1,000 tasks) as the trained arm.

### Option C: type-bridge edges (numbers <-> text)

- *Mechanism:* in the graph of option B, allow edges between an int block
  and a str block when a certified bridge program contains both joined by a
  conversion operator; activation then crosses types, so a text goal can pull
  in the numeric blocks that previously certified next to it (and vice
  versa).
- *Targets:* the open gap "number and text skills don't combine".
- *Cost / risk:* small; affects only bridge/str tasks, which are already
  the weakest (TEXT 3/24), so a regression is easy to see.
- *Judged:* on a new sealed mixed int/str suite with the bridge on; control:
  bridge edges shuffled across types.
- *Speculative:* depends on the bridge field producing enough certified
  mixed programs to form edges at all.

### Option D: invention driven by graph structure (*speculative*)

- *Mechanism:* INVENT today proposes abstractions by MDL compression over
  all programs. Instead (or in addition), propose an abstraction for each
  dense subgraph / clique of option B (blocks that keep certifying
  together), with the clique's shared structure as the body and the
  differing parts as holes. The new primitive becomes a node; its edges are
  learned from then on. Math (primitives) and structure (graph) then grow
  each other: the graph decides what to abstract, the abstractions reshape
  the graph.
- *Risk:* more primitives widen the INVENT phase; it stays inside
  `INVENT_CAP` and the evidence gate, but invented-primitive bloat is a real
  failure mode (round 1 lost a budget-edge task).
- *Judged:* like INVENT round 2 (fresh suite, composition arm, frozen-suite
  no-loss, LOFO), plus a control with cliques from a rewired graph.

### Option E: genome-tuned routing knobs (low risk, small upside)

- *Mechanism:* expose `PORT_K`, `ANCHOR2_M`, the anchor order temperature
  (and, once B exists, spread steps and decay) as genes; `nomad/evolve.py`
  already mutates one gene, benchmarks before/after offline, keeps wins that
  pass the full test suite, and sleep reverts a >15% live regression.
- *Judged:* on dev benchmarks only during evolution (never the sealed
  suites), then a one-time sealed check of the evolved values.
- *Risk:* overfitting the dev benchmark; mitigated by the one-time sealed
  check.

## 3. Recommended smallest next experiment

**Option B, pairs only.** Build the block co-occurrence graph from the
receipts ROUTE already processes (provenance and canonical forms are in
place), and use it for one thing: an extra list of activated block pairs
tried by GROW's two-block anchor *before* its existing blind top-40 loop,
inside the existing `GROW_CAP`, with the existing loop unchanged afterwards.
Off switch `NOMAD_GRAPH`, default off. Tune on uncommitted dev suites with
both the math_sci field and a 1,000-task practice field; pre-register in a
docs commit; judge on a fresh sealed suite (new seed, new domains) with
cold / empty / trained / trained_graph / trained_graph_rewired (three
degree-preserving rewirings) and require: trained_graph >= trained + 1,
trained_graph >= rewired mean + 1, empty identical, zero per-task losses on
every frozen suite (including the budget-edge sci_water_mol), LOFO 5,883 /
1.0x. Expected honestly: no gain on the tiny math_sci field; a measurable
gain, if any, on the practice field, which would tell us that learned
interconnect is limited by memory size rather than by mechanism.
