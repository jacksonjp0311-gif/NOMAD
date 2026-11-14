from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from .python_model import PythonExample, PythonTask


PUBLIC_PAIRS = [
    (-5, 0), (-4, -2), (-3, 3), (-2, 1), (-1, -1), (0, 0),
    (1, 0), (1, 2), (2, 2), (2, -3), (3, 1), (4, 0), (5, -2),
]
CHALLENGE_PAIRS = [
    (-9, 0), (-8, 3), (-7, -4), (-6, -6), (-5, 2), (-2, 0),
    (0, 4), (1, 1), (3, 0), (4, 7), (6, -3), (7, 7), (8, 2), (9, 0),
    (10, -5), (11, 4),
]


@dataclass(frozen=True)
class HiddenPythonTask:
    public: PythonTask
    target_source: str
    challenge_examples: tuple[PythonExample, ...]
    repair_families: tuple[str, ...]
    composition: str


def _call_target(source: str, x: int, y: int) -> int:
    ns: dict[str, object] = {"__builtins__": {}}
    exec(compile(source, "<nomad-target>", "exec"), ns, ns)
    return int(ns["solve"](x=x, y=y))


def _examples(source: str, pairs: Sequence[tuple[int, int]], rng: random.Random, n: int) -> tuple[PythonExample, ...]:
    chosen = list(pairs)
    rng.shuffle(chosen)
    chosen = chosen[:n]
    required = [(1, 0), (2, 2), (2, -3)] if pairs is PUBLIC_PAIRS else [(-9, 0), (7, 7), (8, 2)]
    for pair in required:
        if pair in pairs and pair not in chosen:
            chosen[-1] = pair
    return tuple(PythonExample({"x": x, "y": y}, _call_target(source, x, y)) for x, y in chosen)


def _fn(expr: str, colon: bool = True) -> str:
    suffix = ":" if colon else ""
    return f"def solve(x, y){suffix}\n    return {expr}\n"


def _single(family: str, variant: int) -> tuple[str, str, tuple[str, ...], str]:
    base = 2 + (variant % 4)
    if family == "syntax":
        target = _fn("x + y")
        broken = _fn("x + y", colon=False)
    elif family == "identifier":
        target = _fn("x + y")
        broken = _fn("z + y")
    elif family == "zero_guard":
        target = _fn("x // (y if y != 0 else 1)")
        broken = _fn("x // y")
    elif family == "binary_operator":
        choices = [("x - y", "x + y"), ("x * y", "x + y"), ("x + y", "x - y")]
        t, b = choices[variant % len(choices)]
        target, broken = _fn(t), _fn(b)
    elif family == "comparison":
        target = _fn("x if x >= y else y")
        broken = _fn("x if x > y else y")
    elif family == "constant":
        target = _fn(f"x + {base}")
        broken = _fn(f"x + {base + 2}")
    elif family == "negate":
        choices = [("-(x + y)", "x + y"), ("-x", "x")]
        t, b = choices[variant % len(choices)]
        target, broken = _fn(t), _fn(b)
    else:
        raise ValueError(family)
    return target, broken, (family,), family


COMPOUNDS = (
    "syntax+binary",
    "identifier+constant",
    "zero_guard+constant",
    "comparison+negate",
    "identifier+binary",
    "syntax+constant+negate",
)


def _compound(name: str, variant: int) -> tuple[str, str, tuple[str, ...], str]:
    base = 2 + (variant % 4)
    if name == "syntax+binary":
        return _fn("x - y"), _fn("x + y", colon=False), ("syntax", "binary_operator"), name
    if name == "identifier+constant":
        return _fn(f"x + {base}"), _fn(f"z + {base + 2}"), ("identifier", "constant"), name
    if name == "zero_guard+constant":
        return (
            _fn(f"x // (y if y != 0 else 1) + {base}"),
            _fn(f"x // y + {base + 2}"),
            ("zero_guard", "constant"),
            name,
        )
    if name == "comparison+negate":
        return (
            _fn("-(x if x >= y else y)"),
            _fn("x if x > y else y"),
            ("comparison", "negate"),
            name,
        )
    if name == "identifier+binary":
        return _fn("x * y"), _fn("z + y"), ("identifier", "binary_operator"), name
    if name == "syntax+constant+negate":
        return (
            _fn(f"-(x + {base})"),
            _fn(f"x + {base + 2}", colon=False),
            ("syntax", "constant", "negate"),
            name,
        )
    raise ValueError(name)


def make_python_task(kind: str, variant: int, seed: int, *, compound: bool = False) -> HiddenPythonTask:
    target, broken, families, composition = _compound(kind, variant) if compound else _single(kind, variant)
    rng = random.Random((seed << 9) ^ (variant << 3) ^ sum(map(ord, kind)))
    public = _examples(target, PUBLIC_PAIRS, rng, 10)
    challenge = _examples(target, CHALLENGE_PAIRS, rng, 13)
    return HiddenPythonTask(
        public=PythonTask(
            task_id=f"py-{composition}-{seed}-{variant}",
            source=broken,
            examples=public,
            function_name="solve",
            family=composition,
        ),
        target_source=target,
        challenge_examples=challenge,
        repair_families=families,
        composition=composition,
    )


def single_dataset(seed: int, per_family: int = 8, *, skew: bool = True) -> list[HiddenPythonTask]:
    families = ["syntax", "identifier", "zero_guard", "binary_operator", "comparison", "constant", "negate"]
    weights = {
        "syntax": 1,
        "identifier": 2,
        "zero_guard": 1,
        "binary_operator": 4,
        "comparison": 2,
        "constant": 4,
        "negate": 2,
    } if skew else {f: 1 for f in families}
    tasks: list[HiddenPythonTask] = []
    serial = 0
    for family in families:
        for variant in range(per_family * weights[family]):
            tasks.append(make_python_task(family, variant, seed + serial, compound=False))
            serial += 1
    random.Random(seed).shuffle(tasks)
    return tasks


def compound_dataset(seed: int, per_composition: int = 5) -> list[HiddenPythonTask]:
    tasks: list[HiddenPythonTask] = []
    serial = 0
    for name in COMPOUNDS:
        for variant in range(per_composition):
            tasks.append(make_python_task(name, variant, seed + serial, compound=True))
            serial += 1
    random.Random(seed).shuffle(tasks)
    return tasks
