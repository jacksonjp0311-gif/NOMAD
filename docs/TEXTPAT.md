# TEXT_ABSTRACT: reusable string templates from certified text chains (pre-registered)

TEXT_CHAIN (docs/TEXT_CHAIN.md) assembles a string goal from three or more computed
pieces by recursive prefix / suffix peeling. Its sealed result was a search operator
the field unlocks, not new learned content: "nothing new is abstracted from certified
chains yet (a next step: lift certified chains into templates)." TEXT_ABSTRACT does
that step. Certified TEXT_CHAIN / INVENT_TEXT (and any other concat-shaped string)
programs in the field's PORT memory are anti-unified into templates -- variables
become holes, and the least general generalisation of a pair of chains turns the
places they differ into holes too (e.g. `upper(a) ':' b '/' itos(n)`). Templates
live in a small dedicated library and are instantiated onto a new task's inputs by
type-preserving binding, so NOMAD reuses language shapes instead of assembling every
chain from scratch.

Everything is behind **`NOMAD_TEXT_ABSTRACT`, default OFF until the sealed judge
below passes** (off switch: `NOMAD_TEXT_ABSTRACT=off`). No transformers, no neural
weights, no LLM; WITNESS certifies every program; the cold control is untouched.

## What is built (`nomad/textpat.py`; `nomad/world.py`: `text_templates`)

