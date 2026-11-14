from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean
from typing import Iterable

from .benchmarks import HiddenTask, dataset
from .engine import NomadEngine
from .learner import ContextualOperatorLearner
from .operators import FAMILIES


@dataclass(frozen=True)
class PolicyResult:
    policy: str
    solved: int
    total: int
    mean_attempts: float
    median_attempts: float
    attempts: tuple[int, ...]


def _median(xs: list[int]) -> float:
    ys = sorted(xs)
    n = len(ys)
    if n % 2:
        return float(ys[n // 2])
    return (ys[n // 2 - 1] + ys[n // 2]) / 2.0


def train(learner: ContextualOperatorLearner, tasks: Iterable[HiddenTask]) -> None:
    engine = NomadEngine(learner=learner, learn=True)
    for hidden in tasks:
        engine.solve(hidden.public)


def evaluate(policy: str, engine: NomadEngine, tasks: Iterable[HiddenTask]) -> PolicyResult:
    attempts: list[int] = []
    solved = 0
    total = 0
    for hidden in tasks:
        total += 1
        result = engine.solve(hidden.public)
        attempts.append(result.attempts)
        solved += int(result.solved)
    return PolicyResult(policy, solved, total, mean(attempts), _median(attempts), tuple(attempts))


def run_seed(seed: int, train_per_family: int = 10, test_per_family: int = 6) -> dict:
    train_tasks = dataset(seed, train_per_family, skew=True)
    test_tasks = dataset(seed + 10_000, test_per_family, skew=True)
    shifted_tasks = dataset(seed + 20_000, test_per_family, skew=False)

    fixed = NomadEngine(fixed_order=FAMILIES, learn=False)

    global_learner = ContextualOperatorLearner(contextual=False)
    train(global_learner, train_tasks)
    global_engine = NomadEngine(learner=global_learner, learn=False)

    contextual_learner = ContextualOperatorLearner(contextual=True)
    train(contextual_learner, train_tasks)
    contextual_engine = NomadEngine(learner=contextual_learner, learn=False)

    results = [
        evaluate("fixed", fixed, test_tasks),
        evaluate("global", global_engine, test_tasks),
        evaluate("contextual", contextual_engine, test_tasks),
    ]
    shifted_results = [
        evaluate("fixed", fixed, shifted_tasks),
        evaluate("global", global_engine, shifted_tasks),
        evaluate("contextual", contextual_engine, shifted_tasks),
    ]
    return {
        "seed": seed,
        "train_tasks": len(train_tasks),
        "test_tasks": len(test_tasks),
        "results": [asdict(r) for r in results],
        "shifted_test_tasks": len(shifted_tasks),
        "shifted_results": [asdict(r) for r in shifted_results],
        "contextual_learner": contextual_learner.snapshot(),
        "global_learner": global_learner.snapshot(),
    }


def run_suite(seeds=(11, 17, 23, 31, 47)) -> dict:
    runs = [run_seed(s) for s in seeds]
    policies = ("fixed", "global", "contextual")
    summary = {}
    for policy in policies:
        rows = [next(r for r in run["results"] if r["policy"] == policy) for run in runs]
        summary[policy] = {
            "mean_attempts_across_runs": mean(r["mean_attempts"] for r in rows),
            "solve_rate": sum(r["solved"] for r in rows) / sum(r["total"] for r in rows),
            "total_solved": sum(r["solved"] for r in rows),
            "total_tasks": sum(r["total"] for r in rows),
        }
    fixed = summary["fixed"]["mean_attempts_across_runs"]
    for policy in ("global", "contextual"):
        cur = summary[policy]["mean_attempts_across_runs"]
        summary[policy]["attempt_reduction_vs_fixed"] = (fixed - cur) / fixed
    shifted_summary = {}
    for policy in policies:
        rows = [next(r for r in run["shifted_results"] if r["policy"] == policy) for run in runs]
        shifted_summary[policy] = {
            "mean_attempts_across_runs": mean(r["mean_attempts"] for r in rows),
            "solve_rate": sum(r["solved"] for r in rows) / sum(r["total"] for r in rows),
            "total_solved": sum(r["solved"] for r in rows),
            "total_tasks": sum(r["total"] for r in rows),
        }
    shifted_fixed = shifted_summary["fixed"]["mean_attempts_across_runs"]
    for policy in ("global", "contextual"):
        cur = shifted_summary[policy]["mean_attempts_across_runs"]
        shifted_summary[policy]["attempt_reduction_vs_fixed"] = (shifted_fixed - cur) / shifted_fixed
    return {
        "schema": "nomad.v0.1.simulation.v1",
        "seeds": list(seeds),
        "runs": runs,
        "summary": summary,
        "distribution_shift_summary": shifted_summary,
    }
