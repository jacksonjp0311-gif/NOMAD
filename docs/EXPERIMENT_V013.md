# NOMAD v0.13 — preregistered TRANSCEND experiment

**Status:** frozen source and release seeds before heldout study; registered gates passed. **Scope:** synthetic two-variable integer expression synthesis with a common, fixed AST vocabulary.

## Objective

Does a witnessed, context-sensitive program-synthesis ordering policy learned entirely from Python remain useful on held-out JavaScript tasks, and vice versa, versus matched cold, global and shuffled-context controls?

## Source and sampling isolation

The plan and source lock were written to `experiments/PLAN_V013.json` and `experiments/FREEZE_V013.json` **before generating release evaluation tasks**. The source code hashes are fixed. Separate processes produced source-language native WITNESS receipts, persisted training ledgers, and then evaluated holdout tasks after loading frozen memory.

- Python source training seeds: 4211, 4241, 4283; JavaScript source training seeds: 5219, 5249, 5297.
- Python target holdout: 7211, 7213, 7229; JavaScript target holdout: 6211, 6217, 6221.
- Training families: `square_plus`, `sum_times_y`, `times_shift`, `shift_times_y`.
- Heldout families: `difference_product`, `sum_times_x_shift`, `bilinear_plus`, `shifted_product`.
- 2 tasks per family/seed = **24 per direction**, **48 heldout**. Source training has **24 tasks/language**.
- Each task has 12 public, 10 WITNESS challenge, and 10 independent final examples.
- All policies can search the exact same bounded 7-node AST grammar with a per-task budget of 65,000 candidate-vector evaluations.

The synthetic families are distinct by name/formula but share a highly structured arithmetic world and compiler adapters. The semantic normalization is hand-designed. Similar performance on this benchmark should **not** be extrapolated to open-ended code.

## Frozen results

| Heldout direction | Policy | Correct / tasks | Mean candidate vectors | Total vectors |
|:--|:--|--:|--:|--:|
| Python → JavaScript | Cold | 24/24 | 6693.00 | 160,632 |
| | Global prior | 24/24 | 3083.25 | 73,998 |
| | Shuffled context | 24/24 | 3083.25 | 73,998 |
| | **Bitwork transfer** | **24/24** | **1212.25** | **29,094** |
| JavaScript → Python | Cold | 24/24 | 6693.00 | 160,632 |
| | Global prior | 24/24 | 3083.25 | 73,998 |
| | Shuffled context | 24/24 | 3083.25 | 73,998 |
| | **Bitwork transfer** | **24/24** | **1203.25** | **28,878** |
| **Combined** | Cold | 48/48 | 6693.00 | 321,264 |
| | Global | 48/48 | 3083.25 | 147,996 |
| | Shuffled | 48/48 | 3083.25 | 147,996 |
| | **Bitwork transfer** | **48/48** | **1207.75** | **57,972** |

The observed reduction against cold search is **81.95%**; against global-frequency learning, **60.83%**. Every policy solved every target task with valid WITNESS and final evidence, so this experiment measures **search order**, not improved solve rate. Bitwork context produced a different AST-root ordering from the global prior. The shuffled-context policy's result coincided with global on the registered targets; this is retained as observed, not tuned away.

## Audit

The separate auditor checked **192 candidate programs on 6,144 source-independent scalar input/output evaluations**, then reexecuted all **48 final transfer programs** using their native target runtimes. It checked 1,536 native observations and reproduced 48 WITNESS receipt hashes. Zero observed mismatches, false certifications or native execution failures.

The independent scalar interpreter differs from the search implementation, but the experiment uses the same fixture generator family and is **internal independent-code verification**, not external scientific replication. The detailed audit report is `results/AUDIT_V013.json`.

## Negative evidence / limitations

1. **No native Rust verification.** `rustc` is not installed in this environment. Rust source is emitted and bounded; no compiler/result claims are made. A future machine with Rust must run `python -m nomad.transcend_cli --demo --language rust` before treating its adapter as validated.
2. **Not an independent unknown-language grammar.** Python and JavaScript share the same hand-specified arithmetic IR. Transfer occurs at the search policy, not learned language understanding.
3. **Finite, constructed tasks.** Four heldout formulas are new to training but sampled from a known generator. Real repository bugs, arbitrary control flow, and external task selection remain untested.
4. **No runtime efficiency claim.** Candidate-vector counts include repeated computed vectors, not physical CPU/RSS or energy. Native execution subprocess costs may dominate real systems.
5. **No actual native BGR integration demonstration.** This release reuses NOMAD's Bitwork-derived Python failure-state encoder and grammar prior, not the separate BGR Rust/native runtime.
6. **No adversarial integrity proof.** Hash links detect accidental evidence changes, not a full-store malicious editor who can recompute all hashes.
7. **No statistically independent replication.** Six heldout seeds across two matched synthetic target languages represent a limited evaluation family.

## Evidence files

`experiments/PLAN_V013.json`, `experiments/FREEZE_V013.json`, `results/v013-training/`, `results/v013-release/STUDY.json`, `results/v013-release/GATES.json`, `results/AUDIT_V013.json`, and `results/RELEASE_MANIFEST_V013.json`.
