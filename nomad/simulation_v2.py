from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Iterable, Sequence

from .benchmarks import dataset as single_dataset
from .learner import ContextualOperatorLearner
from .multi_benchmarks import HiddenMultiTask, challenge_passes, multi_dataset
from .operators import FAMILIES
from .search import MultiNomadEngine, MultiSolveResult
from .simulation import train as train_single
from .skills import SkillRegistry


SEEN_TEMPLATE_INDICES = (0, 1, 2, 3, 4, 5)
UNSEEN_TEMPLATE_INDICES = (6, 7, 8)


@dataclass(frozen=True)
class SearchPolicyResult:
    policy: str
    public_solved: int
    challenge_correct: int
    total: int
    mean_expansions: float
    median_expansions: float
    p95_expansions: float
    max_expansions: int
    mean_depth: float
    expansions: tuple[int, ...]


def _median(values: Sequence[int]) -> float:
    xs = sorted(values)
    if not xs:
        return 0.0
    n = len(xs)
    if n % 2:
        return float(xs[n // 2])
    return (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _p95(values: Sequence[int]) -> float:
    xs = sorted(values)
    if not xs:
        return 0.0
    index = max(0, int(0.95 * len(xs) + 0.999999) - 1)
    return float(xs[min(index, len(xs) - 1)])


def _train_temporal(learner: ContextualOperatorLearner, tasks: Iterable[HiddenMultiTask]) -> None:
    engine = MultiNomadEngine(learner=learner, learn=True)
    for hidden in tasks:
        engine.solve(hidden.public, max_depth=4, max_expansions=320, frontier_cap=512)


def _prepare_learner(seed: int, contextual: bool) -> ContextualOperatorLearner:
    learner = ContextualOperatorLearner(contextual=contextual)
    # Preserve v0.1 learning: first acquire single-edit operator evidence.
    train_single(learner, single_dataset(seed, per_family=8, skew=True))
    # v0.2 then learns local transition value from successful and unsuccessful
    # executions on multi-edit compositions 0..5. Compositions 6..8 remain unseen.
    _train_temporal(
        learner,
        multi_dataset(seed + 1_000, per_template=5, template_indices=SEEN_TEMPLATE_INDICES),
    )
    return learner


def _evaluate(policy: str, engine: MultiNomadEngine, tasks: Sequence[HiddenMultiTask], registry: SkillRegistry | None = None) -> SearchPolicyResult:
    expansions: list[int] = []
    depths: list[int] = []
    public_solved = 0
    challenge_correct = 0
    for hidden in tasks:
        result = engine.solve(hidden.public, max_depth=4, max_expansions=320, frontier_cap=512)
        expansions.append(result.expansions)
        depths.append(result.depth)
        public_solved += int(result.solved)
        challenge_ok = bool(result.solved and challenge_passes(hidden, result.source))
        challenge_correct += int(challenge_ok)
        if registry is not None and result.solved:
            registry.record_challenge(
                signature=result.root_signature,
                sequence=result.operator_sequence,
                task_id=hidden.public.task_id,
                challenge_passed=challenge_ok,
                evaluator="withheld-expression-challenge-v2",
            )
    return SearchPolicyResult(
        policy=policy,
        public_solved=public_solved,
        challenge_correct=challenge_correct,
        total=len(tasks),
        mean_expansions=mean(expansions),
        median_expansions=_median(expansions),
        p95_expansions=_p95(expansions),
        max_expansions=max(expansions) if expansions else 0,
        mean_depth=mean(depths),
        expansions=tuple(expansions),
    )


def _summary(rows: list[dict], field: str) -> dict:
    out: dict[str, dict] = {}
    for policy in ("fixed", "global", "contextual"):
        selected = [next(r for r in row[field] if r["policy"] == policy) for row in rows]
        out[policy] = {
            "public_solve_rate": sum(r["public_solved"] for r in selected) / sum(r["total"] for r in selected),
            "challenge_correct_rate": sum(r["challenge_correct"] for r in selected) / sum(r["total"] for r in selected),
            "mean_expansions_across_runs": mean(r["mean_expansions"] for r in selected),
            "median_expansions_across_runs": mean(r["median_expansions"] for r in selected),
            "p95_expansions_across_runs": mean(r["p95_expansions"] for r in selected),
            "total_tasks": sum(r["total"] for r in selected),
            "total_challenge_correct": sum(r["challenge_correct"] for r in selected),
        }
    fixed = out["fixed"]["mean_expansions_across_runs"]
    for policy in ("global", "contextual"):
        current = out[policy]["mean_expansions_across_runs"]
        out[policy]["expansion_reduction_vs_fixed"] = (fixed - current) / fixed
    return out


def run_seed(seed: int) -> dict:
    seen = multi_dataset(seed + 20_000, per_template=4, template_indices=SEEN_TEMPLATE_INDICES)
    unseen = multi_dataset(seed + 30_000, per_template=4, template_indices=UNSEEN_TEMPLATE_INDICES)

    global_learner = _prepare_learner(seed, contextual=False)
    contextual_learner = _prepare_learner(seed, contextual=True)

    fixed = MultiNomadEngine(fixed_order=FAMILIES, learn=False)
    global_engine = MultiNomadEngine(learner=global_learner, learn=False)
    contextual_engine = MultiNomadEngine(learner=contextual_learner, learn=False)
    registry = SkillRegistry()

    seen_results = [
        _evaluate("fixed", fixed, seen),
        _evaluate("global", global_engine, seen),
        _evaluate("contextual", contextual_engine, seen, registry=registry),
    ]
    unseen_results = [
        _evaluate("fixed", fixed, unseen),
        _evaluate("global", global_engine, unseen),
        _evaluate("contextual", contextual_engine, unseen, registry=registry),
    ]

    return {
        "seed": seed,
        "seen_tasks": len(seen),
        "unseen_tasks": len(unseen),
        "seen_results": [asdict(r) for r in seen_results],
        "unseen_results": [asdict(r) for r in unseen_results],
        "contextual_learner": contextual_learner.snapshot(),
        "skill_registry": registry.snapshot(),
        "promoted_skills": len(registry.promoted()),
    }


def run_suite(seeds=(11, 17, 23, 31, 47)) -> dict:
    runs = [run_seed(seed) for seed in seeds]
    seen_summary = _summary(runs, "seen_results")
    unseen_summary = _summary(runs, "unseen_results")

    total_promoted = sum(run["promoted_skills"] for run in runs)
    return {
        "schema": "nomad.v0.2.multiedit-simulation.v1",
        "seeds": list(seeds),
        "training": {
            "single_edit_pretraining": "v0.1 bounded tasks",
            "multi_edit_training_templates": list(SEEN_TEMPLATE_INDICES),
            "withheld_composition_templates": list(UNSEEN_TEMPLATE_INDICES),
            "search_time_examples": 9,
            "withheld_challenge_examples": 14,
            "max_depth": 4,
            "max_expansions": 320,
            "frontier_cap": 512,
        },
        "runs": runs,
        "seen_summary": seen_summary,
        "unseen_composition_summary": unseen_summary,
        "promoted_skill_records_across_runs": total_promoted,
    }
