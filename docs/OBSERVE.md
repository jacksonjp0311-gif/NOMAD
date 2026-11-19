# Agent observation

Any agent can read the live state of the field.

`python -m nomad.observe` writes `data/observe.json` with:

- current sensory snapshot (packet count, fitness, uptime)
- recent bus messages
- recent SIM receipts

The continuous runners push this file on every cycle. External agents poll the file or the raw jsonl logs under `data/`.

No network endpoint. Local and inspectable.
