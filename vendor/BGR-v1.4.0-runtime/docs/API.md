# Bitwork v1.4 API

Bitwork accepts chronological **binary action/outcome streams**. Given the next
action, it predicts a probability for outcome `1`; after the actual outcome is
observed, the caller supplies that outcome to update the learner. The interface
does not interpret natural language, connect to a database, choose external
actions, or execute tools. An application adapter must define the meaning of
its binary observations.

## Python interface

Run from the extracted project root with Python 3.11 or later. The engine uses
the Python standard library.

```python
from bgr140 import Bitwork, GovernedBitworkV14, FullBitworkV14

model = Bitwork()  # Alias for GovernedBitworkV14.

# Illustrative replay of previously recorded observations, in time order.
# Replace these example labels with observations from your actual task.
recorded_stream = [(0, 1), (1, 0), (1, 1)]
for action, observed_outcome in recorded_stream:
    probability_one = model.predict(action)
    print(probability_one)
    model.observe(action, observed_outcome)

diagnostics = model.snapshot()
```

For live use, call `predict(action)` **before obtaining or supplying the
corresponding outcome**, then call `observe(action, observed_outcome)` after the
result is measured. Supply integer `0` or `1` for each. A model's prediction,
an assumed answer, or a preferred route is not an observed label.

| Operation | Meaning |
| --- | --- |
| `model.predict(action)` | Return the conditional probability of outcome `1` and open a pending prediction. |
| `model.observe(action, outcome)` | Close that pending prediction with the matching action and actual binary outcome; update learning state. |
| `model.snapshot()` | Return diagnostic state, accumulated evidence summaries, and the policy/version labels. |
| Construct a new model | Start an independent stream or explicitly reset learning. There is no Python instance `reset()` method. |

The required sequence is `predict`, then matching `observe`, repeated. Do not
request a second prediction while an observation is pending. Use one model per
independent stream and serialize calls to each model. Interleaving unrelated
streams inside one model mixes their evidence.

Snapshots are diagnostic views, not restorable checkpoints. Treat returned
diagnostics as read-only. Direct edits to model history, grammar pools, evidence
arrays, pending state, caches, or runtime hyperparameters are unsupported.

## Choosing the learning policy

| Import | Policy retained by v1.4 |
| --- | --- |
| `Bitwork` | Alias for the governed policy below. |
| `GovernedBitworkV14` | The selected v1.3 surprise-gated lag-discovery policy. Its compiled grammar remains active; additional lag search starts only when the gate activates. |
| `FullBitworkV14` | The v1.2 always-on lag-discovery policy, using the optimized execution components. |

These modes intentionally retain different learning policies. Do not expect
governed and full mode to produce identical forecasts. An equivalence comparison
must pair governed v1.4 with the selected governed v1.3 reference, or full v1.4
with the always-on v1.2 reference.

The governed constructor accepts the inherited keyword settings:

```python
model = GovernedBitworkV14(
    surprise_threshold=0.66,
    checkpoints=(24, 30, 36, 48, 60),
    monitor_window=24,
    max_replay=100,
    promote_gain=0.5,
)
full_model = FullBitworkV14(promote_gain=0.5)
```

Configure a new instance rather than mutating these settings after learning
has started. Changing settings creates a different experimental condition.
The replay limit bounds historical replay at activation; it is not a complete
CPU, RAM, or wall-clock budget.

## JSON-lines command line

Start a stateful process from the project root:

```bash
python -m bgr140 --mode governed
```

Use `--mode full` for always-on discovery. Each nonblank input line must be one
JSON object. The process emits and flushes one JSON response per request.
All lines in that process share one model until `reset` is requested or the
process ends. The mode is chosen at startup; reset preserves that choice.

### Requests

| Request | Successful `result` |
| --- | --- |
| `{"op":"predict","action":0}` | `{"probability_one": <number>}` |
| `{"op":"observe","action":0,"outcome":1}` | `{"observations": <count>}` |
| `{"op":"snapshot"}` | The selected model's diagnostic snapshot. |
| `{"op":"reset"}` | `{"observations":0}` |

The CLI requires **JSON integers** `0` or `1`; booleans, strings, floats such as
`0.0`, and other numbers are rejected. `observe` must match a pending prediction.
`snapshot` does not complete or replace a pending observation. `reset` discards
all state, including a pending prediction.

For example, these two lines replay one illustrative observation:

```json
{"op":"predict","action":0}
{"op":"observe","action":0,"outcome":1}
```

A fresh default governed process in the validation environment returned:

```json
{"ok":true,"result":{"probability_one":0.47726341740642253},"version":"1.4.0"}
{"ok":true,"result":{"observations":1},"version":"1.4.0"}
```

The probability is a model output, not a correctness guarantee. The key order
of JSON objects has no semantic meaning.

### Errors and diagnostic encoding

Expected parsing, input, and sequencing errors produce an error response, and
the CLI continues reading subsequent lines:

```json
{"ok":false,"error":"observation pending"}
```

That example occurs when another `predict` arrives before the pending result
is observed. A matching `observe` may still close that pending prediction.
Python callers receive the corresponding `ValueError`, `RuntimeError`, or
`TypeError` from the underlying operation rather than a JSON envelope. Error
text can differ between the inherited policies. Unexpected internal failures
are not converted into a success response.

Some diagnostic traces legitimately use negative infinity to mean that no
candidate qualified. It remains a float in the Python model. At the JSON
boundary it is encoded explicitly:

```json
{"nonfinite_float":"-inf"}
```

This tagged object is a diagnostic sentinel, not a probability or numeric zero.
Consumers should preserve its meaning. The serializer similarly tags any other
nonfinite float rather than emitting invalid JSON `Infinity` or `NaN` tokens.

## Demonstration and execution diagnostics

```bash
python -m bgr140 --demo
python -m bgr140 --mode full --demo
```

The demonstration runs a fixed, synthetic fourth-lag stream and prints the
final diagnostic snapshot. It is not a connection to an external task or a new
held-out benchmark.

Read-only execution counters can be inspected separately from learning state:

```python
grammar_work = dict(model.base.discovered.execution_cost)
lag_work = (
    model.lags.optimization_snapshot()
    if model.lags is not None
    else None
)
```

An inactive governed lag learner has no lag-execution counters yet. See
[IMPLEMENTATION.md](IMPLEMENTATION.md) for what these counters measure and
which storage limits they do not provide.
