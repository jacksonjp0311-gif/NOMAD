# WORLD: wider program world, curriculum, library, string and list domains

`nomad/world.py` is a typed, bounded program world beside GENESIS. Programs are trees over a fixed operator table and run through NOMAD's own interpreter. There is no Python `eval`. Every operator is total and bounded: division or modulo by zero, `max` of an empty list, a type mismatch, or an oversize value is simply invalid.

| Opset | Operators |
|---|---|
| `genesis` | add, sub, mul |
| `int` | add, sub, mul, div (floor), mod, min, max, ite(c, a, b) = a if c > 0 else b; constants 0–3 |
| `str` | upper, lower, srev, concat, first, last, strlen, add, sub |
| `list` | sort, lrev, tail, sum, len, lmax, lmin, head, add, sub, mul |

Search is bottom-up enumeration with observational dedup over **public rows only**. WITNESS certifies on withheld challenge rows (strings and lists are encoded as exact 48-bit content hashes so WITNESS still recomputes the match itself), then the final split is checked independently. Library calls are inlined before certification, so a certified program stands on its own.

## Field (`WorldPrior`)

- Per-family operator counts (balance: an untrained family keeps the cold order), a global table used only for unknown families, and `decay`.
- **Library learning**: every sub-program (size ≥ 3) of a certified solution is harvested as a named primitive for tasks with the same input signature. The top six by (decayed) use enter search as size-1 atoms. A known family uses the library only if its own certified solutions have reused library parts before.
- Stored at `data/continuous/world_prior.json` (with `.prev.json` last-good). Written only by the sleep learner.

## Curriculum (`nomad/curriculum.py`)

Families are grouped by domain (mathematics, language = strings, coding = lists) and level. Level 2 opens in a domain only after the field has **beaten the control** on every level-1 family: a twin pair where treatment was certified and either control was not, or treatment needed fewer evaluations. A tie is not a win. Unbeaten families come first; after 4 attempts without a win a family is parked so it cannot stall the loop.

## Loop

Each awake `pair()` now also runs one `world_pair()`: control is a cold `WorldPrior` (no family evidence, no library); treatment reads the field. Both arms go to the same scoreboard with kind `world-certified` and per-arm evaluations. A certified treatment becomes a versioned packet; sleep re-verifies the receipt and updates the world field. Sleep then probes the held-out families into `data/continuous/world_heldout.json`. Set `NOMAD_WORLD=off` to skip the world pair.

## Held-out probes (never trained)

Since the staged-transfer change (below), an unfamiliar family searches the cold space up to size 6 first, then adds library atoms for size 7.

| Probe | Needs | Budget | Cold | Field before (order + library) | Field now (staged) |
|---|---|---|---|---|---|
| absdiff = \|x − y\| | wider world | 10,000 | not found (29,660 unlimited) | certified, ~1.7k–7.8k | **not found at 10k**; certified at 19,982 |
| quartic_sum = x⁴ + y⁴ | learned building blocks | 150,000 | **unreachable** (exhausts at 9,603) | certified, ~64k–108k | certified, 23,352 |
| last_first_upper | string world | 5,000 | certified, 358 | certified, ~600–1,468 | certified, 358 (tie) |
| sum_minus_max | list world | 5,000 | certified, 241 | certified, ~250–411 | certified, 241 (tie) |

Budgets were first drafted at 5,000 / 20,000 and raised after one measurement; this is stated in `world_tasks.py`. They were **not** changed for staged transfer, so absdiff now counts as a loss at its budget.

## Unfamiliar families: staged transfer

Cause of the string/list gap, measured by leave-one-family-out (LOFO) on the 16 training families (train on 15, solve the 16th with no family evidence, 2 offline rounds):

| Unfamiliar-family policy | LOFO total evaluations | Worst family vs cold |
|---|---|---|
| cold order, no library (control) | 12,972 | 1.0× |
| field global order, no library | 14,955 | 3.8× |
| cold order + library | 18,001 | 3.9× |
| field global order + library (old) | 14,375 | 13× |
| 1:1 hedge of old field and cold | 17,470 | 2.1× |
| **staged: cold to size 6, then cold order + library** | **12,972** | **1.0×** |

The cross-family operator order and library atoms do not transfer on average; library atoms only pay when the program is deeper than the cold space reaches. Staged transfer was chosen on the LOFO numbers, before the held-outs were measured with it. Familiar families still use their own order and library. Cost: anything that needs library atoms pays the full shallow cold search first (absdiff now loses at 10k).

On trained families, the field typically reaches the same certified program with far less search after one certified attempt (offline 48-cycle run: max/min/mod/div 86–179 → 8; pick_gt 9,561 → 921; double_lower 80 → 8; second_smallest 113 → 12). A family's first field attempt now costs exactly the cold search when the program has ≤ 6 nodes; sort_desc never beat cold (17 vs 17–28) and is parked.

