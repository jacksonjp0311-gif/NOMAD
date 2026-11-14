from __future__ import annotations

import ast
import importlib
import math
import random
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from statistics import mean
from typing import Iterable

from .python_operators import PY_FAMILIES, generate_python_candidates
from .witness import Witness


@dataclass(frozen=True)
class RepoExample:
    inputs: dict[str, int]
    expected: int | bool


@dataclass(frozen=True)
class RepoTask:
    task_id: str
    files: dict[str, str]
    entry_module: str
    public: tuple[RepoExample, ...]
    challenge: tuple[RepoExample, ...]
    final: tuple[RepoExample, ...]
    true_bug_file: str  # evaluator metadata only
    true_family: str    # evaluator metadata only


@dataclass(frozen=True)
class RepoRepairResult:
    task_id: str
    solved: bool
    final_correct: bool
    attempts: int
    file_visits: int
    chosen_file: str | None
    predicted_file: str | None
    localization_correct: bool | None
    witness_supported: bool
    public_tests_passed: bool


_ERROR_CODES = {
    "SyntaxError": 2001.0,
    "NameError": 2002.0,
    "ZeroDivisionError": 2003.0,
    "ImportError": 2004.0,
    "ModuleNotFoundError": 2005.0,
    "AttributeError": 2006.0,
    "MissingSolve": 2007.0,
}


def _expected(examples: tuple[RepoExample, ...]) -> tuple[float, ...]:
    return tuple(float(e.expected) for e in examples)


def _clear_local_modules(root: Path) -> None:
    stems = {p.stem for p in root.glob("*.py")}
    for name in list(sys.modules):
        if name.split(".")[0] in stems:
            sys.modules.pop(name, None)
    # Candidate files are rewritten many times within a single filesystem timestamp
    # tick. Remove bytecode caches so import never reuses stale pre-edit code.
    cache = root / "__pycache__"
    if cache.exists():
        for pyc in cache.glob("*.pyc"):
            try:
                pyc.unlink()
            except OSError:
                pass


def run_repo(root: Path, entry_module: str, examples: tuple[RepoExample, ...]) -> tuple[tuple[float, ...] | None, str | None]:
    _clear_local_modules(root)
    sys.path.insert(0, str(root))
    try:
        importlib.invalidate_caches()
        mod = importlib.import_module(entry_module)
        solve = getattr(mod, "solve", None)
        if not callable(solve):
            return None, "MissingSolve"
        out: list[float] = []
        for ex in examples:
            try:
                out.append(float(solve(**ex.inputs)))
            except Exception as exc:  # observable runtime consequence
                return None, type(exc).__name__
        return tuple(out), None
    except Exception as exc:
        return None, type(exc).__name__
    finally:
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass
        _clear_local_modules(root)


def evidence(root: Path, task: RepoTask, examples: tuple[RepoExample, ...]) -> tuple[float, ...]:
    vals, err = run_repo(root, task.entry_module, examples)
    if err is None and vals is not None:
        return vals
    code = _ERROR_CODES.get(str(err), 2099.0)
    return tuple(code for _ in examples)


def _public_test_text(task: RepoTask) -> str:
    rows = [
        "import unittest",
        f"from {task.entry_module} import solve",
        "",
        "class RepositoryTests(unittest.TestCase):",
    ]
    for idx, ex in enumerate(task.public):
        args = ", ".join(f"{k}={v!r}" for k, v in ex.inputs.items())
        rows += [f"    def test_{idx:02d}(self):", f"        self.assertEqual(solve({args}), {ex.expected!r})"]
    rows += ["", "if __name__ == '__main__':", "    unittest.main()", ""]
    return "\n".join(rows)


def materialize(task: RepoTask, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)
    for filename, source in task.files.items():
        (root / filename).write_text(source, encoding="utf-8")
    (root / "tests" / "test_public.py").write_text(_public_test_text(task), encoding="utf-8")
    (root / "README.md").write_text(
        "# NOMAD WORLD MODEL fixture\n\nRepair the repository. The failing file is not disclosed.\n",
        encoding="utf-8",
    )


def run_public_tests(root: Path) -> bool:
    p = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    return p.returncode == 0


def _local_imports(source: str, local_stems: set[str]) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in local_stems:
                    out.add(top)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in local_stems:
                out.add(top)
    return out


def build_graph(task: RepoTask) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, int]]:
    by_stem = {Path(name).stem: name for name in task.files}
    stems = set(by_stem)
    edges: dict[str, set[str]] = {name: set() for name in task.files}
    reverse: dict[str, set[str]] = {name: set() for name in task.files}
    for filename, source in task.files.items():
        for dep_stem in _local_imports(source, stems):
            dep = by_stem[dep_stem]
            edges[filename].add(dep)
            reverse[dep].add(filename)
    entry_file = by_stem[task.entry_module]
    distance = {name: 999 for name in task.files}
    distance[entry_file] = 0
    frontier = [entry_file]
    while frontier:
        cur = frontier.pop(0)
        for dep in edges[cur]:
            if distance[dep] > distance[cur] + 1:
                distance[dep] = distance[cur] + 1
                frontier.append(dep)
    return edges, reverse, distance


