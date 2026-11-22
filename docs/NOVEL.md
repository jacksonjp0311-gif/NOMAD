# NOVEL: honest generalization to never-trained task families (measurement only)

This is a **measurement**, not a new ability. Nothing in `nomad/` changes. The question: when NOMAD
meets task families it has never trained on, and no curriculum, dev suite or sealed suite in this
repository contains, does what it learned elsewhere help? And does the current NOMAD (every switch
turned on since Nov 20) transfer better than the older NOMAD?

Pre-registered here, committed and pushed **before** any field arm is measured on the suite. Only the
cold control and the memory-lookup guard have touched the suite (that is how every sealed suite is built).

## Task families (scripts/novel_catalogue.py)

All on the existing `int` opset (add, sub, mul, div, mod, min, max, ite; constants 0-3), no new operator.

| family | what | inputs | why it is new |
|---|---|---|---|
| `coord` | lattice coordinate geometry on two points P, Q: taxicab, Chebyshev and squared distance, dot / cross product, bounding-box area and perimeter, triangle area, lattice midpoint, interval overlap | `px py qx qy` | no catalogue has points or coordinates; the geometry catalogues (TRANSFER, TRANSFER-2) are lengths, areas and volumes of solids |
| `digits` | decimal place value on one number with the base stated as a constant column `tn = 10`: digit sum, digit swap, rounding, dropping a digit, digit product, casting out nines, alternating sum | `nn tn` | no int catalogue reads digits; BRIDGE's `itos` / "digits in" tasks count string length, not place value |
| `order` | order statistics of plain numbers: median of three, clamp, range, sum of the two largest, gap to the top, how many exceed a threshold, second largest and middle two of four | `oa ob oc od` | no catalogue has median / clamp / ranking over scalars; the trained `second_smallest` / `range` are list tasks on the `list` opset (`sort`, `lmax`) |

Absence checks (run on d64d3a1, the base of this work):

- Keyword grep over `nomad/` and `scripts/` for `manhattan`, `taxicab`, `chebyshev`, `coordinate` (only
  in non-task code), `dot product`, `median`, `clamp`, `digit` in int catalogues, `place value`,
  `cipher`, `weekday`: no task catalogue matches. Candidates I rejected because they **are** covered:
  clock / time arithmetic (TRANSFER-3 travel `t3_arrival_minute`, science `sci_hm_to_min`), unit
  conversions (SELFEDIT `calendar` / `travel` units), list transformations (WORLD `coding`), string
  rotations / cipher-like maps (TEXT, BRIDGE, TEXT_CHAIN, TEXTPAT).
- Structure: every NOVEL reference tree, canonicalized up to variable renaming, against all 546 reference
  trees found in `nomad/` catalogues: only `nv_c_dot` (= MEANING `two_areas`, TRANSFER-2 `f2_two_lines`)
  and `nv_c_cross` (= MEANING `frame`) match, and the lookup guard drops both. Sub-structures do recur:
  `|a - b|` as `max - min` is the held-out probe `absdiff` (deep suite, never trained) and appears inside
  one DISCRIM task. That is expected: transfer is supposed to reuse pieces.
- Input names `px py qx qy nn tn oa ob oc od` appear in no training signature and no catalogue.

## Sealed suite

`scripts/novel_suite.py`, **seed 20270613** (unused: checked against every seed in docs/, scripts/,
nomad/, tests/), `data/deep/novel_suite.json`, sha256
`9ae25df5ef35f8ed619296423ced5cee8fbe758315cc5e3fa44f221208ede6d1`. Same procedure as
`scripts/transfer_suite.py`: 30 families, 11 rows each (5 public, 3 challenge, 3 final; the final split
is never read by search or WITNESS), cold control at 10,000 evaluations, max_size 7:

- **easy** (cold certifies; reported, never scored): `nv_d_tens`, `nv_d_nines`.
- **dropped by the lookup guard** (a remembered program of a trained field, renamed, certifies it
  outright, so it would measure retrieval, not transfer): `nv_c_dot`, `nv_c_cross`.
