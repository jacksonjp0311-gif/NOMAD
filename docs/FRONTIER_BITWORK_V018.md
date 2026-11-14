# FRONTIER: what native Bitwork does, and what the new evidence supports

The original BGR runtime can learn the temporal structures deliberately represented in this controlled study. It remains worse than frequency on the registered stationary distribution and costs substantially more computation. These results concern trusted generated binary streams. They do not establish repository repair, general coding intelligence, autonomy or efficiency.

The completed preregistration is [`PLAN_FRONTIER_BITWORK_MECHANISMS_V018.json`](../experiments/PLAN_FRONTIER_BITWORK_MECHANISMS_V018.json), identity `a9f75b824f7f5d3ab9f6ded0d975bb9d568fb7ab4d4ba45f3c75a6d2993f7ee3`. It was written before evaluation outcomes were generated. The original execution is [`FRONTIER_BITWORK_MECHANISMS_V018.json`](../results/FRONTIER_BITWORK_MECHANISMS_V018.json). A fresh-process replay and independent trace arithmetic audit are [`FRONTIER_BITWORK_REPLAY_V018.json`](../results/FRONTIER_BITWORK_REPLAY_V018.json) and [`FRONTIER_BITWORK_REPRODUCIBILITY_V018.json`](../results/FRONTIER_BITWORK_REPRODUCIBILITY_V018.json). Historical v0.14 and earlier v0.18 results and protocols are unchanged.

## Actual mathematical and computational mechanisms

The executed class is the preserved `bgr140.GovernedBitworkV14`, imported through the manifest-verified bridge. The study changes no vendored file. Its binary geometry is a finite Boolean representation: a program's outputs over 32 possible five-bit contexts are stored as a truth-signature integer. The context consists of current action, previous outcome/action and second-previous outcome/action. This is a supplied, bounded representation, not discovery of arbitrary primitives.

The base predictor combines two actual learners:

1. `GrammarEnsemble` mixes eight conditional count experts: context orders 0–3 crossed with retentions 1.0 and 0.82. Order zero uses a KT/Beta(1/2,1/2) estimate. Higher orders add a strength-two backoff estimate. For a context containing counts `n0,n1`, its forecast is

   `p_k = (n1 + 1/2 + 2 p_(k-1)) / (n0 + n1 + 3)` for `k > 0`.

   Exponential retention discounts old evidence. Expert weights update by likelihood with fixed share: `w'_i = (1-s) w_i likelihood_i / sum_j(w_j likelihood_j) + s prior_i`. This expert bank uses `s=0.025`.

2. `ExactCompiledGrammarSynthesizer` retains Boolean atoms and composes XOR, AND and OR expressions. Defaults include beam 20, pool limit 105, expression size 13, depth 4, evidence retention 0.975, noise probability 0.075 and complexity penalty 0.55 per extra expression node. It periodically grows the candidate pool from observed evidence. Its score is discounted noisy-program log likelihood minus the complexity penalty. The forecast averages the top 24 scored programs, with the stated noise floor. Truth signatures, lookup tables and epoch-local caches reduce repeated scoring while preserving the original semantics.

The guarded base mixes those two forecasts. Its prior is `(0.75,0.25)` and fixed share is 0.03. The outer governed learner can additionally activate bounded lag-feature discovery. Its surprise gate checks after 24, 30, 36, 48 and 60 observations, using a 24-observation window and threshold 0.66. The replay limit is 100 past observations. Lag proposals use XORs of at most three supplied features, adding action/outcome lags 3–6. They require both an earlier validation interval and a separate subsequent validation interval before promotion. The outer lag mixture affects forecasts only after a feature is promoted.

These mechanisms are documented directly in the preserved [count expert bank](../vendor/BGR-v1.4.0-runtime/bgr100/grammar.py), [Boolean synthesis](../vendor/BGR-v1.4.0-runtime/bgr110/synthesis.py), [lag discovery](../vendor/BGR-v1.4.0-runtime/bgr120/lag_discovery.py), [surprise gate](../vendor/BGR-v1.4.0-runtime/bgr130/governed.py) and [v1.4 executor](../vendor/BGR-v1.4.0-runtime/bgr140/engine.py). Their forecasts authorize no repair acceptance.

## Why the earlier eight-event replay lost

[`FRONTIER_BITWORK_DIAGNOSIS_V018.json`](../results/FRONTIER_BITWORK_DIAGNOSIS_V018.json) performs a new **post hoc computational diagnosis** using only already public, frozen evidence. This is not a new held-out test, and no replacement predictor was selected for deployment.

The old model had observed eight events. The first lag checkpoint is 24, and the actual recorded state has no lag learner. Disabling the lag gate reproduces both old native probabilities exactly. Lag discovery therefore did not cause that earlier loss.

