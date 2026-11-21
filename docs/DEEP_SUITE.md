# DEEP suite: frozen deep unseen int tasks (pre-registered)

Frozen before any field was measured on it. Generated once by
`python3 scripts/deep_suite.py` (seed 20261120); verify with
`python3 scripts/deep_suite.py --check`.

- File: `data/deep/deep_suite.json` (40 tasks, families `deep_00`..`deep_39`)
- SHA-256 (canonical JSON, sorted keys, no whitespace): `da3ae9bf3a984afb1584153f2fe6044c94d955037086c73ae036049537966fbd`
- Generator stats: 659 trees sampled; 420 invalid/trivial, 31 behaviour duplicates, 0 held-out look-alikes, 168 rejected because cold certified them at 10,000 evaluations.
- Every kept task: generating tree of size 8-12 over the `int` opset with uniform operator choice; the cold control does **not** certify it at 10,000 evaluations, max_size 7. 27 of 40 cold misses are budget exhaustion; 13 are cold stopping on a public-row fit that WITNESS/final rejects.
- Leakage guard: tasks observationally equal (probe inputs + task rows) to square_product, absdiff or quartic_sum are excluded; last_first_upper and sum_minus_max are str/list and cannot match. The generator never reads held-out task rows.
- Development of the case-split organ used a separate dev suite (`--seed 7`, not committed); this frozen suite was not read while choosing anything.

## Pre-registered success metric (fixed before measuring)

1. 16-family leave-one-family-out total stays at or below cold's 5,883, worst family 1.0x.
2. Deep suite, each task's family held out (every deep family is unseen by construction): the field certifies **at least 25%** of the tasks cold cannot certify at equal budget (10,000), and no task is worse than cold.
3. A "cold + case-split" arm is reported to separate the mechanism from the learned field.
4. Held-outs are report-only (absdiff under 10k live without min(x, y) is noted, not targeted).

Results are recorded below once measured.

## Results (2026-11-20, `python3 scripts/casesplit_probe.py`, after `7dde50b`)

| Metric | Bar | Cold | Cold + split | Field, split off | Field | Met? |
|---|---|---|---|---|---|---|
| LOFO total (16 families) | <= 5,883, worst 1.0x | 5,883 | 5,883 | 5,883 | 5,883, worst 1.0x | yes |
| Deep: certified among 40 cold misses @10k | >= 25% | 0 | 6 (15%) | 0 | 6 (15%) | **no** |
| Deep: tasks worse than cold | 0 | | 0 | 0 | 0 | yes |

Certified by the split (field and cold + split alike): deep_06, deep_15, deep_16, deep_26, deep_27, deep_30. The split also proposed 10 public-row fits that WITNESS rejected. Nothing was re-tuned after this measurement. Details: `docs/WORLD.md` "Case split".

## SENSE step (2026-11-20, `python3 scripts/sense_probe.py`)

Criteria pre-registered in `docs/SENSE.md` (commit db61a83) before this suite was measured with SENSE. Field + sense certifies **14 of 40** cold misses at 10,000 evaluations (35%; pre-sense field 6, cold 0), no pre-sense win lost, no task worse than cold, LOFO 5,883 (worst 1.0x), 187,678 evaluations over the suite (pre-sense field 204,588; cold 284,839). This is the first pass to clear the 25% bar above. Details: `docs/SENSE.md`.

## WITNESS_CONTINUE (2026-11-20, `python3 scripts/witness_continue_probe.py`)

Criteria pre-registered in `docs/WITNESS_CONTINUE.md` (commit 0439494). A
WITNESS rejection no longer ends the field arm's search: field certifies
**25 of 40** (62.5%; switch-off field 14, cold 0), no win lost, none worse
than cold, LOFO 5,883 (worst 1.0x). An empty field with the switch on also
certifies 25: this is a search mechanism, not learning. Details there.

## PORT and the 3-arm learning judge (2026-11-21, `python3 scripts/learning_judge.py`)

Pre-registered in `docs/PORT.md`. Arms cold / empty field (all search on, no
memory) / trained field. Deep: cold 0, empty **25**, trained **25** (same
evaluations): PORT does not fire on `(x, y)` tasks and memory still does not
count on this suite. Science hard: cold 0, empty 0, trained (PORT off) 5,
trained **9**. LOFO 5,883 (worst 1.0x). Details: `docs/PORT.md`.
