from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean

from .morphic import MORPHIC_FAMILIES, MorphicLearner
from .morphic_benchmarks import make_dataset
from .morphic_engine import MorphicEngine

DOMAINS = ("code", "math", "data", "workflow")


@dataclass(frozen=True)
class EvalRow:
    held_out_domain: str
    policy: str
    solved: int
    challenge_correct: int
    total: int
    mean_attempts: float
    top1_correct: int


def _train(seed: int, held_out: str, contextual: bool) -> MorphicLearner:
    learner = MorphicLearner(contextual=contextual)
    engine = MorphicEngine(learner, learn=True)
    for domain in DOMAINS:
        if domain == held_out:
            continue
        for task in make_dataset(domain, seed + 1000, per_family=10):
            engine.solve(task)
    return learner


def _evaluate(seed: int, held_out: str, policy: str, engine: MorphicEngine) -> EvalRow:
    rows = make_dataset(held_out, seed + 20_000, per_family=12)
    attempts = []
    solved = 0
    correct = 0
    top1 = 0
    for task in rows:
        result = engine.solve(task)
        attempts.append(result.attempts)
        solved += int(result.solved)
        correct += int(result.challenge_correct)
        top1 += int(result.challenge_correct and result.attempts == 1)
    return EvalRow(held_out, policy, solved, correct, len(rows), mean(attempts), top1)


def run_seed(seed: int) -> dict:
    rows: list[EvalRow] = []
    for held_out in DOMAINS:
        global_learner = _train(seed, held_out, contextual=False)
        transfer_learner = _train(seed, held_out, contextual=True)
        policies = {
            "cold_fixed": MorphicEngine(fixed_order=MORPHIC_FAMILIES, learn=False),
            "global_frequency": MorphicEngine(global_learner, learn=False),
            "morphic_transfer": MorphicEngine(transfer_learner, learn=False),
        }
        for name, engine in policies.items():
            rows.append(_evaluate(seed, held_out, name, engine))
    return {
        "seed": seed,
        "rows": [asdict(r) for r in rows],
    }


def _aggregate(runs: list[dict]) -> dict:
    summary = {}
    for domain in DOMAINS:
        summary[domain] = {}
        for policy in ("cold_fixed", "global_frequency", "morphic_transfer"):
            rows = [
                next(r for r in run["rows"] if r["held_out_domain"] == domain and r["policy"] == policy)
                for run in runs
            ]
            total = sum(r["total"] for r in rows)
            correct = sum(r["challenge_correct"] for r in rows)
            attempts = mean(r["mean_attempts"] for r in rows)
            top1 = sum(r["top1_correct"] for r in rows)
            summary[domain][policy] = {
                "challenge_correct": correct,
                "total": total,
                "challenge_correct_rate": correct / total,
                "mean_attempts_across_runs": attempts,
                "top1_rate": top1 / total,
            }
        cold = summary[domain]["cold_fixed"]["mean_attempts_across_runs"]
        glob = summary[domain]["global_frequency"]["mean_attempts_across_runs"]
        transfer = summary[domain]["morphic_transfer"]["mean_attempts_across_runs"]
        summary[domain]["morphic_transfer"]["transfer_gain_vs_cold"] = (cold - transfer) / cold
        summary[domain]["morphic_transfer"]["transfer_gain_vs_global"] = (glob - transfer) / glob

    all_cold = mean(summary[d]["cold_fixed"]["mean_attempts_across_runs"] for d in DOMAINS)
    all_global = mean(summary[d]["global_frequency"]["mean_attempts_across_runs"] for d in DOMAINS)
    all_transfer = mean(summary[d]["morphic_transfer"]["mean_attempts_across_runs"] for d in DOMAINS)
    return {
        "domains": summary,
        "overall": {
            "cold_fixed_mean_attempts": all_cold,
            "global_frequency_mean_attempts": all_global,
            "morphic_transfer_mean_attempts": all_transfer,
            "transfer_gain_vs_cold": (all_cold - all_transfer) / all_cold,
            "transfer_gain_vs_global": (all_global - all_transfer) / all_global,
        },
    }


def run_suite(seeds=(11, 17, 23, 31, 47)) -> dict:
    runs = [run_seed(seed) for seed in seeds]
    return {
        "schema": "nomad.v0.4.morphic-simulation.v1",
        "codename": "MORPHIC",
        "claim": "bounded cross-substrate effect-signature transfer; not general intelligence",
        "domains": list(DOMAINS),
        "families": list(MORPHIC_FAMILIES),
        "protocol": {
            "rotation": "train on three substrates; freeze; evaluate the fourth; rotate all four holdouts",
            "training_tasks_per_domain_per_seed": 50,
            "held_out_tasks_per_domain_per_seed": 60,
            "search_evidence": "four public numeric probes",
            "challenge_evidence": "six disjoint probes not used to rank transformations",
            "global_control": "same experience without effect-signature conditioning",
        },
        "seeds": list(seeds),
        "runs": runs,
        "summary": _aggregate(runs),
    }
