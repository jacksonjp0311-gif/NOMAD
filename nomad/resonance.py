from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Sequence

from .python_model import PythonExample, PythonTask
from .python_runtime import PythonExecution, execute_python

# Parser channel
P_PARSE_ERROR = 1 << 0
P_DEF_HEADER = 1 << 1
# Runtime channel
R_NAME_ERROR = 1 << 4
R_ZERO_DIVISION = 1 << 5
R_TYPE_ERROR = 1 << 6
R_OTHER_ERROR = 1 << 7
R_ERROR_ON_RETURN = 1 << 8
# Test channel
T_FEW_FAILURES = 1 << 12
T_MANY_FAILURES = 1 << 13
T_ALL_FAILURES = 1 << 14
T_FAILS_Y_ZERO = 1 << 15
T_FAILS_EQUAL = 1 << 16
T_CONSTANT_RESIDUAL = 1 << 17
T_MIXED_RESIDUAL = 1 << 18
T_PROP_X = 1 << 19
T_PROP_Y = 1 << 20
# AST channel
A_BINOP = 1 << 24
A_COMPARE = 1 << 25
A_IFEXP = 1 << 26
A_UNARY = 1 << 27
A_UNKNOWN_NAME = 1 << 28
A_FLOORDIV = 1 << 29
# Cost channel (deterministic structural/work proxy)
C_HIGH_STRUCTURAL_WORK = 1 << 32
C_EXCEPTION_HEAVY = 1 << 33


def _constant_ratio(nums: Sequence[int], dens: Sequence[int]) -> bool:
    pairs = [(n, d) for n, d in zip(nums, dens) if d != 0]
    if len(pairs) < 2:
        return False
    n0, d0 = pairs[0]
    return all(n * d0 == n0 * d for n, d in pairs[1:])


@dataclass(frozen=True)
class ResonanceState:
    parser_bits: int
    runtime_bits: int
    test_bits: int
    ast_bits: int
    cost_bits: int
    failures: int
    runtime_errors: int
    ast_nodes: int
    executed_tests: int
    measured_duration_ns: int
    parse_ok: bool

    @property
    def fusion_signature(self) -> int:
        return self.parser_bits | self.runtime_bits | self.test_bits | self.ast_bits | self.cost_bits

    @property
    def test_signature(self) -> int:
        # Deliberately weaker control: only observable pass/fail/residual evidence.
        return self.test_bits

    def key(self, mode: str) -> int:
        if mode == "fusion":
            return self.fusion_signature
        if mode == "test_only":
            return self.test_signature
        raise ValueError(f"unknown resonance mode: {mode}")

    @property
    def evidence_score(self) -> float:
        # Evidence dominance: inability to parse is worse than runtime failure,
        # runtime failure is worse than an ordinary wrong result. Learned priors
        # never enter this score.
        n = max(1, self.executed_tests)
        parse_penalty = 3.0 if not self.parse_ok else 0.0
        runtime_penalty = 1.5 * (self.runtime_errors / n)
        test_penalty = self.failures / n
        return parse_penalty + runtime_penalty + test_penalty


def _ast_bits(source: str) -> tuple[int, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0, 0
    bits = 0
    nodes = list(ast.walk(tree))
    if any(isinstance(n, ast.BinOp) for n in nodes):
        bits |= A_BINOP
    if any(isinstance(n, ast.Compare) for n in nodes):
        bits |= A_COMPARE
    if any(isinstance(n, ast.IfExp) for n in nodes):
        bits |= A_IFEXP
    if any(isinstance(n, ast.UnaryOp) for n in nodes):
        bits |= A_UNARY
    if any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.FloorDiv) for n in nodes):
        bits |= A_FLOORDIV
    params: set[str] = set()
    for n in nodes:
        if isinstance(n, ast.FunctionDef):
            params.update(a.arg for a in n.args.args)
    names = {n.id for n in nodes if isinstance(n, ast.Name)}
    if any(name not in params for name in names):
        bits |= A_UNKNOWN_NAME
    return bits, len(nodes)