## Honest limits

- String and list held-outs show **no transfer**: staged transfer ties cold there; it no longer loses, but it does not win either.
- absdiff no longer fits its 10k budget under staged transfer.
- Programs are still tiny (size ≤ 7 nodes, ≤ 6 library atoms). This is not unrestricted coding.
- Domain names label small task families. "Language" means a few string transforms, not language understanding.

## Adaptive cold-stage size: tried on LOFO, not adopted (2026-11-20)

Question: can the cold stage of staged transfer be sized adaptively so absdiff fits its 10,000 budget again without losing the "never worse than cold" LOFO property? Measured with `scripts/lofo_stage_probe.py` (LOFO priors, cold vs library-augmented search at each max_size).

- absdiff's cheapest library route is a size-5 program (`max(@sub(x,y), sub(y,x))`-class) costing 8,480 library-search evaluations; a cold stage can therefore be at most ~1,500 evaluations (cold to size 4 costs 414, to size 5 costs 4,374) to stay under 10k.
- On LOFO, cold solves most families within 80-900 evaluations, but pick_gt needs 9,561 cold and its library search needs 11,396. Any cold stage short enough for absdiff (cold to size 4, then library) makes pick_gt ~11.8k vs 9.6k cold, and square_plus_y, ysquare_minus_x, first_last and range 2-4x worse than cold.
- Lock-step or geometric (iterative-deepening) interleaving of cold and library search keeps the loss bounded (a constant factor) but not zero, and absdiff needs the library arm to get nearly the whole budget, so a share small enough to protect LOFO cannot solve it.
- absdiff and pick_gt are indistinguishable at the point where the choice must be made (both unsolved by cold and library search to size 4), so no principled familiarity or confidence signal separates them. Fitting a signal to that pair would be tuning to a held-out.

Result: no change to `synthesize`. Staged transfer keeps LOFO = cold (12,972, worst 1.0x), string/list ties, and absdiff remains a loss at 10k (certified at 19,982). Trade-off stays explicit: strict never-worse-than-cold and a 10k absdiff win are incompatible with the current library search; a cheaper library search (not a different stage size) would be the next lever.


## Cheaper search: exact redundancy skips + resumed library stage (2026-11-20)

Lever: make the search cheaper, not the cold stage shorter. Two changes, both judged on leave-one-family-out (LOFO) first; held-outs were measured afterwards and inform no parameter.

1. **Exact redundancy skips (shared engine, both arms).** `world._redundant` skips a combination from the children's cached public-row values when its result is provably invalid or provably equal to a child's values or an integer-constant atom (both already deduped at a smaller size): `ite` with a condition that is >0 on every row or <=0 on every row, or with equal branches; `div`/`mod` by a divisor with a zero; `div(a, 1)`; `sub/min/max/div/mod(a, a)`; `a + 0`, `0 + b`, `a - 0`; `mul` by all-0 or all-1. A skip costs no evaluation (like the existing commutative-order skip). Pools, offers and the program found are identical with and without it (test: same tree on every training and held-out task). On absdiff's cold size-6 space, 7,175 of 11,496 evaluations were `ite` duplicates.
2. **Resumed library stage.** Stage 1 is still exactly the cold search below max_size. Stage 2 now resumes from stage 1's pools: combinations whose children all came from stage 1 and whose size is below max_size were already evaluated there, so only combinations touching a library-stage entry, plus the whole max_size level, are evaluated. A value that a library tree reaches at a smaller size than stage 1 did is re-entered at that size, so reach is unchanged (test: staged finds a program whenever a from-scratch library search does).

Comparability: the redundancy skips also lower the **cold control's** counts, so evaluation numbers before and after this change are not comparable; within a run both arms share the engine, so twin deltas stay fair.

| Measure (engine after change unless noted) | Cold | Field (staged) |
|---|---|---|
| LOFO total, 16 families | 5,883 | 5,883 (every family = cold, worst 1.0x) |
| LOFO pick_gt (largest) | 3,283 | 3,283 |
| absdiff @10k | not found | **certified, 8,608** |
| absdiff unlimited | 21,264 | 8,608 |
| absdiff, skips only (restart stage 2) | | 11,130 |
| absdiff, resume only (old engine) | 29,660 | 16,902 |
| absdiff, before (old engine, restart) | 29,660 | 19,982 |
| quartic_sum @150k | not found (8,414, frontier) | certified, 21,343 |
| last_first_upper @5k | 332 | 332 (tie) |
| sum_minus_max @5k | 203 | 203 (tie) |

Before (old engine) LOFO was 12,972 = 12,972. Neither change alone fits absdiff in 10k; together they do, while LOFO stays never worse than cold by construction (stage 1 is still the exact cold search). String and list held-outs remain ties, not wins.
