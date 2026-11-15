# Optional persistent computation in bounded missions

This path is opt-in research. The prospective temporal mechanism study failed
its primary superiority gate. Wiring its controller into a repair mission does
not establish coding improvement, native containment, or cross-repository
transfer. The existing arithmetic adapter, four repository arms A–D, and
optional adaptive E retain their prior interfaces and behavior.

`initialize_functions(..., persistent_controller=PersistentConfig(...))` accepts
only a validated configuration or a plain configuration dictionary. It rejects
a controller object, learned snapshot, simultaneous `computation_controller`,
or explicit static ranker. `--persistent-controller CONFIG.json` exposes this
separate path in `nomad.platform_cli init`. The mechanism study selected the
short selective-warm configuration before evaluation; its frozen configuration
is in `experiments/computation_candidate_TEMPORAL_V018/candidate/config.json`.
The API does not silently replace its caller's policy with an experiment result.

For example, after choosing a reviewed digest-pinned image and independent
contracts:

```powershell
python -B -m nomad.platform_cli --image IMAGE@sha256:DIGEST init `
  --root MISSION --source SOURCE --contract CONTRACT.json `
  --persistent-controller experiments/computation_candidate_TEMPORAL_V018/candidate/config.json
python -B -m nomad.platform_cli run --root MISSION
```

The supported program grammar remains the existing bounded JSON Python-function
adapter. Source inspection is AST-only. Unfamiliar source is executed only by
the existing Docker worker, with no host fallback. WITNESS and final comparison
remain in the trusted controller; expected private values are not sent to the
candidate worker or predictor. All current native mission qualification remains
HOLD when Docker or its qualified recovery evidence is absent.

## Decisions and evidence

The initial persistent decision sets actual registered effort caps: frequency
uses at most 16 proposals, one public probe and no GENESIS evaluations; temporal
uses at most 32 proposals, two probes and 1,024 GENESIS evaluations; native uses
the requested bounded proposal/probe budget and 4,096 GENESIS evaluations.
AST admission-check caps are 64, 256 and 1,024. These are explicit heuristics,
not calibrated coding-cost estimates. AST candidate enumeration remains eager;
its admission-check cap is not a bound on all enumeration cost.

The mechanism also controls whether structural localization and scoped MNEMONIC
recall are invoked. Existing WORLD MODEL and INQUIRY choose permitted public
probes. Their receipt-derived posterior changes actual candidate priority.
The inventory is frozen before execution; continuation does not invent new
unreviewed edits. This is bounded selection, not arbitrary autonomous repair.
Each coding decision receives at most its configured commitment length of
remaining public attempts, further reduced by the execution/history limits.
This task budget can truncate the controller's exploratory credit horizon;
it does not reproduce the unlimited-stream experiment schedule.

After diagnosis, `F_P_CONTROL` records a bounded decision, remaining dispatch
budget, candidate order, recall results and settled direct state. Before each
candidate executes, `F_P_FORECAST` binds the action and probability to that
state. The existing `F_DISPATCHED`/`F_OBSERVED` pair retains execution identity,
source, command, image and trusted comparison. `F_P_UPDATED` binds one observed
public result to one forecast and saves its settled learned state. A later
control decision can change ranking, native/temporal activation, recall,
continuation or abstention. Mandatory independent-verification dispatches are
reserved before a new search attempt.

Only candidate public-contract pass/fail enters the binary predictor stream:
registered comparison edits are action 0 and other admitted edits action 1.
Baseline probes affect diagnosis and public structural counts; they are not
relabeled as candidate success. Challenge/final outcomes never enter this
stream. They decide whether the resulting public history may be admitted to
cross-task memory. Accepted-only sampling is biased and is not a causal estimate
of computation benefit.

## Persistence and recovery

The original `AdaptiveController` already retains inactive learners during
ordinary in-process switches. Its snapshot/load reconstructs those learners
from history. The new path retains direct learned state across durable
checkpoints. The cold study control explicitly discards switched-away state;
it is not the original controller's ordinary switching behavior.

The existing concrete JSON codec bounds and validates direct state. Mission
goals and persistent journals have 64,000,000-byte ceilings; individual state
limits remain in `PersistentConfig`. No pickle or arbitrary class import is
used. Checksums provide local integrity, not authentication against an attacker
who can replace every trusted source and journal anchor.

An unconsumed recorded control is reused after restart. A forecast interrupted
before its public update is replayed from its settled prestate, checked against
the recorded probability, and settled once from the bound receipt. An ambiguous
Docker dispatch still requires explicit confirmed cleanup before retry. New
test hooks cover control, forecast, public search observation and update. These
hooks do not extend earlier native recovery qualifications automatically.
The retained 21-case default function recovery protocol does not cover these
persistent decision, pending-forecast, public-update and accepted-cache stages.
They require separately registered actual native recovery evidence.

Replay compares exact decisions, forecasts and learned state. Only explicit
codec paths for diagnostic timing and cost counters are omitted
from learned-state comparison. Histories, counts, weights, grammar, lag
proposals, gains, policy, epochs, source identities and decision chronology
remain checked, including the numerical scoring/ranking caches used by native
prediction. The codec itself invalidates its unencoded process-local packed
epoch. A terminal replay never dispatches another worker. A bounded immutable
validation memo keys the entire goal/trace, authority mode, candidate and current
source/runtime; altered content is replayed afresh, and cached data is copied.

Cross-task memory is built only from independently accepted, current-runtime,
source-distinct public records within the existing four-epoch evidence window.
The planning head and ordered receipt bindings anchor the initial public
prefix. `read_function_persistent_controller(memory_root, config=...,
now_epoch=...)` returns the controller and an explicit cache disposition.
Direct restoration requires the exact eligible prefix, compatible policy and
unexpired state. A changed, expired or extended prefix is rebuilt from the
eligible public records; suffix-only cache extension is not implemented.
Expired observations cannot survive as hidden learned state. Failed final
verification admits neither a shared checkpoint nor a new memory observation.

## Validation and remaining gates

`tests/test_persistent_mission_v18.py` runs the real controller, parser and memory
logic with explicitly authored fixture execution doubles. It checks actual
choices and state updates, restart decisions, accepted cross-task reuse,
expiry/policy invalidation, private noninterference and altered-evidence refusal.
Its accelerated boundary fixtures use commitment 1 and credit horizon 2, so a
few tasks reach actual temporal/native activation. These fixture settings are
not the frozen C32/H64 mechanism efficacy configuration.
These are software contracts, not native Docker or authentic repair outcomes.

Recorded stage costs cover inspection/admitted-memory loading, generation,
control/ranking and public updates. They exclude some preload, forecast,
whole-trace validation and recovery work outside those timers, plus Docker
worker CPU and strict peak memory. They must not be presented as complete
mission cost or used to claim efficiency.

`scripts/experiment_repository_temporal_v18.py` prepares a separate F design
linked to the frozen mechanism policy, while preserving A–D and E. It declares
prospective empty/warm/expired/foreign/shuffled memory and state-policy controls.
The executable schedule, independent curated contracts, persistent-stage native
recovery and aggregate resource accounting are not qualified. Its run command
therefore records HOLD/NOT_RUN, keeps corpus hashes null, opens no private
contracts and dispatches no repository code. No self-revision is promoted.
