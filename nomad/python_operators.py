from __future__ import annotations

import ast
import copy
from collections import OrderedDict

from .python_model import PythonCandidate


PY_FAMILIES = (
    "syntax",
    "identifier",
    "zero_guard",
    "binary_operator",
    "comparison",
    "constant",
    "negate",
)


def _unparse(tree: ast.AST) -> str:
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def _try_parse(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def generate_python_candidates(source: str) -> dict[str, list[PythonCandidate]]:
    out: dict[str, list[PythonCandidate]] = OrderedDict((f, []) for f in PY_FAMILIES)
    seen = {source.strip()}

    def add(family: str, candidate: str, description: str) -> None:
        key = candidate.strip()
        if key and key not in seen:
            seen.add(key)
            out[family].append(PythonCandidate(candidate, family, description))

    tree = _try_parse(source)
    if tree is None:
        lines = source.splitlines()
        if lines and lines[0].lstrip().startswith("def ") and not lines[0].rstrip().endswith(":"):
            fixed = lines.copy()
            fixed[0] = fixed[0].rstrip() + ":"
            add("syntax", "\n".join(fixed) + "\n", "add missing function-header colon")
        return out

    # Identifier repair: unknown names -> each function parameter.
    params: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            params = [a.arg for a in n.args.args]
            break
    name_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Name)]
    for idx, node in enumerate(name_nodes):
        if node.id in params:
            continue
        for replacement in params:
            t = copy.deepcopy(tree)
            names = [n for n in ast.walk(t) if isinstance(n, ast.Name)]
            names[idx].id = replacement
            add("identifier", _unparse(t), f"replace unknown identifier {node.id} with {replacement}")

    # Binary operator mutations at every binary node.
    bin_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp)]
    op_options = (ast.Add(), ast.Sub(), ast.Mult(), ast.FloorDiv())
    for idx, node in enumerate(bin_nodes):
        for op in op_options:
            if type(op) is type(node.op):
                continue
            t = copy.deepcopy(tree)
            bins = [n for n in ast.walk(t) if isinstance(n, ast.BinOp)]
            bins[idx].op = op
            add("binary_operator", _unparse(t), f"replace {type(node.op).__name__} with {type(op).__name__}")

    # Integer constants.
    # The same numeric alternatives apply to augmented assignments in loops.
    # No issue identifier, reference patch or expected private output is used.
    augmented = [n for n in ast.walk(tree) if isinstance(n, ast.AugAssign)]
    for idx, node in enumerate(augmented):
        for op in (ast.Add(), ast.Sub(), ast.Mult(), ast.Div(), ast.FloorDiv(), ast.Mod()):
            if type(op) is type(node.op):
                continue
            t = copy.deepcopy(tree)
            assignments = [n for n in ast.walk(t) if isinstance(n, ast.AugAssign)]
            assignments[idx].op = op
            add('binary_operator', _unparse(t), f'replace augmented {type(node.op).__name__} with {type(op).__name__}')

    # Integer constants.
    constants = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool)]
    for idx, node in enumerate(constants):
        for delta in (-2, -1, 1, 2):
            t = copy.deepcopy(tree)
            cs = [n for n in ast.walk(t) if isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool)]
            cs[idx].value = int(node.value) + delta
            add("constant", _unparse(t), f"adjust constant {node.value} by {delta:+d}")

    # Comparison operators.
    compare_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Compare) and len(n.ops) == 1]
    cmp_options = (ast.Gt(), ast.GtE(), ast.Lt(), ast.LtE(), ast.Eq())
    for idx, node in enumerate(compare_nodes):
        for op in cmp_options:
            if type(op) is type(node.ops[0]):
                continue
            t = copy.deepcopy(tree)
            cmps = [n for n in ast.walk(t) if isinstance(n, ast.Compare) and len(n.ops) == 1]
            cmps[idx].ops[0] = op
            add("comparison", _unparse(t), f"replace comparison {type(node.ops[0]).__name__} with {type(op).__name__}")

    # Guard a simple divisor against zero.
    for idx, node in enumerate(bin_nodes):
        if not isinstance(node.op, ast.FloorDiv):
            continue
        if isinstance(node.right, ast.IfExp):
            continue
        t = copy.deepcopy(tree)
        bins = [n for n in ast.walk(t) if isinstance(n, ast.BinOp)]
        right = copy.deepcopy(bins[idx].right)
        bins[idx].right = ast.IfExp(
            test=ast.Compare(left=copy.deepcopy(right), ops=[ast.NotEq()], comparators=[ast.Constant(0)]),
            body=copy.deepcopy(right),
            orelse=ast.Constant(1),
        )
        add("zero_guard", _unparse(t), "guard divisor with nonzero conditional")

    # Toggle a unary minus around the returned expression.
    returns = [n for n in ast.walk(tree) if isinstance(n, ast.Return) and n.value is not None]
    for idx, node in enumerate(returns):
        t = copy.deepcopy(tree)
        rs = [n for n in ast.walk(t) if isinstance(n, ast.Return) and n.value is not None]
        value = rs[idx].value
        if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
            rs[idx].value = value.operand
            add("negate", _unparse(t), "remove return negation")
        else:
            rs[idx].value = ast.UnaryOp(op=ast.USub(), operand=value)
            add("negate", _unparse(t), "negate returned expression")

    return out
