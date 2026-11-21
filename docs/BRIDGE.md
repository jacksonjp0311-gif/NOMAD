# BRIDGE: do integer and string skills combine? (pre-registered)

TEXT (docs/TEXT.md) ended with: string transfer passes narrowly, integer and
string skills **do not combine** (math_sci and all_sci - lang = 0), and the
mixed string+integer tasks got nothing, because the DSL had no operator that
turns an integer into a position, a length-bounded slice, a repeat or a digit
string. BRIDGE adds those operators, a mixed int/str domain, a bridge
training set, and lets INVENT run on string goals. Everything is behind
**`NOMAD_BRIDGE`, default OFF until proven (flipped ON after the sealed run below)**. No transformers, no neural
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

## Sealed result (measured once, 2026-11-21, after `67e1459`; `results/bridge/`)

`python3 scripts/bridge_judge.py`, sha `ddc3a93d...b712f`, 22 hard:

| Arm | Certified /22 | Evaluations |
|---|---|---|
| cold | 0 | 201,051 |
| empty (no memory) | 0 | 201,051 |
| **trained** (WORLD + science + bridge training) | **6** | 182,449 (-9.3% vs empty) |
| world_only (no bridge training; report) | 3 | 195,407 |
| bridge_only (report) | 9 | 183,151 |
| trained, PORT off | 0 | 201,051 |
| trained, INVENT off / INVENT-on-strings off | 6 / 6 | 182,449 / 182,449 |
| trained, NOMAD_BRIDGE=off (memory only; report) | 7 | 167,779 |

| Criterion | Bar | Result | Met? |
|---|---|---|---|
| 1. trained vs empty | >= +3 or 25% fewer | **+6** (6 vs 0), -9.3% | yes |
| 2. gain vanishes with an empty field | empty - cold <= 1 | 0 (empty 0, PORT off 0) | yes |
| 3. no task worse than cold | 0 | 0 (trained, empty, and every report arm) | yes |
| 4. no per-task loss on existing sealed suites, switch on vs off | 0 | **0 losses, 0 gains, outputs byte-identical** on deep, science hard, transfer 1-4, text, and the INVENT secondary sweep (381 per-task records, every arm) | yes |
| 5. LOFO <= 5,883, worst 1.0x; tests | | 5,883, worst 1.0x; 424 tests pass | yes |

Decision: all five pass, so `NOMAD_BRIDGE` is **on by default** (commit below).

Honest reading:

- The gain is **renamed memory (PORT)**, not search and not INVENT: empty = cold = 0, PORT off = 0,
  INVENT on strings changes nothing (the field's string inventions are tiny:
  `itos(strlen(a))`, `concat(a, a)`; most bridge programs recur once, below MIN_USES = 2).
- The WORLD-only field (no bridge training) certifies 3, so bridge training is what lets integer and
  string skills combine; 6 of 22 is a modest transfer, not a solved one.
- **bridge_only (9) beats trained (6)** and **bridge_off (7, fewer evaluations) beats bridge_on (6)**:
  the broad WORLD memory dilutes the narrow bridge memory, and exposing five more operators to the
  cold stage enlarges every pool for programs that memory already supplies. The operators matter for
  *training* (bridge families are uncertifiable without them), not for searching. A follow-up could
  gate the extra operators to the post-memory stage; not attempted here.
- Because default-on changes no existing result (byte-identical with the switch on), it is safe, but it
  also means the live body does not benefit until its curriculum contains bridge families; that is not
  part of this step.

## Live curriculum (`NOMAD_LIVE_BRIDGE`)

The running body now practises number-text tasks: with `NOMAD_LIVE_BRIDGE=on` the 16 bridge
training families (`nomad.bridge.train_tasks`, opset `bridge`, the same tasks the sealed judge's
`trained` field learns from) join the live curriculum as one more domain, `bridge`, at a single
open level (`world_tasks.curriculum_train`). They go through the normal twin pair (cold control,
then the field), the WITNESS receipt, the queue and the single learner (`by_family` /
`domain_of` resolve them), and the curriculum's usual rules: never-attempted, not-yet-beaten
families first, parked after `patience` attempts without beating the control. Requires the
bridge opset itself (`NOMAD_BRIDGE`, on).

- **Code default: off.** Off, `curriculum_train()` *is* `world_tasks.TRAIN`; verified: `choose()`
  on 205 prefixes of the live scoreboard (7,366 rows) picks byte-identical families / candidates /
  open levels before and after the change. `all_training()` (evolve benchmark, feed, sealed judges)
  never includes bridge families.
- **The body workflow turns it on**: `.github/workflows/nomad-body.yml` passes
  `NOMAD_LIVE_BRIDGE: ${{ vars.NOMAD_LIVE_BRIDGE || 'on' }}`; set the repo variable
  `NOMAD_LIVE_BRIDGE=off` to switch it off without a commit.
- Smoke (local, temp `NOMAD_DATA`, `--max-cycles 6`, inline learner, evolve on): on -> the six
  pairs were br_at, br_chop, br_digits, br_drop, br_head_rep, br_itos_len (all certified, learner
  absorbed all six); off -> div_pair, first_last, max_pair, min_pair, mod_pair, range, as before;
  both exit 0, lease released, no cycle errors.
- Expected effect on the live body: the bridge families have 0 attempts, so the next ~16-64 pairs
  are mostly bridge families until each is beaten or parked; then the usual rotation resumes.
