# Continuous cybernetic loop

Awake and sleep runners that live inside NOMAD.

## Schedule

30/30 sprint.

- Awake: top of every hour (`0 * * * *`).
- Sleep: half hour (`30 * * * *`).

Awake acts. Sleep consolidates. Then the next awake. Control arm freezes updates on both.

## Loop

- **Awake**: loads MNEMONIC and the grammar prior, attempts bounded synthesis on a public task, records the outcome (candidate, public_correct, abstention) with timestamp.
- **Sleep**: consolidates the prior from recent successes. Control arm freezes.
- **Twin**: treatment and control run the same schedule. Only measured difference on public success counts as learning.

## Fitness

Public-example correctness under the current prior. Later: predictive compression proxy (bits needed under the shared model).

## Boundaries

- Bounded arithmetic synthesis only (GENESIS scope).
- No unrestricted code generation.
- Memory and prior updates remain candidates until external authorize.
- No transformers.
- Existing platform HOLDs and claim boundaries unchanged.

The field and the receipts are the persistent geometry. The runners keep it moving.
