# Temporal study: retained state, failed combined objective

The registered combined quality-and-cost criterion failed. Four of its five
tests failed; only the quality-margin test against the conventional temporal
learner passed. Selective persistent computation used more CPU and had higher
log loss than always-native BGR. It also used more CPU than the previous
adaptive controller, with slightly higher mean log loss.

Retaining state did eliminate repeated work in the matched cold comparison.
That local engineering result did not make the complete controller competitive
on the registered objective. The detector and delayed-credit ablations expose
additional negative findings below. No frozen parameters, arms, or acceptance
rules were changed after opening the evaluation.

Evidence is preserved in [the primary result](../results/TEMPORAL_MECHANISMS_V018.json),
[the independent numerical audit](../results/TEMPORAL_INDEPENDENT_AUDIT_V018.json),
and [the data-only diagnostic](../results/TEMPORAL_DIAGNOSIS_V018.json). The
[mechanism document](PERSISTENT_TEMPORAL_V018.md) defines the implementation,
credit rule, state policies, and limitations. Earlier contract failures and
their corrections remain in [the state review](../results/TEMPORAL_STATE_REVIEW_V018.json).

## Registered experiment and outcome

All 576 trials completed: nine arms, eight families, and eight independent seed
blocks. Each trial made 512 chronological forecasts, with the first 64 excluded
from predictive scoring. This gives 294,912 forecasts and 258,048 scored
forecasts. Families sharing a seed use common random draws; they are not 64
independent replicates. The independent audit checked all 294,912 forecasts.

Development selected the short registered profile: commitment 32, credit horizon
64, discount 0.98, detector windows of 16, threshold 0.25, and cooldown 64.
Primary arm E uses selective warm state. All arms serialize and restore at
observation 256 and serialize their final state. Worker startup, identity
verification, computation, inactive work, storage, restoration, and supervisor
CPU are charged. Equal wall/memory/process limits do not imply equal consumed
computation. The study did not impose an equal hard aggregate CPU allowance.

These are means per 512-observation trial. CPU is whole worker Job plus
supervisor CPU, in seconds. Log loss is in natural-log units.

| Arm | Log loss | Brier | ECE10 | CPU seconds | Wall seconds |
|---|---:|---:|---:|---:|---:|
| A frequency | 0.616591 | 0.217254 | 0.038993 | 0.617676 | 0.683657 |
| B conventional temporal | 0.510751 | 0.169282 | 0.063818 | 1.054932 | 1.132311 |
| C native BGR | 0.474825 | 0.154519 | 0.053182 | 3.229248 | 3.362223 |
| D previous adaptive | 0.501269 | 0.166523 | 0.049761 | 1.905029 | 1.997327 |
| E selective persistent | 0.502447 | 0.165873 | 0.060114 | 3.603516 | 3.752666 |
| F no detector | 0.490751 | 0.162090 | 0.049028 | 3.146240 | 3.279609 |
| G no delayed credit | 0.496696 | 0.164069 | 0.053884 | 3.683838 | 3.828521 |
| H cold computational state | 0.502447 | 0.165873 | 0.060114 | 5.102539 | 5.275032 |
| I full warm state | 0.501477 | 0.165372 | 0.060338 | 4.645996 | 4.818234 |

The registered objective is mean log loss plus `2 * total CPU / 512`.
The quality margin is 0.02 nats. Five one-sided paired seed-block sign tests
use Holm correction. The shifted-margin sign test is not a proof of mean
equivalence.

| Registered test | Favorable seed blocks | One-sided p | Passed |
|---|---:|---:|---|
| E versus C objective | 0/8 | 1.00000000 | No |
| E versus C quality margin | 1/8 | 0.99609375 | No |
| E versus C CPU | 1/8 | 0.99609375 | No |
| E versus B objective | 3/8 | 0.85546875 | No |
| E versus B quality margin | 8/8 | 0.00390625 | Yes |

E minus C is **+0.0276214876 nats and +0.3742675781 CPU seconds**.
E minus B is **−0.0083041249 nats and +2.5485839844 CPU seconds**.
E minus D is **+0.0011783178 nats and +1.6984863281 CPU seconds**.
These are observed aggregate differences, not extrapolations to repository work.

The complete primary run consumed 1,729.03125 measured CPU seconds and
1,802.022101 wall seconds. Unallocated harness CPU was 1.734375 seconds and is
included in the whole-study CPU total. Subsequent engineering and diagnosis
may overlap the replay; replay timing is not confirmatory cost evidence.

## What state retention accomplished

E and H produced identical choices and predictive probabilities on all 32,768
forecasts per arm. Their log loss, Brier score, and ECE are therefore identical.
E retained expensive learner state; H discarded it on switches and rebuilt the
same observed prefix when needed. Across their 64 trials:

| Paid work | E selective | H cold | I full warm |
|---|---:|---:|---:|
| Past observations replayed | 26,416 | 116,476 | 0 |
| Active forecasts and updates | 32,768 each | 32,768 each | 32,768 each |
| Inactive forecasts and updates | 26,238 each | 26,238 each | 65,536 each |
| Expensive state evictions | 0 | 418 | 0 |
| Logical restorations | 64 | 64 | 64 |
| Total Job-plus-supervisor CPU | 230.625000 | 326.562500 | 297.343750 |
| Measured catchup-stage CPU | 59.765625 | 173.906250 | 0.125000 |
| Measured build-stage CPU | 9.062500 | 32.390625 | 8.953125 |
| Measured inactive-stage CPU | 0.062500 | 0.156250 | 106.296875 |

