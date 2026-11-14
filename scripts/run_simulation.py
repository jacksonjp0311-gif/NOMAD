from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad.simulation import run_suite

result = run_suite()
path = ROOT / "results" / "simulation-v001.json"
path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result["summary"], indent=2))
print(f"wrote {path}")
