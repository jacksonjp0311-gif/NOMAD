# NOMAD v0.18.0 PLATFORM architecture

The platform adds Windows operation, bounded execution, durable mission state and release verification around the existing intelligence system. It does not replace Bitwork with a cloud model. Native container qualification on this ROG remains **HOLD** because Docker is unavailable. A working controller or a passing mock test does not clear that gate.

## Preserved intelligence architecture

```text
Bitwork → RESONANCE → WORLD MODEL → INQUIRY → GENESIS
                                              ↓
                                          execution
                                              ↓
WITNESS → MNEMONIC → verified learning → next action
```

These components and their earlier research results remain in the repository. Their current integration differs by adapter:

| Component | v0.18 isolated mission integration | Boundary |
|---|---|---|
| Original native BGR/Bitwork | `NativeDecisionRanker` can rank public-correct proposals through the preserved runtime. | Ranking only. No eligible evidence means stable cold ordering. |
| RESONANCE | Preserved implementation and inherited tests. GENESIS retains its existing Bitwork failure encoding. | Full RESONANCE observation fusion is not wired into the isolated adapter. |
| WORLD MODEL | Preserved repository graph and localization research. | The operator supplies the target file; isolated multi-module localization remains HOLD. |
| INQUIRY | Preserved public-probe selection and evidence contracts. | The new adapter uses a fixed public test command; isolated adaptive probes remain HOLD. |
| GENESIS | The existing bounded synthesizer constructs expressions from public examples. Existing AST transformations provide additional proposals. | No challenge/final input enters synthesis or ranking. |
| Execution | `isolation.run_isolated` executes repository tests through Docker only. | Missing backend, preflight or cleanup proof means refusal/HOLD, never host fallback. |
| WITNESS | The original `Witness` consumes independently recomputed public and private observations. | A bounded arithmetic interpreter supplies observations without executing repository code. |
| MNEMONIC | Existing scoped memory, expiry, contradiction handling and skill-admission boundaries are retained. | The new mission does not automatically promote its observation into MNEMONIC skills. |
| Learning | A completed mission persists one content-bound observation in `learning.json`. | Replay reuses that observation. It is not multiple independent tasks or a general skill. |

The older WORLD MODEL and INQUIRY execution helpers run explicitly trusted fixtures on the host. Routing an unfamiliar repository through those helpers would bypass the new isolation boundary. Integration requires a new isolated adapter and qualification, rather than a call added merely to complete the diagram.

## Supported repository contract

`nomad.platform_mission` currently repairs one operator-selected Python file containing exactly one `solve(x, y)` function with a single bounded integer-arithmetic return expression. It rejects imports, decorators, default arguments, annotations, arbitrary calls and unsupported syntax in that target. The rest of the admitted repository may contain public tests, but NOMAD does not import or execute those files while planning.

The source directory must be separate from the mission directory and pass source admission. Git metadata, credential-like files, links, Windows reparse points, hardlinks, unsafe names and quota violations are refused. Use a reviewed source-only export rather than a working checkout containing `.git` or environment files. The original source directory is never edited.

Each mission supplies nonempty `public`, `challenge` and `final` partitions. An observation is `{"x": 4, "y": 2, "expected": 2}`. Input identities must be unique within each partition and disjoint across partitions. Source size, syntax size, input values and GENESIS work are bounded. Private rejection ends the mission; the controller does not feed hidden failures back into search.

The accepted claim is limited to this arithmetic contract and the observed public test run. It does not establish arbitrary Python behavior, multi-file correctness, a real upstream issue repair or safe deployment.

## Operator and Python interfaces

`python -m nomad.platform_cli` and the supported source-linked `NOMAD.cmd` launcher expose:

| Command | Effect |
|---|---|
| `doctor` | Reports runtime and Docker prerequisites without running repository code. |
| `runtime-smoke` | Runs controlled native language smoke programs, separately from untrusted isolation. |
| `trusted-demo` | Runs the preserved generated CodeWorld fixture with explicit trusted host execution. |
| `dry-run --source PATH` | Admits and hashes a source snapshot without executing it. |
| `init --source PATH --root PATH --contract FILE` | Freezes source, contract, policy, runtime identity and the public proposal. |
| `run --root PATH` | Continues the mission through isolation and independent contract checks. |
| `status --root PATH` | Checks persisted identities and reports state. |
| `recover --root PATH` | Confirms disposal of a recorded ambiguous container; does not accept a missing result. |
| `isolated-demo --root PATH` | Creates a controlled fixture and attempts the same Docker-only mission path. |

Use global `--config FILE` or `--image REVIEWED_REFERENCE` before the subcommand. An image must be reviewed, present locally and pinned by its real registry digest. The platform does not fetch images or install Docker. `init` and `isolated-demo` offer `--ranker cold|native|frequency|shuffled`; these modes do not relax verification.

