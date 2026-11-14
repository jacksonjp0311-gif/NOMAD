# NOMAD v0.1.0 Experiment

## Question

Can a compact execution-evidence signature help a coding learner choose repair transformations more efficiently than either a fixed search order or a global learned prior?

## Design

The benchmark creates bounded Python-expression repair tasks from five structural repair families. Each task exposes only the broken expression and input/output examples. The hidden target source and repair-family label are retained by the evaluator and never passed to the solver.

Three policies are compared:

1. fixed operator-family order;
2. a global Beta-smoothed success prior over repair families;
3. a contextual learner conditioned on a binary execution-failure signature.

Each seed uses disjoint training and held-out task instances. The learned policies are frozen during evaluation. Five seeds are used: 11, 17, 23, 31, and 47.

## Registered primary outcome

Mean number of candidate programs executed before a passing repair is found, subject to preserving the fixed search policy's solve rate.

## Results

### Held-out tasks with the training distribution

| Policy | Held-out solved | Mean candidate attempts | Reduction vs fixed |
|---|---:|---:|---:|
| Fixed | 420 / 420 | 4.679 | — |
| Global prior | 420 / 420 | 3.121 | 33.3% |
| Contextual Bitwork policy | **420 / 420** | **1.955** | **58.2%** |

### Distribution-shift check

The trained policies were also evaluated on a balanced repair-family distribution rather than the skewed training distribution.

| Policy | Shifted solved | Mean candidate attempts | Reduction vs fixed |
|---|---:|---:|---:|
| Fixed | 150 / 150 | 4.367 | — |
| Global prior | 150 / 150 | 3.247 | 25.6% |
| Contextual Bitwork policy | **150 / 150** | **1.733** | **60.3%** |

The contextual policy therefore becomes the v0.1 architecture. The global policy remains as a baseline and fallback prior.

## Interpretation

This is evidence that the supplied execution signature contains useful information about which repair family to attempt first in this bounded environment. It is not evidence that NOMAD understands arbitrary code. The task generator, edit vocabulary, expression language, and test distribution are all controlled by this repository.

## Reproduce

```bash
python scripts/verify_release.py
```

Raw output is stored in `results/simulation-v001.json`; release gates are stored in `results/GATES.json`.
