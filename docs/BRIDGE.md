# BRIDGE: do integer and string skills combine? (pre-registered)

TEXT (docs/TEXT.md) ended with: string transfer passes narrowly, integer and
string skills **do not combine** (math_sci and all_sci - lang = 0), and the
mixed string+integer tasks got nothing, because the DSL had no operator that
turns an integer into a position, a length-bounded slice, a repeat or a digit
string. BRIDGE adds those operators, a mixed int/str domain, a bridge
training set, and lets INVENT run on string goals. Everything is behind
**`NOMAD_BRIDGE`, default OFF until proven**. No transformers, no neural
weights, no LLM; WITNESS certifies; the cold control's code is untouched.

## What is built

- **Operators** (`nomad/world.py`, mirrored in `feed/nomad_feed_check.py`; the
  existing op-table test pins both): `at(s, i)` = s[i]; `take(s, i)` = first
  i characters; `drop(s, i)` = all but the first i; `srep(s, i)` = i copies;
  `itos(i)` = decimal digits. All are partial: a negative or out-of-range
  index, a negative count, a count above `MAX_STR` is `Invalid`.
  `str -> int` already existed (`strlen`); `stoi` is deliberately absent
  (a digit-string parse has no certified use yet).
- **Opset `bridge`** = the `text` opset + the five bridges. `str`, `text` and
  every other opset are unchanged. `world.opset_of(task)` resolves a `bridge`
  task to the `text` opset while `NOMAD_BRIDGE` is off, so with the switch off
  no search anywhere changes.
- **INVENT on string goals** (switch on, `NOMAD_BRIDGE_INVENT` default on): the
  INVENT phase (invented blocks over the task's inputs; invented primitives as
  single nodes) now also runs for `str` goals. It is always *deferred*: it
  spends only the budget the regular levels left (a first version ran before
  them and cost ~1,500 evaluations per task for no certified program, so it was
  rejected on dev). Integer-only machinery (learned scales, derived constants,
  residual add / sub / mul anchors) is skipped for string goals. Synthetic rows
  for behavioural dedup of mixed int/str inventions use indices 0..6 (so `at`
  is not always invalid); no existing invention has both int and str holes, so
  nothing existing changes.
- **Domain** (`nomad/bridge.py`): inputs `bw bw2 bk bj bs` (disjoint from every
  other catalogue); the separator is an input column, as in TEXT. Reference
  trees are checked against independent Python truth. Three sets of families:
  - `TRAIN_FAMILIES` (16): small bridge blocks on `(s: str, x: int)`, fixed
    literal rows (WORLD style): take, drop, at, repeat, `itos(len)`, length
    tag, rotate (+ upper, + reversed), tail, chop, number-first, head repeat,
    upper-take, `itos(len + x)`, digits of `len * x`.
  - `DEV_CATALOGUE` (29): what the mechanism was tuned on, uncommitted dev
    suites only (`/workspace/nomad/bridge_dev/`, seeds 7, 11).
  - `CATALOGUE` (27) -> sealed suite: written blind, as *compositions* of the
    training blocks (cut gaps, frames, labels, repeats, derived lengths), never
    run through a search except the generator's cold control.
- **Sealed suite** `scripts/bridge_suite.py`, seed 20261121:
  `data/deep/bridge_suite.json`, sha256
  `ddc3a93d1972e265f6822c8052782b0ee4c62a36161711a5fe66927aa2bb712f`: 5 easy
  (cold certifies at 10k; never scored), **22 sealed hard**; the lookup guard
  (every trained arm's memory under every type-preserving renaming, plus easy
  twins) dropped none.

## Arms (`python3 scripts/bridge_judge.py`, budget 10,000, max_size 7, NOMAD_BRIDGE=on)

`cold` (prior=None); `empty` (WorldPrior(), every feature on); **`trained`**
(16 WORLD families + 14 easy science + the 16 bridge training tasks; scored);
`world_only` (no bridge training), `bridge_only`, `trained_port_off`,
`trained_invent_off`, `trained_binvent_off` (INVENT not run on string goals),
`trained_bridge_off` (NOMAD_BRIDGE=off; memory only) are reported.

## Pre-registered criteria (committed before any sealed measurement)

All must hold to flip `NOMAD_BRIDGE` on by default:

1. **Trained beats empty** on the sealed suite: `trained` certifies >= **+3**
   over `empty`, or >= 0 more with >= **25% fewer** evaluations.
2. **Gains vanish with an empty field**: `empty - cold <= 1` certified (else the
   gain is search, not learning, and is labelled so). Reported with it:
   `trained_port_off`, `world_only`.
3. **No task worse than cold** for `trained` and `empty` on the sealed suite
   (certified lost, or more evaluations than cold on a task cold certifies).
4. **No per-task loss on the existing sealed suites** with the switch on versus
   off: deep, science hard, transfer 1-4, text, every arm of every judge
   (`scripts/bridge_regress.py compare`: a loss is certified-off-not-on or more
   evaluations).
5. **LOFO total <= 5,883, worst 1.0x** with the switch on; **the full test suite
   passes**.

Decision rule: all five pass -> default on in a follow-up commit with the
results; otherwise it stays off and an honest negative-result note is
committed. Nothing under `results/` is overwritten.

## Dev expectations (stated before the sealed run; dev seeds 7 and 11)

On the dev catalogue the trained arm certified 9 / 8 of 21 hard tasks against 0
for cold and empty (evaluations -12.6% / -16.7% vs empty); `trained_port_off`
0 (so the gain is renamed memory: PORT), `world_only` 3 (so the bridge
training matters, not just the WORLD memory), INVENT on string goals **0** (the
field holds only tiny string inventions such as `itos(strlen(a))`; most
bridge programs recur once). `trained_bridge_off` (memory only, bridge ops not
in the search) certified as many or one more with fewer evaluations: the
operators matter for *training* (the bridge families can only be certified
with them) and the transfer is carried by memory, not by searching them.
Expectation for the sealed suite: criteria 1-3 pass with a smaller margin than
dev; INVENT on strings adds nothing measurable.
