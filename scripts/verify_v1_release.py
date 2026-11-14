from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    test = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    print(test.stdout)
    print(test.stderr, file=sys.stderr)
    if test.returncode:
        return test.returncode

    sim = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_simulation.py")], cwd=ROOT)
    if sim.returncode:
        return sim.returncode

    result_path = ROOT / "results" / "simulation-v001.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    c = payload["summary"]["contextual"]
    f = payload["summary"]["fixed"]
    cs = payload["distribution_shift_summary"]["contextual"]
    fs = payload["distribution_shift_summary"]["fixed"]
    gates = {
        "tests": "passed",
        "simulation_solve_rate": c["solve_rate"],
        "fixed_solve_rate": f["solve_rate"],
        "contextual_attempt_reduction_vs_fixed": c["attempt_reduction_vs_fixed"],
        "gate_same_solve_rate": c["solve_rate"] == f["solve_rate"],
        "gate_search_reduction_gt_20pct": c["attempt_reduction_vs_fixed"] > 0.20,
        "distribution_shift_solve_rate": cs["solve_rate"],
        "distribution_shift_fixed_solve_rate": fs["solve_rate"],
        "distribution_shift_attempt_reduction_vs_fixed": cs["attempt_reduction_vs_fixed"],
        "gate_shift_same_solve_rate": cs["solve_rate"] == fs["solve_rate"],
        "gate_shift_search_reduction_gt_20pct": cs["attempt_reduction_vs_fixed"] > 0.20,
        "simulation_sha256": sha256(result_path),
    }
    gates["status"] = "passed" if all([
        gates["gate_same_solve_rate"],
        gates["gate_search_reduction_gt_20pct"],
        gates["gate_shift_same_solve_rate"],
        gates["gate_shift_search_reduction_gt_20pct"],
    ]) else "failed"
    (ROOT / "results" / "GATES.json").write_text(json.dumps(gates, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gates, indent=2))
    return 0 if gates["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