E avoided 90,060 repeated observations relative to H and saved 1.4990234375 CPU
seconds per trial on average, or 29.38% of H's measured mean CPU. All inferred
catchup counts from the selected episodes and registered state policies match
the actual cumulative counters. Retention was not uniformly faster: on the
irreducible family E used 0.947265625 more CPU seconds per trial than H, where
it avoided comparatively little replay but retained larger state.

Full warm state eliminated catchup but paid for all inactive predictors. It was
slightly better in mean log loss than E by 0.0009702786 nats and used
1.0424804688 additional CPU seconds per trial. It also obtained more actual
public forecast feedback; the E/I comparison does not isolate storage alone.

State handling was substantial. E's enclosing checkpoint and final-state CPU
intervals totaled 87.234375 seconds across 64 trials, versus 35.09375 seconds
for always-native C. Those two E intervals account for 37.83% of its charged
CPU. This is one observed source of controller overhead. Build, catchup,
serialization, and restoration stage timers overlap enclosing intervals and
must not be added to them as a second CPU bill.

Mean final stored state was 529,976 bytes for E, 355,881 for C, 229,992 for H,
and 648,769 for I. E's maximum recorded Job peak counter was 58,490,880 bytes,
compared with 41,975,808 for C. These are recorded native counters, not qualified
strict simultaneous aggregate memory peaks. No energy or dollar measurements
were made.

## The detector interrupted useful native computation

The primary detector raised 316 alarms. Under the registered evaluator rule,
29 matched one of 32 known changes within the 96-observation detection window;
287 were classified as false alarms. The classification does not give the
learner access to those change times. There were 48 alarms on the delayed
family, 50 on temporal, 50 on stationary, and 52 on sparse/noisy, all of which
had no registered distribution changes.

The delayed family gives a concrete interaction failure. In every seed, E
first selected native at step 64 with a commitment through prefix 128. Its
first native episode instead lasted **8, 8, 11, 5, 13, 17, 34, and 22 forecasts**.
Every episode ended at a detector alarm, before the promised initial credit
release. The next decision had zero mature native samples. The implemented
alarm rule deliberately resets credit and interrupts commitments; the retained
trace shows that override operating against the intended delayed-credit wait.

With the detector disabled, F selected native at step 64 and retained it for
all remaining 448 forecasts in every delayed seed. Its delayed-family log loss
was 0.3023735606, exactly the native control's scored loss, versus E's
0.4876010496. This diagnoses the observed scheduling failure. It does not
establish that disabling change detection is generally optimal. The detector
improved the genuinely shifting family substantially, as the next table shows.

## Delayed credit and detection were mixed, mostly negative overall

The following differences are descriptive family means. Positive values mean
higher log loss for E. No additional significance tests were introduced.

| Family | E minus F, detector enabled | E minus G, delayed credit enabled |
|---|---:|---:|
| Stationary | +0.003630 | −0.001423 |
| Temporal | +0.019432 | +0.010269 |
| Delayed | +0.185227 | +0.069632 |
| Shift | −0.105710 | −0.008422 |
| Sparse/noisy | +0.001930 | +0.001559 |
| Misleading | −0.017226 | −0.010807 |
| Unseen structure | +0.005418 | −0.016564 |
| Irreducible | +0.000863 | +0.001765 |

Overall, enabling the detector increased mean log loss by 0.0116955705 and CPU
by 0.4572753906 seconds relative to F. Enabling the delayed-credit package
increased log loss by 0.0057511396 while reducing CPU by 0.0803222656 seconds
relative to G. The latter package includes horizon release, its associated
initial waiting rule, and a different credit window, so this comparison does
not isolate discounting alone.

The false-alarm burden and exact episode interruptions support a specific
engineering diagnosis: selected predictive loss is not a stable detector input
when the scheduler itself changes the predictor. A predictor switch can change
that loss series without any change in the stream's generating distribution.
This remains a posthoc diagnosis of the frozen implementation. It does not
authorize a retuned detector or a new positive claim from these outcomes.

## Prediction matching and remaining claim boundaries

Every selected forecast from E, F, G, H, I, and D exactly matched its independently
executed fixed frequency, temporal, or native control on the same observed
prefix. For E this comprised 6,530 frequency, 19,332 temporal, and 6,906 native
forecasts. There were zero mismatches and zero selected-learner log-loss
differences. The observed quality differences come from selection among those
forecasts rather than an approximate native reconstruction in these traces.
This statement is about the measured streams, not a proof for every input.

The held-out study contains no standard-profile persistent arm. Therefore the
short profile's development selection remains **DEVELOPMENT_NOMINATION_ONLY**.
These held-out comparisons do not independently verify improvement of the short
profile over the standard persistent profile. No extra arm was added after
evaluation and no candidate was promoted from this result.

The work establishes bounded software state restoration and a measured local
reconstruction saving against H. It does not establish the registered combined
intelligence claim, authentic repository repair advantage, cross-repository
memory transfer, qualified strict peak memory, or native containment. The
existing containment and corpus HOLDs remain relevant to those separate tasks.

Reproduce the data-only analysis into a new output path:

```
python -B -m unittest tests.test_temporal_diagnosis_v18 -q
python -B scripts/diagnose_temporal_v18.py --result results/TEMPORAL_MECHANISMS_V018.json --output runs/temporal-diagnosis-recheck.json
```

The four diagnostic contracts passed. The script imports no learner or
experiment harness, generates no outcomes, preserves the original assessment,
and refuses an incomplete or unmatched trial inventory. Its per-episode replay
counts are explicitly derived from traces; actual CPU is only reported at the
instrumented cumulative scopes.
