from __future__ import annotations

from statistics import mean

from .repo_world import make_repository_tasks, solve_repository, summarize, train_world_models


def run_seed(seed: int) -> dict[str, object]:
    training = make_repository_tasks(seed, per_kind=3)
    evaluation = make_repository_tasks(seed + 10_000, per_kind=3)
    world, static, distance_counts = train_world_models(training)

    flat_rows = [solve_repository(t) for t in evaluation]
    static_rows = [solve_repository(t, static_model=static) for t in evaluation]
    world_rows = [solve_repository(t, world_model=world) for t in evaluation]
    return {
        "seed": seed,
        "training_tasks": len(training),
        "evaluation_tasks": len(evaluation),
        "world_model": world.snapshot(),
        "static_model": static.snapshot(),
        "verified_location_distance_counts": distance_counts,
        "flat": summarize(flat_rows),
        "static": summarize(static_rows),
        "world": summarize(world_rows),
    }


def run_suite(seeds: tuple[int, ...] = (17, 29, 41)) -> dict[str, object]:
    runs = [run_seed(s) for s in seeds]
    flat_attempts = mean(float(r["flat"]["mean_attempts"]) for r in runs)  # type: ignore[index]
    static_attempts = mean(float(r["static"]["mean_attempts"]) for r in runs)  # type: ignore[index]
    world_attempts = mean(float(r["world"]["mean_attempts"]) for r in runs)  # type: ignore[index]
    flat_visits = mean(float(r["flat"]["mean_file_visits"]) for r in runs)  # type: ignore[index]
    world_visits = mean(float(r["world"]["mean_file_visits"]) for r in runs)  # type: ignore[index]
    tasks = sum(int(r["world"]["tasks"]) for r in runs)  # type: ignore[index]
    correct = sum(int(r["world"]["final_correct"]) for r in runs)  # type: ignore[index]
    loc_correct = sum(int(r["world"]["localization_correct"]) for r in runs)  # type: ignore[index]
    loc_preds = sum(int(r["world"]["localization_predictions"]) for r in runs)  # type: ignore[index]

    integration_train = make_repository_tasks(777, per_kind=3)
    wm, _, _ = train_world_models(integration_train)
    integration_tasks = make_repository_tasks(888, per_kind=2)
    integration_rows = [solve_repository(t, world_model=wm, verify_repo_tests=True) for t in integration_tasks]
    integration = {
        "tasks": len(integration_rows),
        "solved": sum(r.solved for r in integration_rows),
        "final_correct": sum(r.final_correct for r in integration_rows),
        "witness_supported": sum(r.witness_supported for r in integration_rows),
        "public_unittest_process_passed": sum(r.public_tests_passed for r in integration_rows),
        "physical_file_edits_required": True,
    }

    return {
        "schema": "nomad.v0.8.repository-world-model-study.v1",
        "version": "0.8.0",
        "codename": "WORLD MODEL",
        "seeds": list(seeds),
        "runs": runs,
        "integration": integration,
        "summary": {
            "held_out_repositories": tasks,
            "world_final_correct": correct,
            "world_final_correct_rate": correct / tasks if tasks else 0.0,
            "flat_mean_attempts": flat_attempts,
            "static_mean_attempts": static_attempts,
            "world_mean_attempts": world_attempts,
            "world_attempt_reduction_vs_flat": (flat_attempts - world_attempts) / flat_attempts if flat_attempts else 0.0,
            "world_attempt_reduction_vs_static": (static_attempts - world_attempts) / static_attempts if static_attempts else 0.0,
            "flat_mean_file_visits": flat_visits,
            "world_mean_file_visits": world_visits,
            "world_file_visit_reduction_vs_flat": (flat_visits - world_visits) / flat_visits if flat_visits else 0.0,
            "world_localization_accuracy": loc_correct / loc_preds if loc_preds else None,
            "world_localization_correct": loc_correct,
            "world_localization_predictions": loc_preds,
        },
        "claim_boundary": (
            "Generated multi-file Python repositories with shuffled filenames, real imports, physical file edits, public unittest execution in the integration gate, and WITNESS-held challenge evidence. "
            "The repository topology, task families, candidate edit vocabulary, and sensory features remain bounded and supplied. This is not arbitrary-repository software engineering."
        ),
    }
