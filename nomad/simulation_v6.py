from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from random import Random
from statistics import mean
from typing import Iterable

from .echo_map import EchoMapEncoder, EchoRecord
from .morphic import MORPHIC_FAMILIES, Observation, effect_signature
from .morphic_adapters import ADAPTERS
from .morphic_benchmarks import MorphicTask, make_dataset
from .witness import Witness, WitnessReceipt
from .witness_skills import WitnessedSkillRegistry

DOMAINS = ("code", "math", "data", "workflow")
POLICIES = ("public_only_self", "inline_echo", "witness_fixed", "witness_echo")


@dataclass(frozen=True)
class EvalRow:
    held_out_domain: str
    policy: str
    solved_public: int
    witness_supported: int
    final_correct: int
    false_certifications: int
    total: int
    mean_attempts: float
    stale_receipts_rejected: int = 0
    tampered_receipts_rejected: int = 0
    promoted_skills: int = 0
    contested_skills: int = 0


def _same(a: tuple[float, ...], b: tuple[float, ...], tol: float = 1e-9) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def _verified_training_records(seed: int, held_out: str) -> list[EchoRecord]:
    records: list[EchoRecord] = []
    for domain in DOMAINS:
        if domain == held_out:
            continue
        adapter = ADAPTERS[domain]
        for task in make_dataset(domain, seed + 1000, per_family=10):
            current = adapter.observe(task.artifact, task.public_inputs)
            target = adapter.observe(task.target_artifact, task.public_inputs)
            verified = None
            for family in MORPHIC_FAMILIES:
                candidate = adapter.transform(task.artifact, family)
                if not _same(adapter.observe(candidate, task.public_inputs), target):
                    continue
                if _same(
                    adapter.observe(candidate, task.challenge_inputs),
                    adapter.observe(task.target_artifact, task.challenge_inputs),
                ):
                    verified = family
                    break
            if verified is None:
                raise RuntimeError(f"no verified training transformation for {task.task_id}")
            records.append(EchoRecord(current, target, verified))
    return records


def _lagrange(xs: tuple[float, ...], ys: tuple[float, ...], x: float) -> float:
    """Interpolate the public target using only public observations."""
    total = 0.0
    for i, (xi, yi) in enumerate(zip(xs, ys)):
        term = yi
        for j, xj in enumerate(xs):
            if i == j:
                continue
            term *= (x - xj) / (xi - xj)
        total += term
    return total


def _public_overfit_outputs(
    public_inputs: tuple[float, ...],
    target_public: tuple[float, ...],
    eval_inputs: tuple[float, ...],
) -> tuple[float, ...]:
    """A repair-time overfit constructed without challenge labels.

    The interpolant exactly matches every public example.  A null-space term
    that is zero on those public inputs creates a candidate that can still be
    wrong elsewhere.  This is a deliberate self-certification stressor.
    """
    bump_scale = 0.01
    out = []
    for x in eval_inputs:
        base = _lagrange(public_inputs, target_public, x)
        null = 1.0
        for p in public_inputs:
            null *= x - p
        out.append(base + bump_scale * null)
    return tuple(out)


def _true_candidate(task: MorphicTask, family: str, inputs: tuple[float, ...]) -> tuple[float, ...]:
    adapter = ADAPTERS[task.domain]
    candidate = adapter.transform(task.artifact, family)
    return adapter.observe(candidate, inputs)


def _evidence_id(task_id: str, family: str, attempt: int) -> str:
    return hashlib.sha256(f"{task_id}|{family}|{attempt}".encode()).hexdigest()[:24]


