# TRANSCEND Architecture — v0.13

## Scope and objective

`NOMAD` carries a scalar, language-neutral learning policy into language-specific execution. The **learning mechanism is not rewritten per language**: `GENESIS GrammarPrior` uses NOMAD's existing eleven-bit failure signature as the context and the AST root production as the learnable choice. Learning from `python` and `javascript` is restricted to program candidates independently executed in those runtimes and supported by WITNESS.

This tests **cross-language portability of a decision policy under a supplied common grammar**. It is not a demonstration that arbitrary software has been semantically unified or that NOMAD has independently learned programming languages.

## Typed expression intermediate representation

Supported nodes: `Name(x|y)`, small integer constants, `Add`, `Sub`, `Mult`. Non-supported AST nodes raise an error; no attributes, imports, arbitrary calls, floor division, loops, mutation, IO, or lexical rewriting. Nesting, syntactic size and intermediate integer magnitude are bounded. Resulting source is emitted as:

```python
def solve(x: int, y: int) -> int:
    return ((x * x) + y)
```

```javascript
function solve(x, y) { return ((x * x) + y); }
module.exports = {solve};
```

```rust
fn solve(x: i64, y: i64) -> i64 { ((x * x) + y) }
```

The emitter *never* embeds the target expression oracle, successful transformation label or hidden task-family name. Those exist only in the independent fixture generator or evaluator metadata. The search process sees **public examples only**.

## Two-process training/evaluation separation

- Process A runs frozen training families in **one** native language; it saves only successful source-language WITNESS events. A second, separate Process A instance trains the opposite source language. Both processes exit.
- A separate Process B loads the two **frozen** memory ledgers; it creates disjoint held-out expression families from preregistered seeds; and it runs cold, global, shuffled-context and Bitwork-conditioned search under the same expression-evaluation budget.
- Target-language source is constructed from the selected candidate and executed with its **actual** runtime; fresh public, WITNESS challenge, and final-test observations must pass. Final examples are never returned to the search policy.

The transfer key is `(binary_failure_signature, AST_root_production)`. Language identity, module name, path and task family are excluded from the key; source language is retained as provenance and checked before transfer.

## Evidence and negative controls

`TransferMemory` stores source task ID, source language, original Bitwork context, validated AST root, generated program hash, complete WITNESS receipt and a hash chain. Exact task IDs cannot be double-counted. Frozen ledgers cannot be extended. A changed event or mismatched WITNESS hash is rejected when loaded. The hash chain detects accidental/noncoordinated corruption but is **not a cryptographic signature** against a full-store attacker.

A current-language `WITNESS` receipt is needed on *every* target task; past source receipts never authorize target certification. Independent final tests follow afterward. Overfitted candidates that only pass public examples remain unpromoted.

The fixed grammar is the same for all policies; only candidate ordering changes. Cold search starts with no learned preference. Global learns frequencies but discards Bitwork context. Shuffled keeps training exposure and global frequencies but scrambles context associations. All candidate evaluations are counted deterministically.

## Runtime and numeric assumptions

Actual `python -I -S -B` and Node.js executions were observed; `rustc` was absent. Rust codegen and an optional native test runner are implemented but **the released Python↔JavaScript data do not claim any Rust success**. The reference evaluator preflights every intermediate result against the common exact integer range \([-2^{53}+1,2^{53}-1]\); invalid inputs and overflow lead to refusal, not guessed equivalence. No arbitrary third-party code is run or sandboxed.

The native execution subprocesses are intentionally allowed only **trusted generated fixtures**. They do not provide process isolation or safe execution of user-supplied repositories. Use containers, network restrictions, resource limits, disposable workspaces, and explicit permissions for later real-world evaluation.

## v0.14 progression

Build independently sourced repository-level tests with frozen issue descriptions and branches. Establish language semantics at the program and module level, not only integer expression level. Test Rust natively; add benchmark leakage checks, effects across files, time/CPU/RSS measurements, and multi-run uncertainty intervals. Leave failed claims in evidence history.
