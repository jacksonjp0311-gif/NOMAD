# NOMAD v0.9 — INQUIRY experimental report

## Research question

Does a Bitwork-derived, WITNESS-trained diagnostic planner obtain useful new observations **before** patching, reducing the total cost of verified repairs relative to its v0.8 repository-world baseline and reasonable equal-option query controls?

## Setup and disclosure

- **Development seeds:** 17, 29, 41. Initial development found 36/36 final-correct, a 13.37% weighted-cost reduction, and a pre-sealing execution issue when many subprocess-heavy seeds were run under a single command window. The research solver was retained; seed batches were executed separately for reproducibility.
- **Frozen evaluation seeds:** 101, 137, 181, 223. Four train/evaluation pairs, each with 16 training and 16 separately seeded evaluation tasks; **64 generated test repositories**.
- **Synthetic repo:** six shuffled-name Python modules, declared public entry test contract, four unique causal-fault families, public module probes and a supplied candidate-edit set.
- **Training labels:** the file where a patch passed the existing WITNESS challenge and final evaluation. Evaluator metadata `true_bug_file` and `true_family` is not consumed by the diagnostic policy; a direct invariance test checks that changing these labels does not alter query choice.
- **Probe menus:** core, config, middle, entry module contract tests. Cost is respectively 0.24, 0.20, 0.34, 0.50 simulated units, with **0.90 maximum cost and three unique queries**.
- **Search cost:** each attempted edit and public test evaluation costs one simulated unit. Total proxy cost is actual candidate attempts plus contracted query costs; no measured power or CPU equivalence is claimed.
- **Final correctness:** public repair tests are distinct from the WITNESS challenge and an additional held-back final split.

All policies receive the same model-training exposure and **the same optional diagnostic menu**. The v0.8 comparator chooses to search without making optional queries. The others include prior-only ranking, a single random probe, all affordable probes, and a negative control that pays for probes but shuffles the diagnostic outcome before updating its beliefs.

## Findings

| Policy | Final correct | Candidate attempts / task | Queries / task | Total proxy / task | First-file accuracy |
|---|---:|---:|---:|---:|---:|
| v0.8 WORLD MODEL | 64/64 | 4.7500 | 0 | 4.7500 | 75.00% |
| Cost-aware prior only | 64/64 | 6.7500 | 0 | 6.7500 | 50.00% |
| Random single query | 64/64 | 5.5469 | 1 | 5.8656 | 64.06% |
| Exhaustive affordable queries | 64/64 | 3.7500 | 3 | 4.5300 | 100.00% |
| Shuffled-outcome negative control | 64/64 | 7.3438 | 1.50 | 7.7097 | 54.69% |
| **INQUIRY** | **64/64** | **3.7500** | **1.50** | **4.1150** | **100.00%** |

INQUIRY reduced mean attempted edits by **21.05%** and combined proxy cost by **13.37%** against WORLD MODEL. Relative to always probing until budget exhaustion, INQUIRY performed half as many queries while preserving the same edit count. It used **9.16% less total proxy cost** than exhaustive affordable probing.

## Why the negative results matter

**Naive cost-aware ranking underperformed.** The uncalibrated world-model score transformed into a posterior and reordered by prior/candidate-count ratio alone, which raised search from 4.75 to 6.75 attempts. That is a warning that a computational prior is not automatically reliable evidence.

**Random questioning was harmful on average.** Paying for a question is not equivalent to selecting an informative question; random querying produced 5.87 cost units/task, compared with 4.12 under INQUIRY.

**All policies solved the benchmark.** The differentiator is verified search and probe efficiency, **not** a new gain in task success or capability beyond the supplied finite operator family.

**The generated families are repetitive.** Multiple seeds change module names and values, but tasks share the same four causal patterns and public diagnostic contract structure. These results should not be used to infer performance on unseen software architectures.

## The decision rule

The current model learns smoothed `P(public_probe_passes | witnessed_fault_role, probe_role)` tables from training repairs. It combines a softened WORLD MODEL prior and these likelihoods into a posterior over candidate fault files. For every permitted query it computes expected entropy reduction and expected patch-search savings after either observation. It chooses among positive-net-value queries by information gain per unit of probe cost.

No hidden final observation enters query selection. Receipt digests bind public probe outcomes to the original source snapshot; a hash is **not** an authenticated independent execution signature.

## Independent audit and deployment check

The independent audit recreated all original fixture worlds and repeated the recorded public queries, **448 probe receipts** across the study's policies. All recorded receipt digests and pass/fail results agreed, with zero cost-accounting or budget violations. This audit verifies the *probe execution record*, not an independent implementation of the entire repair model.

A distinct four-repository integration gate required physical edits to Python sources, real subprocess `unittest` success, WITNESS challenge acceptance and final hidden evaluation. All **4/4** completed. Execution uses generated trusted fixtures only; untrusted external repository sandboxing is not provided.

## Publication-grade gaps to address

1. **Real repositories:** independently authored Python packages and failure reports with no generator-provided contracts; untrusted process isolation must precede external code execution.
2. **Probe calibration:** expected information gain depends on a simplified likelihood table. Evaluate log loss and posterior calibration, plus noisy/ambiguous contracts.
3. **Cost measurement:** replace proxy units with measured per-probe/per-candidate wall time, CPU, memory, and process launch overhead under controlled hardware.
4. **Causal ambiguity:** support multiple interacting faults, compensating patches, nonunique failure origins, and negative/non-idempotent side effects.
5. **Vocabulary invention:** learn, synthesize, and verify operators outside the supplied patch set. This is v0.10 GENESIS.
6. **Cross-domain claims:** neither direct BGR-v1.4 runtime coupling nor cross-language skill transfer was established here.

**Interpretation:** the study supports a narrow form of budget-aware active diagnostic selection that improves verified repair efficiency on a bounded synthetic repository family. It is not evidence of general autonomous software engineering or AGI.