The Python API is:

```python
initialize(root, source, *, goal_text, public, challenge, final,
           policy, target="solution.py", max_eval=65000, ranker=None)
run(root, *, interrupt_at=None)
inspect(root)
recover(root)
```

`policy` is a validated `SandboxPolicy`. An optional ranker for this adapter uses the explicit `genesis-vs-ast` action schema. Historical relational-edit observations are not interchangeable with evidence about this schema. The CLI creates an empty scoped ranker; it does not silently import an unverified prior. Without eligible observations, selecting `native` does not imply a learned ordering or an advantage.

## Mission storage and transitions

```text
mission/
  goal.json       pinned goal, policy, proposal and runtime/source identities
  sealed.json     challenge/final examples; never in the worker mount
  baseline/       admitted original repository bytes
  workspace/      disposable candidate repository; committed snapshot stays here
  events.jsonl    fsynced, hash-chained transitions
  mission.lock   operating-system ownership lock
  effects/        separate fenced external-effect ledger
  learning.json  one verified observation, written only after local commit
```

Normal progression is:

```text
PLATFORM_CREATED → PATCH_PLANNED → PATCH_APPLIED
  → EXECUTION_DISPATCHED → PUBLIC_RESULT → WITNESS_RESULT
  → FINAL_RESULT → COMMITTED → LEARNED
```

A negative public, WITNESS or final observation restores the original target and records `REVERTED`. No public-correct proposal leads to `EXHAUSTED`. Here, `COMMITTED` means accepting the mission's local candidate snapshot. It does not create a Git commit, merge, push, publish or deploy.

The controller uses the existing OS ownership lock and validates every journal transition. Original-source, candidate, source-manifest, private-evidence and runtime-source identities prevent stale artifacts from silently continuing after changes. Windows fixture materialization writes exact UTF-8 bytes so newline conversion cannot invalidate the planned hash. Windows byte-range lock contention becomes a mission HOLD.

Each dispatch gets a fresh container name persisted before launch. Identical semantic missions in separate directories do not share cleanup ownership. An execution receipt must match that name, image digest, command, source snapshot hash, file count and byte count. Exit status, timeout, cleanup and pass fields must agree. WITNESS receipts and final observations are checked again during recovery.

If the controller dies after dispatch but before recording an outcome, the next `run` refuses to guess. `recover` asks Docker to confirm disposal of only that recorded container. If confirmed, the lost result is discarded and the next run performs a new experiment. If disposal is uncertain or Docker is unavailable, recovery remains HOLD. Recorded final results and learning observations are reused rather than counted again.

The external-effect ledger must exist and be replay-safe before a mission advances. Unknown remote effects require independent authoritative reconciliation. This adapter adds no irreversible external-action integration and makes no distributed exactly-once claim.

## Isolation and verifier trust boundaries

The worker sees a disposable source-only snapshot mounted read-only. It does not mount the original repository, mission journal, evidence partitions, host credential stores or Docker socket, and it does not inherit the host's environment secrets. Path admission rejects known credential-like files; it does not certify that arbitrary source text contains no embedded secret. The backend requests Linux containers, no network, a read-only root filesystem, a non-root user, dropped capabilities, no privilege escalation, private cgroup namespace, and CPU, memory, PID, time and output limits. Image-declared volumes are refused. Fresh Docker client configuration and a fixed local endpoint avoid inherited contexts and registry helpers.

These settings are requests to the real engine, not containment proof by themselves. `scripts/qualify_isolation_v18.py` records controlled native probes when prerequisites are available. On this host, Docker absence leaves native containment HOLD and no controlled container case has run.

Private arithmetic checks use a separate observer implementation within the trusted controller process. The observer interprets the admitted grammar; it never imports the candidate. This protects against candidate-written test reports and keeps private rows out of the worker mount. It is not authenticated remote WITNESS, a separately protected verifier service, or protection from an attacker who can rewrite the trusted host controller and all evidence. Local hashes are integrity checks, not signatures.

## Verification and remaining integration

`tests/test_platform_mission_v18.py` covers interruption points, ambiguous dispatch recovery, receipt substitution, stale runtime/evidence, private contradictions, duplicate observations, source preservation, Windows ownership, links and portable snapshot ordering. Docker mocks test controller contracts only. Native process tests and native containment experiments are reported separately.

The inherited Catalogue false-positive remains a permanent regression: incomplete public test success must not authorize a namespace-breaking repair. Platform work does not revise the negative v0.14 transfer result or turn a bounded native Bitwork benchmark into proof of general coding improvement.

The next work is in [NEXT_ITERATION.md](NEXT_ITERATION.md): native containment and interrupted isolated missions, independently validated external repairs, and isolated WORLD MODEL/INQUIRY integration. Automatic cross-mission MNEMONIC skill admission remains HOLD until its evidence and independence gates are demonstrated.