def encode_resonance(task: PythonTask, source: str | None = None, *,
                     execution: PythonExecution | None = None) -> ResonanceState:
    """Fuse observations; an adapter may supply a trusted, bound observation.

    The legacy default executes trusted generated fixtures. Isolated adapters
    must supply observations from their permitted evaluator instead of calling
    that host executor. Supplied observations do not confer verification power.
    """
    source = task.source if source is None else source
    if execution is not None:
        if (not isinstance(execution, PythonExecution)
                or len(execution.observations) != len(task.examples)
                or any(o.expected != int(e.expected) for o, e in zip(execution.observations, task.examples))):
            raise ValueError('precomputed RESONANCE observations do not match public contract')
        run = execution
    else:
        run = execute_python(source, task.examples, function_name=task.function_name)

    parser_bits = 0
    if not run.parse_ok:
        parser_bits |= P_PARSE_ERROR
        if run.syntax_line == 1:
            parser_bits |= P_DEF_HEADER

    runtime_bits = 0
    types = [o.exception_type for o in run.observations if o.exception_type]
    if "NameError" in types:
        runtime_bits |= R_NAME_ERROR
    if "ZeroDivisionError" in types:
        runtime_bits |= R_ZERO_DIVISION
    if "TypeError" in types:
        runtime_bits |= R_TYPE_ERROR
    if any(t not in {"NameError", "ZeroDivisionError", "TypeError", "SyntaxError"} for t in types):
        runtime_bits |= R_OTHER_ERROR
    if any(o.exception_type and o.traceback_line and o.traceback_line >= 2 for o in run.observations):
        runtime_bits |= R_ERROR_ON_RETURN

    total = max(1, len(task.examples))
    failures = run.failures
    test_bits = 0
    if 0 < failures <= max(1, total // 3):
        test_bits |= T_FEW_FAILURES
    if failures >= max(2, (2 * total) // 3):
        test_bits |= T_MANY_FAILURES
    if failures == total:
        test_bits |= T_ALL_FAILURES

    residuals: list[int] = []
    xs: list[int] = []
    ys: list[int] = []
    for ex, obs in zip(task.examples, run.observations):
        x = int(ex.inputs.get("x", 0))
        y = int(ex.inputs.get("y", 0))
        xs.append(x)
        ys.append(y)
        if not obs.passed and y == 0:
            test_bits |= T_FAILS_Y_ZERO
        if not obs.passed and x == y:
            test_bits |= T_FAILS_EQUAL
        if obs.actual is not None:
            residuals.append(int(ex.expected) - obs.actual)
        else:
            residuals.append(0)

    nonzero = [r for r in residuals if r]
    if nonzero and len(set(nonzero)) == 1:
        test_bits |= T_CONSTANT_RESIDUAL
    if any(r > 0 for r in nonzero) and any(r < 0 for r in nonzero):
        test_bits |= T_MIXED_RESIDUAL
    if _constant_ratio(residuals, xs):
        test_bits |= T_PROP_X
    if _constant_ratio(residuals, ys):
        test_bits |= T_PROP_Y

    ast_bits, ast_nodes = _ast_bits(source)
    cost_bits = 0
    # Deterministic proxy: structural size plus the number of executed tests.
    structural_work = ast_nodes + (len(run.observations) if run.parse_ok else 0)
    if structural_work >= 30:
        cost_bits |= C_HIGH_STRUCTURAL_WORK
    if run.runtime_errors >= max(2, total // 2):
        cost_bits |= C_EXCEPTION_HEAVY

    return ResonanceState(
        parser_bits=parser_bits,
        runtime_bits=runtime_bits,
        test_bits=test_bits,
        ast_bits=ast_bits,
        cost_bits=cost_bits,
        failures=failures,
        runtime_errors=run.runtime_errors,
        ast_nodes=ast_nodes,
        executed_tests=(len(run.observations) if run.parse_ok else 0),
        measured_duration_ns=run.total_duration_ns,
        parse_ok=run.parse_ok,
    )

PARSER_MASK = P_PARSE_ERROR | P_DEF_HEADER
RUNTIME_MASK = R_NAME_ERROR | R_ZERO_DIVISION | R_TYPE_ERROR | R_OTHER_ERROR | R_ERROR_ON_RETURN
TEST_MASK = (
    T_FEW_FAILURES | T_MANY_FAILURES | T_ALL_FAILURES | T_FAILS_Y_ZERO |
    T_FAILS_EQUAL | T_CONSTANT_RESIDUAL | T_MIXED_RESIDUAL | T_PROP_X | T_PROP_Y
)
AST_MASK = A_BINOP | A_COMPARE | A_IFEXP | A_UNARY | A_UNKNOWN_NAME | A_FLOORDIV
COST_MASK = C_HIGH_STRUCTURAL_WORK | C_EXCEPTION_HEAVY
