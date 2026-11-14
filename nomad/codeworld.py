from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from statistics import mean
from typing import Iterable

from .causal_skills import CausalSkillRegistry
from .python_operators import PY_FAMILIES, generate_python_candidates
from .witness import Witness


@dataclass(frozen=True)
class CodeWorldExample:
    inputs: dict[str, int]
    expected: int | bool


@dataclass(frozen=True)
class CodeWorldTask:
    task_id: str
    source: str
    public: tuple[CodeWorldExample, ...]
    challenge: tuple[CodeWorldExample, ...]
    final: tuple[CodeWorldExample, ...]
    true_family: str  # evaluator metadata; search/ranking never reads this field


@dataclass(frozen=True)
class CodeWorldResult:
    task_id: str
    solved: bool
    final_correct: bool
    attempts: int
    family_attempts: int
    chosen_family: str | None
    predicted_family: str | None
    predicted_family_correct: bool | None
    witness_supported: bool
    abstained_reason: str | None


def _outputs_from_source(source: str, examples: tuple[CodeWorldExample, ...]) -> tuple[tuple[float, ...] | None, str | None]:
    namespace: dict[str, object] = {}
    try:
        exec(compile(source, "<codeworld>", "exec"), {"__builtins__": {}}, namespace)
        solve = namespace.get("solve")
        if not callable(solve):
            return None, "MissingSolve"
        out = []
        for ex in examples:
            try:
                value = solve(**ex.inputs)
                out.append(float(value))
            except Exception as e:
                return None, type(e).__name__
        return tuple(out), None
    except Exception as e:
        return None, type(e).__name__


def _run_outputs(root: Path, examples: tuple[CodeWorldExample, ...]) -> tuple[tuple[float, ...] | None, str | None]:
    return _outputs_from_source((root / "solution.py").read_text(encoding="utf-8"), examples)



_ERROR_CODES = {
    "SyntaxError": 1001.0,
    "NameError": 1002.0,
    "ZeroDivisionError": 1003.0,
    "MissingSolve": 1004.0,
    "NonNumericOutput": 1005.0,
}

def _evidence_vector(source: str, examples: tuple[CodeWorldExample, ...]) -> tuple[float, ...]:
    values, err = _outputs_from_source(source, examples)
    if err is None and values is not None:
        return values
    code = _ERROR_CODES.get(str(err), 1099.0)
    # Runtime/parser failure is still an observable consequence.  CODEWORLD
    # represents it as a deterministic finite sentinel so WITNESS can compare
    # the before/after evidence without trusting a caller success boolean.
    return tuple(code for _ in examples)

def _expected_vector(examples: tuple[CodeWorldExample, ...]) -> tuple[float, ...]:
    return tuple(float(e.expected) for e in examples)


def _public_test_text(task: CodeWorldTask) -> str:
    lines = [
        "import unittest",
        "from solution import solve",
        "",
        "class PublicTests(unittest.TestCase):",
    ]
    for idx, ex in enumerate(task.public):
        args = ", ".join(f"{k}={v!r}" for k, v in ex.inputs.items())
        lines.append(f"    def test_{idx:02d}(self):")
        lines.append(f"        self.assertEqual(solve({args}), {ex.expected!r})")
    lines += ["", "if __name__ == '__main__':", "    unittest.main()", ""]
    return "\n".join(lines)


def materialize(task: CodeWorldTask, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)
    # Mission identities bind exact UTF-8 bytes. Native Windows text-mode
    # newline conversion must not silently change the planned source digest.
    (root / "solution.py").write_bytes(task.source.encode("utf-8"))
    (root / "tests" / "test_public.py").write_bytes(_public_test_text(task).encode("utf-8"))
    (root / "README.md").write_text(
        f"# CODEWORLD fixture {task.task_id}\n\nRepair `solution.py` until the public tests pass.\n",
        encoding="utf-8",
    )


def run_public_tests(root: Path) -> bool:
    p = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=root, text=True, capture_output=True,
    )
    return p.returncode == 0


def _source_predicates(source: str) -> set[str]:
    out: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"parse_error"}
    out.add("parse_ok")
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp):
            out.add("ast_binop")
            out.add(f"ast_binop_{type(n.op).__name__}")
            if isinstance(n.right, ast.Name):
                out.add("ast_binop_rhs_name")
            if isinstance(n.right, ast.Constant):
                out.add("ast_binop_rhs_constant")
        elif isinstance(n, ast.Compare) and n.ops:
            out.add("ast_compare")
            out.add(f"ast_compare_{type(n.ops[0]).__name__}")
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            out.add("ast_unary_negate")
    return out


