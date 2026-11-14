from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from random import Random
from statistics import mean

from .echo_engine import EchoMapEngine
from .echo_map import EchoMapEncoder, EchoRecord
from .morphic import MORPHIC_FAMILIES, MorphicLearner
from .morphic_adapters import ADAPTERS
from .morphic_benchmarks import MorphicTask, make_dataset
from .morphic_engine import MorphicEngine

DOMAINS = ("code", "math", "data", "workflow")
POLICIES = ("cold_fixed", "global_frequency", "morphic_hand_signature", "echo_map", "echo_map_shuffled")


@dataclass(frozen=True)
class EvalRow:
    held_out_domain: str
    policy: str
    solved: int
    challenge_correct: int
    total: int
    mean_attempts: float
    top1_correct: int


def _same(a: tuple[float, ...], b: tuple[float, ...], tol: float = 1e-9) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def _verified_training_records(seed: int, held_out: str) -> list[EchoRecord]:
    """Collect successful transformations by execution, not by reading hidden labels."""
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
                public_pred = adapter.observe(candidate, task.public_inputs)
                if not _same(public_pred, target):
                    continue
                challenge_pred = adapter.observe(candidate, task.challenge_inputs)
                challenge_target = adapter.observe(task.target_artifact, task.challenge_inputs)
                if _same(challenge_pred, challenge_target):
                    verified = family
                    break
            if verified is None:
                raise RuntimeError(f"no verified training transformation for {task.task_id}")
            records.append(EchoRecord(current, target, verified))
    return records


def _train_morphic(seed: int, held_out: str, *, contextual: bool) -> MorphicLearner:
    learner = MorphicLearner(contextual=contextual)
    engine = MorphicEngine(learner, learn=True)
    for domain in DOMAINS:
        if domain == held_out:
            continue
        for task in make_dataset(domain, seed + 1000, per_family=10):
            engine.solve(task)
    return learner


def _shuffle_records(records: list[EchoRecord], seed: int) -> list[EchoRecord]:
    rng = Random(seed ^ 0xEC40)
    labels = [r.verified_family for r in records]
    rng.shuffle(labels)
    return [EchoRecord(r.current, r.target, label) for r, label in zip(records, labels)]


def _evaluate(seed: int, held_out: str, policy: str, engine: object) -> EvalRow:
    rows = make_dataset(held_out, seed + 20_000, per_family=12)
    attempts: list[int] = []
    solved = challenge = top1 = 0
    for task in rows:
        result = engine.solve(task)
        attempts.append(result.attempts)
        solved += int(result.solved)
        challenge += int(result.challenge_correct)
        top1 += int(result.challenge_correct and result.attempts == 1)
    return EvalRow(held_out, policy, solved, challenge, len(rows), mean(attempts), top1)


def run_seed(seed: int) -> dict:
    rows: list[EvalRow] = []
    maps: dict[str, dict] = {}
    for held_out in DOMAINS:
        records = _verified_training_records(seed, held_out)
        echo = EchoMapEncoder(dimensions=4).fit(records)
        shuffled = EchoMapEncoder(dimensions=4).fit(_shuffle_records(records, seed))
        global_learner = _train_morphic(seed, held_out, contextual=False)
        morphic_learner = _train_morphic(seed, held_out, contextual=True)
        policies = {
            "cold_fixed": MorphicEngine(fixed_order=MORPHIC_FAMILIES, learn=False),
            "global_frequency": MorphicEngine(global_learner, learn=False),
            "morphic_hand_signature": MorphicEngine(morphic_learner, learn=False),
            "echo_map": EchoMapEngine(echo),
            "echo_map_shuffled": EchoMapEngine(shuffled),
        }
        for name, engine in policies.items():
            rows.append(_evaluate(seed, held_out, name, engine))
        maps[held_out] = echo.snapshot()
    return {"seed": seed, "rows": [asdict(r) for r in rows], "echo_maps": maps}