def _ast_tokens(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"parse_error"}
    t: set[str] = {"parse_ok"}
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if funcs:
        t.add("has_function")
    if any(isinstance(n, (ast.Assign, ast.AnnAssign)) for n in tree.body):
        t.add("has_module_assignment")
    if any(isinstance(n, ast.BinOp) for n in ast.walk(tree)):
        t.add("has_binop")
    if any(isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) for n in ast.walk(tree)):
        t.add("has_negate")
    if any(isinstance(n, ast.Compare) for n in ast.walk(tree)):
        t.add("has_compare")
    families = generate_python_candidates(source)
    for fam, rows in families.items():
        if rows:
            t.add(f"candidate_{fam}")
    return t


def _failure_tokens(root: Path, task: RepoTask) -> set[str]:
    vals, err = run_repo(root, task.entry_module, task.public)
    target = _expected(task.public)
    if err is not None or vals is None:
        return {"runtime_error", f"runtime_{err}"}
    diffs = [v - t for v, t in zip(vals, target)]
    nz = [d for d in diffs if abs(d) > 1e-9]
    out = {"runtime_ok", "numeric_failure"}
    if not nz:
        return out | {"no_public_failure"}
    if all(d > 0 for d in nz):
        out.add("error_above")
    elif all(d < 0 for d in nz):
        out.add("error_below")
    else:
        out.add("error_mixed")
    if max(nz) - min(nz) < 1e-9:
        out.add("error_constant")
        mag = abs(nz[0])
        if abs(mag - 1.0) < 1e-9:
            out.add("error_constant_mag1")
        elif abs(mag - 2.0) < 1e-9:
            out.add("error_constant_mag2")
        else:
            out.add("error_constant_other")
    else:
        out.add("error_variable")
    return out


def file_signature(root: Path, task: RepoTask, filename: str, *, include_failure: bool) -> frozenset[str]:
    edges, reverse, distance = build_graph(task)
    source = (root / filename).read_text(encoding="utf-8")
    tokens = _ast_tokens(source)
    d = distance.get(filename, 999)
    tokens.add("reachable" if d < 999 else "unreachable")
    tokens.add(f"distance_{d if d < 4 else '4plus'}")
    tokens.add(f"outdegree_{min(len(edges[filename]), 3)}")
    tokens.add(f"indegree_{min(len(reverse[filename]), 3)}")
    if include_failure:
        tokens |= _failure_tokens(root, task)
    return frozenset(tokens)




def _model_features(signature: Iterable[str], *, include_failure: bool) -> set[str]:
    base = set(signature)
    if not include_failure:
        return base
    failures = sorted(t for t in base if t.startswith("error_") or t.startswith("runtime_"))
    structural = sorted(t for t in base if t.startswith(("distance_", "candidate_", "has_", "outdegree_", "indegree_")) or t in {"reachable", "unreachable"})
    distances = sorted(t for t in structural if t.startswith("distance_"))
    candidates = sorted(t for t in structural if t.startswith("candidate_"))
    expanded = set(base)
    for f in failures:
        for st in structural:
            expanded.add(f"pair:{f}|{st}")
        for d in distances:
            for c in candidates:
                expanded.add(f"triple:{f}|{d}|{c}")
    return expanded


class RepositoryWorldModel:
    """Learn where verified repairs live from graph + failure evidence.

    Filenames are never features.  We learn additive log-odds for observable
    graph/AST/failure tokens, with Laplace smoothing.  Static mode omits failure
    evidence and serves as the global-structure control.
    """

    def __init__(self, *, include_failure: bool = True) -> None:
        self.include_failure = bool(include_failure)
        self.pos: dict[str, int] = {}
        self.neg: dict[str, int] = {}
        self.observations = 0

    def observe(self, signature: Iterable[str], repaired_here: bool) -> None:
        target = self.pos if repaired_here else self.neg
        for token in _model_features(signature, include_failure=self.include_failure):
            target[token] = target.get(token, 0) + 1
        self.observations += 1

    def score(self, signature: Iterable[str]) -> float:
        score = 0.0
        for token in _model_features(signature, include_failure=self.include_failure):
            p = self.pos.get(token, 0)
            n = self.neg.get(token, 0)
            score += math.log((p + 1.0) / (n + 1.0))
        return score

    def rank(self, root: Path, task: RepoTask, files: Iterable[str]) -> list[str]:
        scored = []
        for filename in files:
            sig = file_signature(root, task, filename, include_failure=self.include_failure)
            scored.append((self.score(sig), filename))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [f for _, f in scored]

    def snapshot(self) -> dict[str, object]:
        return {
            "schema": "nomad.v0.8.repository-world-model.v1",
            "include_failure": self.include_failure,
            "observations": self.observations,
            "positive_tokens": dict(sorted(self.pos.items())),
            "negative_tokens": dict(sorted(self.neg.items())),
        }