The exact additive decomposition of native probability minus the old Laplace frequency forecast is:

| Contribution | Relational action 0 | Other action 1 |
|---|---:|---:|
| Frequency starting probability | 0.400000000000 | 0.285714285714 |
| KT prior versus Laplace prior | -0.025000000000 | -0.035714285714 |
| Temporal expert bank versus static KT | +0.049517056625 | +0.088276287964 |
| Induced-grammar mixture contribution | -0.004672571153 | +0.007262329748 |
| Reconstructed native probability | 0.419844485472 | 0.345538617712 |

For action 1, the static expert has four failures and one success, giving `(1+0.5)/(5+1)=0.25`. Direct inspection confirms that its current higher-order contexts have zero observations. At an empty context, the actual backoff rule becomes

`p_k = 1/6 + (2/3) p_(k-1) = 1/2 + (2/3)^k (p_0 - 1/2)`.

Thus the static higher-order experts forecast `1/3`, `7/18` and `23/54`, moving toward 0.5 despite the lower action-level estimate. Their retained mixture weights, plus the discounted experts, raise the expert-bank forecast to 0.338276287964. The induced grammar then adds 0.007262329748. The KT-versus-Laplace prior difference actually moves in the opposite direction; it is not the reason native predicts more success.

The frozen evaluation contains zero successes in 15 action-1 events. This upward forecast shift increases its loss. This establishes the mechanism of the particular computed forecast: sparse temporal contexts and their mixture weights dominate the upward shift. It does not establish that all real repair tasks are stationary or that temporal modelling is generally inappropriate. Concatenating candidates from unrelated tasks is also not evidence of a genuine temporal law.

Constructor-supported module interventions on the same public prefix give these retrospective losses:

| Predictor/intervention | Frozen evaluation mean log loss |
|---|---:|
| Original native | 0.48641297739326594 |
| Native with lag gate disabled | 0.48641297739326594 |
| Guarded base with grammar growth disabled | 0.4664889590101616 |
| Temporal expert bank alone | 0.4782425354166344 |
| Static order-zero KT | 0.38434502402686865 |
| Original Laplace frequency | 0.42060709421822373 |

These post hoc numbers are explanatory counterfactuals, not a retuned benchmark victory. The Catalogue false positive and the original negative native-versus-frequency finding remain intact.

## Preregistered generated-stream study

The new experiment fixes four generator families, eight evaluation seeds per family, 128 steps per stream and a 32-step unscored prefix. Each model forecasts before the generator draws that step's outcome. All models then receive the same observation, including during the scored prequential segment. No predictor receives the generator identity, seed, true rule or future outcomes. Seeds are reused across families; those families are not treated as independent replicas of one common task distribution.

The distributions are deliberately chosen to exercise the known representation: stationary action-conditioned success probabilities `(0.1,0.3)`; current action XOR previous outcome with 0.075 noise; current action XOR action three steps ago with 0.075 noise; and a switch at step 64 from `(0.1,0.3)` to `(0.8,0.6)`. This is a designed mechanism study, not a representative coding benchmark.

All native constructor defaults are retained. The no-lag intervention passes `checkpoints=()`. The no-growth intervention uses the actual `ExactCompiledGuardedLearner(growth=False)`, compared with the no-lag guarded base. The conventional temporal control is the original `GrammarEnsemble`, with no induced Boolean grammar or lag discovery. Static KT isolates the frequency-prior difference. One separate development seed was used to check execution cost; its record is retained in [`FRONTIER_BITWORK_DEVELOPMENT_V018.json`](../results/FRONTIER_BITWORK_DEVELOPMENT_V018.json). No generator or predictor parameter was changed after the evaluation freeze.

Mean scored natural-log loss, averaged over the eight streams in each family:

| Predictor | Stationary | Boolean history | Lag 3 | Switch |
|---|---:|---:|---:|---:|
| Cold 0.5 | 0.693147 | 0.693147 | 0.693147 | 0.693147 |
| Laplace frequency | 0.478565 | 0.702128 | 0.702936 | 0.769760 |
| Static KT | 0.479090 | 0.702818 | 0.703684 | 0.777487 |
| Conventional temporal | 0.489977 | 0.358759 | 0.680390 | 0.644287 |
| Guarded, no grammar growth | 0.486141 | 0.365842 | 0.685855 | 0.651248 |
| Native, no lag discovery | 0.487530 | 0.292385 | 0.687305 | 0.650146 |
| Original native | 0.487530 | 0.292385 | 0.412302 | 0.650146 |

The four preregistered one-sided paired sign tests use seed streams as units and Holm correction across the four contrasts:

