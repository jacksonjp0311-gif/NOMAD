# Temporal Ascension: prospective experimental contract

This study evaluates trusted binary prediction mechanisms, not independently
authored programming tasks. The source-bound machine-readable plan is the
authoritative registration. The previous adaptive results remain exposed
development evidence and are never counted as new confirmation.

## Prospective comparisons

| Arm | Mechanism |
|---|---|
| A | Original action-conditional frequency predictor |
| B | Original conventional temporal ensemble |
| C | Original native `GovernedBitworkV14` |
| D | Frozen original adaptive controller with its original calibrated configuration |
| E | Persistent controller with selective warm retention |
| F | E with change alarms disabled |
| G | E without delayed credit release or the associated initial maturity wait |
| H | E with cold reconstruction on return to an expensive mechanism |
| I | E with all three learners continuously warm and updated |

Selecting E's selective policy occurred through source review before the first
calibration outcome. Updating all three learners necessarily retains native
execution on every observation; it therefore has no clear algorithmic route
to avoid native work. I measures the extra expense and available paid feedback.
E versus I is not a pure causal comparison of storage alone. A separate forced
selection development diagnostic compares retention and reconstruction while
holding actual mechanism choices and observations fixed.

Three bounded E profiles are declared in source before calibration: standard
commitment 64/credit horizon 128, long commitment 96/horizon 192, and short
commitment 32/horizon 64. The short profile also uses a shorter, more sensitive
detector. The chosen profile minimizes mean development log loss plus twice
whole-process CPU seconds divided by 512; ties use declared profile order.
This jointly selects among predetermined profiles, not separate causal effects
of every parameter. F, G, H and I change only their named configuration fields
from the selected E profile. Mechanism priors and native code remain unchanged.

## Information and independence

Development uses seeds 18186001 and 18186002 in seven regimes. Evaluation uses
new reserved seeds 18186101 through 18186108 in eight regimes. The unfamiliar
structural combination is excluded from calibration. Each arm receives the
same action and outcome stream for each seed/regime. Models receive current
action and previously observed outcomes only. Generator family, seed, change
locations, future outcome draws and evaluator labels never enter a predictor.

Each stream has 512 forecasts, with the first 64 excluded from predictive
scoring. All work, including this prefix, remains in the cost outcome. Every
arm writes and restores a checkpoint after observation 256. Fixed and new
persistent learners restore direct typed state. D restores its original
history/logical snapshot and lazily reconstructs its learners. The registered
restart is an in-process object restoration from a real disk checkpoint;
separate trusted process tests exercise fresh-process native restoration and
writer death before publication.

Regimes cover stationary, temporal, delayed, distribution switching,
sparse/noisy, misleading, irreducible and unfamiliar structural relationships.
Switching and misleading streams have evaluator-only changes at observations
171 and 341. The generators are designed and known to the researchers. These
are not independently authored hidden tasks. Outcomes across families share
random numbers within a seed, so the inferential unit is **eight seed blocks**,
not 64 streams or hundreds of thousands of observations.

## Acceptance and cost

The primary combined score is mean scored log loss plus `2 * total_CPU / 512`.
Five one-sided paired seed-block sign tests use Holm correction at alpha 0.05:

- E versus C: lower combined score, loss difference below 0.02 nats, lower CPU.
- E versus B: lower combined score, loss difference below 0.02 nats.

All five must pass for the registered joint success claim. The margin-shifted
sign test gives directional seed-block evidence, not a general proof of mean
noninferiority. Paired 4,000-resample seed-block bootstrap intervals are
descriptive. All remaining comparisons, individual regimes and ablations are
descriptive and cannot rescue a failed primary criterion.

Each trial runs in a trusted Windows Job with equal 60-second wall, 512 MiB
memory and four-process limits. CPU is measured, with no separate hard CPU-time
kill limit. Equal resource ceilings do not mean equal consumed computation.
Whole Job user/kernel CPU plus supervisor CPU includes startup, integrity
checks, inference, active and inactive updates, detector/credit decisions,
replay, checkpoint encoding, disk publication, parsing/restoration and worker
transport. Parent orchestration and analysis CPU is additionally reported.
The final parent JSON write lies outside the study timer.

Stage timers identify nested subsets; they must not be added again to inclusive
totals. State storage and native process/Job peak counters are reported
separately. Native peak counters are not a qualified strict simultaneous
committed-memory limit. Energy and GPU costs are not measured.

Detector alarms are reconstructed independently from the public selected-loss
trace. For each known distribution change, the first alarm within 96 subsequent
observations is matched and its delay reported. Other alarms count as false
alarms. This operational metric includes alarms caused by a predictor switch;
it does not certify identification of causal or temporal structure.

## Freezing, auditing and recovery

Development selection requires complete current-source receipts, exact trial
inventory, unchanged worker transport hashes, matched inputs, registered
configurations and independently recomputed CPU arithmetic. All failed or
superseded attempts remain retained. The plan binds predictor/harness/auditor/
replay source, original BGR manifest, interpreter, development receipt, seeds,
configuration, budgets and scoring before evaluation starts. A local Git
commit precedes reserved evaluation generation. This is a source commitment,
not an external trusted timestamp or authenticated-host attestation.

An auditor importing no predictor independently recalculates probability
metrics, detector decisions, process-cost arithmetic, source/transport bindings,
paired blocks, bootstrap intervals and the five Holm decisions. An unchanged
replay must match every forecast, selection, checkpoint's deterministic state,
final deterministic state and operation count. Timing and raw serialized
timing fields are excluded from exact replay comparison. Replaying seeds adds
no independent samples and cannot replace the primary cost run.

No favorable prediction result alone authorizes coding efficacy, persistent
MNEMONIC benefit, cross-repository transfer, self-improvement promotion or
release qualification. Gates A through D retain their independent requirements.