- **hard (scored): 26 tasks**: coord 8, digits 8, order 10.

## Arms (scripts/novel_judge.py)

Budget 10,000, max_size 7, no words (the tasks are plain formulas; MEANING and CLAUSE2 need words, so
they cannot act at evaluation time here; MEANING still shapes what the current field learned from the
stories). `PYTHONHASHSEED=0` pinned for the measurement.

Training curriculum of every trained field (never a NOVEL family): the 16 WORLD families, the easy
science curriculum, then the 72 MEANING training stories, 2 rounds each (the CLAUSE2 / ROLES `trained`
curriculum, without NOMAD_ROLES).

Switch settings:

- **CURRENT**: every switch at its present default. Post-Nov-20 switches on: PORT, ANCHOR2, SCALE,
  INVENT, BRIDGE, BRIDGE_INVENT, SELFEDIT, INVENT_TEXT, TEXT_CHAIN, MEANING, CLAUSE2. Nov-20 switches on:
  CASESPLIT, SENSE, BLOCKPROBE, WITNESS_CONTINUE, VARIATION. Experimental switches off (ROLES, COMBINE,
  CLAUSE, LET, LET2, DISCRIM, MERGE, CEIL, ROUTE, ROUTE_CUT, GRAPH, SPLICE, CONST, INFLECT,
  TEXT_ABSTRACT, LIVE_*).
- **OLD** ("older NOMAD"): CURRENT with all 11 post-Nov-20 switches off (introduced on Nov 21, by
  commit date). The field is trained **and** evaluated under OLD.

| arm | field | switches | role |
|---|---|---|---|
| `cold` | none (prior=None) | CURRENT | twin control |
| `empty` | empty WorldPrior | CURRENT | control |
| **`trained_on`** | trained under CURRENT | CURRENT | **scored** |
| `trained_old` | trained under OLD | OLD | older-NOMAD baseline |
| `shuffled_1..3` | the trained_on field, content rewired | CURRENT | content control |
| `empty_old` | empty WorldPrior | OLD | report only |
| `trained_on_field_old` | the trained_on field | OLD | report only (switches vs field) |

Shuffled field: a deep copy of the trained_on field where every remembered tree (library blocks, whole
programs, concepts, variation elites and archive) keeps its shape, size, inputs and constants, and each
operator is replaced by a seeded random operator with the same type signature; per-family
operator-order tables are permuted within each signature. Same number of memories and same counts, with
the learned content destroyed.

## Hypothesis and criteria (fixed now)

Hypothesis: learning on the training curriculum transfers to these never-trained families, and the
post-Nov-20 machinery (mainly PORT, which moves whole programs across input signatures, plus GROW and
INVENT) transfers more than the older NOMAD.

Rule "A beats B": A certifies at least 3 more hard tasks than B, **or** certifies at least as many with
at least 25% fewer total evaluations (the GROW / TRANSFER rule).

1. **C1 transfer**: `trained_on` beats `empty` **and** beats `cold`.
2. **C2 current beats older**: `trained_on` beats `trained_old`.
3. **C3 content** (attribution): `trained_on` beats every `shuffled_s`.

**Evidence of transfer = C1 and C2.** If C3 also holds, the verdict is "transfer, attributable to
learned content"; if C1 and C2 hold but C3 fails, the verdict is "transfer, not attributable to learned
content" (the machinery, not what it learned, made the difference). Anything else is a null result,
and it is reported as one. `worse_than_cold` (any task cold certifies with fewer evaluations) is
reported per arm. Per-family breakdowns and per-task (certified, evaluations, via, program) are
reported for every arm. The suite is measured **once**; no criterion, arm or budget changes afterwards.

Results will go to `results/novel/` and the verdict below.

## Results

(pending; filled in after the single measurement)
