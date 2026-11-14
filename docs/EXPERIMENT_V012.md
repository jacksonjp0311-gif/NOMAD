# NOMAD v0.12 — Registered MNEMONIC experiment

**Study status:** frozen release evaluation passed. **Scope:** generated arithmetic Python module graphs, a fixed AST intervention, and supplied structural features. Not independent external replication.

## Preregistration and data isolation

- Training seeds: `17011, 17047, 17123, 17183` (**16** generated repositories).
- Calibration seed: `18011` (**4** repositories; predictions observed, never used to tune release policy).
- Development seeds (seen before source freeze): `19011, 19057, 19121, 19181, 19231` (excluded from release).
- New release evaluation seeds: `29011, 29053, 29117, 29191, 29251` (**20** untouched repositories; **180** downstream contract cases).
- Source/frozen seed lock: [`experiments/FREEZE_V012.json`](../experiments/FREEZE_V012.json) and [`experiments/PLAN_V012.json`](../experiments/PLAN_V012.json).
- Training and release evaluation were executed in **different Python interpreter processes**. The learner received no release labels, filename identity or evaluator-only target family labels.

## Matched evaluation results

| Policy | Correct classified | False classified | Abstained | Mean true effects in first 3 | Mean probes to first effect |
|---|---:|---:|---:|---:|---:|
| Memory reset / random order | 0 / 0 | 0 | 180 | 1.60 | 1.90 |
| Pooled-frequency prior without structural context | 80 / 180 | 100 | 0 | 1.60 | 1.90 |
| Direct call graph | 120 / 160 | 40 | 20 | 2.00 | 1.45 |
| Structural evidence deliberately shuffled | 80 / 160 | 80 | 20 | 1.40 | 1.65 |
| **Restarted MNEMONIC** | **160 / 160** | **0** | **20** | **3.00** | **1.00** |

MNEMONIC ranked all three chosen checks as affected on all 20 target worlds. The counterfactual test-ranking score is an efficiency *proxy*, not full workflow CPU time; **every current code change still requires WITNESS and final tests**. A zero-error observation on 160 synthetic predictions does not imply perfect accuracy elsewhere.

## Registered negative and safety controls

1. **Memory reset:** a cold instance has no prior experience; it abstains on all 180 effects.
2. **Pooled-frequency:** has the same source observations but no binary context, classifies incorrectly on 100/180.
3. **Shuffled association:** retains all training exposure but destroys matching between binary state and observed consequence, yielding 80/160 correct.
4. **Graph-only:** sees current call graph but overpredicts masked/cancelled effects (120/160 correct).
5. **Known unknown:** 20 dynamic calls cannot be represented, requiring 20/20 abstentions.
6. **Action scope:** a changed AST intervention has no matching memory cell and must abstain.
7. **Temporal expiry:** a recall six epochs later exceeds the four-epoch horizon and abstains.
8. **Independent negative case:** the conditional call `if x > 999` produces an unchanged effect despite matching the original positive conditional's coarse feature signature. The post-witness memory branch marks that scope contested.

## Reproduction and audit

Original stored evidence: [`results/study-v012.json`](../results/study-v012.json), [`results/MNEMONIC_MEMORY.json`](../results/MNEMONIC_MEMORY.json), [`results/AUDIT_V012.json`](../results/AUDIT_V012.json), [`results/GATES_V012.json`](../results/GATES_V012.json).

The separate process auditor regenerated the five release seeds and recomputed all **180 intervention outcomes**, while checking the remembered predictions against the persisted frozen training ledger. No mismatches remained. This replay uses the same generated world family and is not an external lab replication.

The source-freeze plan includes a descriptive coordinate-count error (`17` instead of `15`). It is preserved with an explicit post-evaluation correction in [`ERRATA_V012.md`](ERRATA_V012.md). No learning or benchmark decisions changed.

## Interpretation

MNEMONIC proves persistent, source-scoped prediction transfer *under this supplied structural grammar*. It does **not** show learned language semantics, unrestricted causal discovery, self-modification or a real production coding throughput benefit. The next scientific gates involve real external repositories, semantic distribution shifts and cross-language transfer with frozen adapters.
