from __future__ import annotations

from dataclasses import dataclass
import random

from .morphic import MORPHIC_FAMILIES
from .morphic_adapters import ADAPTERS, CodeArtifact, DataArtifact, MathArtifact, WorkflowArtifact


@dataclass(frozen=True)
class MorphicTask:
    task_id: str
    domain: str
    artifact: object
    target_artifact: object
    public_inputs: tuple[float, ...]
    challenge_inputs: tuple[float, ...]
    true_family: str


def _base_artifact(domain: str, rng: random.Random) -> object:
    # Deliberately different representations with the same observable affine base.
    a = rng.choice([1.0, 1.5, 2.0, 3.0])
    b = rng.choice([-3.0, -1.0, 0.0, 2.0])
    if domain == "code":
        return CodeArtifact(f"({a} * x) + ({b})")
    if domain == "math":
        return MathArtifact(lambda x, a=a, b=b: a * x + b, f"{a}x + {b}")
    if domain == "data":
        return DataArtifact(a, b, False)
    if domain == "workflow":
        return WorkflowArtifact(a, b, 1.0)
    raise KeyError(domain)


def make_dataset(domain: str, seed: int, *, per_family: int = 8) -> list[MorphicTask]:
    rng = random.Random((seed * 1009) ^ sum(ord(c) for c in domain))
    adapter = ADAPTERS[domain]
    tasks: list[MorphicTask] = []
    for family in MORPHIC_FAMILIES:
        for i in range(per_family):
            artifact = _base_artifact(domain, rng)
            target = adapter.transform(artifact, family)
            # Include zero often enough to make some ratio clues incomplete but
            # not enough to make the public examples degenerate.
            pool = [-6, -4, -2, -1, 0, 1, 2, 3, 5, 7]
            rng.shuffle(pool)
            public = tuple(float(x) for x in pool[:4])
            challenge = tuple(float(x) for x in pool[4:])
            tasks.append(MorphicTask(
                task_id=f"{domain}-{seed}-{family}-{i}",
                domain=domain,
                artifact=artifact,
                target_artifact=target,
                public_inputs=public,
                challenge_inputs=challenge,
                true_family=family,
            ))
    rng.shuffle(tasks)
    return tasks
