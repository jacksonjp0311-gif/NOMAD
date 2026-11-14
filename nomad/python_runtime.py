from __future__ import annotations

import ast
import traceback
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Sequence

from .python_model import PythonExample


@dataclass(frozen=True)
class TestObservation:
    passed: bool
    expected: int
    actual: int | None
    exception_type: str | None
    traceback_line: int | None
    duration_ns: int


@dataclass(frozen=True)
class PythonExecution:
    parse_ok: bool
    syntax_error_type: str | None
    syntax_line: int | None
    syntax_offset: int | None
    ast_nodes: int
    observations: tuple[TestObservation, ...]
    total_duration_ns: int

    @property
    def failures(self) -> int:
        if not self.parse_ok:
            return len(self.observations)
        return sum(not o.passed for o in self.observations)

    @property
    def runtime_errors(self) -> int:
        return sum(o.exception_type is not None for o in self.observations)


def _ast_node_count(source: str) -> int:
    try:
        return sum(1 for _ in ast.walk(ast.parse(source)))
    except SyntaxError:
        return 0


def execute_python(
    source: str,
    examples: Sequence[PythonExample],
    *,
    function_name: str = "solve",
) -> PythonExecution:
    """Execute a deliberately tiny synthetic Python function surface.

    The benchmark generator owns the source. This is not an arbitrary-code sandbox.
    Builtins are removed from the execution globals so the v0.3 study cannot use
    imports, filesystem access, networking, or ambient process capabilities.
    """

    try:
        code = compile(source, "<nomad-v03-task>", "exec")
    except SyntaxError as exc:
        observations = tuple(
            TestObservation(
                passed=False,
                expected=int(ex.expected),
                actual=None,
                exception_type="SyntaxError",
                traceback_line=exc.lineno,
                duration_ns=0,
            )
            for ex in examples
        )
        return PythonExecution(
            parse_ok=False,
            syntax_error_type="SyntaxError",
            syntax_line=exc.lineno,
            syntax_offset=exc.offset,
            ast_nodes=0,
            observations=observations,
            total_duration_ns=0,
        )

    ns: dict[str, object] = {"__builtins__": {}}
    exec(code, ns, ns)
    fn = ns.get(function_name)
    if not callable(fn):
        observations = tuple(
            TestObservation(False, int(ex.expected), None, "MissingFunction", None, 0)
            for ex in examples
        )
        return PythonExecution(True, None, None, None, _ast_node_count(source), observations, 0)

    rows: list[TestObservation] = []
    total = 0
    for ex in examples:
        started = perf_counter_ns()
        try:
            actual_obj = fn(**dict(ex.inputs))
            elapsed = perf_counter_ns() - started
            total += elapsed
            actual = int(actual_obj) if isinstance(actual_obj, (int, bool)) else None
            passed = actual == int(ex.expected)
            rows.append(TestObservation(passed, int(ex.expected), actual, None, None, elapsed))
        except Exception as exc:  # synthetic benchmark exceptions are evidence
            elapsed = perf_counter_ns() - started
            total += elapsed
            frames = traceback.extract_tb(exc.__traceback__)
            line = frames[-1].lineno if frames else None
            rows.append(
                TestObservation(
                    False,
                    int(ex.expected),
                    None,
                    type(exc).__name__,
                    line,
                    elapsed,
                )
            )

    return PythonExecution(
        parse_ok=True,
        syntax_error_type=None,
        syntax_line=None,
        syntax_offset=None,
        ast_nodes=_ast_node_count(source),
        observations=tuple(rows),
        total_duration_ns=total,
    )
