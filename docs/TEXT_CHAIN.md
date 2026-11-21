# TEXT_CHAIN: string goals of three or more parts (pre-registered)

INVENT_TEXT (docs/INVENT_TEXT.md) completes a string goal from **two** known pieces: a block that
is a prefix (suffix) of the goal plus a pool / block value equal to the remainder. Goals built from
three or more pieces -- `last(w) + sep + first(w)`, `word + ":" + name + "/" + k`, `tail + sep +
tail` -- stay out of reach unless some pool entry happens to hold two pieces already. TEXT_CHAIN
peels pieces off both ends recursively. Everything is behind **`NOMAD_TEXT_CHAIN`, default OFF**
until the sealed judge below passes. No transformers, no neural weights, no LLM; WITNESS certifies
every program; the cold control is untouched.

## What is built (`nomad/invent.py`: `chain_parts`, `text_chain`; `nomad/world.py`: `text_chain`)

- **Parts**: every computed string value of the task's block probe (the probe pools of every size,
  the bank blocks instantiated on the task's inputs, INVENT's invented blocks -- the abstractions it
  anti-unified from certified programs -- in the INVENT phase), plus
  - **case variants** `upper(t)` / `lower(t)` when the opset has them,
  - **number-to-text** `itos(t)` of the integer pool values when the opset has `itos`,
  kept only when every row's value is a non-empty proper substring of that row's goal; at most
  `TEXT_CHAIN_POOL` = 400 values (the same value twice: the smaller / pool one wins).
- **Recursive peeling** (iterative deepening on the number of peels, fewest parts first): a part
  whose value is a proper prefix (suffix) of the remaining segment on every public row is peeled off
  the front (back); after 2 or 3 peels the remaining segment must equal a part's values exactly, and
  `concat(p1, concat(p2, ... ))` is assembled. Chains of 3-4 parts (`TEXT_CHAIN_PARTS` = 4; a pool
  entry that is itself a concat makes longer goals reachable); two-part chains are INVENT_TEXT's.
