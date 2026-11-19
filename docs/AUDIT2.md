# Second audit fixes

Addressed the critical measurement defects from the November 19 second audit.

- Twin scoreboard now records each arm independently. Delta is computed only when both treatment and control results for the same task identity are present. The hard-coded control failure is removed.
- accumulate no longer records a second SIM entry. One receipt per outcome.
- Cellular automata prefer no-op unless a rule preserves every successful packet label and does not reduce packet count.
- Prior load restores global and contextual operator counts from the snapshot.
- Workflow rebase conflicts now fail the job instead of being swallowed.

The field can still change. Recorded advantage now requires an actual paired difference.
