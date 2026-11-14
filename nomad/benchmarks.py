from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .model import CodeTask, Example
from .safe_eval import evaluate


# Each benchmark task is produced from a correct target and a one-edit broken source.
# Target source is evaluator-only and never placed in CodeTask.
@dataclass(frozen=True)
class HiddenTask:
    public: CodeTask
    target: str
    repair_family: str


PAIRS = [
    (-4, -1), (-3, 2), (-2, 5), (-1, -4), (0, 0), (1, 3), (2, -3),
    (3, 1), (4, -2), (5, 2), (2, 2), (-2, -2), (1, -1), (-1, 1),
]


def _examples(target: str, rng: random.Random, n: int = 10) -> list[Example]:
    pairs = PAIRS.copy()
    rng.shuffle(pairs)
    chosen = pairs[:n]
    # Ensure swap evidence and x == y evidence exist.
    required = [(2, -3), (-3, 2), (2, 2)]
    for p in required:
        if p not in chosen:
            chosen[-1] = p
    out = []
    for x, y in chosen:
        try:
            expected = evaluate(target, {"x": x, "y": y})
        except ZeroDivisionError:
            continue
        out.append(Example({"x": x, "y": y}, expected))
    return out


def make_task(family: str, variant: int, seed: int) -> HiddenTask:
    rng = random.Random((seed << 8) ^ variant ^ sum(map(ord, family)))
    if family == "root_operator":
        choices = [
            ("x + y", "x - y"),
            ("x - y", "x + y"),
            ("x * y", "x + y"),
            ("x + y", "x * y"),
        ]
        target, broken = choices[variant % len(choices)]
    elif family == "swap_operands":
        choices = [("x - y", "y - x"), ("x // y", "y // x")]
        target, broken = choices[variant % len(choices)]
    elif family == "constant":
        base = 1 + (variant % 5)
        delta = 1 if variant % 2 == 0 else -1
        target = f"x + {base}"
        broken = f"x + {base + delta}"
    elif family == "variable":
        choices = [
            ("x + x", "x + y"),
            ("y + y", "x + y"),
            ("x * x", "x * y"),
            ("y * y", "x * y"),
        ]
        target, broken = choices[variant % len(choices)]
    elif family == "negate":
        choices = [("-x", "x"), ("-y", "y"), ("-(x + y)", "x + y")]
        target, broken = choices[variant % len(choices)]
    else:
        raise ValueError(family)
    examples = _examples(target, rng)
    task = CodeTask(
        task_id=f"{family}-{seed}-{variant}",
        source=broken,
        examples=examples,
        family=family,
    )
    return HiddenTask(task, target, family)


def dataset(seed: int, per_family: int, skew: bool = True) -> list[HiddenTask]:
    families = ["root_operator", "swap_operands", "constant", "variable", "negate"]
    weights = {
        "root_operator": 3,
        "swap_operands": 2,
        "constant": 4,
        "variable": 3,
        "negate": 2,
    } if skew else {f: 1 for f in families}
    tasks: list[HiddenTask] = []
    serial = 0
    for family in families:
        count = per_family * weights[family]
        for i in range(count):
            tasks.append(make_task(family, i, seed + serial))
            serial += 1
    rng = random.Random(seed)
    rng.shuffle(tasks)
    return tasks
