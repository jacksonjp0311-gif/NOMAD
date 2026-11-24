# NOMAD Measurement Index

Single entry point for any agent entering this repository. Every measurement maps to its file, timestamp, result, and status. If a number is not in this index, it does not exist for reporting purposes.

Last updated: 2026-11-24 19:17 UTC

## Core State

| Measurement | File | Latest | Value | Status |
|---|---|---|---|---|
| Field version | data/organism.json | organism.status() | 2729 | live |
| Library size | data/organism.json | world_library_size | 72 | live |
| Body checkpoint | data/organism.json | checkpoint | 4 / 24 cycles | live |
| Body lease host | data/organism.json | lease | gh-45395469371 | live |
| Schedule | .github/workflows/continuous-*.yml | cron 8/23 awake, 38 sleep | firing | live |

## Twin Measurement

| Measurement | File | Latest | Value | Status |
|---|---|---|---|---|
| World twin groups | data/organism.json | twin_summary | 128 | live |
| World twin pass rate | data/organism.json | | 0.852 | live |
| World twin informative rate | data/organism.json | | 0.078 (10/128) | below 0.10 threshold, flag set |
| World twin mean evals saved | data/organism.json | | ~1339 | live |
| Genesis twin groups | data/organism.json | | 128 | live |
| Genesis twin pass rate | data/organism.json | | 1.0 | live |
| Genesis twin informative rate | data/organism.json | | 0.0 | all pairs uniform, not measuring |
| Genesis mean evals saved | data/organism.json | | 57 | live |

## Held-Out Probes

| Probe | File | Field | Cold | Fingerprint | Status |
|---|---|---|---|---|---|
| absdiff | data/organism.json heldout | certified | exhausted 10k | method (case split, 0 primitives) | certified |
| quartic_sum | data/organism.json heldout | certified @ 90k evals | not reached | library (2 stored primitives) | certified |
| square_product | data/sealed_compare.json | certified @ 999 | abstained @ 2000 | recall (trivial rearrangement) | certified |
| last_first_upper | data/organism.json heldout | none | none | unknown | WALL - no probe-failure receipt written yet |
| sum_minus_max | data/organism.json heldout | none | none | unknown | WALL - no probe-failure receipt written yet |

## Genesis Held-Out

| Probe | File | Field | Cold | Status |
|---|---|---|---|---|
| genesis held-out | data/organism.json | certified TRUE | certified FALSE | field-over-cold certified win |

## Selfedit

| Measurement | File | Latest | Value | Status |
|---|---|---|---|---|
| Last attempt | data/organism.json | 18:06 UTC | gene none, sandbox_clean, no_change | 5 consecutive |
| Tabu | selfedit.py gene_tabu_from_log | | inv_floor_fit refused after 2 consecutive tests_failed | active |
| Journal bias | selfedit.py propose() | pushed 05:12 | reads dreamlog + organism.json | loaded, not yet surfaced different gene |

## Sealed Comparisons

| Comparison | File | Result | Interpretation | Status |
|---|---|---|---|---|
| sealed_compare (Abs/Min/FloorDiv available to all arms) | data/sealed_compare.json | cold=field identical: absdiff 24, median 9, clamp 6 | prior not causal | complete |
| sealed_prefer (prefer-fastest-ops prior) | data/sealed_prefer.json | prefer WORSE: absdiff 23 vs 21, clamp 6 vs 5 | preference not causal for improvement | complete |
| sealed_invent (inventions in enumerator) | data/sealed_invent.json | cold=field: absdiff 24/23, median 9/8, clamp 6/5 | prior changed order, not cost | complete |
| abstract_measure | data/abstract_measure.json | absdiff fit 24, median fit 9 (needs FloorDiv), clamp fit 6 | all 3 reachable with extended grammar | complete |
| invent_measure | data/invent_measure.json | interface_ready, 0 inventions extracted | full extraction needs world bank | stub |
| invent_extract | data/invent_extract.json | stub | workflow dispatch was broken, rewritten | stub |
| compress_measure | data/compress_measure.json | cold=field identical | compression invariant not yet causal | complete |

## Plans

