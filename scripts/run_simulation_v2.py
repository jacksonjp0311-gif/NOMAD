from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nomad.simulation_v2 import run_suite


def main() -> None:
    result = run_suite()
    path = ROOT / "results" / "simulation-v002.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "seen_summary": result["seen_summary"],
        "unseen_composition_summary": result["unseen_composition_summary"],
        "promoted_skill_records_across_runs": result["promoted_skill_records_across_runs"],
    }, indent=2))


if __name__ == "__main__":
    main()