def candidate_files(task: RepoTask) -> list[str]:
    out = []
    for filename, source in task.files.items():
        groups = generate_python_candidates(source)
        if any(groups[f] for f in PY_FAMILIES):
            out.append(filename)
    return sorted(out)


def _candidate_rows(source: str):
    groups = generate_python_candidates(source)
    for family in PY_FAMILIES:
        yield from groups[family]


def _attest_candidate(witness: Witness, root: Path, task: RepoTask, filename: str, attempt: int):
    current_public = getattr(task, "_baseline_public", None)
    # Task dataclasses are frozen; recompute from a pristine materialization held
    # by the caller before each candidate search instead of caching on the task.
    candidate_public = evidence(root, task, task.public)
    candidate_challenge = evidence(root, task, task.challenge)
    transmission_id = sha256(f"{task.task_id}|{filename}|{attempt}|{candidate_public}".encode()).hexdigest()[:24]
    return transmission_id, candidate_public, candidate_challenge


def solve_repository(
    task: RepoTask,
    *,
    world_model: RepositoryWorldModel | None = None,
    static_model: RepositoryWorldModel | None = None,
    verify_repo_tests: bool = False,
    max_attempts: int = 80,
    file_order: Iterable[str] | None = None,
) -> RepoRepairResult:
    witness = Witness("nomad-witness-v0.8-world-model")
    with tempfile.TemporaryDirectory(prefix="nomad-world-") as td:
        root = Path(td)
        materialize(task, root)
        files = candidate_files(task)
        if world_model is not None:
            order = world_model.rank(root, task, files)
        elif static_model is not None:
            order = static_model.rank(root, task, files)
        else:
            order = files
        if file_order is not None:
            proposed = list(file_order)
            if len(proposed) != len(files) or set(proposed) != set(files) or len(set(proposed)) != len(files):
                raise ValueError("file_order must be a permutation of eligible repository files")
            order = proposed
        predicted = order[0] if order else None
        baseline_public = evidence(root, task, task.public)
        baseline_challenge = evidence(root, task, task.challenge)
        attempts = 0
        visits = 0
        originals = {f: (root / f).read_text(encoding="utf-8") for f in files}
        for filename in order:
            visits += 1
            original = originals[filename]
            for cand in _candidate_rows(original):
                if attempts >= max_attempts:
                    return RepoRepairResult(task.task_id, False, False, attempts, visits, None, predicted,
                                            None if predicted is None else predicted == task.true_bug_file,
                                            False, False)
                attempts += 1
                (root / filename).write_text(cand.source, encoding="utf-8")
                public = evidence(root, task, task.public)
                if public != _expected(task.public):
                    (root / filename).write_text(original, encoding="utf-8")
                    continue
                tests_ok = True
                if verify_repo_tests:
                    tests_ok = run_public_tests(root)
                    if not tests_ok:
                        (root / filename).write_text(original, encoding="utf-8")
                        continue
                challenge = evidence(root, task, task.challenge)
                transmission_id = sha256(f"{task.task_id}|{filename}|{attempts}|{cand.source}".encode()).hexdigest()[:24]
                receipt = witness.attest(
                    task_id=task.task_id,
                    transmission_id=transmission_id,
                    world_epoch=0,
                    current_public=baseline_public,
                    target_public=_expected(task.public),
                    candidate_public=public,
                    current_challenge=baseline_challenge,
                    target_challenge=_expected(task.challenge),
                    candidate_challenge=challenge,
                )
                if not witness.authorize(receipt, task_id=task.task_id, transmission_id=transmission_id, world_epoch=0):
                    (root / filename).write_text(original, encoding="utf-8")
                    continue
                final = evidence(root, task, task.final)
                final_correct = final == _expected(task.final)
                return RepoRepairResult(task.task_id, True, final_correct, attempts, visits, filename, predicted,
                                        None if predicted is None else predicted == task.true_bug_file,
                                        True, tests_ok)
            (root / filename).write_text(original, encoding="utf-8")
        return RepoRepairResult(task.task_id, False, False, attempts, visits, None, predicted,
                                None if predicted is None else predicted == task.true_bug_file,
                                False, False)


