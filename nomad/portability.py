"""Portability check.

Verifies that a frozen field transferred to a recipient process preserves
the declared distinctions. For a deterministic adapter T, the recipient
operation must satisfy f_B(T(x)) = T(f(x)) on the declared examples.
Derived from the Theory of Language (v0.2.0, Section 3.5).
"""
from __future__ import annotations

from typing import Any, Callable

def check(
    examples: list[tuple[int, int, int]],
    source: Callable[[int, int], int],
    recipient: Callable[[int, int], int],
    adapter: Callable[[int], int] | None = None,
) -> dict[str, Any]:
    """Check portability on examples.

    If adapter is None, identity is used. Returns agreement count and failures.
    """
    T = adapter or (lambda x: x)
    failures = []
    agreed = 0
    for x, y, expected in examples:
        source_out = source(x, y)
        recip_out = recipient(T(x), T(y))
        if T(source_out) == recip_out:
            agreed += 1
        else:
            failures.append({"x": x, "y": y, "source": source_out, "recipient": recip_out})
    return {
        "agreed": agreed,
        "total": len(examples),
        "portable": len(failures) == 0,
        "failures": failures,
    }
