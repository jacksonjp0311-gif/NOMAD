from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from nomad.codeworld import make_codeworld_tasks, solve_task, train_causal_registry

training = make_codeworld_tasks(17, per_family=4)
registry = train_causal_registry(training)
task = next(t for t in make_codeworld_tasks(9001, per_family=1) if t.true_family == "comparison")
result = solve_task(task, causal=registry)
print(json.dumps({"task": task.task_id, "result": result.__dict__, "causal_skills": registry.snapshot()["skills"]}, indent=2))
