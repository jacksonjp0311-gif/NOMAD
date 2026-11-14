# Candidate self-revision and rollback

Version 0.18.0. This extends the existing RECURSION mechanism; it does not install
an autonomous replacement for NOMAD or establish measured self-improvement.

`nomad.recursion.review_isolated_revision` audits an already completed platform
mission against its original source-only NOMAD checkout. It requires a completed
WITNESS observation and a distinct final observation, exact baseline identity,
an unchanged file inventory, and changes confined to one or two explicitly
declared NOMAD modules. Tests, evidence, version, mission supervision and verifier
modules are outside that scope. A stale authoritative checkout is refused.

Two separate isolated regression receipts must identify the exact baseline and
candidate bytes, reviewed image, complete unittest discovery command, separate
container identities, successful completion, complete bounded output and
confirmed cleanup. A public test command cannot substitute for the regression
command. Receipt checksums require an independently trusted storage/commit
anchor; they are not signatures or protection from a hostile host administrator.
Passing this audit means **eligible for independent review**, not acceptance of
an improvement. Exit status alone does not establish comprehensive test quality
or an efficacy gain. A controlled held-out comparison is still required.

The audit has no authoritative-source write operation. The original source and
mission baseline remain available for rollback. A failed review preserves the
candidate, original and evidence for investigation. Uncertain external effects
remain subject to the existing EffectLedger reconciliation rules.

## Native qualification

The command first checks Docker availability, the exact current host/image/policy
containment receipt and live Docker preflight. It does not run candidate code on
the host and does not turn an absent prerequisite into a mock pass.

```powershell
py -3 -B scripts\review_self_revision_frontier_v18.py --output runs\self-review.json
# After an independently completed isolated candidate mission and full regressions:
py -3 -B scripts\review_self_revision_frontier_v18.py --mission-root runs\self-mission --authoritative-source .\source-only-original --allowed nomad/proposal.py --baseline-regression runs\baseline-regression.json --candidate-regression runs\candidate-regression.json --native-qualification runs\native-qualification.json --output runs\self-review-native.json
```

Use forward slash repository paths with `--allowed`, for example
`--allowed nomad/proposal.py`; the sample module name denotes the operator's
reviewed proposal scope, not a module added to NOMAD. The original source checkout
must be disjoint from the mission and must exactly match its pinned baseline.

Actual evidence: `results/SELF_REVISION_FRONTIER_RECHECK_V018.json` records HOLD
before candidate review because Docker is absent. Earlier source-bound receipts
remain unchanged. Software tests exercise stale
source, protected edits, missing final evidence, altered receipts and unchanged
authoritative bytes using explicitly mocked mission completion. They do not
demonstrate native isolated self-improvement. The current general function
adapter also admits only a bounded subset of Python; arbitrary NOMAD modules may
remain unsupported rather than being executed directly.
