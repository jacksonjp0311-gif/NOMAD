# v0.18 qualification: evidence and mathematics

This supplement preserves the original studies and their negative findings. It
does not introduce a new version or claim a learning breakthrough. The decisive
prospective experiment is specified in `INTELLIGENCE_PROTOCOL_V018.md`; it has
not run on an independently curated held-out repository corpus.

## What the frozen negative result means

The original `results/BITWORK_V018.json` compares predictions over preserved
public execution traces. A separate implementation in
`scripts/analyze_frozen_bitwork_v18.py` checks its likelihood arithmetic against
the original bytes. It neither reruns the predictor nor edits the benchmark.
The new audit is `results/BITWORK_NEGATIVE_AUDIT_V018.json`.

For binary public outcomes y and predicted success probability p, the recorded
loss is L(p,y) = -y ln(p) - (1-y) ln(1-p). The original action encoding has only
two classes: relational edits and other expression/operator edits. Native BGR
is actually invoked by the original study, but this two-action experiment is
not a demonstration of general repository reasoning.

| Action class | Evaluation success / events | Frequency probability | BGR probability | Weighted excess BGR loss |
|---|---:|---:|---:|---:|
| Relational edits | 2 / 5 | 0.4 | 0.4198444855 | 0.0002030366 |
| Other edits | 0 / 15 | 0.2857142857 | 0.3455386177 | 0.0656028466 |

The weighted excess losses sum to 0.0658058832. The independently recomputed
mean losses are 0.4206070942 for frequency and 0.4864129774 for BGR. BGR places
more probability on success in both classes; its higher probability for the
failure-only second class explains almost all the observed difference. This
is a decomposition of an already observed result, not a causal experiment on
the predictor's internal mechanisms.

Both controls rank every recorded candidate pool identically. Their mean
observed public-success rank is 1.0. The ranking statistic is conditioned on
the two pools containing a public pass, excludes unobserved candidates, and
does not certify the resulting patches. The preserved Catalogue false positive
remains rejected by its independent namespace contract.

Only eight training events and twenty evaluation events appear in this replay.
The three cost repetitions are repeated timings of the same data, not three
independent efficacy samples. No significance, general transfer, GPU efficiency,
energy saving or dollar saving is inferred.

## Prospective qualification

The next experiment contrasts cold NOMAD, adaptive NOMAD without native BGR,
full adaptive NOMAD with native BGR, and frequency learning without the other
adaptive components. B and C differ only in the native ranker. Every arm sees
the same training observations, public information, candidate grammar and
declared budgets. Evaluation tasks must not update later evaluation trials.

A valid preregistration binds code, seeds, task and repository identities,
public specifications, independent final contracts, acceptance rules and
metrics before private contracts are opened. The current protocol draft and
training candidate catalogue are not a completed preregistration: an admissible
unseen corpus and native isolation/recovery receipts are missing. Repeating a
deterministic task under different order seeds does not add independent tasks.

Independent final acceptance is the primary functional metric. Public test
success alone is insufficient. False success must be reported with an explicit
denominator, along with rejection, exhaustion, unavailable tasks, execution
count, CPU, memory and latency. Host-controller costs and isolated workload
costs must remain distinguishable; missing measurements are null, not zero.

The current repair adapter is intentionally restricted to strict arithmetic
functions and transparent public aliases. Authentic upstream tasks outside that
envelope are unsupported. Rewriting such tasks into synthetic arithmetic
fixtures would not demonstrate repair of their original repositories.

## Evidence and verification limits

A mission identity binds its original source, goal, runtime and private-contract
hashes. A chained journal records the actual public probe, proposal, execution,
WITNESS observation, final check and memory admission. The learner cannot grant
acceptance. Private negative outcomes terminate the attempt rather than
becoming a search oracle. Accepted memory must retain source and verification
provenance; duplicates, expired observations and conflicting support cannot be
silently promoted into new independent evidence.

The bounded observer checks finite private examples through a restricted
arithmetic interpreter. It is not a proof of arbitrary Python semantics.
Checksum chains detect changed bytes relative to a trusted anchor; they do not
authenticate a maliciously replaced chain or a compromised host administrator.
Mocked Docker receipts exercise control-flow contracts, not a kernel execution
boundary. Production qualification requires actual independent consequences.
