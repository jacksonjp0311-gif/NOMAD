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
