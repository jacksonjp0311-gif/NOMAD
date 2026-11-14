# v0.18 FRONTIER typed function missions

This incremental adapter broadens the existing isolated mission beyond a single
arithmetic `solve(x,y)`. It reuses FRONTIER, GENESIS, RESONANCE, WORLD MODEL,
INQUIRY, original native BGR, WITNESS, MNEMONIC, the mission journal and the
existing Docker backend. It does not qualify arbitrary Python or native
containment. Docker is absent on the development host; all completed mission
tests described here use controlled observation doubles.

## Supported contract

An admitted source-only repository may contain up to 32 Python modules, with
ordinary functions, local package imports, literal module constants, branches,
loops, comprehensions and a registered set of pure builtins and collection/string
methods. Module ASTs are limited to 512 nodes, functions to eight parameters,
and source admission applies the existing file, byte, path, link and credential
limits. Function execution occurs only through Docker.

The adapter rejects external imports, classes, decorators, callbacks expressed
as lambdas, nested definitions, dynamic imports, reflection, global/nonlocal
rebinding, I/O, executable module initialization and unregistered attributes.
It rejects native libraries, bytecode and importable archives in the snapshot.
Module aliases cannot be rebound or shadowed. Forbidden builtins cannot be
retrieved as values and then called through an allowed spelling. These are
conservative admission rules, not a replacement for kernel containment.

Each case specifies `module`, `function`, positional JSON `args`, optional JSON
`kwargs`, and exactly one of `expected` or `raises`. Only registered builtin
exception names may appear in `raises`. JSON is finite, depth and byte bounded.
Comparison preserves distinctions such as boolean versus integer, and integer
versus floating JSON representation. The three nonempty public, challenge and
final partitions must have disjoint input identities.

```json
{
  "adapter": "python-functions-v1",
  "goal_text": "Preserve the declared API behavior",
  "public": [{"module": "bounds", "function": "limit", "args": [2, 5], "expected": 2}],
  "challenge": [{"module": "bounds", "function": "limit", "args": [-3, 1], "expected": -3}],
  "final": [{"module": "bounds", "function": "limit", "args": [18, 7], "expected": 7}]
}
```

An optional `public_command` is exactly the registered full unittest command:
`["python","-B","-m","unittest","discover","-s","tests","-q"]`.
Other test runners and dependency installation remain outside this adapter.

## Actual planning and learning

`frontier.inspect_function_repository` performs admission and constructs a
finite inventory without importing repository code. Existing Python AST
transformations include expression, comparison, constant, identifier and
augmented-assignment changes. Bounded composition joins transformations across
at most two files. The inventory is fixed before preference ranking.

For public two-integer APIs, existing GENESIS also searches its typed expression
grammar and binds the resulting expression to the actual parameter names with
AST renaming. This can synthesize a replacement expression absent from the
registered local mutation list. GENESIS uses public examples only, at most
4,096 evaluations per eligible API. String/list program synthesis and general
conditional synthesis are not implemented. GENESIS and AST work counts remain
separate; candidate executions are separate again.

Existing repository graph construction and WORLD MODEL structural scores give
an initial file prior. INQUIRY selects public callable probes by expected
utility. A declared reachability likelihood assumption models a fault in a
reachable module as more likely to fail that API. This is a heuristic model,
not learned calibration or causal proof. Probe results update the posterior,
which changes actual file/proposal priority. A deterministic baseline probe is
used when no discretionary query has positive utility. Disabling adaptation
uses fixed probe order and removes world/MNEMONIC preference.

RESONANCE encodes the bound API equality observations with numeric input
correlations disabled. The original native BGR ranks the same proposals through
the distinct `python-call-relational-vs-other` action scope: comparison versus
other registered transformation. A typed GENESIS expression is explicitly
recorded as originating from GENESIS and uses the coarse other-action class.
No eligible history means cold effective probabilities. This is actual native
invocation, not evidence that native ranking improves repairs.

