# PRIMREC: primitives learned only by cross-family recurrence (UNSEALED, switch OFF)

Status (2026-11-27, ET): code landed with `NOMAD_PRIMREC` **default off** (it also needs `NOMAD_MEMIDX`).
The dev measurements show the gate has nothing real to learn from in the current trained field, so no
sealed suite was pre-registered or measured and no seed was taken. Same outcome class as CERT and MEMIDX.

## Why this was tried

docs/MEMIDX.md found that PRIM's gain came from the closure rule `g(f(a, b), f(b, a))`, which turns any
asymmetric function (even a shuffled field's random `sub`) into `|a - b|`. Its recommendation: derive a
primitive only when the field certified it repeatedly in different families, so shuffled memory cannot
produce it. PRIMREC is that rule, with no closure.

## What it is

- `memidx.recurring(prior)`: every subtree of every certified library block and program, size
  `REC_MIN_SIZE = 5` .. `MAX_SIZE = 7` (a composite: at least two operators), with 1..`REC_ARITY = 2` int
  variables, is renamed to parameters (`_canon_vars`) and keyed by behavior (fingerprint on fixed synthetic
  probe rows; never a task's rows). A behavior class becomes a primitive only when it occurs in at least
  `REC_FAMILIES = 2` distinct source families (`library_src` / `programs_src`). It is input-agnostic (bound to
  any task's int inputs) and behavior-indexed (any tree shape that computes it counts).
- It enters the MEMIDX index (weight 1.0 per supporting family) and is used only by the existing MEMIDX
  stage, which is funded only by MERGE's unspent skips, WITNESS-gated, with the rejection record restored
  on a miss.
- Control `NOMAD_MEMIDX_CONTROL=rewired:<seed>` also permutes the family labels over memory slots, so
  recurrence is counted against the wrong families.
- One guard added to the MEMIDX second-order step (skip functions with more than two parameters); it can
  only matter when `REC_ARITY > 2`, which is not the committed setting.

## Dev evidence (uncommitted dev suites; nothing sealed)

Cached NOVEL-curriculum field (`trained_on`), budget 10,000, PYTHONHASHSEED=0, certified hard tasks. The
dev suites are the MEMIDX ones (dv7 / dv9 are dominated by `|a - b|` tasks; novel_d11 / d13 are NOVEL
catalogue). `off` = MEMIDX off (current default), `memidx` = MEMIDX on, `on` = MEMIDX + PRIMREC.
`shN` = `novel_judge.shuffled(field, N)` with MEMIDX only / with PRIMREC.

Recurrence census (number of recurring primitives found):

| setting | real | sh1 | sh2 | sh3 | sh4 | sh5 |
|---|---|---|---|---|---|---|
| REC_ARITY 2 (committed) | 1 | 1 | 1 | 1 | 1 | 0 |
| REC_ARITY 3 | 5 | 16 | 14 | 17 | 15 | 16 |

The single real one is `ite(sub(a, b), a, 0)` (in piecewise and quotient). The field never certified
`|a - b|` anywhere, so no rule that requires repeated certification can produce it.

Solves (REC_ARITY 2, committed):

| dev suite | cold | empty off / on | off | memidx | **on** | rewired | sh1-5 memidx only | sh1-5 PRIMREC |
|---|---|---|---|---|---|---|---|---|
| dv7 | 0 | 4 / 4 | 6 | 7 | **7** | 8 | 7 9 10 10 8 | 7 9 10 10 8 |
| dv9 | 0 | 2 / 2 | 6 | 7 | **7** | 8 | 6 8 8 8 5 | 6 8 8 8 5 |
| novel_d11 | 0 | 1 / 1 | 9 | 9 | **9** | 9 | 7 6 10 9 7 | 7 6 10 9 7 |
| novel_d13 | 0 | 2 / 2 | 9 | 9 | **9** | 9 | 5 7 10 8 7 | 5 7 10 8 7 |

PRIMREC on is identical to MEMIDX alone, in solves and evaluations, on every dev suite (the one recurring
primitive never fires). Empty and cold are untouched.

Bounded tuning step (the only one): REC_ARITY 3. Real memory: still exactly the MEMIDX-only score
(7 / 7 / 9 / 9). Shuffled fields: PRIMREC *gains* there (dv7 sh4 10 -> 11, dv9 sh5 5 -> 7, d11 sh1 7 -> 8,
sh3 10 -> 11, d13 sh1 5 -> 7), because in a seven-operator DSL a scrambled field makes more chance
cross-family coincidences than the real field, whose programs concentrate in one family
(`polynomial/growth`, 51 of 99 programs). Rewired dv7 6.

## What it shows

1. The gate is honest: a closure-free recurrence rule does not hand shuffled memory the `|a - b|` gift.
2. But the real field has no cross-family composite recurrence to learn from. The primitives that would
   help (`|a - b|`) were never certified, and the recurrences that exist are DSL-chance level: scrambled
   memory produces as many or more.
3. On these dev suites even MEMIDX alone is no better with real memory than with scrambled memory
   (dv7: real 7 vs shuffles 7-10). The bottleneck is the field's content and curriculum, not the index.

## Why not sealed

Pre-registration requires dev to show on > off and real > every shuffle. Dev shows on == memidx and
shuffled >= real. Measuring a sealed suite would burn a seed on a known failure. No seed was reserved.

## Next, if picked up again

- Learned primitives need a curriculum in which the same sub-behavior is genuinely certified in several
  families (for example, distance tasks in two domains). Then PRIMREC can be tested with real vs shuffled
  memory on a fresh sealed suite of unseen domains.
- Recurrence should be scored against a chance baseline (how often scrambled memory recurs), not a
  raw count of 2.

## Switch off = old behavior

With `NOMAD_PRIMREC` off, `memidx.build` never calls `recurring`. With `NOMAD_MEMIDX` off nothing is built.
Tests: `tests/test_primrec.py`.
