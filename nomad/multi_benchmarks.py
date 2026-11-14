from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from .model import CodeTask, Example
from .safe_eval import evaluate


@dataclass(frozen=True)
class HiddenMultiTask:
    public: CodeTask
    target: str
    expected_families: tuple[str, ...]
    challenge_examples: tuple[Example, ...]
    composition: str


PUBLIC_PAIRS = [
    (-7, 3), (-5, -2), (-4, 5), (-3, 2), (-2, -5), (-1, 4),
    (0, 3), (1, -4), (2, 5), (3, -2), (4, 1), (5, -3),
    (2, 2), (-3, -3), (1, -1), (-1, 1),
]
CHALLENGE_PAIRS = [
    (-11, 2), (-9, -4), (-8, 7), (-6, 5), (-4, -7), (-2, 9),
    (1, 8), (3, -8), (5, 6), (7, -5), (9, 4), (11, -2),
    (6, 6), (-6, -6), (8, 1), (1, 8), (-8, 1), (1, -8),
]


def _make_examples(target: str, pairs: Sequence[tuple[int, int]], rng: random.Random, n: int) -> tuple[Example, ...]:
    items = list(pairs)
    rng.shuffle(items)
    out: list[Example] = []
    for x, y in items:
        try:
            value = evaluate(target, {"x": x, "y": y})
        except (ZeroDivisionError, ValueError):
            continue
        out.append(Example({"x": x, "y": y}, value))
        if len(out) >= n:
            break
    return tuple(out)


# Each pair is intentionally not solvable by a single v0.1 operator under the
# supplied public examples. `expected_families` is evaluator-only metadata and is
# never placed in CodeTask.
TEMPLATES: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("x + 2", "y + 4", ("variable", "constant"), "variable+constant"),
    ("x * y", "y + y", ("root_operator", "variable"), "operator+variable"),
    ("x - y", "y + x", ("swap_operands", "root_operator"), "swap+operator"),
    ("-(x + 3)", "x + 1", ("constant", "negate"), "constant+negate"),
    ("-x", "y", ("variable", "negate"), "variable+negate"),
    ("x * 3", "x + 1", ("root_operator", "constant"), "operator+constant"),
    ("x - 2", "4 - x", ("swap_operands", "constant"), "swap+constant"),
    ("x * 3", "y + 1", ("variable", "root_operator", "constant"), "triple-vrc"),
    ("-(x + 3)", "y + 1", ("variable", "constant", "negate"), "triple-vcn"),
    ("-(x - y)", "y + x", ("swap_operands", "root_operator", "negate"), "triple-srn"),
)


def make_multi_task(template_index: int, variant: int, seed: int) -> HiddenMultiTask:
    target, broken, families, composition = TEMPLATES[template_index % len(TEMPLATES)]
    rng = random.Random((seed << 10) ^ (template_index << 4) ^ variant)

    # Small algebraically equivalent perturbations create disjoint source strings
    # without changing the hidden repair structure.
    if composition == "variable+constant":
        base = 2 + (variant % 3)
        target = f"x + {base}"
        broken = f"y + {base + 2}"
    elif composition == "operator+constant":
        base = 2 + (variant % 3)
        target = f"x * {base}"
        broken = f"x + {base - 2}"
    elif composition == "swap+constant":
        base = 2 + (variant % 3)
        target = f"x - {base}"
        broken = f"{base + 2} - x"
    elif composition == "triple-vrc":
        base = 2 + (variant % 3)
        target = f"x * {base}"
        broken = f"y + {base - 2}"
    elif composition == "triple-vcn":
        base = 2 + (variant % 3)
        target = f"-(x + {base})"
        broken = f"y + {base - 2}"

    public = _make_examples(target, PUBLIC_PAIRS, rng, n=9)
    challenge = _make_examples(target, CHALLENGE_PAIRS, rng, n=14)
    task = CodeTask(
        task_id=f"multi-{template_index}-{seed}-{variant}",
        source=broken,
        examples=public,
        family="hidden-multi",
    )
    return HiddenMultiTask(task, target, families, challenge, composition)


def multi_dataset(
    seed: int,
    per_template: int = 4,
    template_indices: Sequence[int] | None = None,
) -> list[HiddenMultiTask]:
    indices = list(range(len(TEMPLATES))) if template_indices is None else list(template_indices)
    tasks: list[HiddenMultiTask] = []
    serial = 0
    for idx in indices:
        for variant in range(per_template):
            tasks.append(make_multi_task(idx, variant, seed + serial))
            serial += 1
    rng = random.Random(seed)
    rng.shuffle(tasks)
    return tasks


def challenge_passes(hidden: HiddenMultiTask, source: str) -> bool:
    try:
        return all(evaluate(source, ex.inputs) == ex.expected for ex in hidden.challenge_examples)
    except Exception:
        return False