def _aggregate(runs: list[dict]) -> dict:
    domains: dict[str, dict] = {}
    for domain in DOMAINS:
        domains[domain] = {}
        for policy in POLICIES:
            rows = [next(r for r in run["rows"] if r["held_out_domain"] == domain and r["policy"] == policy) for run in runs]
            total = sum(r["total"] for r in rows)
            correct = sum(r["challenge_correct"] for r in rows)
            domains[domain][policy] = {
                "challenge_correct": correct,
                "total": total,
                "challenge_correct_rate": correct / total,
                "mean_attempts_across_runs": mean(r["mean_attempts"] for r in rows),
                "top1_rate": sum(r["top1_correct"] for r in rows) / total,
            }
        cold = domains[domain]["cold_fixed"]["mean_attempts_across_runs"]
        echo = domains[domain]["echo_map"]["mean_attempts_across_runs"]
        morphic = domains[domain]["morphic_hand_signature"]["mean_attempts_across_runs"]
        shuffled = domains[domain]["echo_map_shuffled"]["mean_attempts_across_runs"]
        domains[domain]["echo_map"]["gain_vs_cold"] = (cold - echo) / cold
        domains[domain]["echo_map"]["gap_vs_hand_signature"] = (echo - morphic) / morphic
        domains[domain]["echo_map"]["gain_vs_shuffled"] = (shuffled - echo) / shuffled

    overall: dict[str, float] = {}
    for policy in POLICIES:
        overall[f"{policy}_mean_attempts"] = mean(domains[d][policy]["mean_attempts_across_runs"] for d in DOMAINS)
    cold = overall["cold_fixed_mean_attempts"]
    echo = overall["echo_map_mean_attempts"]
    morphic = overall["morphic_hand_signature_mean_attempts"]
    shuffled = overall["echo_map_shuffled_mean_attempts"]
    overall.update({
        "echo_gain_vs_cold": (cold - echo) / cold,
        "echo_gap_vs_hand_signature": (echo - morphic) / morphic,
        "echo_gain_vs_shuffled": (shuffled - echo) / shuffled,
    })

    selected = Counter()
    for run in runs:
        for snap in run["echo_maps"].values():
            selected.update(snap["selected"])
    return {
        "domains": domains,
        "overall": overall,
        "feature_selection_frequency": dict(selected.most_common()),
    }


def run_suite(seeds=(11, 17, 23, 31, 47)) -> dict:
    runs = [run_seed(seed) for seed in seeds]
    return {
        "schema": "nomad.v0.5.echo-map-simulation.v1",
        "codename": "ECHO MAP",
        "claim": "bounded learned cross-substrate relation representation; not unrestricted representation learning or general intelligence",
        "domains": list(DOMAINS),
        "families": list(MORPHIC_FAMILIES),
        "protocol": {
            "rotation": "train on three substrates; learn relation coordinates from verified transformations; freeze; evaluate fourth; rotate all four",
            "representation_input": "paired raw observable current/target outputs only; no domain identifier or hand-coded MORPHIC signature",
            "generic_relation_grammar": "difference/sum/absolute/ratio/product/current/target x mean/spread/RMS",
            "learned_dimensions": 4,
            "feature_selection": "training-data Fisher separation among verified transformation outcomes",
            "ranking": "distance to learned transformation prototypes in standardized learned coordinates",
            "bit_compaction": "sign of each standardized coordinate forms a four-bit Echo key; continuous coordinates retain ranking precision",
            "training_labels": "obtained by executing transformations and retaining only separate-challenge-verified success",
            "search_evidence": "four public probes",
            "challenge_evidence": "six disjoint probes",
            "controls": ["cold fixed", "global frequency", "hand-designed MORPHIC signature", "shuffled transformation evidence"],
        },
        "seeds": list(seeds),
        "runs": runs,
        "summary": _aggregate(runs),
    }