| Plan | File | Phase | Status |
|---|---|---|---|
| PLAN_V2 | docs/PLAN_V2.md | A done (version space, portability) | in |
| PLAN_V3 | docs/PLAN_V3.md | B (generation-first, default OFF), C (abstract targets) | in, unmeasured in loop |
| PLAN_V4 | docs/PLAN_V4.md | extended genesis behind flag | in |
| PLAN_V5 | docs/PLAN_V5.md | invent -> sealed comparison | in, measurement queued |
| INVARIANT_CALM | docs/INVARIANT_CALM.md | compression invariant from CALM paper | documented |
| ORBIT_MATH | docs/ORBIT_MATH.md | orbit algorithm from translation-symmetry invariant | documented |
| CAUSAL | docs/CAUSAL.md | causal path documentation | documented |
| DOMAIN_PACKETS | docs/DOMAIN_PACKETS.md | 10 seeded domain packets | documented |
| GAPS | docs/GAPS.md | original 5 gaps | 4 closed, twin pairing wired untested |

## Key Modules

| Module | Path | Role |
|---|---|---|
| Body loop | nomad/body.py | long-lived process, ~5.5h, checkpoints data/ every 10m |
| Watch | nomad/watch.py | restarts body if heartbeat stale past 30m |
| World engine | nomad/world.py | typed runtime: integers, strings, lists; 72 primitives; curriculum |
| Genesis | nomad/genesis.py | solve(x,y) synthesizer, max 7 nodes |
| Invent | nomad/invent.py | extracts common subexpressions, promotes by frequency not verified transfer |
| Selfedit | nomad/selfedit.py | bounded scalar tweaks, test-gated, revert guard, journal-biased propose |
| Dreamlog | nomad/dreamlog.py | write-only journal; NOW readable by selfedit.propose |
| Organism | nomad/organism.py | status aggregator; NOW computes informative_rate_flag |
| Interlink | nomad/interlink.py | external control surface: inspect/observe/control/evidence; mutations deny-by-default |
| Interlink permissions | nomad/interlink_permissions.py | three-layer gate; no self-authorization |
| Interlink receipts | nomad/interlink_receipts.py | append-only redacted export |
| Extended enum | nomad/extended_enum.py | Abs/Min/Max/Sub/Add/FloorDiv, prior-ordered | default OFF |
| Extended genesis | nomad/extended_genesis.py | NOMAD_EXTENDED=on | default OFF |
| Prefer ops | nomad/prefer_ops.py | prior preferring fastest operators | measured, not causal |
| Sealed compare | nomad/sealed_compare.py | cold/empty/field arms | |
| Sealed invent | nomad/sealed_invent.py | cold vs field with inventions | |
| Sealed prefer | nomad/sealed_prefer.py | cold vs prefer prior | |
| Abstract targets | nomad/abstract_targets.py | absdiff, median, clamp example sets | |
| Version space | nomad/versionspace.py | abstains on conflicting operators | |
| Portability | nomad/portability.py | adapter commuting check | |
| Compress measure | nomad/compress_measure.py | compression invariant measurement | |
| Invent measure | nomad/invent_measure.py | invent interface recording | |
| Invent enum | nomad/invent_enum.py | inventions in enumerator | NOMAD_INVENT_ENUM=on |
| Query | nomad/query.py | domain-name or hash lookup | |
| Continuous | nomad/continuous.py | awake/sleep scheduling | |
| World loop | nomad/world_loop.py | FIXED: library items are strings not objects (line 137) | |

## Known Issues

1. invent-extract.yml dispatch was broken; rewritten but not re-verified
2. Probe-failure receipt code is in but no receipt has been written for last_first_upper or sum_minus_max
3. Informative rate below threshold on world twin (0.078, flag set)
4. Genesis twin entirely uniform - not measuring
5. Selfedit rotator still sampling from exhausted space under tabu
6. Body checkpoint does not inline full packet state - restart consistency hole if data commit fails
7. Organism file and dream journal were write-only; now readable by proposer (pushed 05:12)

## Claim Boundaries

- No AGI claim. Architecture is recursive field intelligence; capability is bounded program synthesis plus field query.
- Evaluation savings are descriptive, not a general learning claim.
- One genesis held-out win is a data point, not a pattern yet.
- Sealed comparisons show prior is causal for order, not for improvement.
- WITNESS is the certification gate. Search and memory do not certify.
