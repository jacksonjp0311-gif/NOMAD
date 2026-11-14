# NOMAD v0.4 MORPHIC — Cross-Substrate Transfer Experiment

## Question

Can a learner trained on three structured substrates use a domain-neutral effect signature to reduce transformation search on a fourth substrate that was never used during training?

## Protocol

Domains: `code`, `math`, `data`, `workflow`.

Families: `shift_up`, `shift_down`, `amplify`, `dampen`, `invert`.

For each seed and each held-out domain:

1. Generate balanced training tasks on the other three domains.
2. Train a global-frequency control and a signature-conditioned MORPHIC learner through executed transformations.
3. Freeze both learners.
4. Generate fresh tasks on the held-out domain.
5. Rank and execute transformations using four public probes.
6. Check the selected transformation on six additional challenge probes not used for ranking.
7. Rotate the held-out domain.

Seeds: 11, 17, 23, 31, 47.

## Results

Across 1,200 held-out evaluations all three policies reached 100% challenge correctness. Mean transformation attempts:

| Domain | Cold | Global | MORPHIC |
|---|---:|---:|---:|
| code | 3.000 | 3.000 | 1.030 |
| math | 3.000 | 3.000 | 1.003 |
| data | 3.000 | 3.000 | 1.043 |
| workflow | 3.000 | 3.000 | 1.073 |
| overall | 3.000 | 3.000 | 1.038 |

Overall transfer gain versus cold and global controls: 65.42% fewer executed candidates.

## Interpretation

This establishes a bounded mechanism for cross-substrate reuse: a signature derived from observable effect geometry can support transformation ranking on a representation withheld from training.

It does **not** establish arbitrary domain transfer. All four environments share an intentionally aligned affine transformation family, and the signature is hand-designed. The next scientific gate is to learn the representation itself and test against independently specified environments.
