# MEMIDX and PRIM: behavior-indexed memory and learned primitives (UNSEALED, switches OFF)

Status (2026-11-26, ET): code landed with `NOMAD_MEMIDX` and `NOMAD_PRIM` **default off**. The dev
measurements predict that the content criterion (real memory beats scrambled memory) fails, so no sealed
suite was pre-registered or measured. This is the same outcome CERT had (docs/CERT.md): honest code, switch
off, no seal.

## What it is

- **MEMIDX** (`nomad/memidx.py`): every remembered int tree (library blocks and whole certified programs,
  size 3..7, at most 2 int variables) is renamed to parameters `_v0, _v1` and indexed by *behavior* (its
  fingerprint on fixed synthetic probe rows, never a task's rows). Blocks that compute the same thing under
  different input names merge into one entry whose weight is their summed learned usage. Entries are bound
  to a new task's int inputs by injective assignment (one per unordered pair when symmetric). Retrieval
  order: weight, then size, then tree. `FUNCS = 16` functions per task.
- **PRIM**: for every learned asymmetric 2-parameter function `f`, the swap closure `g(f(a, b), f(b, a))` for
  `g` in max / min / add is derived; it enters the index only when it is new, non-constant and symmetric.
  From a learned `sub` it yields `|a - b|`. The only hand-written part is the closure rule.
- **Search stage** (`world._staged_gen` -> `memidx_stage`, inside `port_body`): instances, residual lookups
  (add / sub / reversed sub / mul), max / min pairs, learned-scale targets, and one second-order step. It is
  funded **only by MERGE's unspent skips** (like LET2 / AGREE), WITNESS-gated, at most `MEMIDX_REJECTS = 4`
  rejections, and the gate's rejection record is restored on a miss, so it is budget-neutral when it can't help.
- Control `NOMAD_MEMIDX_CONTROL=rewired:<seed>` (judge only): learned weights permuted across functions,
  and PRIM combines `f(a, b)` with a seeded *different* function `h(b, a)`.

## Dev evidence (uncommitted dev suites only; the sealed seed was never measured)

One cached NOVEL-curriculum field (`trained_on`), budget 10,000, PYTHONHASHSEED=0. Certified hard tasks.
`shN` = `novel_judge.shuffled(field, N)` (shapes, sizes, inputs and counts kept, every operator replaced by a
random one of the same type signature) with MEMIDX + PRIM on.

| dev suite | cold | off | **on** | rewired | sh1 | sh2 | sh3 | sh4 | sh5 |
|---|---|---|---|---|---|---|---|---|---|
| dv7 (MEMIDX catalogue, 20 hard) | 0 | 6 | **12** | 13 | 7 | 13 | 10 | 14 | 13 |
| dv9 (MEMIDX catalogue, 20 hard) | 0 | 6 | **14** | 13 | 8 | 13 | 9 | 13 | 13 |
| novel_d11 (NOVEL catalogue) | 0 | 9 | **13** | 11 | 7 | 8 | 10 | 11 | 9 |
| novel_d13 (NOVEL catalogue) | 0 | 9 | **11** | 10 | 5 | 8 | 10 | 10 | 8 |

Bounded tuning on those dev suites (nothing else was tried):

| setting | dv7 on / best shuffle | dv9 on / best shuffle | d11 | d13 |
|---|---|---|---|---|
| FUNCS 16 (as committed) | 12 / 14 | 14 / 13 | 13 / 11 | 11 / 10 |
| FUNCS 8 | 7 / 15 | 7 / 14 | 9 / 13 | 9 / 11 |
| FUNCS 4 | 7 / 15 | 7 / 14 | 9 / 13 | 9 / 11 |
| PRIM only from top-2 / top-4 weighted sources | same as FUNCS 16 | same | same | same |

Earlier dev sweeps (FUNCS 8 / 12 / 16 / 24 / 40, split targets) are summarized in the code comments.

## What it shows

1. **On beats off** clearly (dv7 6 -> 12, dv9 6 -> 14, NOVEL dev 9 -> 13 / 11), with fewer evaluations.
2. **But scrambled memory does about as well.** On the MEMIDX-catalogue dev suites at least one shuffled
   field ties or beats real memory (dv7: shuffle 4 has 14 vs real 12). The reason is visible in the trees:
   shuffled fields still contain asymmetric two-argument functions (often a surviving `sub`), and PRIM's swap
   closure turns *any* of them into a useful symmetric primitive such as `max(sub(a, b), sub(b, a))`. The
   gain comes from the closure rule over the DSL, not from what the field learned.
3. Shrinking the index (FUNCS 4 / 8) makes this worse: real memory's top-weighted functions aren't the ones
   that help new domains, while some random shuffles happen to put a good one on top.
4. **Rewired** (weights permuted) matches real memory (13 vs 12, 13 vs 14): the learned usage order
   carries almost nothing.
5. On the NOVEL dev suites real memory does beat every shuffle (+2, +1), but by margins the MEMIDX dev
   suites contradict, so a sealed run would most likely be a FAIL on the content criterion.

## Why not sealed

The planned criteria (3-arm judge plus switch on/off; shuffled and rewired controls; empty_on == empty_off;
cold untouched; on beats off AND real beats every shuffle on a fresh unseen-domain suite; zero per-task losses
on all existing judges; LOFO 5,883 worst 1.0x) were never pre-registered, because dev already predicts the
content criterion fails. Measuring anyway would burn a sealed suite on a known-likely failure.
Seed **20270917** (`scripts/memidx_suite.py`) is reserved by MEMIDX. A candidate suite was generated off-repo
by the cold control but never measured by any arm and is not committed; a future MEMIDX attempt should still
take a fresh seed.

## Switch off = old behavior

With `NOMAD_MEMIDX` off nothing is built and `memidx_stage` never runs (`port_bank` only adds the MEMIDX
flag to its existing gate). Full test suite with switches off: 643 passed, 6 skipped.

## Next, if this is picked up again

- Make the primitive *learned*, not closed by a fixed rule: derive a primitive only when the field certified
  it at least twice in different families (e.g. both `max(sub(x, y), sub(y, x))` uses), so shuffled fields
  cannot produce it.
- Or test PRIM honestly as a DSL change (a cold-search operator) with its own sealed suite, since that is what
  the evidence says it is.
