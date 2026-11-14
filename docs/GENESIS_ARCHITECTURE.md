# GENESIS synthesis contract

## Claim
GENESIS constructs **expressions** from a supplied safe integer AST grammar. It does not autonomously author arbitrary code or execute untrusted projects inside a security sandbox. The existing NOMAD Bitwork state encoder orders grammatical exploration; the WITNESS evaluator admits candidate consequences on withheld evidence.

## Algorithm

1. Parse a safe single-return `solve(x,y)` function and compute a Bitwork failure signature from the initial program and visible examples.
2. Look up the witnessed contextual root-operator prior for that signature. Fall back toward global frequencies with empirical-Bayes shrinkage.
3. Enumerate typed arithmetic expressions by AST size in the order dictated by the root-production prior. Deduplicate programs observationally *on the active visible subset* to reduce redundant work.
4. When a candidate matches the active subset, test it against the rest of the public examples. Append a counterexample and restart if needed. All attempts share a bounded total candidate budget.
5. Once a candidate matches all visible examples, materialize its AST into a generated `solution.py`; optionally run real on-disk `unittest`.
6. Invoke WITNESS once on the separate challenge split; check the final split separately; only a supported, final-correct example can train another prior. A WITNESS failure does **not** become a hidden training signal during the search.
7. Persist a witnessed model snapshot using a checksummed JSON envelope. A checksum detects accidental changes but cannot identify or authenticate a malicious publisher.

## Guarantees within this model

- No candidate syntax outside the validated arithmetic AST grammar is executed by this module.
- Neither challenge values nor final expected values are an argument to `synthesize`'s decision logic; the `SynthesisTask` object contains them only for downstream evaluation. A regression test changes both hidden splits and confirms identical search outcomes.
- Both grammar expansion and number of visible counterexamples have explicit bounds. Observational dedup may discard a distinguishing program on a small subset; adding a public counterexample rebuilds equivalence classes.
- The learner can alter expansion order but cannot assert correctness. A WITNESS receipt with an invalid checksum is refused by the learner.

## Non-guarantees

- General semantic equivalence, full Python type inference, unrestricted code generation, adversarial isolation, unbounded completeness, or optimized resource use.
- End-to-end speedup; the study measures candidate-vector evaluations, not total training and evaluation cost.
- Correctness of external tasks without an independent specification and tests.
- Proof that the original standalone BGR predictor contributes to performance; the current encoding and contextual policy are derived from earlier NOMAD/Bitwork implementations.
