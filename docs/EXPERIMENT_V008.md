# NOMAD v0.8 — WORLD MODEL Experiment

## Question

Can NOMAD learn a filename-independent mapping from observable repository structure plus failure evidence to verified repair locations, and can that learned model reduce repair search on held-out multi-file repositories without lowering final correctness?

## Precondition

Only WITNESS-supported repairs from the training set are admitted as positive location evidence. Evaluator-only `true_bug_file` metadata is used to score localization and is not exposed to the model.

## Repository generator

Each task contains six modules with randomized names:

1. entry module tested through `solve(x, y)`;
2. intermediate service;
3. leaf computational dependency;
4. configuration dependency when applicable;
5. disconnected mutation-rich distractor;
6. second disconnected distractor.

Four unique-location fault families are used: leaf binary operator, intermediate constant, entry syntax, configuration constant.

The initial development benchmark contained an entry negation case that could be compensated by a valid downstream negation. Because that made causal location non-unique, the case was rejected before the frozen study.

## Evidence features

No filename token is admitted. File signatures contain:

- import-graph distance from entry;
- reachability;
- in/out degree;
- AST structural predicates;
- available supplied candidate transformation families;
- public failure shape;
- learned interactions between failure tokens and structural tokens.

The structure-only control learns from the same verified repair locations but omits failure evidence.

## Frozen study

Seeds: 17, 29, 41.

For each seed, 12 training repositories are used to build the models and 12 separately seeded repositories are used for evaluation. Total held-out repositories: 36.

## Result

| Metric | Flat | Structure only | WORLD MODEL |
|---|---:|---:|---:|
| Final correct | 36/36 | 36/36 | 36/36 |
| Mean attempts | 16.7778 | 6.5000 | 4.7500 |
| Mean files visited | 3.5556 | 1.7500 | 1.2500 |
| First-rank localization | — | 50.0% | 75.0% |

WORLD MODEL reduced attempts 71.69% vs flat and 26.92% vs structure-only. File visits fell 64.84% vs flat.

The model was not perfectly calibrated: 9/36 faults were not ranked first. Search preserved alternate files and still produced 36/36 final-correct repairs.

## Integration gate

Eight additional repositories were materialized to disk. Candidate edits were written to the relevant module, the repository's actual `unittest` process was launched, WITNESS evaluated disjoint challenge evidence and a final hidden split was checked.

Result: 8/8 solved, 8/8 unittest passed, 8/8 WITNESS-supported, 8/8 final-correct.

## Claim boundary

This is a generated bounded repository family. It does not demonstrate arbitrary repository understanding or arbitrary patch synthesis. The graph topology family, fault families, candidate transformation vocabulary and feature language are supplied.

The supported claim is that a learned, filename-independent relationship between failure evidence and repository structure reduced verified repair search on held-out repositories from this family.