- **Budget**: peeling is a comparison on values already computed (no evaluation; like INVENT_TEXT's
  remainder lookup, INVENT's rescaled targets and the SELFEDIT floor fit), capped at
  `TEXT_CHAIN_NODES` = 600 states per task; every **assembled chain costs 1 evaluation** and is
  WITNESS-gated; at most `TEXT_CHAIN_N` = 16 chains per task, inside the INVENT_TEXT budget limit.
- **Where**: right after INVENT_TEXT's concat anchors -- the free early pass after the PORT block
  probe, and in the (deferred) INVENT phase. It only runs for string goals, only where INVENT_TEXT's
  anchors run (a field with a bank and a kit; an empty field never reaches it), and only after the
  two-part anchors found nothing. Integer goals are untouched; the switch off changes nothing.
- Dev (uncommitted dev catalogue, inputs `da db dk dj dq dp`, seeds 11 / 12; plus fresh seed-7 / 11
  rows of the TEXT, BRIDGE-dev, TRANSFER-4 and INVENT_TEXT catalogues): trained 12 -> 18 / 12 -> 17
  of 18, empty 0 -> 0; 0 per-task losses on 144 guard tasks x 2 fields at both seeds. A first
  version demanded a part that only a learned block adds (as SPLICE does); with the bridge opset
  the probe pools already hold every such value, so it never fired; that requirement is off
  (`TEXT_CHAIN_LEARNED` = False).

## Sealed suite

`nomad/text_chain_tasks.py` (24 formulas: 20 string goals of 3-5 parts -- slices, case changes,
repeats, rotations, number-to-text -- and 4 controls: a two-part goal, a top-level `lower`, two
integer outputs; new inputs `ma mb mk mj ms mt`, disjoint from every catalogue; separators ":" and
"/"), written before any field arm was measured on it; `scripts/text_chain_suite.py` (the
INVENT_TEXT generator: cold at 10,000 / max_size 7 -> easy / hard, lookup guard on every bridge
trained arm's memory, easy-twin guard), seed **20261205** (unused):
`data/deep/text_chain_suite.json`, sha256
`630f7a9eb941fccf9c77289f134bc0d0678f42983bc8d22a64b380576210d4eb`: 2 easy (never scored),
**22 sealed hard**, none dropped.

## Judge (`python3 scripts/text_chain_judge.py`, budget 10,000, max_size 7)

NOMAD_BRIDGE, PORT / ANCHOR2 / SCALE, INVENT_TEXT and **SELFEDIT at their defaults (on)**; the
live repo has no `data/genome.json`, so SELFEDIT's genes equal the frozen constants. Fields =
`scripts/bridge_suite.fields()`. Arms: `cold`, `empty_off`, `empty_on`, `trained_off`,
**`trained_on`** (scored); report: `world_only_off/_on`, `bridge_only_off/_on`,
`trained_on_text_off` (NOMAD_INVENT_TEXT off).
Regressions: `SWITCH=NOMAD_TEXT_CHAIN scripts/switch_regress.py` over learning (deep, science
hard, LOFO), TRANSFER-1..4, secondary, TEXT, BRIDGE, INVENT_TEXT, TRANSFER-5 (route5),
**TRANSFER-6** (graph_judge) and **SELFEDIT round 2** (selfedit_judge --round 2) -- (a) default
genome, (b) `NOMAD_GENOME` = the SELFEDIT round-2 tuned genome G\* (`results/selfedit2/
genome_tuned.json`, what the live body's sandbox may adopt).

## Pre-registered criteria (committed before any sealed measurement)

All must hold to flip `NOMAD_TEXT_CHAIN` on by default:

1. **It helps**: `trained_on` certifies >= **+3** over `trained_off`, or >= 0 more with >= **25%
   fewer** evaluations.
2. **Gains vanish with an empty field**: `empty_on - empty_off <= 1` (`empty_on - cold` reported).
3. **No sealed task worse**: zero per-task losses (lost certification or more evaluations) of
   `trained_on` vs `trained_off`; `trained_on` and `empty_on` no worse than cold on any task cold
   certifies.
4. **Zero per-task losses on every existing suite** (every arm, switch on vs off), in both (a)
   and (b): deep, science hard, TRANSFER-1..4, secondary, TEXT (lang 7 / all_sci 10), BRIDGE
   (trained 13), INVENT_TEXT (trained_on 13 / 15), TRANSFER-5 (trained 26), TRANSFER-6 (trained 23),
   SELFEDIT round 2 (trained_tuned 14).
5. **LOFO** totals 5,883, worst ratio 1.0x, in (a) and (b); full pytest passes.
6. **Safety**: the off arm of every regression reproduces the headline numbers above (the switch
   off is the current code).

Rule: all pass -> `NOMAD_TEXT_CHAIN` default ON in a separate commit; any fail -> stays OFF with an
honest note. Measured once, from a code snapshot.

Expectation (stated before measuring): criterion 1 passes by a wide margin on the 3-5 part goals;
`m_head_mid_tail` (a middle slice) and the integer controls stay unsolved by the chain; 2-6 pass.

## Sealed result (measured once, 2026-11-21, code `9207b34`; `results/text_chain/`): **PASS**

Sealed suite (sha `630f7a9e...d4eb`, 22 hard), certified / evaluations:

| arm | certified | evaluations |
|---|---|---|
| cold | 0 | 220,000 |
| empty_off | 0 | 220,000 |
| empty_on | 0 | 220,000 |
| trained_off | 10 | 170,828 |
| **trained_on** | **22** | **111,785** |
| world_only_off / _on | 2 / 20 | 210,053 / 120,413 |
| bridge_only_off / _on | 10 / 22 | 170,516 / 111,323 |
| trained_on_text_off | 3 | 205,418 |

The 12 gains are all `port:invent:text:chain` (3-5 part goals: take/take/take, tail:tail, rot/rot,
word:name/k, both initials + total length, head:mid:tail, ...); `m_lower_rot_ctrl` also got cheaper
(5,228 -> 5,052). Against the stated expectation, `m_head_mid_tail` was solved too (the probe pool
held `concat(take(ma, mj), ms)`).

| criterion | result |
|---|---|
| 1 it helps (>= +3) | **pass**: +12 (10 -> 22 of 22), 34.6% fewer evaluations |
| 2 empty_on - empty_off <= 1 | **pass**: 0 - 0 (empty_on - cold = 0) |
| 3 no sealed task worse | **pass**: no loss vs trained_off; nothing worse than cold |
| 4 existing suites, (a) default genome and (b) SELFEDIT G\* | **pass**: 0 losses in both on every arm of learning (deep, science), TRANSFER-1..4, secondary, TEXT, BRIDGE, INVENT_TEXT, TRANSFER-5, TRANSFER-6, SELFEDIT-2. Gains: TEXT 26 -> 56 certified records (lang 7 -> 17, all_sci 10 -> 20), BRIDGE 47 -> 60 (trained 13 -> 15), INVENT_TEXT 39 -> 51 (trained_on 13 -> 15 of 15), secondary 265 -> 275; TRANSFER-1..6, SELFEDIT-2 (14) unchanged |
| 5 LOFO, tests | **pass**: LOFO 5,883 (cold / trained / trained_port_off), worst 1.0x, (a) and (b); 464 passed, 6 skipped |
| 6 safety | **pass**: off arms reproduce INVENT_TEXT 13, BRIDGE 13, TEXT lang 7 / all_sci 10, TRANSFER-5 26, TRANSFER-6 23, SELFEDIT-2 14 |

Decision (pre-registered rule): all pass -> `NOMAD_TEXT_CHAIN` default ON in a separate commit.

Honest reading:
- The gain needs a field arm (the chain runs inside the PORT / INVENT_TEXT path, which an empty field
  never reaches), but not specific string memory: `world_only` (no bridge training) goes 2 -> 20.
  Most chain parts are probe-pool values; the field mainly buys the probe and its budget. This is a
  search operator that the field unlocks, not new learned content.
- Peeling is counted as free (comparisons on computed values); only assembled chains are charged.
  That is the INVENT_TEXT convention, stated before measuring; a charged-lookup variant would cost
  more evaluations.
- No new anti-unified string abstraction was added: invented blocks enter as parts, but nothing new
  is abstracted from certified chains yet (a next step: lift certified chains into templates).
