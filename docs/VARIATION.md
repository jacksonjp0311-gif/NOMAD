# VARIATION: perturb, reward novelty, remember what paid (2026-11-20)

Three organs layered onto WORLD search (`nomad/variation.py`). WITNESS still certifies; search, mutation, novelty and memory never do. No transformers, no weights, integer/float counts only. Deterministic (fixed probe literals, seeded hash tie-breaks).

## 1. Variation operator

`mutants(tree, opset, inputs)` makes every one-step perturbation of a certified pattern instead of only re-emitting it:

| Kind | What it does | Example |
|---|---|---|
| `op_swap` | operator -> another operator of the task's opset with the same signature | `min(x, y)` -> `max(x, y)` |
| `const_flip` | integer constant -> another world constant (0-3) | `sub(x, 0)` -> `sub(x, 2)` |
| `var_swap` | input variable -> another input of the same type | `sub(x, 0)` -> `sub(y, 0)` |
| `reorder` | swap two same-typed arguments of a non-commutative op | `sub(x, y)` -> `sub(y, x)`; `ite` branches |

Sources: whole programs the sleep learner kept from certified treatment packets ("elites", cap 64), the field's certified library blocks (inlined), and novelty-archive entries (stepping stones). A task never mutates its own family's elites.

Where mutants enter search (field arm only; the cold twin control never reads variation state):

- **Unfamiliar family (staged search):** stage 1 is still exactly the cold search below `max_size`. Only if it misses, up to `SEARCH_TRIES = 32` mutants are tried as whole programs (1 evaluation each), then stage 2 (library atoms) resumes as before.
- **Familiar family or no library:** mutants are tried only *after* the search has failed, with the budget it left unused. A search that finds a program is returned untouched.

A mutant that fits the public rows is returned like any other candidate and then goes through WITNESS on withheld rows and the final split (`world.evaluate`). `tests/test_variation.py::test_mutation_alone_never_certifies` shows a public-row fit (`max(x, y)` via `op_swap`) that WITNESS/final reject.

## 2. Novelty reward

Behaviour = outputs on fixed probe inputs per input signature (`PROBES`; literals chosen once, independent of every task and held-out). Novelty = mean distance to the 3 nearest known behaviours (archive, elites, library). Retention score = fitness + 0.5 x novelty, fitness = fraction of public rows right. A mutant with novelty >= 0.34 is kept **even at fitness 0**. Bounds: archive cap 48 (lowest score evicted), at most 32 mutants per search and 12 per awake exploration, mutant size <= 9. The archive only adds variation *sources*; it can never raise a search's cost above those caps.

## 3. Payoff memory

`PayoffMemory`: per situation and kind, `[paid, tried]`. Situation = cheap public-row features: `opset|arity|out type|output sign|output-size relation` (e.g. `int|2|int|nonneg|shrink`). Score = `(paid + 2g) / (tried + 2)` where `g` is the Laplace rate pooled over all situations, so an unseen situation leans on what paid elsewhere. Mutants are ordered by that score (kind), then source rank, then a seeded hash. Decays with the genome's `decay` like the field.

## Actor/learner split

- **Awake (actor)** reads `data/continuous/variation.json` and writes nothing. Each world pair also runs a bounded exploration (`explore`, 12 mutants of other families' patterns on the training task). Its evaluations are reported in `world_pair()["variation"]` and are **outside** the twin comparison.
- The trace (tried kinds/trees, "paid" mutants) rides in the certified treatment packet (`extra.variation`), or in an uncertified `extra.world = "variation"` packet if the treatment missed.
- **Sleep (single learner)** `consolidate` is the only writer. It refuses held-out and unknown families, re-attests every "paid" mutant itself with `world.certify` on the frozen training task (receipt supported, checksum, final split), recomputes fitness and behaviour itself, and adds the receipt-verified treatment tree as an elite. State is saved atomically with a `.prev` copy under `data/`, so the body's checkpoints commit it with the field.
- Held-out probes read the live state and never enqueue anything. `NOMAD_VARIATION=off` disables search-time mutants and exploration.

## Measured before/after vs cold (`python3 scripts/variation_probe.py`)

Leave-one-family-out on the 16 training families (train 15, solve the 16th):

| | Cold | Field (before) | Field + variation (after) |
|---|---|---|---|
| LOFO total evaluations | 5,883 | 5,883 | 5,883 |
| Worst family vs cold | 1.0x | 1.0x | 1.0x |
| Mutants tried on training families | | | 0 (stage 1 always finds them first) |

Held-outs at their fixed budgets, offline test field (reported, never used to choose anything):

| Probe | Cold | Field before | Field + variation |
|---|---|---|---|
| absdiff @10k | not found | certified, 8,608 | certified, 8,640 (+32: 32 mutants tried, none fit) |
| quartic_sum @150k | not found (frontier 8,414) | certified, 21,343 | certified, 21,375 (+32) |
| last_first_upper @5k | 332 | 332 | 332 (tie) |
| sum_minus_max @5k | 203 | 203 | 203 (tie) |

Offline twin, 2 rounds over the 16 families (last round): cold 5,883 vs field 4,538, identical with and without variation. Exploration spent 339 extra evaluations (outside the twin), 4 mutants paid after re-attestation, archive filled to its cap of 48, 16 elites.

Dry run on a copy of the live `data/` (48 world pairs, sleep every 3; live data untouched): both arms certified in 48/48, field 3,101 vs cold 21,646. Exploration 527 evaluations, 3 paid (`reorder` in `int|2|int|nonneg|shrink`, `op_swap` in `list|1|list|na|same`). Live held-outs: absdiff still not certified at 10k in either arm; quartic_sum 13,463 -> 13,495; string/list ties.

## Honest status

- **No measurable gain yet.** Variation fires only where the existing search has already missed, which never happens on training families, and on the held-outs no one-step mutant of the current elites fits. Cost: at most +32 evaluations on a probe that reaches stage 1.5.
- The LOFO never-worse-than-cold guarantee holds by construction (stage 1 unchanged, fallback only uses leftover budget) and is tested (`test_leave_one_family_out_with_variation_never_worse_than_cold`).
- What it adds is the machinery: novel, not-yet-useful programs are now kept as stepping stones, and the memory now records which perturbations pay off where (so far `reorder` for int pair tasks and `op_swap` for list tasks). Whether two-step paths through the archive start paying will show in the live trace over the next bodies.
