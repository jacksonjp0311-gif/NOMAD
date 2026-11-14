from __future__ import annotations

from statistics import mean

from .codeworld import (
    global_family_order,
    make_codeworld_tasks,
    solve_task,
    summarize_results,
    train_causal_registry,
)


def run_seed(seed: int) -> dict[str, object]:
    training = make_codeworld_tasks(seed, per_family=5, include_ood=True)
    evaluation = make_codeworld_tasks(seed + 10_000, per_family=3, include_ood=True)
    causal = train_causal_registry(training)
    global_order = global_family_order(training)

    fixed_rows = [solve_task(task, verify_repo_tests=False) for task in evaluation]
    global_rows = [solve_task(task, global_order=global_order, verify_repo_tests=False) for task in evaluation]
    causal_rows = [solve_task(task, causal=causal, verify_repo_tests=False) for task in evaluation]

    registered_idx = [i for i, t in enumerate(evaluation) if t.true_family != "unavailable"]
    ood_idx = [i for i, t in enumerate(evaluation) if t.true_family == "unavailable"]
    def pick(rows, indices):
        return [rows[i] for i in indices]
    return {
        "seed": seed,
        "training_tasks": len(training),
        "evaluation_tasks": len(evaluation),
        "causal_registry": causal.snapshot(),
        "all": {
            "fixed": summarize_results(fixed_rows),
            "global": summarize_results(global_rows),
            "causal": summarize_results(causal_rows),
        },
        "registered": {
            "fixed": summarize_results(pick(fixed_rows, registered_idx)),
            "global": summarize_results(pick(global_rows, registered_idx)),
            "causal": summarize_results(pick(causal_rows, registered_idx)),
        },
        "ood": {
            "fixed": [fixed_rows[i].__dict__ for i in ood_idx],
            "global": [global_rows[i].__dict__ for i in ood_idx],
            "causal": [causal_rows[i].__dict__ for i in ood_idx],
        },
    }


def run_suite(seeds: tuple[int, ...] = (17, 29, 41)) -> dict[str, object]:
    runs = [run_seed(s) for s in seeds]
    fixed_attempts = mean(r["registered"]["fixed"]["mean_attempts"] for r in runs)  # type: ignore[index]
    global_attempts = mean(r["registered"]["global"]["mean_attempts"] for r in runs)  # type: ignore[index]
    causal_attempts = mean(r["registered"]["causal"]["mean_attempts"] for r in runs)  # type: ignore[index]
    total_tasks = sum(int(r["registered"]["causal"]["tasks"]) for r in runs)  # type: ignore[index]
    total_correct = sum(int(r["registered"]["causal"]["final_correct"]) for r in runs)  # type: ignore[index]
    predictions = sum(int(r["all"]["causal"]["predictions"]) for r in runs)  # type: ignore[index]
    false_predictions = sum(int(r["all"]["causal"]["false_skill_predictions"]) for r in runs)  # type: ignore[index]
    ood_rows = [row for r in runs for row in r["ood"]["causal"]]  # type: ignore[index]
    integration_training = make_codeworld_tasks(777, per_family=4, include_ood=True)
    integration_registry = train_causal_registry(integration_training)
    integration_tasks = make_codeworld_tasks(888, per_family=1, include_ood=False)
    integration_rows = [solve_task(t, causal=integration_registry, verify_repo_tests=True) for t in integration_tasks]
    integration = {
        "tasks": len(integration_rows),
        "solved": sum(r.solved for r in integration_rows),
        "final_correct": sum(r.final_correct for r in integration_rows),
        "witness_supported": sum(r.witness_supported for r in integration_rows),
        "actual_unittest_process_required": True,
    }
    return {
        "schema": "nomad.v0.7.codeworld-causal-study.v1",
        "version": "0.7.0",
        "codename": "CAUSAL SKILLS / CODEWORLD",
        "seeds": list(seeds),
        "runs": runs,
        "integration": integration,
        "summary": {
            "registered_evaluation_tasks": total_tasks,
            "registered_causal_final_correct": total_correct,
            "registered_causal_final_correct_rate": total_correct / total_tasks,
            "fixed_mean_attempts": fixed_attempts,
            "global_mean_attempts": global_attempts,
            "causal_mean_attempts": causal_attempts,
            "causal_attempt_reduction_vs_fixed": (fixed_attempts - causal_attempts) / fixed_attempts,
            "causal_attempt_reduction_vs_global": (global_attempts - causal_attempts) / global_attempts if global_attempts else 0.0,
            "causal_skill_predictions": predictions,
            "causal_false_skill_predictions": false_predictions,
            "causal_skill_precision": (predictions - false_predictions) / predictions if predictions else None,
            "ood_causal_abstentions": sum(1 for row in ood_rows if row["predicted_family"] is None),
            "ood_false_skill_predictions": sum(1 for row in ood_rows if row["predicted_family"] is not None),
            "ood_count": len(ood_rows),
        },
        "claim_boundary": (
            "Small generated Python repositories with real file edits and unittest execution. "
            "The operator vocabulary and context predicates are supplied; this is not arbitrary repository engineering."
        ),
    }