| Registered lower-loss direction | Wins / 8 | Mean proposed minus control loss | One-sided p | Holm threshold | Result |
|---|---:|---:|---:|---:|---|
| Stationary: frequency over native | 7 | -0.008965015693 | 0.03515625 | 0.05 | Significant |
| Boolean history: native no-lag over frequency | 8 | -0.409743687690 | 0.00390625 | 0.0125 | Significant |
| Lag 3: native over native no-lag | 8 | -0.275002463147 | 0.00390625 | 0.01666667 | Significant |
| Switch: conventional temporal over frequency | 8 | -0.125473005760 | 0.00390625 | 0.025 | Significant |

Native lag search activated in 4/8 stationary, 1/8 Boolean-history, 8/8 lag-3 and 4/8 switch streams. Actual lag promotions occurred in all eight lag-3 streams and in none of the other families. Native and no-lag forecasts are consequently identical in the other families, even where dormant lag search spent work. Comparisons involving grammar growth and the conventional temporal control beyond the registered table are descriptive secondary results.

Eight seeds provide limited power and limited distribution coverage. Significance here supports the stated generated-stream contrast only. The positive lag result does not reverse the negative stationary result or the earlier repository-trace result.

## Computation and reproducibility

Information and observation budgets are matched; **computation is not equal**. Every predictor processes 128 observations per stream. Each has the same cooperative 60-second prediction/update wall allowance, checked between operations. There is no matched hard whole-process memory or CPU budget. The full native model uses substantially more time than both frequency and the conventional temporal control.

| Predictor | Mean prediction/update wall seconds per 128-step stream | Summed measured controller CPU seconds |
|---|---:|---:|
| Cold | 0.001230 | 0.062500 |
| Frequency | 0.001101 | 0.015625 |
| Static KT | 0.011733 | 0.390625 |
| Conventional temporal | 0.070894 | 2.265625 |
| Guarded, no growth | 0.416934 | 13.406250 |
| Native, no lag | 1.308572 | 40.718750 |
| Original native | 2.555812 | 78.765625 |

The first complete execution took 154.06103859998984 seconds wall and 142.71875 controller CPU seconds. Its whole-study Python allocation peak was 5,878,213 bytes. This is `tracemalloc` allocation accounting for all models and retained traces, not process RSS or a per-model memory limit. Instrumentation and shared-host scheduling affect timing. Coarse CPU timer resolution explains tiny or zero per-cell readings. Overall timing includes orchestration and verified imports and excludes final JSON serialization. No GPU, energy, electricity saving or production speedup was measured.

The replay took 143.0669299000292 seconds wall and 140.265625 CPU seconds. All **28,672 forecasts**, input sequences and final model snapshots matched exactly. A separate verifier recomputed **21,504 scored forecasts'** log loss and Brier arithmetic from the retained traces. Replaying the same seeds adds no independent efficacy samples.

To reproduce without overwriting original evidence:

```powershell
py -3 -B scripts\frontier_bitwork_v18.py run --plan experiments\PLAN_FRONTIER_BITWORK_MECHANISMS_V018.json --output runs\bitwork-replay.json
py -3 -B scripts\verify_frontier_bitwork_replay_v18.py --original results\FRONTIER_BITWORK_MECHANISMS_V018.json --replay runs\bitwork-replay.json --output runs\bitwork-replay-audit.json
```

The runner refuses changed generator/predictor source, runtime manifest, Python version or design. A started receipt precedes outcome generation. Result paths are write-once. The source freeze covers the actual mechanism implementation and runtime, not unrelated ongoing platform packaging changes.

## New repository arms and remaining gates

The separate [`experiment_frontier_v18.py`](../scripts/experiment_frontier_v18.py) implements the user's new arms: A cold, B conventional frequency, C native Bitwork alone, D native Bitwork with verified memory and the adaptive pipeline. The older A/B/C/D protocol is not edited or silently reinterpreted.

No authentic repository trial has run. The new repository experiment requires disjoint independently curated training/evaluation sources, fresh private contracts, current native Docker qualification, explicit native recovery evidence for the function adapter and matched hard **whole-mission controller-plus-worker CPU, peak-memory and wall budgets**. The last requirement is not implemented/qualified; preflight explicitly returns HOLD even if a corpus or worker-only receipt is supplied. Arithmetic-only recovery does not admit the new function adapter. Details are in [the FRONTIER repository protocol](FRONTIER_PROTOCOL_V018.md).

The public development material includes a pinned upstream issue and an exact nested-function projection described in [the development provenance note](FRONTIER_DEVELOPMENT_PROVENANCE_V018.md). It is already exposed, excluded from unseen evaluation and has not executed in a native worker. It is not evidence of complete upstream repository repair.
