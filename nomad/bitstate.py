from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .model import CodeTask
from .safe_eval import evaluate


BIT_CONSTANT_RESIDUAL = 1 << 0
BIT_MIXED_SIGN = 1 << 1
BIT_PROPORTIONAL_X = 1 << 2
BIT_PROPORTIONAL_Y = 1 << 3
BIT_MATCHES_WHEN_X_EQ_Y = 1 << 4
BIT_ANTISYMMETRIC_PAIR = 1 << 5
BIT_ALL_ZERO_CURRENT = 1 << 6
BIT_MAGNITUDE_GROWS = 1 << 7
BIT_COMPILE_OR_RUNTIME_ERROR = 1 << 8
BIT_FEW_FAILURES = 1 << 9
BIT_MANY_FAILURES = 1 << 10


@dataclass(frozen=True)
class FailureState:
    bits: int
    residuals: tuple[int, ...]
    actuals: tuple[int | None, ...]
    failures: int
    runtime_errors: int

    @property
    def key(self) -> int:
        return self.bits


def _constant_ratio(nums: Sequence[int], dens: Sequence[int]) -> bool:
    pairs = [(n, d) for n, d in zip(nums, dens) if d != 0]
    if len(pairs) < 2:
        return False
    n0, d0 = pairs[0]
    return all(n * d0 == n0 * d for n, d in pairs[1:])


def encode_failure(task: CodeTask, source: str | None = None) -> FailureState:
    """Encode observable execution failure into a compact Bitwork-style state.

    v0.2 accepts an explicit candidate source. This matters for temporal search:
    every child state is recomputed from the evidence produced by *that exact
    program*, rather than reusing the root failure signature.
    """

    source = task.source if source is None else source
    actuals: list[int | None] = []
    residuals: list[int] = []
    error = False
    runtime_errors = 0
    failures = 0
    xs: list[int] = []
    ys: list[int] = []
    expected: list[int] = []
    for ex in task.examples:
        xs.append(int(ex.inputs.get("x", 0)))
        ys.append(int(ex.inputs.get("y", 0)))
        expected.append(int(ex.expected))
        try:
            a = evaluate(source, ex.inputs)
            actuals.append(a)
            residuals.append(ex.expected - a)
            if a != ex.expected:
                failures += 1
        except Exception:
            actuals.append(None)
            residuals.append(0)
            error = True
            runtime_errors += 1
            failures += 1

    bits = 0
    nonzero = [r for r in residuals if r != 0]
    if nonzero and len(set(residuals)) == 1:
        bits |= BIT_CONSTANT_RESIDUAL
    if nonzero and any(r > 0 for r in nonzero) and any(r < 0 for r in nonzero):
        bits |= BIT_MIXED_SIGN
    if _constant_ratio(residuals, xs):
        bits |= BIT_PROPORTIONAL_X
    if _constant_ratio(residuals, ys):
        bits |= BIT_PROPORTIONAL_Y
    eq = [i for i, (x, y) in enumerate(zip(xs, ys)) if x == y]
    if eq and all(actuals[i] == expected[i] for i in eq):
        bits |= BIT_MATCHES_WHEN_X_EQ_Y

    lookup = {(x, y): residuals[i] for i, (x, y) in enumerate(zip(xs, ys))}
    pairs = []
    for (x, y), r in lookup.items():
        if x != y and (y, x) in lookup:
            pairs.append((r, lookup[(y, x)]))
    if pairs and all(a == -b and a != 0 for a, b in pairs):
        bits |= BIT_ANTISYMMETRIC_PAIR

    valid_actuals = [a for a in actuals if a is not None]
    if valid_actuals and all(a == 0 for a in valid_actuals):
        bits |= BIT_ALL_ZERO_CURRENT

    mags = [(abs(e), abs(a)) for e, a in zip(expected, actuals) if a is not None]
    if mags and sum(e for e, _ in mags) > sum(a for _, a in mags):
        bits |= BIT_MAGNITUDE_GROWS
    if error:
        bits |= BIT_COMPILE_OR_RUNTIME_ERROR

    total = max(1, len(task.examples))
    if 0 < failures <= max(1, total // 3):
        bits |= BIT_FEW_FAILURES
    if failures >= max(2, (2 * total) // 3):
        bits |= BIT_MANY_FAILURES

    return FailureState(
        bits=bits,
        residuals=tuple(residuals),
        actuals=tuple(actuals),
        failures=failures,
        runtime_errors=runtime_errors,
    )
