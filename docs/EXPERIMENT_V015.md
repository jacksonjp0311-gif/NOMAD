# RECURSION v0.15 — Experimental record

## Status and provenance

This study was developed after inspection of the v0.14 known benchmark outcomes; it is **not a preregistered, blind new external benchmark**. The included source fingerprint is post-development and is not misrepresented as a prospective freeze. Both `results/STUDY_V015-initial-precheck.json` and the final `results/STUDY_V015.json` are retained as provenance for an admission-gate correction.

## 1. Native BGR shadow observation

BGR runtime: preserved standalone v1.4 `bgr140.GovernedBitworkV14` from the actual original release, not a NOMAD reimplementation. One chronological stream represents candidate attempts from recorded v0.14 training and cold-policy searches. Action 0 indicates a relational change; action 1 indicates another operator category. Label is whether that candidate passed the *public* tests, not WITNESS final acceptance. The model forecasts before seeing the next outcome and updates after seeing it. All 28 recorded events are retained in `results/STUDY_V015.json`.

| Model | Mean prequential log loss |
|---|---:|
| Action-frequency Laplace baseline | 0.437958 |
| BGR v1.4 governed | 0.477507 |

BGR performs **worse** on this small, nonindependent retrospective sequence. The native connection is proved technically; decision-quality benefit is not.

## 2. Evidence-scoped prior

The old learned prior had two witnessed source tasks, not enough to warrant transferring broad operator preferences. v0.15 scores a prior cell only with at least three **distinct task IDs, candidate source hashes, and witness receipt hashes**. Scope conflicts are contested. Integrity checksums must match. This prevents inflating apparent sample support by replaying the same recorded receipt under different names. An evaluator-owned `independently_observed` indication is still required; this is **not** cryptographically signed authentication.

**Retrospective native replay on four previously seen upstream-source mutations:**

| Metric | v0.14 transferred | v0.14 cold | v0.15 evidence-gated |
|---|---:|---:|---:|
| Independently accepted repairs | 1/4 | 2/4 | **2/4** |
| Candidate attempts | 22 | 20 | **20** |

All four v0.15 attempt counts and witness outcomes agree with the cold control. This is a correction to overconfident transfer, not a new generalization result. The Catalogue namespace counterexample remains rejected by a behavior contract beyond distributed upstream tests.

## 3. Source-revision code synthesis

The revision engine produces actual Python `ranking_key(semantic, prior, line)` source via bounded AST construction, then validates the exact whitelist and evaluates it without arbitrary system imports. It only produces candidate receipts and never updates production source.

Two 32-task favorable synthetic sets (development and holdout) use a made-up correlation in which a learned prior is more informative than the incumbent ranking. Here the generated candidate reduces attempts **5.0 → 1.0**. In a separate 32-task **distribution-shift** holdout the correlation is reversed, yielding **1.0 → 5.0** and an explicit failed gate. Neither synthetic result is evidence of true autonomous code-engineering improvement.

## 4. Reproducibility and independent authority

The CLI `python scripts/run_recursion_v15.py --output runs/my-study.json` constructs the report without changing any preserved original. The four known upstream-source checks are separately re-executed using `external_check_v15.py` in fresh directories and run upstream test executables; WITNESS runs after search and does not feed its hidden contract to the candidate ordering.

The v0.14 source corpus remains restricted to known trusted distributions; this laboratory has **no secure isolation for unknown adversarial repositories**. The v1.4 BGR API currently only supports binary action/outcome streams and is not a multiclass code generator. Future work must test an actual meaningful BGR routing decision under matched compute budgets.

## Gate summary

- **Engineering:** native source loaded, observations ordered, memory scope enforced, AST synthesized safely under whitelist, original tests retained — PASS.
- **External transfer:** insufficient independent unseen tasks, performance not better than cold — HOLD.
- **Native BGR coding contribution:** shadow predictions worse than baseline — FAIL.
- **Self-improvement:** candidate-only lab, no verified real-world improvement — HOLD.
- **Production:** isolation/independent authentication/runtime continuity not implemented — HOLD.