Accepted tasks enter a separately scoped append-only learning journal. The
record binds immutable mission origin, source and proposal, public execution,
WITNESS, private-final aggregate identity, commit identity and capture epoch.
Private examples and observed private values are not copied into shared
memory. Source/action replays do not create independent support or refresh TTL.
Original EvidenceMemory admits representable single-file effects and its recall
can affect later priority. Package and joint multi-file effects abstain from
that per-file representation rather than invent individual causal effects.
The world/native models can still retain scoped accepted task observations.
No learning record grants skill authority or skips fresh verification.

## Durable execution and private verification

The existing mission owner lock, journal, effect ledger and snapshots are reused.
`F_PATCH` records complete before/after manifests before any file write;
`F_PATCHED` closes the transaction. A restart accepts only old/new bytes for
each file in a pending transaction and finishes the recorded patch. An
unrecognized modification remains HOLD.

Every `F_DISPATCHED` operation records a fresh container name before execution.
`F_OBSERVED` binds image, exact command, source digest, file/byte counts, cleanup,
exit status and complete output digest. Ambiguous dispatch requires explicit
`recover`, confirmed disposal and a new budgeted observation. A lost result is
never treated as a pass. All probes, candidate checks, suite checks, verifier
workers and recovery retries consume the persisted execution budget.

Public-correct search seals one candidate with `F_SELECTED`. Optional full-suite
checking follows. Separate fresh workers observe baseline public/challenge,
candidate challenge and candidate final behavior. Expected private values never
enter their commands or mounted source. The fixed observer returns one bounded
JSON document; the trusted controller compares the returned values, then the
existing WITNESS recomputes agreement from those observations. Strict source
admission prevents repository code from reaching stdout/reflection channels to
impersonate the observer. This restricted grammar boundary is not a proof for
arbitrary Python or a hostile administrator.

Private rejection restores the baseline and ends the mission. It does not
reorder candidates or provide hidden counterexamples to search. Successful
`F_WITNESS`, `F_FINAL`, `F_COMMITTED` and `F_LEARNED` are each recorded once.
Commit accepts only the disposable local snapshot. It does not edit the original
repository, replace NOMAD, create a Git commit, merge, publish or deploy.

## Interfaces

```python
initialize_functions(root, source, *, goal_text, public, challenge, final,
    policy, ranker=None, memory_root=None, capture_epoch=0,
    adaptive_enabled=True, max_candidates=64, max_executions=96,
    probe_budget=3, max_files_changed=2, public_command=None)
run(root, *, interrupt_at=None)
inspect(root)
recover(root)
resolved_goal(root)
read_function_memory_ranker(memory_root, *, mode="native", now_epoch=0)
```

The original arithmetic API remains available. The common run/status/recover
commands route by the sealed adapter identity. `resolved_goal` exposes
`candidate.files` as the selected relative-path-to-source map and `candidate.id`
as its identity. Raw `goal.json` retains a null candidate and the frozen inventory.

```powershell
python -m nomad.platform_cli --image REVIEWED_IMAGE@sha256:REAL_DIGEST init `
  --source SOURCE --root MISSION --contract CONTRACT.json `
  --candidate-budget 64 --execution-budget 96 --probe-budget 3 `
  --max-files-changed 2 --ranker native --memory-root MEMORY --epoch 0
python -m nomad.platform_cli run --root MISSION
```

No image fetch or host execution fallback occurs. A reviewed local image and
actual native isolation/recovery qualification are still required.

## Evidence boundaries

`tests/test_frontier_function_mission_v18.py` exercises branches, multi-file
composition, real parser/GENESIS/native calls, diagnostic ordering, distinct-task
memory, expiry, rejection and crash boundaries with controlled worker doubles.
`tests/test_function_security_frontier_v18.py` retains independent admission and
provenance regressions. Passing these tests is controller/admission evidence,
not native Docker qualification.

The public-development case in `experiments/development/keon2733` pins an authentic
upstream defect and its exact function projection. It is exposed development
material, not an unseen evaluation task, and the projection is not the complete
upstream repository. It has not run natively and does not establish a repair.

Remaining gates include native qualification of this function adapter's recovery,
independent external repairs, matched evidence of useful learning, broader
dependency/API support and authenticated verifier protection. The frozen v0.14
negative transfer result and Catalogue false positive remain unchanged.
