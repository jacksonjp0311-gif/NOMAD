# NOMAD v0.5 — ECHO MAP Experiment

## Question

Can NOMAD learn a compact cross-substrate effect representation from verified transformation outcomes instead of receiving the hand-designed MORPHIC signature?

## Protocol

Four substrates are retained from v0.4: code, math, data and workflow. For each deterministic seed, one entire substrate is held out. NOMAD collects verified transformation outcomes on the other three substrates by actually executing candidate transformations and requiring both public and separate challenge evidence to agree.

ECHO MAP receives only paired observable current/target outputs. It is not given the domain name and does not receive the v0.4 `EffectSignature` fields.

The supplied generic relation grammar contains seven relation channels:

- difference
- sum
- absolute difference
- ratio
- product
- current
- target

Each channel exposes mean, spread and RMS, yielding 21 generic candidate relations. ECHO MAP learns which four coordinates separate verified transformation outcomes best using a Fisher-style between/within-family score. It then standardizes those coordinates and learns one prototype per transformation family.

At evaluation time the learned map is frozen. Candidate transformations are ranked by distance to the learned prototypes. Final correctness is checked on six challenge probes that were not used for ranking.

## Controls

1. **Cold fixed search** — fixed transformation order.
2. **Global frequency** — learns which transformation families were common but ignores effect state.
3. **MORPHIC hand signature** — v0.4 manually designed effect representation.
4. **ECHO MAP shuffled** — same learned-representation procedure after verified transformation labels are shuffled, breaking the relationship between observed effects and transformations while preserving the label counts.

## Results

Across five seeds and four held-out substrates:

- 1,200 ECHO MAP held-out tasks;
- 1,200 / 1,200 challenge-correct;
- cold mean search: 3.000 attempts;
- global-frequency mean search: 3.000 attempts;
- hand-designed MORPHIC mean search: 1.0375 attempts;
- learned ECHO MAP mean search: 1.2408 attempts;
- shuffled-label ECHO MAP mean search: 2.9675 attempts.

Therefore ECHO MAP reduced candidate search by **58.64% versus cold search** and **58.19% versus the shuffled-evidence control** while preserving challenge correctness.

The learned representation remained **19.60% more expensive in search attempts than the hand-designed MORPHIC signature**. This is a retained negative/limiting result. v0.5 does not claim that learned representation has already surpassed the tailored representation.

### Held-out substrate detail

| Held-out substrate | Cold | Hand MORPHIC | ECHO MAP | Shuffled | ECHO challenge correctness |
|---|---:|---:|---:|---:|---:|
| Code | 3.000 | 1.030 | 1.210 | 2.827 | 100% |
| Math | 3.000 | 1.003 | 1.253 | 2.930 | 100% |
| Data | 3.000 | 1.043 | 1.230 | 2.837 | 100% |
| Workflow | 3.000 | 1.073 | 1.270 | 3.277 | 100% |

## What the map learned

Across the 20 seed/holdout fits, the most frequently selected generic relation coordinates were:

- `ratio.mean`: 20 / 20
- `ratio.rms`: 20 / 20
- `absolute.rms`: 16 / 20
- `absolute.spread`: 10 / 20
- `difference.rms`: 9 / 20

This is evidence that the learner consistently recovered useful relations from the supplied relation grammar rather than relying on a domain label. It is **not** evidence that NOMAD can yet invent arbitrary mathematical operators or raw sensory representations from nothing.

## Claim boundary

v0.5 learns **feature selection, scaling and transformation prototypes** from experience, but the generic relation grammar is still supplied by the system designer. The transformations themselves are also supplied. This is therefore bounded representation discovery, not unrestricted representation invention or AGI.

The next research gate is to reduce dependence on the supplied relation grammar and convert learned transformations into causal skills with explicit preconditions, expected effects and failure envelopes.
