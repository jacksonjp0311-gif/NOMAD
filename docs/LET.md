# LET: reasoning with an intermediate result used twice (pre-registered)

Axis: REASONING. Many everyday problems are two-stage: first compute an intermediate result
(`t = pens x sheep per pen`, `money left = paid - price x qty`), then use it again
(`t + t // 3`, `t (t - 1) // 2`, `|t - goal|`, `t // 4 + t mod 4`, `left // price`). Written out, the
program repeats `t`, so it is too big for the search (cold max_size 7), and PORT's anchors
(`goal = block op residual`, residual over the inputs only) cannot reuse the block inside the
residual. LET binds a certified block of the field as `t` and lets the answer be built from two
one-step terms over the same `t`. Everything is behind **`NOMAD_LET`, default OFF** until the sealed
judge below passes. No transformers, no neural weights, no LLM; WITNESS certifies every program; the
cold control is untouched; the program is plain DSL (`t` written out twice; no new node type).

## What is built (`nomad/world.py`: `let_enabled`, `let_terms`, `let_stage` in the PORT probe)

- **Where**: in the PORT probe (`port_body`), int goals only, right after the GROW anchors
  (anchor, ANCHOR2, SCALE) found nothing and before the probe's atoms. It only runs where PORT runs (a
  field with a bank); an empty field never reaches it; cold never does.
- **Binding**: the bank blocks PORT has already run on the public rows (1 evaluation each, already
  charged by PORT), distinct public values, smallest tree first, then `block_score`; at most
  `LET_N` = 64 bindings.
- **Terms** (`let_terms`): `t`, and `op(t, x)` / `op(x, t)` for op in add, sub, mul, div, mod, max, min
  and x in the task's int inputs, the constants 1-3 and `t` itself (so `t*t`, `t+t`), deduplicated by
  public values. A term whose public values are already in the probe's table is **free** (the regular
  levels already paid for that value); every other term costs **1 evaluation**.
- **Fits**: a term equal to the goal; a pair of terms over the same `t` whose add / sub / reversed sub /
  mul gives the goal (hash lookup of the residual among the terms: free, the ANCHOR / TEXT_CHAIN
  lookup convention); a term `// k` for the learned scales `k` (GROW). Every **assembled program costs 1
  evaluation** and is WITNESS-gated.
- **Caps**: the stage spends at most `LET_CAP` = 0.35 of max_eval; it stops after `LET_REJECTS` = 2
  WITNESS rejections and is skipped when the task's rejection cap could be spent (so a let fit never
  slips through an exhausted gate).
- **Judge-only control** `NOMAD_LET_SOURCE=pool`: bind the probe's own pool values (unlearned trees of
  size >= 2 the regular levels built) instead of the field's certified blocks; same ranking and caps.

Dev (uncommitted, `/workspace/nomad/reason_dev`, inputs `ra rb rc rd`, seeds 11 / 12, field
`all_sci`): trained 8 -> 11 of 12 and 4 -> 6 of 12, empty 1 = 1, cold 1. Guard rows (TRANSFER-1/4/5 and
SELFEDIT catalogues at dev seed 7): gains +0 / +2 / +2 / +3, but **small per-task evaluation losses**
remain on TRANSFER-4 / -5 (+8 evaluations on tasks solved at ~2,300-3,300; +150 to +950 on three tasks
solved late), the cost of terms and rejected fits on tasks the probe solves later. Stated before measuring:
criterion 4 (zero per-task losses) is therefore expected to **fail**; this is measured anyway, once.

## Sealed suite

`nomad/let_tasks.py` (24 formulas, domains farm / school / kitchen, inputs `xa xb xc xd` disjoint from
every catalogue: 22 two-stage problems where an intermediate is reused or feeds a second step, 2 one-step
controls), written before any field arm was measured on it; `scripts/let_suite.py` (the TRANSFER
generator: cold at 10,000 / max_size 7 -> easy / hard, lookup guard on every trained arm's memory under
every renaming, easy-twin guard), seed **20261231** (unused): `data/deep/let_suite.json`, sha256
`0acf8ab57aa7e4df4eb6ab6648460189ca2ac503528f5224a8300b372416dd4a`: 2 easy (the controls; never scored),
**22 sealed hard**, none dropped.

## Judge (`python3 scripts/let_judge.py`, budget 10,000, max_size 7, PORT / ANCHOR2 / SCALE on)

Every other switch at its default. Fields = `scripts/transfer_suite.fields()`. Arms: `cold`,
`empty_off`, `empty_on`, `trained_off` (all_sci), **`trained_on`** (all_sci; scored),
`trained_on_pool` (control, `NOMAD_LET_SOURCE=pool`), `math_sci_off` / `math_sci_on` (report).
Regressions: `SWITCH=NOMAD_LET scripts/switch_regress.py` over every existing sealed suite (learning:
deep, science hard, LOFO; TRANSFER-1..4, secondary, TEXT, BRIDGE, INVENT_TEXT, TRANSFER-5, TRANSFER-6,
SELFEDIT-2, TEXT_CHAIN, MEANING, INFLECT).

## Pre-registered criteria (committed before any sealed measurement)

All of 1-6 must hold to flip `NOMAD_LET` on by default:

1. **It helps**: `trained_on` certifies >= **+3** over `trained_off`, or >= 0 more with >= 25% fewer
   evaluations.
2. **Gains vanish with an empty field**: `empty_on == empty_off` (`empty_on - cold` reported).
3. **No sealed task worse**: zero per-task losses of `trained_on` vs `trained_off`; `trained_on` and
   `empty_on` no worse than cold on any task cold certifies.
4. **Zero per-task losses on every existing suite** (every arm, switch on vs off; a loss = certified
   off but not on, or more evaluations on).
5. **LOFO** totals 5,883, worst ratio 1.0x; full pytest passes.
6. **Safety**: the off arms reproduce the current headline numbers (switch off = current code).

Report-only (not a flip condition, because the claim is a search operator that the field unlocks, not
new learned content): the pool control `trained_on_pool - trained_off`; `trained_on - trained_on_pool >= 2`
would support "the field's certified blocks matter as intermediates", otherwise that reading is not
supported. `math_sci_on - math_sci_off` reported.

Rule: all of 1-6 pass -> `NOMAD_LET` default ON in a separate commit; any fail -> stays OFF with an
honest note and `results/let/`. Measured once, from a code snapshot.

Expectation (stated before measuring): criterion 1 passes narrowly (+3 to +6), 2-3 pass, **4 fails** on
TRANSFER-4 / TRANSFER-5 evaluation counts (see dev), so the switch stays off; the pool control solves
about as many as the field (the useful intermediates `xa xb`, `xa + xb` are also pool values).