def extract_context(task: CodeWorldTask, root: Path) -> frozenset[str]:
    source = (root / "solution.py").read_text(encoding="utf-8")
    features = _source_predicates(source)
    current, err = _run_outputs(root, task.public)
    target = _expected_vector(task.public)
    if err:
        features.add(f"runtime_{err}")
        features.add("runtime_error")
    else:
        features.add("runtime_ok")
        assert current is not None
        diffs = [c - t for c, t in zip(current, target)]
        failed = sum(abs(d) > 1e-9 for d in diffs)
        features.add("public_numeric")
        features.add("one_failure" if failed == 1 else "many_failures" if failed > 1 else "zero_failures")
        nonzero = [d for d in diffs if abs(d) > 1e-9]
        if nonzero and all(d > 0 for d in nonzero):
            features.add("error_all_above")
        elif nonzero and all(d < 0 for d in nonzero):
            features.add("error_all_below")
        elif nonzero:
            features.add("error_mixed")
        if nonzero and max(nonzero) - min(nonzero) < 1e-9:
            features.add("error_constant_delta")
        if all(v in (0.0, 1.0) for v in current + target):
            features.add("boolean_outputs")
    if all(isinstance(ex.expected, bool) for ex in task.public):
        features.add("target_boolean")
    else:
        features.add("target_numeric")
    if task.public and all(len(ex.inputs) == 1 for ex in task.public):
        if all(float(ex.expected) == float(next(iter(ex.inputs.values()))) for ex in task.public):
            features.add("target_identity_single_input")
        offsets = [float(ex.expected) - float(next(iter(ex.inputs.values()))) for ex in task.public]
        if offsets and max(offsets) - min(offsets) < 1e-9:
            features.add("target_constant_offset_single_input")
    if task.public and all(len(ex.inputs) == 2 for ex in task.public):
        if all(float(ex.expected) == float(sum(ex.inputs.values())) for ex in task.public):
            features.add("target_matches_sum_inputs")
        prod_ok = True
        for ex in task.public:
            vals = list(ex.inputs.values())
            if float(ex.expected) != float(vals[0] * vals[1]):
                prod_ok = False
                break
        if prod_ok:
            features.add("target_matches_product_inputs")
    zero_rows = [ex for ex in task.public if any(v == 0 for v in ex.inputs.values())]
    if zero_rows:
        features.add("public_contains_zero_input")
        if all(float(ex.expected) == 0.0 for ex in zero_rows):
            features.add("zero_case_target_zero")
        equals_other = True
        for ex in zero_rows:
            nonzero = [v for v in ex.inputs.values() if v != 0]
            if not nonzero or float(ex.expected) != float(nonzero[0]):
                equals_other = False
                break
        if equals_other:
            features.add("zero_case_target_nonzero_arg")
    eq_rows = [ex for ex in task.public if len(ex.inputs) >= 2 and len(set(ex.inputs.values())) == 1]
    if eq_rows:
        features.add("public_contains_equal_args")
    return frozenset(features)


def _receipt_for_candidate(
    *,
    witness: Witness,
    task: CodeWorldTask,
    root: Path,
    family: str,
    attempt: int,
    epoch: int = 0,
):
    candidate_source = (root / "solution.py").read_text(encoding="utf-8")
    cur_pub = _evidence_vector(task.source, task.public)
    cur_ch = _evidence_vector(task.source, task.challenge)
    cand_pub = _evidence_vector(candidate_source, task.public)
    cand_ch = _evidence_vector(candidate_source, task.challenge)
    transmission_id = sha256(f"{task.task_id}|{family}|{attempt}|{candidate_source}".encode()).hexdigest()[:24]
    receipt = witness.attest(
        task_id=task.task_id,
        transmission_id=transmission_id,
        world_epoch=epoch,
        current_public=cur_pub,
        target_public=_expected_vector(task.public),
        candidate_public=cand_pub,
        current_challenge=cur_ch,
        target_challenge=_expected_vector(task.challenge),
        candidate_challenge=cand_ch,
    )
    return transmission_id, receipt


def _available_groups(source: str) -> dict[str, list]:
    groups = generate_python_candidates(source)
    return {k: v for k, v in groups.items() if v}


