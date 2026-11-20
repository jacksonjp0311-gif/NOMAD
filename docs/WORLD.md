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

| Probe | Needs | Budget | Cold | Field after a short curriculum (2 rounds offline) |
|---|---|---|---|---|
| absdiff = \|x − y\| | wider world | 10,000 | not found (budget) | certified, `sub(max(x, y), min(x, y))`, ~1.7k–7.8k evaluations |
| quartic_sum = x⁴ + y⁴ | learned building blocks | 150,000 | **unreachable** (size 15 > 7; cold exhausts the full space at 9,603) | certified via library `mul(x, x)`, `mul(y, y)`, ~64k–108k evaluations |
| last_first_upper | string world | 5,000 | certified, 358 | certified, ~600–1,500: **no win** |
| sum_minus_max | list world | 5,000 | certified, 241 | certified, ~250–430: **no win** |

Budgets were first drafted at 5,000 / 20,000 and raised after one measurement; this is stated in `world_tasks.py`. For absdiff the robust fact is the cost ratio at an unlimited budget (field with library 7,820 vs cold 29,660 in one run). For quartic_sum, cold cannot reach the program at any budget within `max_size` 7.

On trained families, the field typically reaches the same certified program with far less search after one certified attempt (offline 48-cycle run: max/min/mod/div 86–179 → 8; pick_gt 9,561 → 921; double_lower 80 → 8; second_smallest 113 → 12). A family's first field attempt can cost more than cold when library atoms widen the search (square_plus_y 296 → 454 first, 53 later); sort_desc never beat cold (17 vs 17–28) and is parked.

## Honest limits

- String and list held-outs show **no transfer**: the field is slower than cold there.
- Programs are still tiny (size ≤ 7 nodes, ≤ 6 library atoms). This is not unrestricted coding.
- Domain names label small task families. "Language" means a few string transforms, not language understanding.
