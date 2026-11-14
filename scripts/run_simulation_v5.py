from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nomad.simulation_v5 import run_suite

if __name__ == "__main__":
    print(json.dumps(run_suite(), indent=2))
