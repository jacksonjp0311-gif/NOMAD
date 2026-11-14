# NOMAD v0.14 — FRONTIER external-source study

**Status:** executed development case series; positive external-transfer gate **HOLD**. This study is not SWE-bench, not a dataset of authentic upstream defects, not preregistered before task curation, and not external independent replication.

## Research question

Can NOMAD's fixed compact failure-state contextual prior reduce candidate repair search across independently authored source code, while preserving full-suite witnessed correctness?

## Corpus and provenance

Source was copied locally from installed upstream distributions, whose upstream projects and versions are recorded by `external_sources/*.manifest.json`. It includes original tests and license copies. The project code itself was not authored by NOMAD. Each task intentionally introduces **one evaluator-defined source mutation** into a disposable copy. That mutation is a research stimulus, *not a real reported upstream bug*. The correct original source is used only by the evaluator for an additional provenance-based diagnostic, never by the repair search.

All three distribution test suites passed on the clean upstream versions in the environment. Current installed versions: Affine 2.4.0 (66 tests), Catalogue 2.0.10 (7 passed, 2 skipped), Confection 0.1.5 (111 passed, 1 skipped, 4 expected failures). These counts describe the clean local distributions, not real-world defect resolution.

## Experimental conditions

- **Training:** two injected mutations, `affine-almost` and `catalogue-contains`, which generated two witnessed operator-preference observations.
- **Evaluation:** four additional mutations across the same three upstream package families (`affine-rectilinear`, `affine-vector`, `catalogue-names`, `confection-merge`). These are withheld *from the prior updater* but they were seen during benchmark development; do not characterize them as untouched holdout repositories.
- **Policies:** deterministic cold candidate ordering versus contextual prior trained on verified repair outcomes. The prior keys have a 16-bit failure signature and token-operation family; no project/language/filename identifiers. Both policies use the same source, public tests, maximum 12 candidates and full WITNESS.
- **Search:** source AST owner and public test references guide a bounded single-token operator vocabulary. A fresh Python interpreter runs the actual public pytest subset for each proposed edit; there is no batched fake oracle.
- **Final challenge:** a new Python process executes each project's full original distributed suite, plus an independent documented Catalogue namespace API invariant. Successful search cannot see the result of this challenge.
- **Outcome truth:** an additional evaluator-only exact-original-source comparison identifies incomplete test coverage. The policy never receives the original and this comparator is not a realistic production witness.

## Recorded outcomes

| Policy | Public passes | Final WITNESS accepts | Original-source restorations | Candidate subprocess tests |
|---|---:|---:|---:|---:|
| Cold | 2/4 | 2/4 | 2/4 | 20 |
| Learned prior | 2/4 | 1/4 | 1/4 | 22 |

**No positive transfer gain.** Mean candidate counts across both success and failure cases are 5.0 (cold) and 5.5 (learned). These are candidate attempts, **not CPU energy savings**. Different policies can select different hypotheses and stop at different stages, so success counts matter more than this descriptive average.

### Retained counterexample

The evaluator mutates the namespace length condition in `Registry.get_all`. The learned prior prioritizes changing a neighboring `and` to `or`. That alternative passes the existing upstream Catalogue tests but mistakenly includes unrelated namespace entries. An independently specified contract constructs nested and foreign entries and checks exactly the immediate namespace children. It rejects the alternative; the cold search instead restores the original condition and passes both checks. The source-level evaluator separately confirms the difference.

This does **not** prove that WITNESS covers every possible failure. It demonstrates how stronger, separately authored behavioral challenges can expose a false candidate that the original suite missed.

### Tool and runtime limits

This environment cannot clone external GitHub repos through the container network, so the study froze already-installed independent distribution sources. Native `rustc` and `cargo` are unavailable. pytest-based mutation evaluation requires native process execution and is not safe for arbitrary untrusted repositories. Full issue benchmarks and held-out unrelated package families are **not yet evaluated**.

## Reproduction

From the extracted package root:

```bash
python scripts/verify_package_v14.py --tests
python scripts/audit_frontier_v14.py
python scripts/study_frontier_v14.py --budget 12 --output runs/replay-001.json
```

The exact prior study is retained in `results/FRONTIER_STUDY_V014.json`; the prior pre-contract study and the reason it was invalid as a final authority are preserved in `results/FRONTIER_DEV_PRECONTRACT.json`. Independent validation re-executes all selected candidate repairs against fresh workspace copies, checking the separate contract's refusal as well as successful restorations.

## Research decision

- Engineering: **PASS** conditional on release manifest and full regression validation.
- Third-party source execution: **PASS**, within installed and trusted distribution corpus.
- Cross-repository learned advantage: **HOLD**. No demonstrated gain.
- Additional semantic verification: **PASS** for the one registered Catalogue challenge.
- Authentic external issue solving, native Rust, unrestricted program synthesis, native BGR inference: **NOT ESTABLISHED**.

Next: a preregistered independent issue corpus, an execution sandbox, fresh evaluation families, causal localization improvements, and no self-promotion without independent tests.