def _split_challenge(task: MorphicTask) -> tuple[tuple[float, ...], tuple[float, ...]]:
    values = task.challenge_inputs
    midpoint = max(1, len(values) // 2)
    return values[:midpoint], values[midpoint:]


def _candidate_vectors(task: MorphicTask, family: str) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    adapter = ADAPTERS[task.domain]
    witness_inputs, final_inputs = _split_challenge(task)
    target_public = adapter.observe(task.target_artifact, task.public_inputs)
    if family == "public_overfit":
        public = target_public
        witness = _public_overfit_outputs(task.public_inputs, target_public, witness_inputs)
        final = _public_overfit_outputs(task.public_inputs, target_public, final_inputs)
    else:
        public = _true_candidate(task, family, task.public_inputs)
        witness = _true_candidate(task, family, witness_inputs)
        final = _true_candidate(task, family, final_inputs)
    return public, witness, final


def _search_order(
    task: MorphicTask,
    echo: EchoMapEncoder | None,
    fixed: bool,
    *,
    include_overfit: bool,
) -> list[str]:
    if fixed or echo is None:
        families = list(MORPHIC_FAMILIES)
    else:
        adapter = ADAPTERS[task.domain]
        current = adapter.observe(task.artifact, task.public_inputs)
        target = adapter.observe(task.target_artifact, task.public_inputs)
        families = echo.rank(current, target)
    return (["public_overfit"] if include_overfit else []) + families


def _include_overfit(task: MorphicTask, seed: int, mode: str) -> bool:
    if mode == "stress":
        return True
    if mode != "mixed":
        raise ValueError(mode)
    digest = hashlib.sha256(f"{seed}|{task.task_id}|witness-mixed".encode()).digest()
    # Deterministic ~25% contamination rate.
    return digest[0] < 64


def _evaluate_policy(
    *,
    seed: int,
    held_out: str,
    policy: str,
    echo: EchoMapEncoder,
    mode: str,
) -> EvalRow:
    witness = Witness()
    skills = WitnessedSkillRegistry()
    tasks = make_dataset(held_out, seed + 30_000, per_family=10)
    attempts: list[int] = []
    public_solved = witness_supported = final_correct = false_cert = 0
    stale_rejected = tamper_rejected = 0

    for task in tasks:
        adapter = ADAPTERS[task.domain]
        witness_inputs, final_inputs = _split_challenge(task)
        current_public = adapter.observe(task.artifact, task.public_inputs)
        target_public = adapter.observe(task.target_artifact, task.public_inputs)
        current_witness = adapter.observe(task.artifact, witness_inputs)
        target_witness = adapter.observe(task.target_artifact, witness_inputs)
        target_final = adapter.observe(task.target_artifact, final_inputs)
        signature = effect_signature(Observation(current_public, target_public)).key

        fixed = policy == "witness_fixed"
        order = _search_order(
            task,
            echo,
            fixed=fixed,
            include_overfit=_include_overfit(task, seed, mode),
        )

        chosen_family = None
        chosen_final: tuple[float, ...] | None = None
        chosen_receipt: WitnessReceipt | None = None
        count = 0
        for family in order:
            count += 1
            public_pred, challenge_pred, final_pred = _candidate_vectors(task, family)
            public_pass = _same(public_pred, target_public)
            if not public_pass:
                continue

            if policy == "public_only_self":
                chosen_family = family
                chosen_final = final_pred
                public_solved += 1
                # The self-certifying policy promotes its own public result.
                if not _same(final_pred, target_final):
                    false_cert += 1
                break

            if policy == "inline_echo":
                if not _same(challenge_pred, target_witness):
                    continue
                chosen_family = family
                chosen_final = final_pred
                public_solved += 1
                witness_supported += 1  # same held-out evidence, but no durable receipt authority
                break

            transmission_id = _evidence_id(task.task_id, family, count)
            receipt = witness.attest(
                task_id=task.task_id,
                transmission_id=transmission_id,
                world_epoch=0,
                current_public=current_public,
                target_public=target_public,
                candidate_public=public_pred,
                current_challenge=current_witness,
                target_challenge=target_witness,
                candidate_challenge=challenge_pred,
            )
            ingest = skills.ingest(
                witness=witness,
                receipt=receipt,
                signature=signature,
                sequence=(family,),
                task_id=task.task_id,
                transmission_id=transmission_id,
                world_epoch=0,
            )
            if not ingest.accepted_provenance:
                raise RuntimeError("fresh witness receipt was unexpectedly rejected")
            if not receipt.supported:
                continue

            chosen_family = family
            chosen_final = final_pred
            chosen_receipt = receipt
            public_solved += 1
            witness_supported += 1
            # Replay protection: the same receipt must not authorize a later epoch.
            stale_rejected += int(not witness.authorize(
                receipt,
                task_id=task.task_id,
                transmission_id=transmission_id,
                world_epoch=1,
            ))
            # Field mutation invalidates the checksum. This is integrity detection,
            # not cryptographic protection against an actor able to recompute hashes.
            tampered = replace(receipt, transmission_id=transmission_id + "-tampered")
            tamper_rejected += int(not witness.valid_for_context(
                tampered,
                task_id=task.task_id,
                transmission_id=transmission_id,
                world_epoch=0,
            ))
            break

        attempts.append(count)
        if chosen_family is None or chosen_final is None:
            continue
        if _same(chosen_final, target_final):
            final_correct += 1
        elif policy != "public_only_self":
            false_cert += 1

    promoted = len(skills.promoted()) if policy.startswith("witness_") else 0
    contested = 0
    if policy.startswith("witness_"):
        contested = sum(r.status == "contested" for r in skills.registry.records.values())
    return EvalRow(
        held_out_domain=held_out,
        policy=policy,
        solved_public=public_solved,
        witness_supported=witness_supported,
        final_correct=final_correct,
        false_certifications=false_cert,
        total=len(tasks),
        mean_attempts=mean(attempts),
        stale_receipts_rejected=stale_rejected,
        tampered_receipts_rejected=tamper_rejected,
        promoted_skills=promoted,
        contested_skills=contested,
    )


def run_seed(seed: int, *, mode: str) -> dict:
    rows: list[EvalRow] = []
    maps: dict[str, dict] = {}
    for held_out in DOMAINS:
        echo = EchoMapEncoder(dimensions=4).fit(_verified_training_records(seed, held_out))
        maps[held_out] = echo.snapshot()
        for policy in POLICIES:
            rows.append(_evaluate_policy(seed=seed, held_out=held_out, policy=policy, echo=echo, mode=mode))
    return {"seed": seed, "mode": mode, "rows": [asdict(r) for r in rows], "echo_maps": maps}


def _aggregate(runs: list[dict]) -> dict:
    domains: dict[str, dict] = {}
    for domain in DOMAINS:
        domains[domain] = {}
        for policy in POLICIES:
            rows = [next(r for r in run["rows"] if r["held_out_domain"] == domain and r["policy"] == policy) for run in runs]
            total = sum(r["total"] for r in rows)
            final = sum(r["final_correct"] for r in rows)
            false = sum(r["false_certifications"] for r in rows)
            domains[domain][policy] = {
                "total": total,
                "final_correct": final,
                "final_correct_rate": final / total,
                "false_certifications": false,
                "false_certification_rate": false / total,
                "mean_attempts_across_runs": mean(r["mean_attempts"] for r in rows),
                "stale_receipts_rejected": sum(r["stale_receipts_rejected"] for r in rows),
                "tampered_receipts_rejected": sum(r["tampered_receipts_rejected"] for r in rows),
                "promoted_skills_mean": mean(r["promoted_skills"] for r in rows),
                "contested_skills_mean": mean(r["contested_skills"] for r in rows),
            }

    overall: dict[str, object] = {}
    for policy in POLICIES:
        overall[f"{policy}_mean_attempts"] = mean(domains[d][policy]["mean_attempts_across_runs"] for d in DOMAINS)
        overall[f"{policy}_final_correct_rate"] = sum(domains[d][policy]["final_correct"] for d in DOMAINS) / sum(domains[d][policy]["total"] for d in DOMAINS)
        overall[f"{policy}_false_certification_rate"] = sum(domains[d][policy]["false_certifications"] for d in DOMAINS) / sum(domains[d][policy]["total"] for d in DOMAINS)
    overall["witness_echo_attempt_reduction_vs_witness_fixed"] = (
        (overall["witness_fixed_mean_attempts"] - overall["witness_echo_mean_attempts"])
        / overall["witness_fixed_mean_attempts"]
    )
    overall["witness_stale_rejection_rate"] = (
        sum(domains[d]["witness_echo"]["stale_receipts_rejected"] for d in DOMAINS)
        / sum(domains[d]["witness_echo"]["final_correct"] for d in DOMAINS)
    )
    overall["witness_tamper_detection_rate"] = (
        sum(domains[d]["witness_echo"]["tampered_receipts_rejected"] for d in DOMAINS)
        / sum(domains[d]["witness_echo"]["final_correct"] for d in DOMAINS)
    )
    return {"domains": domains, "overall": overall}


def run_suite(seeds=(11, 17, 23, 31, 47)) -> dict:
    stress_runs = [run_seed(seed, mode="stress") for seed in seeds]
    mixed_runs = [run_seed(seed, mode="mixed") for seed in seeds]
    return {
        "schema": "nomad.v0.6.witness-simulation.v1",
        "codename": "WITNESS",
        "claim": "independent consequence attestation and provenance gating in bounded synthetic overfit/contamination tests; not a cryptographic trust boundary or universal truth oracle",
        "domains": list(DOMAINS),
        "families": list(MORPHIC_FAMILIES),
        "protocol": {
            "search_evidence": "four public probes",
            "witness_evidence": "first half of six held-out probes; never used to construct the public-overfit decoy",
            "final_revalidation": "second half of six held-out probes; never visible to WITNESS or search",
            "stressor": "a public-null-space polynomial candidate exactly fits all public target examples but deviates off those points",
            "stress_mode": "overfit candidate appears on every evaluation task",
            "mixed_mode": "deterministic approximately 25% of evaluation tasks include the overfit candidate",
            "witness_role": "recompute factual consequence claims from observations; does not choose goals or transformations",
            "promotion_boundary": "durable skill memory accepts outcome evidence only through context-bound WITNESS receipts",
            "stale_rule": "receipt epoch must exactly match the current world epoch",
            "integrity_rule": "receipt checksum detects field mutation when the checksum is not recomputed; this is not a digital signature",
            "controls": ["public-only self-certification", "inline held-out challenge without durable receipt", "fixed search with WITNESS", "ECHO MAP search with WITNESS"],
        },
        "seeds": list(seeds),
        "stress": {"runs": stress_runs, "summary": _aggregate(stress_runs)},
        "mixed": {"runs": mixed_runs, "summary": _aggregate(mixed_runs)},
    }