def train_causal_registry(tasks: Iterable[CodeWorldTask]) -> CausalSkillRegistry:
    registry = CausalSkillRegistry(min_support=4, max_terms=3)
    witness = Witness(witness_id="nomad-witness-v0.7-codeworld")
    for task in tasks:
        with tempfile.TemporaryDirectory(prefix="nomad-train-") as td:
            root = Path(td)
            materialize(task, root)
            context = extract_context(task, root)
            groups = _available_groups(task.source)
            # Evaluate every available family at least once, so positive claims and
            # counterexamples are both WITNESS-derived rather than caller booleans.
            for family, candidates in groups.items():
                family_receipt = None
                fallback_receipt = None
                for idx, candidate in enumerate(candidates, 1):
                    (root / "solution.py").write_text(candidate.source, encoding="utf-8")
                    info = _receipt_for_candidate(witness=witness, task=task, root=root, family=family, attempt=idx)
                    if info is None:
                        continue
                    transmission_id, receipt = info
                    fallback_receipt = (transmission_id, receipt)
                    if receipt.supported:
                        family_receipt = (transmission_id, receipt)
                        break
                chosen = family_receipt or fallback_receipt
                if chosen is None:
                    continue
                transmission_id, receipt = chosen
                registry.ingest(
                    witness=witness, receipt=receipt, context=context, family=family,
                    task_id=task.task_id, transmission_id=transmission_id, world_epoch=0,
                )
                (root / "solution.py").write_text(task.source, encoding="utf-8")
    return registry


def _global_family_order(tasks: Iterable[CodeWorldTask]) -> list[str]:
    counts = {f: 0 for f in PY_FAMILIES}
    for task in tasks:
        counts[task.true_family] = counts.get(task.true_family, 0) + 1
    return sorted(PY_FAMILIES, key=lambda f: (-counts.get(f, 0), PY_FAMILIES.index(f)))


def solve_task(
    task: CodeWorldTask,
    *,
    causal: CausalSkillRegistry | None = None,
    global_order: Iterable[str] | None = None,
    max_attempts: int = 40,
    verify_repo_tests: bool = True,
) -> CodeWorldResult:
    witness = Witness(witness_id="nomad-witness-v0.7-codeworld")
    with tempfile.TemporaryDirectory(prefix="nomad-eval-") as td:
        root = Path(td)
        materialize(task, root)
        context = extract_context(task, root)
        groups = _available_groups(task.source)
        available = [f for f in PY_FAMILIES if f in groups]
        predicted_family = None
        if causal is not None:
            applicable = causal.applicable(context, available)
            predicted_family = applicable[0].family if applicable else None
            family_order = causal.rank_families(context, available)
        elif global_order is not None:
            go = [f for f in global_order if f in groups]
            family_order = go + [f for f in available if f not in go]
        else:
            family_order = available

        attempts = 0
        family_attempts = 0
        for family in family_order:
            family_attempts += 1
            for candidate in groups[family]:
                if attempts >= max_attempts:
                    return CodeWorldResult(task.task_id, False, False, attempts, family_attempts, None,
                                           predicted_family, None if predicted_family is None else predicted_family == task.true_family,
                                           False, "attempt_budget")
                attempts += 1
                (root / "solution.py").write_text(candidate.source, encoding="utf-8")
                # Cheap execution feedback prunes obviously wrong candidates.  A
                # candidate that appears to solve the public examples must still
                # survive the repository's actual unittest process before WITNESS.
                public_out, public_err = _outputs_from_source(candidate.source, task.public)
                if public_err is not None or public_out != _expected_vector(task.public):
                    continue
                if verify_repo_tests and not run_public_tests(root):
                    continue
                info = _receipt_for_candidate(witness=witness, task=task, root=root, family=family, attempt=attempts)
                if info is None:
                    continue
                _, receipt = info
                if not receipt.supported:
                    continue
                final_out, final_err = _run_outputs(root, task.final)
                final_correct = final_err is None and final_out == _expected_vector(task.final)
                return CodeWorldResult(
                    task.task_id, True, final_correct, attempts, family_attempts, family,
                    predicted_family,
                    None if predicted_family is None else predicted_family == task.true_family,
                    True, None,
                )
            (root / "solution.py").write_text(task.source, encoding="utf-8")
        return CodeWorldResult(
            task.task_id, False, False, attempts, family_attempts, None,
            predicted_family,
            None if predicted_family is None else predicted_family == task.true_family,
            False, "frontier_exhausted",
        )