def train_world_models(tasks: Iterable[RepoTask]) -> tuple[RepositoryWorldModel, RepositoryWorldModel, dict[str, int]]:
    full = RepositoryWorldModel(include_failure=True)
    static = RepositoryWorldModel(include_failure=False)
    repair_counts: dict[str, int] = {}
    for task in tasks:
        # Establish the repair location through actual WITNESS-supported flat search.
        result = solve_repository(task)
        if not (result.solved and result.final_correct and result.chosen_file):
            continue
        with tempfile.TemporaryDirectory(prefix="nomad-world-train-") as td:
            root = Path(td)
            materialize(task, root)
            for filename in candidate_files(task):
                positive = filename == result.chosen_file
                full.observe(file_signature(root, task, filename, include_failure=True), positive)
                static.observe(file_signature(root, task, filename, include_failure=False), positive)
            # Role-free global control: only count graph distance of verified locations.
            _, _, dist = build_graph(task)
            key = f"distance_{dist[result.chosen_file] if dist[result.chosen_file] < 4 else '4plus'}"
            repair_counts[key] = repair_counts.get(key, 0) + 1
    return full, static, repair_counts


def summarize(rows: list[RepoRepairResult]) -> dict[str, object]:
    preds = [r for r in rows if r.predicted_file is not None]
    return {
        "tasks": len(rows),
        "solved": sum(r.solved for r in rows),
        "final_correct": sum(r.final_correct for r in rows),
        "mean_attempts": mean(r.attempts for r in rows) if rows else 0.0,
        "mean_file_visits": mean(r.file_visits for r in rows) if rows else 0.0,
        "localization_predictions": len(preds),
        "localization_correct": sum(bool(r.localization_correct) for r in preds),
        "localization_accuracy": sum(bool(r.localization_correct) for r in preds) / len(preds) if preds else None,
    }


def _names(seed: int, count: int = 6) -> list[str]:
    rng = random.Random(seed)
    alphabet = [f"m{seed % 997}_{c}" for c in "abcdefghijklmno"]
    rng.shuffle(alphabet)
    return alphabet[:count]


def make_repository_tasks(seed: int, *, per_kind: int = 3) -> list[RepoTask]:
    tasks: list[RepoTask] = []
    for i in range(per_kind):
        base = 3 + ((seed + i) % 5)
        for kind_idx, kind in enumerate(("core_binary", "middle_constant", "entry_syntax", "config_constant")):
            names = _names(seed * 100 + i * 11 + kind_idx)
            entry, middle, core, config, extra1, extra2 = names
            files: dict[str, str] = {}
            core_expr = "x + y"
            middle_tail = " + OFFSET"
            offset = 0
            entry_expr = "work(x, y)"
            true_family = "binary_operator"
            bug_stem = core
            if kind == "core_binary":
                core_expr = "x + y"
                target = lambda x, y: x * y
                true_family = "binary_operator"
                bug_stem = core
            elif kind == "middle_constant":
                middle_tail = " + 1"
                target = lambda x, y: x + y + 3
                true_family = "constant"
                bug_stem = middle
            elif kind == "entry_syntax":
                entry_expr = "work(x, y)"
                target = lambda x, y: x + y
                true_family = "syntax"
                bug_stem = entry
            else:
                offset = 1
                target = lambda x, y: x + y + 2
                true_family = "constant"
                bug_stem = config

            files[f"{core}.py"] = f"def core(x, y):\n    return {core_expr}\n"
            files[f"{config}.py"] = f"OFFSET = {offset}\n"
            if kind == "middle_constant":
                files[f"{middle}.py"] = f"from {core} import core\n\ndef work(x, y):\n    return core(x, y){middle_tail}\n"
            else:
                files[f"{middle}.py"] = f"from {core} import core\nfrom {config} import OFFSET\n\ndef work(x, y):\n    return core(x, y) + OFFSET\n"
            files[f"{entry}.py"] = (
                f"def solve(x, y)\n    from {middle} import work\n    return {entry_expr}\n"
                if kind == "entry_syntax"
                else f"from {middle} import work\n\ndef solve(x, y):\n    return {entry_expr}\n"
            )
            # Candidate-rich distractors, disconnected from the tested entry path.
            files[f"{extra1}.py"] = "def helper(x, y):\n    return x + y + 1\n"
            files[f"{extra2}.py"] = "def spare(x):\n    return -x\n"

            rows = []
            for j in range(10):
                x = base + j
                y = 2 + (j % 3)
                rows.append(RepoExample({"x": x, "y": y}, target(x, y)))
            pub, ch, fin = tuple(rows[:4]), tuple(rows[4:7]), tuple(rows[7:10])
            tasks.append(RepoTask(
                task_id=f"s{seed}-{kind}-{i}",
                files=files,
                entry_module=entry,
                public=pub,
                challenge=ch,
                final=fin,
                true_bug_file=f"{bug_stem}.py",
                true_family=true_family,
            ))
    return tasks
