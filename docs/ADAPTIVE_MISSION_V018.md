# Optional adaptive computation in v0.18

The typed function mission now has an optional computation controller. The original arithmetic adapter, default function behavior, and registered A/B/C/D settings retain their behavior. An additional arm must register this optional policy separately. Its inventories can differ from the original arms because the policy changes how much synthesis and search it attempts. Nothing here closes native containment, authentic repair, transfer or historical lineage gates.

Use `initialize_functions(..., computation_controller=AdaptiveConfig(...), ranker=None)`, or pass an exact configuration dictionary. The CLI accepts `nomad-platform init --computation-controller config.json` with a `python-functions-v1` contract. An empty JSON object selects the registered defaults. A learned controller object or snapshot is refused. Configuration has bounded numeric parameters; it cannot import arbitrary policy code or private labels.

## Decisions that change work

Source admission and the memory integrity audit happen first. No repository code is imported or executed on the host. A controller rebuilt from eligible accepted public observations then chooses an allocation **before** proposal generation. The registered effort mappings are hypotheses, not measured optimal allocations:

| Selected mechanism | Candidate inventory ceiling | Public probes | GENESIS evaluations per eligible API | AST admission checks |
|---|---:|---:|---:|---:|
| Frequency | 16 | 1 | 0 | 64 |
| Conventional temporal | 32 | 2 | 1,024 | 256 |
| Native Bitwork | Caller ceiling | Caller ceiling | 4,096 | 1,024 |
| Abstain | 0 | 0 | 0 | 0 |

Every ceiling is further limited by the caller's budget. Three fresh workers are reserved for baseline/challenge/final observation, plus one if the full public suite is requested. Recovery attempts consume the same dispatch budget. Losing enough attempts can therefore cause HOLD before acceptance. No budget extension follows a private rejection.

AST admission checks count candidates checked after the existing operator generator enumerates its bounded source candidates. They do **not** bound every allocation or every enumerated candidate. The source grammar remains bounded, but eager enumeration and repeated parsing remain overhead. The generation stage records wall and controller CPU time. A zero GENESIS budget actually avoids synthesis. Static reachability limits the optional inventory to public-call-reachable files; selected structural localization can order those files using the existing WORLD MODEL.

After the allocated public probes, the controller makes a second choice, durably recorded as `F_CONTROL` before predictor construction. Existing INQUIRY selects probes when structural adaptation is enabled; actual isolated probe outcomes update the file posterior and affect proposal order. A complete passing public contract causes abstention rather than consulting private tests to find a new repair target. Otherwise the selected predictor supplies two edit-family probabilities: comparison edits versus other registered Python operators. These are coarse ranking preferences, not semantic correctness estimates. GENESIS proposals retain their registered binary-operator family in this scope.

Temporal/native choices can retrieve existing MNEMONIC effects only with at least three distinct eligible source tasks. Cheap choices skip recall. The mandatory integrity audit still checks the append-only memory and rebuilds bounded evidence models; turning retrieval off does not remove that audit cost. A structural ablation disables learned localization/probe preference and posterior sorting. A memory ablation excludes prior controller observations/utility and effect recall. A history ablation restricts the selector to frequency. Disabling selection fixes the expensive native mechanism when its registered budget permits it.

## Public learning and authority

The controller never trains from challenge/final labels. A successful independent WITNESS and final observation authorize admission of the **earlier public search trace**, including failed public candidate attempts. For each accepted mission, the stored computation value is the mean public log probability gain over the frequency comparator, clipped to [-8, 8]. The comparator and chosen forecast were recorded before those outcomes. The independent final verdict gates admission; it is not the numerical reward.

Accepted-only sampling can bias these values. WITNESS verifies repair consequences on the bounded contracts; it does not identify the counterfactual benefit of a computation policy. A better forecast on this selected trace is not evidence that the policy solves more repositories or reduces total work. The new repository experiment must test those claims independently.

Memory binds the immutable origin, exact source and candidate, public command/output receipts, before-outcome forecast journal, acceptance aggregate, epoch and action scope. Distinct source identities are required for cross-task support. Duplicate sources do not renew evidence. Evidence older than four epochs and evidence from another runtime are not used. Both public history and verified utility are bounded. Replaying a terminal mission does not create another observation. `read_function_computation_controller(memory_root, config=..., now_epoch=...)` rebuilds a read-only predictor from this audited store.

The frequency comparator is independently recomputed during validation without loading native Bitwork. Native/temporal forecasts retain trusted controller, pinned source and journal provenance; memory reads do not pay their model-inference cost again. Checksums detect corruption and stale receipt reuse. They are not authentication against a hostile writer who replaces every trusted source, journal and external anchor. Independent acceptance of repair behavior does not turn a forecast into a cryptographically attested fact.

## Recovery and cost accounting

The initial allocation lives in the immutable goal. `F_CONTROL` binds the second decision to the recorded public probes and pre/post controller snapshots. `F_DIAGNOSIS` records the actual probabilities, posterior, ordering, recall and completed-stage telemetry. Both choices precede any expensive model construction, so their replay has the same cold-residency assumptions. Once a diagnosis is present, restart reuses it without repeating predictor forecasts. A crash after `F_CONTROL` can repeat unfinished computation; it never repeats a completed public observation. Such lost work is not included in completed-stage timing totals.

`F_ABSTAINED` is terminal and readable through run/status/recover. It produces no WITNESS, final verification or learning claim. A dispatched but unobserved worker still requires the existing explicit named-container cleanup recovery. Source patches retain the existing transaction and rollback checks.

The selector uses **frozen predictor setup/per-step costs**, not noisy measured timing. These costs do not estimate the complete GENESIS/Docker/inspection workload of an effort profile. Measured inspection-plus-memory-audit, generation and post-probe ranking costs are stored separately. The summary totals completed controller stages only. They exclude isolated worker CPU, peak memory, recovery/replay overhead, publication and other uninstrumented controller work. This is not whole-mission energy, latency or peak containment accounting. A repository efficiency claim remains HOLD until the separately registered total-cost experiment runs.

## Candidate self-revision preparation

`recursion.prepare_ranking_experiment(output, development, heldout_sha256=...)` extends the existing four-production ranking research mechanism. It nominates a pure source revision using declared development tasks, writes immutable baseline/candidate projections and a matched-budget protocol, and pins an independently frozen heldout digest without reading its contents. The CLI is `python -B scripts/prepare_adaptive_self_revision_v18.py --development DEV.json --heldout-sha256 SHA --output DIRECTORY`.

This preparation executes only the existing exact-source-whitelisted trusted ranking productions. It does not import unfamiliar code. The full NOMAD module graph is outside the typed function adapter, so the projection is explicitly **not** a whole-engine self-repair. Its status is `PREPARED_NOT_RUN`, with independent native heldout observations and both regression comparisons required before further review. Equal development performance is not an eligible improvement nomination. The original baseline remains available for rollback; the authoritative runtime is never replaced. No verified self-improvement advantage follows from preparing these artifacts.

When no independent heldout corpus exists, omit its digest. The same function then emits `DEVELOPMENT_NOMINATION_ONLY`, a null heldout identity, and an explicit missing-corpus HOLD. No placeholder digest is substituted and the candidate is not yet eligible for independent testing. The current development nomination uses this path.

The focused unit tests use an explicit trusted fixture worker double. They verify choice effects, actual native predictor/GENESIS invocation in the fixed-native control, abstention, public/private separation, replay and memory bindings. They do not establish Docker execution, authentic repairs, learned transfer or repository-level efficiency.