def make_codeworld_tasks(seed: int, *, per_family: int = 6, include_ood: bool = False) -> list[CodeWorldTask]:
    # Deterministic task variation; family labels are used only by the evaluator.
    tasks: list[CodeWorldTask] = []
    offset = seed % 7

    def split_examples(rows):
        return tuple(rows[:4]), tuple(rows[4:7]), tuple(rows[7:10])

    for i in range(per_family):
        base = 3 + ((i + offset) % 4)
        # Binary operator: Add -> Sub or Mult. All inputs positive so effect geometry is stable.
        op = "sub" if i % 2 == 0 else "mul"
        rows = []
        for j in range(10):
            x, y = base + j, 2 + (j % 3)
            expected = x - y if op == "sub" else x * y
            rows.append(CodeWorldExample({"x": x, "y": y}, expected))
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-bin-{i}", "def solve(x, y):\n    return x + y\n", pub, ch, fin, "binary_operator"))

        # Constant repair: x + 1 -> x + 2.
        rows = [CodeWorldExample({"x": base + j}, base + j + 2) for j in range(10)]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-const-{i}", "def solve(x):\n    return x + 1\n", pub, ch, fin, "constant"))

        # Comparison boundary: > -> >=.
        pairs = [(base, base), (base+1, base), (base, base+1), (base+2, base),
                 (base+3, base+3), (base+4, base+3), (base+2, base+3),
                 (base+5, base+5), (base+6, base+5), (base+5, base+6)]
        rows = [CodeWorldExample({"x": x, "y": y}, x >= y) for x, y in pairs]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-cmp-{i}", "def solve(x, y):\n    return x > y\n", pub, ch, fin, "comparison"))

        # Zero guard: floor division, defined as x when y == 0.
        vals = [(base, 0), (base+1, 2), (base+2, 1), (base+3, 0), (base+4, 2),
                (base+5, 0), (base+6, 3), (base+7, 0), (base+8, 2), (base+9, 1)]
        rows = [CodeWorldExample({"x": x, "y": y}, x if y == 0 else x // y) for x, y in vals]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-zero-{i}", "def solve(x, y):\n    return x // y\n", pub, ch, fin, "zero_guard"))

        # Unknown identifier: z -> x.
        rows = [CodeWorldExample({"x": base+j, "y": j % 4}, base+j + (j % 4)) for j in range(10)]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-id-{i}", "def solve(x, y):\n    return z + y\n", pub, ch, fin, "identifier"))

        # Negation: -x -> x.
        rows = [CodeWorldExample({"x": base+j}, base+j) for j in range(10)]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-neg-{i}", "def solve(x):\n    return -x\n", pub, ch, fin, "negate"))

    if include_ood:
        # Boundary counterexamples: the relevant operator family is available,
        # but the requested consequence lies outside that family's demonstrated
        # one-edit envelope. These are used to teach abstention boundaries.
        rows = [CodeWorldExample({"x": 2 + (j % 3), "y": 2 + (j % 2)}, (2 + (j % 3)) ** (2 + (j % 2)) + 1) for j in range(10)]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-ood-pow", "def solve(x, y):\n    return x ** y\n", pub, ch, fin, "unavailable"))

        pairs = [(base+j, 2 + (j % 3)) for j in range(10)]
        rows = [CodeWorldExample({"x": x, "y": y}, x + y) for x, y in pairs]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-ood-cmp", "def solve(x, y):\n    return x > y\n", pub, ch, fin, "unavailable"))

        rows = [CodeWorldExample({"x": base+j}, 2 * (base+j)) for j in range(10)]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-ood-const", "def solve(x):\n    return x + 1\n", pub, ch, fin, "unavailable"))

        pairs = [(base+j, 2 + (j % 3)) for j in range(10)]
        rows = [CodeWorldExample({"x": x, "y": y}, x * y) for x, y in pairs]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-ood-id", "def solve(x, y):\n    return z + y\n", pub, ch, fin, "unavailable"))

        vals = [(base, 0), (base+1, 2), (base+2, 1), (base+3, 0), (base+4, 2),
                (base+5, 0), (base+6, 3), (base+7, 0), (base+8, 2), (base+9, 1)]
        rows = [CodeWorldExample({"x": x, "y": y}, 0 if y == 0 else x // y) for x, y in vals]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-ood-zero", "def solve(x, y):\n    return x // y\n", pub, ch, fin, "unavailable"))

        rows = [CodeWorldExample({"x": base+j}, base+j+1) for j in range(10)]
        pub, ch, fin = split_examples(rows)
        tasks.append(CodeWorldTask(f"s{seed}-ood-neg", "def solve(x):\n    return -x\n", pub, ch, fin, "unavailable"))
    return tasks


def summarize_results(rows: list[CodeWorldResult]) -> dict[str, object]:
    if not rows:
        return {}
    predictions = [r for r in rows if r.predicted_family is not None]
    return {
        "tasks": len(rows),
        "solved": sum(r.solved for r in rows),
        "final_correct": sum(r.final_correct for r in rows),
        "mean_attempts": mean(r.attempts for r in rows),
        "mean_family_attempts": mean(r.family_attempts for r in rows),
        "predictions": len(predictions),
        "prediction_precision": (sum(bool(r.predicted_family_correct) for r in predictions) / len(predictions)) if predictions else None,
        "abstentions": sum(r.predicted_family is None for r in rows),
        "false_skill_predictions": sum(r.predicted_family_correct is False for r in rows),
    }


def global_family_order(training_tasks: Iterable[CodeWorldTask]) -> list[str]:
    return _global_family_order(training_tasks)
