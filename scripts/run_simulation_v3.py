from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nomad.simulation_v3 import run_suite


def main() -> None:
    print(json.dumps(run_suite(), indent=2))


if __name__ == "__main__":
    main()
