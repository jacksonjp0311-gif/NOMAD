# Audit fixes

Addressed the critical defects from the November 19 audit.

- Awake cycle now selects different bounded examples based on the proposed task label.
- Cellular automata evaluate each rule on an independent snapshot. Only the rule with the highest survival count is written back.
- Self-rewrite proposes an edit but does not commit it. Commit remains the caller's responsibility after an independent test.
- Both successes and failures are recorded in SIM.
- Twin scoreboard receives a treatment outcome on every awake cycle.
- Workflows persist the full `data/` tree, including weights and SIM.

The field can still change. Durable change now requires an independent positive measurement.