- **Corpus**: whole certified programs whose tree is a concat chain, optionally
  wrapped in `upper` / `lower` / `srev`. Library references are skipped (same as
  INVENT's corpus).
- **Anti-unification**: `abstract_vars` of every such chain (a certified chain is
  itself a template) and the LGG of every pair of chains / concat subtrees with
  the same root, up to `TEXTPAT_MAX_HOLES` = 6 (INVENT's cap is 3, too tight for
  a 4- or 5-part spine). Candidates are behaviourally deduped on seeded synthetic
  rows (no task row is read), ranked with whole-program abstractions first, then
  by uses and specificity; at most `TEXTPAT_MAX` = 24 are kept.
- **Instantiation**: holes bind to the task's inputs by type; bindings whose
  predicted output length disagrees with the public goal (a length homomorphism
  on input values, no `world.run`) are dropped; at most `TEXTPAT_MAX_INSTANCES`
  = 192 length-matching instances are kept.
- **Free assembly** (before stage 1, string goals only): a template instance
  whose value can be composed from the task's inputs plus the same free case /
  `itos` variants TEXT_CHAIN already computes, and `first` / `last` / `rest` /
  `init` / `itos` of input integer expressions (`strlen`, `+`, `-`, `*`), is
  offered to WITNESS at **1 evaluation** when it equals the public goal. A miss
  costs nothing, so stage 1 remains the exact cold search when no template hits.
  `take` / `drop` / `srep` / rotations are not free (they would be a new
  evaluation); those shapes still rely on PORT, TEXT_CHAIN, or the paid pass.
- **Paid instantiation** (after the INVENT / TEXT_CHAIN phase would otherwise
  give up): remaining length-matching instances are run as whole programs (1
  evaluation each, capped at `TEXTPAT_N` = 24), reaching shapes whose
  intermediate pieces the pool never held. Existing tasks solved earlier never
  reach this pass.
- An empty field has no certified chains, so it invents nothing; the switch off
  changes nothing; the cold control never reads a field.
- **Shuffled-template control** (`textpat.shuffled(prior, seed)`): a deep copy
  whose templates are rewired -- concat children swapped, paired operators
  flipped (`upper`/`lower`, `take`/`drop`, `first`/`last`) -- keeping arity and
  hole types. Instantiation already tries every type-matching binding, so a hole
  permutation would be a no-op; a concat-swap of a *structured* template is not.
- Training families (`nomad.textpat_tasks.TRAIN_CATALOGUE`, inputs `ua..ut`,
  separators "-" and ".") are used only to grow the judge's trained field; they
  are never scored. The lookup guard on the sealed suite is `bridge_suite.fields()`
  only, so a same-shape transfer is not dropped as a memory lookup.
- Dev (uncommitted dev catalogue, inputs `ea eb ek ej es et`, separators "+" and
  "*", seeds 11 / 12): on 20 hard string tasks (cold / empty fail), `trained_on`
  tied `trained_off` and the shuffled control on certifications (PORT and
  TEXT_CHAIN already solve them) and used about 25% fewer evaluations, with
  unique template hits on structured shapes (case, initials, 5-part labels);
  empty 0 = 0; integer controls unchanged; take / drop / rotation shapes still
  found by PORT, not by the free pass. No per-task loss vs off on that slice.

## Sealed suite

`nomad/textpat_tasks.py` (24 formulas: 20 template-shaped string goals of 3-5
parts -- labels, slices, case changes, repeats, rotations, number-to-text -- and
4 controls: a two-part goal, a top-level `lower`, two integer outputs; new
inputs `va vb vk vj vs vt`, disjoint from every catalogue; separators "|" and
"#"), written before any field arm was measured on it; `scripts/textpat_suite.py`
(the TEXT_CHAIN generator: cold at 10,000 / max_size 7 -> easy / hard, lookup
guard on every bridge_suite trained arm's memory under every renaming, easy-twin
guard), seed **20270117** (unused): `data/deep/textpat_suite.json`, sha256
`c7e5e253bb1e50da97ce3e5e47af1e2cd4d137b926c6a21cdec50e55ad835306`: 2 easy (never scored),
**22 sealed hard**, none dropped.

## Judge (`python3 scripts/textpat_judge.py`, budget 10,000, max_size 7)

NOMAD_BRIDGE, PORT / ANCHOR2 / SCALE, INVENT_TEXT, TEXT_CHAIN and **SELFEDIT at
their defaults (on)**; the live repo has no `data/genome.json`, so SELFEDIT's
genes equal the frozen constants. Fields: `trained` = `scripts/bridge_suite.fields()['trained']`
plus the TEXT_ABSTRACT training families (2 rounds); report `world_only`,
`bridge_only`, `patterns_only` (an empty field trained only on the pattern
families). Arms: `cold`, `empty_off`, `empty_on`, `trained_off`, **`trained_on`**
(scored), `shuffled_1..3` (trained field, switch on, `textpat.shuffled(seed 1/2/3)`);
report: `world_only_on`, `bridge_only_on`, `patterns_only_on`,
`trained_on_chain_off` (NOMAD_TEXT_CHAIN off).
Regressions: `SWITCH=NOMAD_TEXT_ABSTRACT scripts/switch_regress.py` over learning
(deep, science hard, LOFO), TRANSFER-1..4, secondary, TEXT, BRIDGE, INVENT_TEXT,
TRANSFER-5 (route5), TRANSFER-6 (graph_judge), SELFEDIT round 2, TEXT_CHAIN,
MEANING, INFLECT and LET -- (a) default genome, (b) `NOMAD_GENOME` = the
SELFEDIT round-2 tuned genome G\* (`results/selfedit2/genome_tuned.json`).

## Pre-registered criteria (committed before any sealed measurement)

All must hold to flip `NOMAD_TEXT_ABSTRACT` on by default:

1. **It helps**: `trained_on` certifies >= **+3** over `trained_off`, or >= 0 more
   with >= **25% fewer** evaluations.
2. **The learned shapes matter**: the same bar against the **best of the three
   shuffled-template controls** (`trained_on` >= best shuffled + 3, or >= 0 more
   with >= 25% fewer evaluations).
3. **Gains vanish with an empty field**: `empty_on - empty_off <= 1`
   (`empty_on - cold` reported).
4. **No sealed task worse**: zero per-task losses (lost certification or more
   evaluations) of `trained_on` vs `trained_off`; `trained_on` and `empty_on` no
   worse than cold on any task cold certifies.
5. **Zero per-task losses on every existing suite** (every arm, switch on vs off),
   in both (a) and (b): deep, science hard, TRANSFER-1..4, secondary, TEXT, BRIDGE,
   INVENT_TEXT, TRANSFER-5, TRANSFER-6, SELFEDIT round 2, TEXT_CHAIN (22 hard),
   MEANING, INFLECT, LET. Includes `sci_water_mol`.
6. **LOFO** totals 5,883, worst ratio 1.0x, in (a) and (b); full pytest passes.
7. **Safety**: the off arm of every regression reproduces the headline numbers
   of the current code (the switch off is the current code).

Rule: all pass -> `NOMAD_TEXT_ABSTRACT` default ON in a separate commit; any fail
-> stays OFF with an honest note. Measured once, from a code snapshot.

Expectation (stated before measuring): criteria 1-2 pass by fewer evaluations
(PORT and TEXT_CHAIN already solve many of the same shapes; the free pass should
hit the structured ones in 1 evaluation); a certification margin is possible if
PORT buries a training program; take / drop / rotation goals may stay on the
PORT / TEXT_CHAIN path; 3-7 pass. The free pass is counted as free (comparisons
and input-derived variants on values already known); only an assembled template
is charged, which is the TEXT_CHAIN convention, stated before measuring.

## Sealed result (measured once, 2026-11-21, code `e54e29b`; `results/textpat/`): **FAIL -> stays OFF**

Suite sha `c7e5e253bb1e50da97ce3e5e47af1e2cd4d137b926c6a21cdec50e55ad835306`, 22 hard tasks (2 easy never scored). Measured once from the pre-registration snapshot; not re-run after later ROLES / COMBINE commits (those switches stay off).

| arm | certified | evaluations |
|---|---|---|
| cold | 0 | 220,000 |
| empty_off | 0 | 220,000 |
| empty_on | 0 | 220,000 |
| trained_off | 22 | 115,698 |
| **trained_on** | **22** | **89,321** |
| shuffled_1 | 22 | 115,698 |
| shuffled_2 | 22 | 115,698 |
| shuffled_3 | 22 | 115,698 |
| world_only_on (report) | 19 | 125,345 |
| bridge_only_on (report) | 22 | 111,303 |
| patterns_only_on (report) | 1 | 215,085 |
| trained_on_chain_off (report) | 22 | 89,317 |

| criterion | result |
|---|---|
| 1 it helps (vs off) | **FAIL**: 22 = 22 certified, **22.8% fewer** evaluations (bar was +3 certifications or 25% fewer) |
| 2 learned shapes matter (vs best shuffled) | **FAIL**: 22 = 22, **22.8% fewer** than every shuffled-template control (all 22 / 115,698, identical to off); the bar was 25% |
| 3 empty field gains nothing | **pass**: empty_on = empty_off = 0, 220,000 = 220,000 |
| 4 no sealed task worse | **pass**: no per-task loss vs off; nothing worse than cold (cold certified 0) |
| 5 existing suites, every arm, default genome and G* | **pass**: 16 judges listed above, 0 losses, 0 gains; on / off output **byte-identical** on both genomes (learning incl. `sci_water_mol`, T1-T4, secondary, text, bridge, INVENT_TEXT, TRANSFER-5, TRANSFER-6, SELFEDIT2, TEXT_CHAIN 22, MEANING, INFLECT, LET). Certified totals unchanged. |
| 6 LOFO, tests | **pass**: LOFO 5,883, worst 1.0x, on and off, default and G*; 540 passed, 6 skipped |
| 7 off arms reproduce current headlines | **pass**: learning 94, T1 50, T2 107, T3 58, T4 61, secondary 275, text 56, bridge 60, INVENT_TEXT 51, route5 162, transfer6 242, SELFEDIT2 44, TEXT_CHAIN 89, MEANING 158, INFLECT 31, LET 51 |

Honest reading. The composition path works where the free pass can fire. Five structured tasks hit a certified template in 1 evaluation (`port:invent:text:template`) and saved 26,377 evaluations against both off and every shuffled control:

- `p_upper_name_sep_lower_word` 5,401 → 1 (off via TEXT_CHAIN)
- `p_first_sep_len` 5,127 → 1 (off via PORT block)
- `p_last_sep_len` 5,127 → 1 (off via PORT block)
- `p_lower_initials_sep` 5,326 → 1 (off via PORT block)
- `p_word_sep_name_sep2_k` 5,401 → 1 (off via TEXT_CHAIN pre)

The other 17 hard tasks tied on PORT / TEXT_CHAIN / probe / anchor, including take / drop / rotation / `srep` (not in the free pass) and the integer / two-part / top-level `lower` controls. Shuffled templates are rewired, so they miss the free pass and fall through to the same search as off, which is why the three shuffled arms are byte-identical to `trained_off` on every task. `patterns_only_on` certified 1 of 22: templates come from certified chains already in the field; pattern-family training alone is not enough. `trained_on_chain_off` (89,317) matches `trained_on`, so the savings do not depend on TEXT_CHAIN during scoring.

The miss is the pre-registered 25% evaluation bar, missed by 2.2 points, with equal certifications. That is an honest fail, not a near-pass to retune. A fair retry needs a new sealed suite, not a re-run: either a heavier share of structured case / `itos` / multi-part shapes that PORT buries, or free / paid coverage of take / drop / `srep` / rotation, with the bar set to what that suite can actually distinguish. `NOMAD_TEXT_ABSTRACT` stays **OFF**.
