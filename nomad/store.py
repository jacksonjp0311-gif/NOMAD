from __future__ import annotations

import json
from pathlib import Path

from .learner import ContextualOperatorLearner, Counts


def save_learner(learner: ContextualOperatorLearner, path: str | Path) -> None:
    Path(path).write_text(json.dumps(learner.snapshot(), indent=2) + "\n", encoding="utf-8")


def load_learner(path: str | Path) -> ContextualOperatorLearner:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    learner = ContextualOperatorLearner(contextual=bool(payload["contextual"]))
    for family, raw in payload.get("global", {}).items():
        learner.global_counts[family] = Counts(success=int(raw["success"]), failure=int(raw["failure"]))
    for key, raw in payload.get("contexts", {}).items():
        sig_text, family = key.split(":", 1)
        learner.context_counts[(int(sig_text), family)] = Counts(
            success=int(raw["success"]), failure=int(raw["failure"])
        )
    return learner
