# RECURSION Architecture — v0.15

## Core responsibility split

1. **NOMAD** inspects and constructs candidate transformations. Code is treated as executable evidence, not a text-only completion problem.
2. **BGR v1.4** consumes a declared binary action/result stream using `predict` before `observe`. In v0.15 it operates in shadow mode because its predictive advantage is unproved. Its diagnostics cannot grant authority.
3. **FRONTIER** runs public tests in a disposable copy of an allowlisted, frozen third-party package. It cannot read the independent behavior oracle during search.
4. **WITNESS** checks full distributed upstream tests and known supplemental API contracts; its digest is integrity-only, not a digital signature.
5. **MNEMONIC / EvidenceScopedPrior** may form a scope-limited preference from independent authenticated execution sources in a future release. v0.15's minimum proof requirement is 3 distinct tasks, patched source digests and receipt hashes, plus no contesting evidence.
6. **RECURSION** proposes bounded changes to a pure Python ranking function and evaluates them in development and heldout microtasks. It never edits live NOMAD source, runs an arbitrary module import, or bypasses WITNESS.

## Why refusing premature promotion is deliberate

The v0.14 learned prior worsened accepted external repairs. A future recurrence of that pattern must not silently become a durable skill. The v0.15 gate restores cold ranking whenever the evidence is insufficient, while retaining the original record. Likewise a toy search policy that wins on one synthetic distribution but fails under another is only a **candidate**, not an upgrade.

## Missing requirements for full RECURSION

- A genuinely independent source of new tasks and a frozen, external behavior evaluator.
- A sandboxed worktree with CPU/time/memory/disk/network limits and reliable process-tree cleanup on Windows.
- Signed or equivalent authenticated WITNESS receipts and trust separation from the program being evaluated.
- Source-level patch synthesis across real modules rather than just tiny generated ranker ASTs.
- Real BGR control of an informative search decision, with ablations proving a benefit over simpler predictors.
- Dual-epoch rollback and deterministic mission recovery after crash/restart.
- Non-regression tests covering multiple source versions and real deployment platforms.

**Conclusion:** This release creates the architecture of verified self-revision without claiming the independent scientific result of self-improvement.
