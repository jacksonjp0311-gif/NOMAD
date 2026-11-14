# NOMAD v0.16 — Frozen MISSION RUNTIME experiment

**Question:** Can a Bitwork-derived coding mission preserve causally relevant action state across a restart, without inventing test success or replaying an already committed edit?

## Registered design

Source hashes and six release cases were frozen in `experiments/FREEZE_V016.json` and `experiments/PLAN_V016.json` **before the release seeds were run**. The development seed `9117` was excluded from the release set. New seeds `32101`, `32203`, and `32309` cover six generated Python repair families. Each mission is tested twice: one uninterrupted reference and one with a recorded interruption, followed by a fresh controller invocation. Each policy receives the same original source, tests, repair operators and attempt budget.

The primary outcome is identical accepted code and matching action/verification decision projections, not CPU reduction or new learned reasoning. The evaluator checks source digests, journal uniqueness, WITNESS receipts and independent final examples. Raw `unittest` failure messages contain workspace-specific paths: their hashes are retained as evidence but are **not expected to be identical across distinct workspace roots**.

## Results

| Case | Interruption | Reference accepted | Resumed accepted | Same decision projection |
|---|---|:---:|:---:|:---:|
| `bin` | After patch write, before receipt | Yes | Yes | Yes |
| `const` | After rollback write, before receipt | Yes | Yes | Yes |
| `neg` | After independent witness receipt | Yes | Yes | Yes |
| `zero` | After public-test receipt | Yes | Yes | Yes |
| `cmp` | After final evidence receipt | Yes | Yes | Yes |
| `id` | After committed completion receipt | Yes | Yes | Yes |

- **12/12** matched run instances completed, including **6/6** interrupted-and-resumed missions.
- **6/6** paired final source digests match, with **6/6** identical ordered logical decisions.
- **11** candidate attempts per arm, with one recorded accepted independent WITNESS receipt per mission.
- **6/6** accepted candidate sources reconstructed independently and replayed against the held-out final examples.
- **Zero** repeated logical action receipts in the six resumed journals.
- The independent auditing script also checked the original WITNESS receipt checksums, identifiers, event references, and final observation digests.

## Adversarial/negative engineering tests

Unit tests deliberately exercise corrupted/partially written event lines, stale workspace source, mutated public tests, modified withheld evidence, unexpected changes after completion, simultaneous owner processes, self-certification traps and disagreement between WITNESS and a separate final split. Their success means the registered test cases reject those failures, **not** that untrusted execution security has been proved.

## Replication

```bash
python -B scripts/verify_package_v16.py --audit
python -B -m unittest tests.test_mission_v16 -q
```

For each study case, run `scripts/study_mission_v16.py --name <case> --run-root <new-directory> --output <new-file>` using fresh paths, then execute `scripts/audit_mission_v16.py --study-dir <results-directory>`. Never overwrite the six frozen packaged case records.

## Scientific interpretation

MISSION RUNTIME demonstrates **operational continuity of a previously bounded coding learner** on generated fixtures. This is an engineering capability, not evidence of general intelligence, external transfer, strong adversarial isolation, true exactly-once arbitrary effects, improved code synthesis, or superior BGR inference. Future external-repository benchmarks must be separately frozen and audited.
