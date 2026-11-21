"""NOMAD v0.10 GENESIS: bounded, typed, evidence-guided AST synthesis.

Research scope: single-return, integer-valued Python functions of (x, y).
This is a finite expression synthesizer, NOT an unrestricted coding agent.
The synthesis policy sees source and *public* examples only. WITNESS and
final examples are held by the evaluation caller, outside the search loop.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .bitstate import encode_failure
from .model import CodeTask, Example
from .learner import ContextualOperatorLearner
from .python_operators import generate_python_candidates
from .witness import Witness, WitnessReceipt


@dataclass(frozen=True)
class IOExample:
    x: int
    y: int
    expected: int


@dataclass(frozen=True)
class SynthesisTask:
    task_id: str
    source: str
    public: tuple[IOExample, ...]
    challenge: tuple[IOExample, ...]
    final: tuple[IOExample, ...]
    # Evaluator metadata only. NEVER passed to the synthesis function.
    hidden_family: str = "unknown"


@dataclass(frozen=True)
class Program:
    text: str
    values: tuple[int, ...]
    cost: int
    op: str


@dataclass(frozen=True)
class SynthesisRun:
    candidate: str | None
    candidates_evaluated: int
    observational_classes: int
    counterexamples: int
    public_correct: bool
    abstained: str | None
    source_context: int


def _extract_expression(source: str) -> str:
    tree = ast.parse(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("GENESIS requires one def solve(x,y)")
    fn = tree.body[0]
    if fn.name != "solve" or [a.arg for a in fn.args.args] != ["x", "y"]:
        raise ValueError("GENESIS requires def solve(x, y)")
    if len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return) or fn.body[0].value is None:
        raise ValueError("GENESIS accepts a single expression return")
    # Reject arbitrary syntax from the source program, even if the expression
    # is well formed; never execute untrusted source inside synthesis.
    from .safe_eval import parse_expr
    expr = ast.unparse(fn.body[0].value)
    parse_expr(expr)
    return expr


def _render(expr: str) -> str:
    from .safe_eval import parse_expr
    parsed = parse_expr(expr)
    if any(isinstance(n, ast.FloorDiv) for n in ast.walk(parsed)):
        raise ValueError("GENESIS grammar excludes division")
    return f"def solve(x, y):\n    return {expr}\n"


def _signature(task: SynthesisTask) -> int:
    expr = _extract_expression(task.source)
    code_task = CodeTask(
        task_id=task.task_id, source=expr,
        examples=[Example({"x": e.x, "y": e.y}, e.expected) for e in task.public],
    )
    return encode_failure(code_task).bits


def _eval_expr(expr: str, examples: Iterable[IOExample]) -> tuple[int, ...]:
    # This is the existing Bitwork safe arithmetic interpreter. It rejects
    # calls, attributes, comprehensions, imports, and arbitrary statements.
    from .safe_eval import evaluate
    return tuple(int(evaluate(expr, {"x": e.x, "y": e.y})) for e in examples)


def _eval_v9_source(source: str, examples: tuple[IOExample, ...]) -> tuple[int, ...] | None:
    try:
        expr = _extract_expression(source)
        return _eval_expr(expr, examples)
    except (ValueError, SyntaxError, ZeroDivisionError, NameError, KeyError, OverflowError):
        return None


def fixed_v9_reachable(task: SynthesisTask, *, all_splits: bool = False) -> tuple[bool, int]:
    """Exhaust the unchanged v0.9 one-edit candidate vocabulary.

    Compare against public only by default. Full-split reachability is an
    *evaluator-only* property never used by synthesis or ranking.
    """
    rows = task.public + task.challenge + task.final if all_splits else task.public
    goal = tuple(e.expected for e in rows)
    candidates = [task.source]
    for group in generate_python_candidates(task.source).values():
        candidates.extend(c.source for c in group)
    return any(_eval_v9_source(src, rows) == goal for src in candidates), len(candidates)


class GrammarPrior:
    """Bitwork-contextual production preference trained on witnessed programs.

    This is not an invented unrestricted grammar. The productions themselves
    are fixed; experience may change their order but cannot certify outcomes.

    Balance (unlearning): each witnessed program may also carry a task family
    (the proposer's domain). ``order(context, family=...)`` then uses only
    that family's evidence, and a family with no witnessed evidence keeps the
    cold default order, so a multiply-heavy field cannot slow a subtract task
    below the control. ``family=None`` keeps the old global/contextual order,
    which is what the never-trained held-out family uses. ``decay(gamma)``
    shrinks every count so old wins fade unless re-earned.
    """
    NAMES = ("Add", "Sub", "Mult")

    def __init__(self, *, contextual: bool = True) -> None:
        self.operator = ContextualOperatorLearner(contextual=contextual)
        self.witnessed = 0
        self.contextual = contextual
        self.families: dict[str, dict[str, list[float]]] = {}

    def add_witnessed(self, context: int, expr: str, receipt: WitnessReceipt,
                      family: str | None = None) -> None:
        if not receipt.supported or not receipt.verify_checksum():
            raise ValueError("Cannot learn from an unverified or failed WITNESS receipt")
        # INTEGRITY (docs/INTEGRITY.md): the receipt admits only the exact candidate it attests
        # (_witness stamps transmission_id = sha256 of the rendered solution source).
        if getattr(receipt, "transmission_id", None) != hashlib.sha256(_render(expr).encode()).hexdigest():
            from .witness import ReceiptMismatch
            raise ReceiptMismatch("submitted candidate does not match the receipt's program hash")
        tree = ast.parse(expr, mode="eval")
        if not isinstance(tree.body, ast.BinOp):
            return
        root = type(tree.body.op).__name__
        for op in self.NAMES:
            self.operator.update(context, op, root == op)
        if family:
            fam = self.families.setdefault(family, {op: [0.0, 0.0] for op in self.NAMES})
            for op in self.NAMES:
                fam.setdefault(op, [0.0, 0.0])[0 if root == op else 1] += 1.0
        self.witnessed += 1

    def decay(self, gamma: float) -> None:
        """Multiply every count by gamma (0 < gamma <= 1). Witnessed count is history and is kept."""
        if not 0.0 < gamma <= 1.0:
            raise ValueError("gamma must be in (0, 1]")
        for counts in list(self.operator.global_counts.values()) + list(self.operator.context_counts.values()):
            counts.success *= gamma
            counts.failure *= gamma
        for fam in self.families.values():
            for pair in fam.values():
                pair[0] *= gamma
                pair[1] *= gamma

    def family_evidence(self, family: str) -> float:
        fam = self.families.get(family) or {}
        return sum(s + f for s, f in fam.values()) / max(1, len(self.NAMES))

    def order(self, context: int, family: str | None = None) -> tuple[str, ...]:
        names = self.NAMES
        if self.witnessed == 0:
            return names
        if family is not None:
            fam = self.families.get(family)
            if not fam or self.family_evidence(family) <= 0:
                return names
            def fscore(op: str) -> float:
                s, f = fam.get(op, [0.0, 0.0])
                return (s + 1.0) / (s + f + 2.0)
            return tuple(sorted(names, key=lambda op: (-fscore(op), names.index(op))))
        return tuple(sorted(names, key=lambda op: (-self.operator.score(context, op), names.index(op))))

    def snapshot(self) -> dict:
        snap = {"schema": "nomad.v0.10.grammar-prior.v1", "witnessed": self.witnessed,
                "contextual": self.contextual, "operator": self.operator.snapshot()}
        if self.families:
            snap["families"] = {k: {op: list(v) for op, v in fam.items()} for k, fam in sorted(self.families.items())}
        return snap


_OPERATOR = {"Add": "+", "Sub": "-", "Mult": "*"}


def _combine(a: Program, b: Program, op: str, *, max_abs: int) -> Program | None:
    if op in ("Add", "Mult") and a.text > b.text:
        return None
    if op == "Add":
        v = tuple(x+y for x,y in zip(a.values,b.values))
    elif op == "Sub":
        v = tuple(x-y for x,y in zip(a.values,b.values))
    else:
        v = tuple(x*y for x,y in zip(a.values,b.values))
    if any(abs(x) > max_abs for x in v):
        return None
    return Program(f"({a.text}{_OPERATOR[op]}{b.text})", v, a.cost+b.cost+1, op)


def _enumerate(
    rows: tuple[IOExample, ...], *,
    root_order: tuple[str, ...], max_nodes: int, max_eval: int,
    max_abs: int = 50000,
) -> tuple[Program | None, int, int]:
    """Bottom-up typed expression synthesis with observational dedup.

    Metric counts every candidate vector actually computed, including aliases.
    Each expression is evaluated only on the caller-visible rows. A bounded
    frontier and exact integer arithmetic prevent accidental overflow/DoS.
    """
    goal = tuple(e.expected for e in rows)
    pools: dict[int, dict[tuple[int,...], Program]] = {}
    budget = 0
    classes = 0
    atom = [("x",tuple(e.x for e in rows)),("y",tuple(e.y for e in rows))]
    atom += [(str(k),tuple(k for _ in rows)) for k in (0,1,2,3)]
    pools[1] = {}
    for text, vals in atom:
        if budget >= max_eval:
            return None, budget, classes
        budget += 1
        if vals not in pools[1]:
            p = Program(text, vals, 1, "atom")
            pools[1][vals] = p
            classes += 1
            if vals == goal:
                return p, budget, classes
    if budget >= max_eval:
        return None,budget,classes
    for size in range(3, max_nodes+1, 2):
        pool: dict[tuple[int,...],Program] = {}
        pools[size] = pool
        # Critical: learned operator priors affect the execution order, but not
        # available programs. Any OOD success is still independently witnessed.
        for op in root_order:
            for left_size in range(1,size-1,2):
                right_size = size-1-left_size
                for left in pools[left_size].values():
                    for right in pools[right_size].values():
                        if budget >= max_eval:
                            return None,budget,classes
                        cand = _combine(left,right,op,max_abs=max_abs)
                        if cand is None:
                            continue
                        budget += 1
                        if cand.values in pool:
                            continue
                        pool[cand.values] = cand
                        classes += 1
                        if cand.values == goal:
                            return cand,budget,classes
    return None,budget,classes


def synthesize(
    task: SynthesisTask, *, prior: GrammarPrior | None = None,
    max_nodes: int = 7, max_eval: int = 65000, max_counterexamples: int = 6,
    family: str | None = None,
) -> SynthesisRun:
    """Search sees public examples only; hidden splits remain inaccessible.

    Counterexamples come from additional *public* rows. The WITNESS challenge
    is never fed back as a counterexample to the synthesizer.
    """
    if not task.public or max_nodes < 1 or max_eval <= 0:
        return SynthesisRun(None,0,0,0,False,"invalid_budget_or_examples",0)
    context = _signature(task)
    if prior is None:
        root_order = ("Add","Sub","Mult")
    elif family is not None:
        root_order = prior.order(context, family=family)
    else:
        root_order = prior.order(context)
    active = [0,1,2] if len(task.public) >= 3 else list(range(len(task.public)))
    consumed = 0
    classes = 0
    counterexamples = 0
    while True:
        left = max_eval - consumed
        if left <= 0:
            return SynthesisRun(None,consumed,classes,counterexamples,False,"candidate_budget",context)
        rows = tuple(task.public[i] for i in active)
        program, used, unique = _enumerate(rows,root_order=root_order,
                                           max_nodes=max_nodes,max_eval=left)
        consumed += used
        classes += unique
        if program is None:
            return SynthesisRun(None,consumed,classes,counterexamples,False,"frontier_or_candidate_budget",context)
        # No hidden split is used to accept/reject candidate during synthesis.
        all_visible = _eval_expr(program.text, task.public)
        mismatches = [i for i, (got, row) in enumerate(zip(all_visible,task.public)) if got!=row.expected and i not in active]
        if not mismatches:
            if all(got == ex.expected for got,ex in zip(all_visible,task.public)):
                return SynthesisRun(program.text,consumed,classes,counterexamples,True,None,context)
            return SynthesisRun(None,consumed,classes,counterexamples,False,"inconsistent_public",context)
        if counterexamples >= max_counterexamples:
            return SynthesisRun(None,consumed,classes,counterexamples,False,"counterexample_budget",context)
        active.append(mismatches[0])
        counterexamples += 1


def _test_text(rows: tuple[IOExample,...]) -> str:
    content=["import unittest","from solution import solve","","class VisibleTests(unittest.TestCase):"]
    for i,e in enumerate(rows):
        content.append(f"    def test_{i:03d}(self):")
        content.append(f"        self.assertEqual(solve({e.x!r}, {e.y!r}), {e.expected!r})")
    content.extend(["","if __name__ == '__main__': unittest.main()",""])
    return "\n".join(content)


def materialize(task: SynthesisTask, root: Path) -> None:
    root.mkdir(parents=True,exist_ok=True)
    (root/'tests').mkdir(exist_ok=True)
    (root/'solution.py').write_text(task.source,encoding='utf8')
    (root/'tests'/'test_public.py').write_text(_test_text(task.public),encoding='utf8')


def _witness(task:SynthesisTask,source:str) -> WitnessReceipt:
    src=_extract_expression(task.source)
    cand=_extract_expression(source)
    witness=Witness(witness_id='nomad-witness-v010-genesis')
    def values(expr,rows):
        return tuple(float(v) for v in _eval_expr(expr,rows))
    return witness.attest(task_id=task.task_id,transmission_id=hashlib.sha256(source.encode()).hexdigest(),
        world_epoch=0,current_public=values(src,task.public),
        target_public=tuple(float(e.expected) for e in task.public),
        candidate_public=values(cand,task.public),
        current_challenge=values(src,task.challenge),
        target_challenge=tuple(float(e.expected) for e in task.challenge),
        candidate_challenge=values(cand,task.challenge))


@dataclass(frozen=True)
class Evaluation:
    task_id: str
    family: str
    synthesized: bool
    public_tests: bool
    witness_supported: bool
    final_correct: bool
    v9_reachable: bool
    v9_candidate_count: int
    candidate_evaluations: int
    counterexamples: int
    learned_context: int
    candidate: str | None
    abstained: str | None


def evaluate_task(task:SynthesisTask, *, prior:GrammarPrior|None=None,
                  max_nodes:int=7,max_eval:int=65000, actual_tests:bool=False,
                  family:str|None=None) -> tuple[Evaluation, WitnessReceipt|None]:
    search=synthesize(task,prior=prior,max_nodes=max_nodes,max_eval=max_eval,family=family)
    reachable, count=fixed_v9_reachable(task)
    if search.candidate is None:
        return Evaluation(task.task_id,task.hidden_family,False,False,False,False,reachable,count,
                          search.candidates_evaluated,search.counterexamples,search.source_context,None,search.abstained),None
    source=_render(search.candidate)
    # WITNESS and the independent final split are used *only after* search has
    # selected one candidate. No false certificate is promoted.
    with tempfile.TemporaryDirectory(prefix='nomad-genesis-') as td:
        root=Path(td)
        materialize(task,root)
        (root/'solution.py').write_text(source,encoding='utf8')
        test_passed=True
        if actual_tests:
            p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],
                cwd=root,capture_output=True,text=True,timeout=10)
            test_passed=p.returncode==0
        if not test_passed:
            return Evaluation(task.task_id,task.hidden_family,True,False,False,False,reachable,count,
                   search.candidates_evaluated,search.counterexamples,search.source_context,search.candidate,'public_unittest_failed'),None
        receipt=_witness(task,source)
        correct=_eval_expr(search.candidate,task.final)==tuple(e.expected for e in task.final)
        return Evaluation(task.task_id,task.hidden_family,True,True,receipt.supported,correct,reachable,count,
             search.candidates_evaluated,search.counterexamples,search.source_context,
             search.candidate,None if receipt.supported and correct else 'withheld_rejected'),receipt


def train_prior(tasks:Iterable[SynthesisTask], *, max_nodes:int=7, max_eval:int=65000,
                contextual:bool=True) -> tuple[GrammarPrior,dict]:
    prior=GrammarPrior(contextual=contextual)
    attempted=0
    accepted=0
    for task in tasks:
        attempted+=1
        evaluated,receipt=evaluate_task(task,max_nodes=max_nodes,max_eval=max_eval,actual_tests=False)
        if evaluated.witness_supported and evaluated.final_correct and receipt is not None:
            prior.add_witnessed(evaluated.learned_context,evaluated.candidate or '',receipt)
            accepted+=1
    return prior,{'attempted':attempted,'verified_skills':accepted}


def prior_from_snapshot(snap: dict) -> GrammarPrior:
    """Restore a GrammarPrior from a snapshot, including older continuous files.

    Older continuous priors stored operator counts at the top level and omitted
    `witnessed`. Those load with witnessed=0 so order stays default until a
    WITNESS-backed success is recorded.
    """
    prior = GrammarPrior(contextual=bool(snap.get("contextual", True)))
    prior.witnessed = int(snap.get("witnessed", 0))
    op_snap = snap.get("operator", snap)
    prior.operator.contextual = bool(op_snap.get("contextual", prior.contextual))
    from .learner import Counts
    for fam, counts in (op_snap.get("global") or {}).items():
        prior.operator.global_counts[fam] = Counts(**counts)
    for key, counts in (op_snap.get("contexts") or {}).items():
        if ":" not in key:
            continue
        sig_s, fam = key.split(":", 1)
        try:
            sig = int(sig_s)
        except ValueError:
            continue
        prior.operator.context_counts[(sig, fam)] = Counts(**counts)
    for family, ops in (snap.get("families") or {}).items():
        prior.families[family] = {op: [float(v[0]), float(v[1])] for op, v in ops.items()}
    return prior


def load_prior_file(path: Path) -> GrammarPrior:
    if not path.exists():
        return GrammarPrior()
    return prior_from_snapshot(json.loads(path.read_text()))


def save_prior_file(prior: GrammarPrior, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prior.snapshot(), indent=2))
