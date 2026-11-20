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

## Live check after the body handoff (2026-11-20, 11:49 UTC)

The body that started at 09:35 UTC (run 44712062354) runs the cheaper search. Its live numbers, measured honestly against the cold control:

- **Live twin pairs (body run, 09:36-11:49 UTC):** 319 WORLD pairs over 16 training families, all 319 certified in both arms. The field used 19,180 evaluations against 113,840 for cold (ratio 0.168).
- **Live held-out probe (`data/continuous/world_heldout.json`, field_witnessed 1,319, library 5 blocks):** absdiff is **not certified at 10k** in either arm. quartic_sum: field certified at 13,463 where cold hits its frontier at 8,414. last_first_upper (332) and sum_minus_max (203) are ties.
- **Why the 8,608 absdiff win isn't live:** the test field (`tests/test_world.py::_train`) keeps four int library atoms (`min(x, y)`, `sub(x, y)`, `x*x`, `y*y`). The live field keeps three: `min(x, y)` is not among its 5 blocks. With the live library, staged search on absdiff reaches 11,244 evaluations without a budget limit and stops at a public-row fit (`mod(sub(x, y), mul(x, 3))`) that WITNESS rejects on the frozen rows. So the 8,608 result depends on the library the field happens to hold. It is a test-field result, not a live one.
- No parameter was changed for this. Choosing library blocks to suit absdiff would be tuning to a held-out. The feed packet reports the live probe as measured (absdiff `field_beats_control: false`).

## Variation, novelty and payoff memory (2026-11-20)

Certified patterns are now perturbed (operator swap, constant flip, variable swap, argument reorder), novel mutants are kept in a bounded archive even when not yet better, and a per-situation payoff memory biases which perturbation is tried first. LOFO stays 5,883 = cold (worst 1.0x). Held-outs: no gain yet, absdiff 8,608 -> 8,640 and quartic_sum 21,343 -> 21,375 (32 mutants tried, none fit), string/list ties. Details and caveats: `docs/VARIATION.md`.

## Case split: divide-and-conquer unification (2026-11-20)

A new **organ** (not learning): `nomad/casesplit.py`, EUSolver-style. In the field arm's staged search, right after the cold stage (cold search below max_size) misses, it reuses the int programs that stage already enumerated: *terms* that are right on a subset of the public rows and *conditions* whose `> 0` mask separates those subsets, assembled into `ite(c, t1, t2)` with the smallest total size (Occam). Charged: 1 evaluation per condition tested, per term tested and per assembled candidate (the values were already paid for in stage 1, so this is a double charge); only bit-mask table lookups are free. Eligible: int output and an opset with `ite` (the `int` opset; not genesis, str or list). A field with no library for a task now also runs staged when the split is eligible. The cold control never splits. WITNESS + final split certify, as for every program. `NOMAD_CASESPLIT=off` disables it; `NOMAD_CASESPLIT=depth2` also allows one nested split (off by default, see below).

Development used a separate dev suite (`scripts/deep_suite.py --seed 7`, not committed); the frozen suite (`docs/DEEP_SUITE.md`, committed with its SHA-256 in `7dde50b` before any field measurement) and the held-outs informed nothing. On the dev suite: depth 1 certified 4/40; depth 2 added 0 (0 of 6 nested candidates passed WITNESS, each pre-empting the library stage), so it is opt-in; requiring 2+ public rows per leaf (1/40) and a leave-one-row-out stability check (2/40) were worse and were dropped.

Measured with `python3 scripts/casesplit_probe.py` (pre-registered metric in `docs/DEEP_SUITE.md`):

| Measure | Cold | Cold + split | Field, split off | Field (split on) |
|---|---|---|---|---|
| LOFO total, 16 families | 5,883 | 5,883 | 5,883 | 5,883 (worst 1.0x) |
| Deep suite certified, 40 tasks cold misses @10k | 0 | 6 (15%) | 0 | **6 (15%)** |
| Deep tasks worse than cold | | 0 | 0 | 0 |
| absdiff @10k (offline test field) | not found | rejected split, 4,296 | certified, 8,640 | **rejected split, 4,296** |
| absdiff @10k (live field, read-only) | not found | | not found, 10,000 | rejected split, 4,296 |
| quartic_sum @150k (test / live) | not found | not found | 21,375 / 13,495 | 21,375 / 13,495 |
| last_first_upper, sum_minus_max | 332, 203 | ties | ties | ties |

- **Pre-registered bar missed:** 6/40 = 15%, below the 25% target. LOFO held (5,883 = cold, worst 1.0x) and no deep task got worse than cold.
- **It is the mechanism, not the learned field:** cold + split certifies exactly the same 6 tasks with the same counts as the trained field. Field without the split certifies 0.
- **Overfitting is the limit:** 5 public rows. The split fired on 16 deep tasks; 6 passed WITNESS, 10 were public-row fits that WITNESS rejected. 13 of the 40 deep tasks are ones where cold itself stops on a WITNESS-rejected fit inside stage 1, which the field shares by construction, so they are unwinnable for any post-stage-1 organ.
- **Held-out cost (report-only, not targeted):** on the offline test field, absdiff's Occam split `ite(sub(x, 2), sub(x, y), 3)` fits the public rows, is rejected by WITNESS, and pre-empts the library stage that used to certify absdiff at 8,640; the absdiff test is now pinned with the split off. Live, absdiff was not certified before either (the live library lacks `min(x, y)`) and still is not.
