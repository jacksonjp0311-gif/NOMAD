# Bitwork v1.4.0 runtime

This lightweight package contains the standard-library Python engine and its integration documentation. The complete research package contains the preserved predecessor, tests, scientific results and whitepaper.

## Run

From this directory, with Python 3.11 or newer:

```bash
python -m bgr140 --demo
python -m bgr140 --mode full --demo
python -m bgr140 --mode governed
```

The last command starts the stateful JSON-lines interface. Send one JSON request per line, for example:

```json
{"op":"predict","action":0}
{"op":"observe","action":0,"outcome":1}
{"op":"snapshot"}
```

The observation line is illustrative. Supply the actual observed outcome in a real application. Use a model per independent chronological stream.

```python
from bgr140 import Bitwork, FullBitworkV14
model = Bitwork()
probability = model.predict(0)
# Update only after observing the actual binary result:
model.observe(0, 1)
```

Governed mode preserves the selected v1.3 policy. Full mode preserves v1.2 always-on discovery. Each uses the optimized executors. These policies can produce different predictions. See [API.md](docs/API.md) and [IMPLEMENTATION.md](docs/IMPLEMENTATION.md).

The complete release demonstrated exact execution equivalence on 44,800 forecast pairs across 238 internal synthetic worlds. See the full package for measurement scope and raw evidence. This is not general intelligence or an unrestricted language model. History storage grows; bounded cache entries do not bound total memory. Windows launcher execution remains untested; Linux Python was validated.

The runtime does not need a GPU, model download, API key or external dependency. It does require an application to encode the binary events and to supply real chronological observations.

Runtime file identities are in `MANIFEST.sha256`; release source and predecessor identity are in `PROVENANCE.json`.
