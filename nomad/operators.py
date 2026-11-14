from __future__ import annotations

import ast
import copy
from collections import OrderedDict
from typing import Iterable

from .model import Candidate
from .safe_eval import parse_expr


FAMILIES = ("root_operator", "swap_operands", "variable", "constant", "negate")


def _src(tree: ast.AST) -> str:
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def generate_candidates(source: str) -> dict[str, list[Candidate]]:
    tree = parse_expr(source)
    root = tree.body
    out: dict[str, list[Candidate]] = OrderedDict((f, []) for f in FAMILIES)
    seen = {source.replace(" ", "")}

    def add(family: str, mutated: ast.Expression, description: str) -> None:
        s = _src(mutated)
        key = s.replace(" ", "")
        if key not in seen:
            seen.add(key)
            out[family].append(Candidate(s, family, description))

    if isinstance(root, ast.BinOp):
        for op in (ast.Add(), ast.Sub(), ast.Mult(), ast.FloorDiv()):
            if type(op) is type(root.op):
                continue
            t = copy.deepcopy(tree)
            assert isinstance(t.body, ast.BinOp)
            t.body.op = op
            add("root_operator", t, f"replace root {type(root.op).__name__} with {type(op).__name__}")

        t = copy.deepcopy(tree)
        assert isinstance(t.body, ast.BinOp)
        t.body.left, t.body.right = t.body.right, t.body.left
        add("swap_operands", t, "swap root operands")

    # Replace one variable occurrence at a time.
    for idx, node in enumerate([n for n in ast.walk(tree) if isinstance(n, ast.Name)]):
        replacement = "y" if node.id == "x" else "x"
        t = copy.deepcopy(tree)
        names = [n for n in ast.walk(t) if isinstance(n, ast.Name)]
        names[idx].id = replacement
        add("variable", t, f"replace variable {node.id} with {replacement}")

    # Move one integer constant by a small exact edit.
    const_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, int)]
    for idx, node in enumerate(const_nodes):
        for delta in (-2, -1, 1, 2):
            t = copy.deepcopy(tree)
            consts = [n for n in ast.walk(t) if isinstance(n, ast.Constant) and isinstance(n.value, int)]
            consts[idx].value = int(node.value) + delta
            add("constant", t, f"adjust constant {node.value} by {delta:+d}")

    t = copy.deepcopy(tree)
    t.body = ast.UnaryOp(op=ast.USub(), operand=t.body)
    add("negate", t, "negate expression")

    return out
