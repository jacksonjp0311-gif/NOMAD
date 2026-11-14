# FRONTIER — architecture and scientific boundaries

## Core contract

For a project snapshot `S`, observed public test output `E`, and an edit `a`, FRONTIER computes:

`b = encode(E)` as a compact 16-bit failure observation, `candidate_order = rank(AST(S), public_test_syntax, b, witnessed_prior)`, and `S' = apply(S,a)` on a disposable copy. The engine executes the public tests and returns an edit proposal only when they pass. It does not claim success or promote a new skill.

WITNESS subsequently executes the complete distributed test suite and, for Catalogue, an independently specified namespace contract. Its checksum-bound result is evidence about **those executed tests on that exact candidate**. It is neither complete semantic equivalence nor a cryptographic signature.

## Separation of authority

The **evaluator** controls mutation insertion, original-source reference checks and withheld behavior. The **searcher** receives the corrupted source and a public test selector. The **witness** independently runs a new Python process with full suites and the supplemental API invariant. The searcher cannot use witness outcomes to reorder search candidates in that case. The **memory updater** may record only a witnessed accepted transformation. In v0.14, memory is a 16-bit-context-to-operation-count prior; it does not expose native BGR inference.

## Trust model

The corpus is trusted, locally installed and SHA-256-pinned, with provenance metadata and upstream license copies. Python is executed natively, not within a secured container. `repo` copying prevents edits to the immutable baseline but is not a defense against adversarial test code or arbitrary filesystem side effects. The allowlist covers Affine, Catalogue and Confection only. Source hashes detect mutation relative to the retained release; they cannot authenticate a fully compromised writer.

## Limitations revealed by the experiment

1. Public test identifiers provide meaningful localization signals but cannot uniquely determine cause.
2. Single-token mutation reversal is insufficient for many faults; a 12-candidate limit failed on two evaluation cases.
3. A learned prior can overfit even a compact 16-bit failure observation and reduce downstream validity.
4. Distributed upstream tests may not fully specify expected API behavior; a separate contract detected an accepted but wrong alternative.
5. A positive transfer claim requires disjoint task families fixed *before* tuning, independent repository holdouts and matched CPU budgets. This release supplies none of those external-inference guarantees.
6. A current negative result is still progress: it identifies the next engineering work and prevents faulty evidence from being promoted.

## Required next step

Independent issue/commit pinning, stronger test oracles, multi-file synthesis, true local sandbox, calibrated abstention and adaptive diagnostics. Maintain source lineage and evaluate the contribution of the native Bitwork runtime explicitly before attributing general coding competence to it.
