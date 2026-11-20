# Causal path

The field can change synthesis order only after a WITNESS-backed success.

- The proposer names a domain. That domain is the acting domain for examples, tool, and operator. Orbit is logged but cannot redirect the cycle to a different domain.
- Treatment loads the saved `GrammarPrior`. Control uses a fresh cold prior (default Add, Sub, Mult; `witnessed = 0`).
- Synthesis sees public examples only. WITNESS scores the challenge split. An independent final split is checked after that. Public-only correctness does not pass the gate and does not update the prior or the packets.
- On a certified treatment success, `GrammarPrior.add_witnessed` increments `witnessed` and updates operator counts for the task's failure signature. `prior.order` then follows those scores. The prior snapshot, including `witnessed`, is persisted.
- A later cycle on a matching signature therefore synthesizes in a different operator order than a cold start.

A certified correctness or evaluation-cost advantage on the frozen `square_product` held-out family is documented in `docs/PLAN.md` and produced by `python -m nomad.heldout`. That result is a matched-budget measurement on one integer family. It is not unrestricted coding and not a general learning claim.
