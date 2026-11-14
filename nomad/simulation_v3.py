from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Sequence

from .python_benchmarks import HiddenPythonTask, compound_dataset, single_dataset
from .python_operators import PY_FAMILIES
from .python_runtime import execute_python
from .python_search import ResonanceSearchEngine
from .sensory_learner import SensoryOperatorLearner
from .resonance_learner import ResonanceOperatorLearner


@dataclass(frozen=True)
class PolicyResult:
    policy: str
    search_solved: int
    challenge_correct: int
    total: int
    mean_expansions: float
    median_expansions: float
    p95_expansions: float
    max_expansions: int
    mean_depth: float
    parse_first_repairs: int
    runtime_first_repairs: int


def _median(xs: Sequence[int]) -> float:
    ys = sorted(xs)
    if not ys:
        return 0.0
    n = len(ys)
    return float(ys[n // 2]) if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2.0


def _p95(xs: Sequence[int]) -> float:
    ys = sorted(xs)
    if not ys:
        return 0.0
    return float(ys[min(len(ys) - 1, max(0, int(0.95 * len(ys) + 0.999999) - 1))])


def _challenge(hidden: HiddenPythonTask, source: str) -> bool:
    run = execute_python(source, hidden.challenge_examples, function_name=hidden.public.function_name)
    return run.parse_ok and run.failures == 0 and run.runtime_errors == 0


def _train(seed: int, *, mode: str, contextual: bool):
    if mode == "fusion" and contextual:
        learner = ResonanceOperatorLearner()
    else:
        learner = SensoryOperatorLearner(contextual=contextual)
    engine = ResonanceSearchEngine(learner, mode=mode, learn=True)
    for hidden in single_dataset(seed, per_family=8, skew=True):
        engine.solve(hidden.public, max_depth=2, max_expansions=100, frontier_cap=256)
    return learner


def _evaluate(policy: str, engine: ResonanceSearchEngine, tasks: Sequence[HiddenPythonTask]) -> PolicyResult:
    expansions: list[int] = []
    depths: list[int] = []
    solved = 0
    correct = 0
    parse_first = 0
    runtime_first = 0
    for hidden in tasks:
        result = engine.solve(hidden.public, max_depth=4, max_expansions=180, frontier_cap=512)
        expansions.append(result.expansions)
        depths.append(result.depth)
        solved += int(result.solved)
        correct += int(result.solved and _challenge(hidden, result.source))
        if result.lineage:
            parse_first += int(result.lineage[0].family == "syntax")
            runtime_first += int(result.lineage[0].family in {"identifier", "zero_guard"})
    return PolicyResult(
        policy=policy,
        search_solved=solved,
        challenge_correct=correct,
        total=len(tasks),
        mean_expansions=mean(expansions),
        median_expansions=_median(expansions),
        p95_expansions=_p95(expansions),
        max_expansions=max(expansions) if expansions else 0,
        mean_depth=mean(depths),
        parse_first_repairs=parse_first,
        runtime_first_repairs=runtime_first,
    )


def run_seed(seed: int) -> dict:
    eval_singles = single_dataset(seed + 20_000, per_family=4, skew=False)
    eval_compounds = compound_dataset(seed + 30_000, per_composition=4)

    global_learner = _train(seed, mode="fusion", contextual=False)
    test_learner = _train(seed, mode="test_only", contextual=True)
    fusion_learner = _train(seed, mode="fusion", contextual=True)

    policies = {
        "fixed": ResonanceSearchEngine(mode="fusion", fixed_order=PY_FAMILIES, learn=False),
        "global": ResonanceSearchEngine(global_learner, mode="fusion", learn=False),
        "test_only": ResonanceSearchEngine(test_learner, mode="test_only", learn=False),
        "fusion": ResonanceSearchEngine(fusion_learner, mode="fusion", learn=False),
    }
    singles = [_evaluate(name, engine, eval_singles) for name, engine in policies.items()]
    compounds = [_evaluate(name, engine, eval_compounds) for name, engine in policies.items()]
    return {
        "seed": seed,
        "single_tasks": len(eval_singles),
        "compound_tasks": len(eval_compounds),
        "single_results": [asdict(x) for x in singles],
        "compound_results": [asdict(x) for x in compounds],
        "fusion_learner": fusion_learner.snapshot(),
        "test_only_learner": test_learner.snapshot(),
    }


def _aggregate(runs: list[dict], key: str) -> dict:
    out: dict[str, dict] = {}
    policies = ("fixed", "global", "test_only", "fusion")
    for policy in policies:
        rows = [next(x for x in run[key] if x["policy"] == policy) for run in runs]
        total = sum(x["total"] for x in rows)
        out[policy] = {
            "challenge_correct": sum(x["challenge_correct"] for x in rows),
            "total": total,
            "challenge_correct_rate": sum(x["challenge_correct"] for x in rows) / total,
            "mean_expansions_across_runs": mean(x["mean_expansions"] for x in rows),
            "median_expansions_across_runs": mean(x["median_expansions"] for x in rows),
            "p95_expansions_across_runs": mean(x["p95_expansions"] for x in rows),
            "mean_depth_across_runs": mean(x["mean_depth"] for x in rows),
        }
    fixed = out["fixed"]["mean_expansions_across_runs"]
    for policy in policies[1:]:
        current = out[policy]["mean_expansions_across_runs"]
        out[policy]["expansion_reduction_vs_fixed"] = (fixed - current) / fixed if fixed else 0.0
    test = out["test_only"]["mean_expansions_across_runs"]
    fusion = out["fusion"]["mean_expansions_across_runs"]
    out["fusion"]["expansion_reduction_vs_test_only"] = (test - fusion) / test if test else 0.0
    return out


def run_suite(seeds=(11, 17, 23, 31, 47)) -> dict:
    runs = [run_seed(seed) for seed in seeds]
    return {
        "schema": "nomad.v0.3.resonance-simulation.v1",
        "codename": "RESONANCE",
        "seeds": list(seeds),
        "training": {
            "surface": "synthetic Python functions owned by benchmark generator",
            "training_tasks": "single-edit only",
            "evaluation_single_tasks_per_seed": 28,
            "evaluation_compound_tasks_per_seed": 24,
            "compound_compositions": 6,
            "visible_tests_per_task": 10,
            "withheld_challenge_tests_per_task": 13,
            "max_depth": 4,
            "max_expansions": 180,
            "frontier_cap": 512,
            "fusion_channels": ["parser", "runtime_exception", "traceback", "tests", "AST", "work_proxy"],
        },
        "runs": runs,
        "single_summary": _aggregate(runs, "single_results"),
        "compound_summary": _aggregate(runs, "compound_results"),
    }
