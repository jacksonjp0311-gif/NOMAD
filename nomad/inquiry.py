"""NOMAD v0.9 INQUIRY: budgeted, consequence-grounded active diagnosis.

Experiment contract:
* Every probe is an executable public module contract with a predeclared cost.
* The policy receives probe identifiers, roles, and costs; only the executor sees
  contract expectations, and the policy only receives pass/fail observations.
* Training fault labels come from v0.8's WITNESS-verified repairs, NEVER from
  evaluator-provided true_bug_file or true_family metadata.
* Only the same pretrained world model and learned likelihood table can inform
  query selection; challenge and final observations are never passed to it.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import math
import random
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping

from .python_operators import generate_python_candidates
from .repo_world import (
    RepoTask, RepoRepairResult, RepositoryWorldModel, build_graph,
    candidate_files, file_signature, make_repository_tasks, materialize,
    solve_repository, train_world_models, _clear_local_modules,
)

PROBE_COSTS = {"core": 0.24, "config": 0.20, "middle": 0.34, "entry": 0.50}
EPS = 1e-12


@dataclass(frozen=True)
class ProbeContract:
    probe_id: str
    role: str
    module: str
    symbol: str
    kwargs: tuple[tuple[str, int], ...]
    expected: float
    cost: float


@dataclass(frozen=True)
class ProbeMenu:
    probe_id: str
    role: str
    cost: float


@dataclass(frozen=True)
class InquiryTask:
    repo: RepoTask
    contracts: tuple[ProbeContract, ...]

    def menu(self) -> tuple[ProbeMenu, ...]:
        return tuple(ProbeMenu(p.probe_id, p.role, p.cost) for p in self.contracts)


@dataclass(frozen=True)
class ProbeReceipt:
    schema: str
    task_id: str
    probe_id: str
    snapshot_digest: str
    observation: str
    passed: bool
    exception: str | None
    cost: float
    record_digest: str

    def verify(self, snapshot_digest: str) -> bool:
        if self.snapshot_digest != snapshot_digest:
            return False
        fields = self.__dict__.copy()
        digest = fields.pop("record_digest")
        return _digest(fields) == digest


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def repo_snapshot(root: Path, task: RepoTask) -> str:
    """Snapshot only submitted source files, not mutable generated Python caches."""
    return _digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sorted(task.files)})


def _roles(task: RepoTask) -> dict[str, str]:
    """Identify an adapter's *observable* API roles, never the evaluator's fault label.

    These roles intentionally depend on the supplied `core/work/OFFSET/solve`
    interface. Unknown real-world repositories require a new adapter.
    """
    out: dict[str, str] = {}
    for name, src in task.files.items():
        if Path(name).stem == task.entry_module:
            out[name] = "entry"
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            out[name] = "other"
            continue
        functions = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assigned = {n.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) for n in (node,)}
        if "core" in functions:
            out[name] = "core"
        elif "work" in functions:
            out[name] = "middle"
        elif "OFFSET" in assigned:
            out[name] = "config"
        else:
            out[name] = "other"
    return out


def _make_contracts(task: RepoTask, *, kind: str) -> tuple[ProbeContract, ...]:
    """Evaluator authors PUBLIC contracts before learning, as in module-level tests.

    This factory knows the fixture's nominal behavior to create reference tests.
    Neither the planner nor the likelihood learner receives the kind/true file.
    """
    roles = _roles(task)
    by_role = {r: Path(name).stem for name, r in roles.items()}
    assert {"entry", "core", "middle", "config"} <= set(by_role)
    sample = task.public[0]
    x, y = sample.inputs["x"], sample.inputs["y"]
    correct_core = x*y if kind == "core_binary" else x+y
    correct_middle = (
        x*y if kind == "core_binary"
        else x+y+3 if kind == "middle_constant"
        else x+y+2 if kind == "config_constant"
        else x+y
    )
    correct_config = 2 if kind == "config_constant" else 0
    expected = {"core": float(correct_core), "middle": float(correct_middle),
                "config": float(correct_config), "entry": float(sample.expected)}
    symbols = {"core": "core", "middle": "work", "config": "OFFSET", "entry": "solve"}
    return tuple(
        ProbeContract(
            probe_id=f"probe_{role}", role=role, module=by_role[role], symbol=symbols[role],
            kwargs=tuple(sorted(sample.inputs.items())) if role != "config" else (),
            expected=expected[role], cost=PROBE_COSTS[role],
        ) for role in ("core", "config", "middle", "entry")
    )


def make_inquiry_tasks(seed: int, *, per_kind: int = 3) -> list[InquiryTask]:
    """Same core WORLD MODEL generator, new publicly executable diagnostic tests.

    Task IDs no longer expose the generator's scenario name to a policy/log.
    """
    result = []
    for i, original in enumerate(make_repository_tasks(seed, per_kind=per_kind)):
        kind = original.task_id.split("-")[1]  # independent fixture author only
        opaque = "inq-" + hashlib.sha256(f"{seed}|{i}|{original.task_id}".encode()).hexdigest()[:16]
        task = replace(original, task_id=opaque)
        result.append(InquiryTask(task, _make_contracts(task, kind=kind)))
    return result


def run_probe(root: Path, task: RepoTask, contract: ProbeContract) -> ProbeReceipt:
    """Execute public contract on the *unmodified* repository snapshot.

    Diagnostic result is NOT equivalent to final acceptance. WITNESS separately
    examines held-back challenge data after any proposed repair.
    """
    snapshot = repo_snapshot(root, task)
    err: str | None = None
    observation = ""
    passed = False
    _clear_local_modules(root)
    sys.path.insert(0, str(root))
    try:
        importlib.invalidate_caches()
        mod = importlib.import_module(contract.module)
        obj = getattr(mod, contract.symbol)
        value = obj(**dict(contract.kwargs)) if callable(obj) else obj
        observed = float(value)
        observation = repr(observed)
        passed = math.isfinite(observed) and math.isclose(observed, contract.expected, rel_tol=1e-12, abs_tol=1e-12)
    except Exception as exc:
        err = type(exc).__name__
        observation = f"error:{err}"
    finally:
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass
        _clear_local_modules(root)
    fields = {
        "schema": "nomad.v0.9.probe-receipt.v1", "task_id": task.task_id,
        "probe_id": contract.probe_id, "snapshot_digest": snapshot,
        "observation": observation, "passed": passed, "exception": err,
        "cost": contract.cost,
    }
    return ProbeReceipt(**fields, record_digest=_digest(fields))


def _entropy(probabilities: Mapping[str, float]) -> float:
    return -sum(p * math.log2(p) for p in probabilities.values() if p > 0.0)


def _normalize(p: Mapping[str, float]) -> dict[str, float]:
    total = sum(max(0.0, v) for v in p.values())
    if total <= EPS:
        return {k: 1.0/len(p) for k in p}
    return {k: max(0.0, v)/total for k, v in p.items()}


class ProbeLikelihoods:
    """Smoothed P(probe fails | verified fault role, public probe role).

    The likelihood is estimated from training probe observations and verified
    repair locations, never evaluation source labels. It is a statistical model,
    not a causal proof or a calibrated posterior guarantee.
    """
    def __init__(self) -> None:
        self.pass_counts: dict[tuple[str, str], int] = defaultdict(int)
        self.fail_counts: dict[tuple[str, str], int] = defaultdict(int)
        self.fit_cases = 0

    def observe(self, fault_role: str, probe_role: str, *, passed: bool) -> None:
        counts = self.pass_counts if passed else self.fail_counts
        counts[(fault_role, probe_role)] += 1

    def pass_probability(self, fault_role: str, probe_role: str) -> float:
        yes = self.pass_counts.get((fault_role, probe_role), 0)
        no = self.fail_counts.get((fault_role, probe_role), 0)
        return (yes+1)/(yes+no+2)

    def snapshot(self) -> dict[str, object]:
        keys = sorted(set(self.pass_counts)|set(self.fail_counts))
        return {
            "schema": "nomad.v0.9.probe-likelihoods.v1",
            "training_tasks": self.fit_cases,
            "rows": [
                {"hypothesis_role": a, "probe_role": b,
                 "passed": self.pass_counts.get((a, b), 0),
                 "failed": self.fail_counts.get((a, b), 0),
                 "pass_probability": self.pass_probability(a, b)}
                for a, b in keys
            ],
        }


def fit_inquiry(training: Iterable[InquiryTask]) -> tuple[RepositoryWorldModel, ProbeLikelihoods]:
    tasks = list(training)
    world, _, _ = train_world_models(t.repo for t in tasks)
    probe_model = ProbeLikelihoods()
    for fixture in tasks:
        # The repair must pass public, WITNESS challenge, and held-out final
        # before it can label where any training evidence belongs.
        repaired = solve_repository(fixture.repo, world_model=world)
        if not (repaired.solved and repaired.final_correct and repaired.witness_supported and repaired.chosen_file):
            continue
        fault_role = _roles(fixture.repo)[repaired.chosen_file]
        with tempfile.TemporaryDirectory(prefix="nomad-inquiry-fit-") as td:
            root = Path(td)
            materialize(fixture.repo, root)
            snapshot = repo_snapshot(root, fixture.repo)
            for probe in fixture.contracts:
                receipt = run_probe(root, fixture.repo, probe)
                if not receipt.verify(snapshot):
                    raise AssertionError("training probe receipt failed integrity check")
                probe_model.observe(fault_role, probe.role, passed=receipt.passed)
        probe_model.fit_cases += 1
    return world, probe_model


def _initial_prior(root: Path, task: RepoTask, world: RepositoryWorldModel,
                   files: list[str]) -> dict[str, float]:
    scores = {f: world.score(file_signature(root, task, f, include_failure=True)) for f in files}
    top = max(scores.values())
    bottom = min(scores.values())
    # Temperature uses the observed log-odds spread, before outcomes are known;
    # preserves uncertainty even when an overconfident v0.8 prior is mistaken.
    temperature = max(12.0, (top-bottom)/3.0)
    soft = _normalize({f: math.exp((s-top)/temperature) for f, s in scores.items()})
    uniform = 1.0/len(files)
    return {f: 0.94*soft[f]+0.06*uniform for f in files}


def _candidate_costs(task: RepoTask, files: list[str]) -> dict[str, int]:
    return {f: max(1, sum(len(rows) for rows in generate_python_candidates(task.files[f]).values())) for f in files}


def _rank(prior: Mapping[str, float], costs: Mapping[str, int]) -> list[str]:
    return sorted(prior, key=lambda f: (-prior[f]/costs[f], -prior[f], f))


def _expected_attempts(prior: Mapping[str, float], costs: Mapping[str, int]) -> float:
    running = 0.0
    expectation = 0.0
    for filename in _rank(prior, costs):
        expectation += prior[filename] * (running + (costs[filename]+1)/2.0)
        running += costs[filename]
    return expectation


def _update(prior: Mapping[str, float], file_roles: Mapping[str, str],
            model: ProbeLikelihoods, probe_role: str, passed: bool) -> dict[str, float]:
    return _normalize({
        f: p * (model.pass_probability(file_roles[f], probe_role)
                if passed else (1.0-model.pass_probability(file_roles[f], probe_role)))
        for f, p in prior.items()
    })


@dataclass(frozen=True)
class QueryDecision:
    probe_id: str
    entropy_before: float
    information_gain_bits: float
    expected_search_savings: float
    probe_cost: float
    net_expected_savings: float


def choose_probe(prior: Mapping[str, float], costs: Mapping[str, int], roles: Mapping[str, str],
                 model: ProbeLikelihoods, menu: Iterable[ProbeMenu],
                 already_seen: frozenset[str], remaining_budget: float) -> QueryDecision | None:
    before = _expected_attempts(prior, costs)
    before_h = _entropy(prior)
    best: QueryDecision | None = None
    best_score = -math.inf
    for probe in menu:
        if probe.probe_id in already_seen or probe.cost > remaining_budget + EPS:
            continue
        prob_pass = sum(prior[f]*model.pass_probability(roles[f], probe.role) for f in prior)
        pass_state = _update(prior, roles, model, probe.role, True)
        fail_state = _update(prior, roles, model, probe.role, False)
        after_cost = prob_pass * _expected_attempts(pass_state, costs) + (1-prob_pass)*_expected_attempts(fail_state, costs)
        after_entropy = prob_pass*_entropy(pass_state)+(1-prob_pass)*_entropy(fail_state)
        info_gain = max(0.0, before_h-after_entropy)
        savings = before-after_cost
        net = savings-probe.cost
        # A query must buy strictly positive expected benefit and information.
        if info_gain < 1e-4 or net < 0.10:
            continue
        # Information-per-cost prioritizes efficient questions among promising
        # choices; tie-break by expected utility, independent of hidden labels.
        score = (info_gain/probe.cost) + 0.001*net
        if score > best_score:
            best_score = score
            best = QueryDecision(probe.probe_id, before_h, info_gain, savings, probe.cost, net)
    return best


@dataclass(frozen=True)
class InquiryResult:
    task_id: str
    policy: str
    solved: bool
    final_correct: bool
    witness_supported: bool
    candidate_attempts: int
    probes: int
    probe_cost: float
    total_proxy_cost: float
    predicted_file: str | None
    chosen_file: str | None
    probe_receipts: tuple[ProbeReceipt, ...]
    query_decisions: tuple[QueryDecision, ...]


def run_inquiry(fixture: InquiryTask, world: RepositoryWorldModel,
                learned: ProbeLikelihoods, *, policy: str="active",
                max_probe_cost: float=0.90, max_probes: int=3,
                max_attempts: int=80, verify_repo_tests: bool=False,
                negative_control_seed: int=0) -> InquiryResult:
    if policy not in {"active", "prior_only", "world", "all", "random", "shuffled"}:
        raise ValueError(f"unsupported policy: {policy}")
    task = fixture.repo
    with tempfile.TemporaryDirectory(prefix="nomad-inquiry-observe-") as td:
        root=Path(td)
        materialize(task, root)
        files=candidate_files(task)
        roles=_roles(task)
        prior=_initial_prior(root,task,world,files)
        costs=_candidate_costs(task,files)
        snapshot=repo_snapshot(root,task)
        menu=fixture.menu()
        available={p.probe_id:p for p in fixture.contracts}
        seen: set[str]=set()
        observations: list[ProbeReceipt]=[]
        decisions: list[QueryDecision]=[]
        budget=float(max_probe_cost)
        rng=random.Random(int(_digest(task.task_id)[:12],16)+negative_control_seed)

        while policy in {"active","all","random","shuffled"} and len(seen) < max_probes:
            remaining=[m for m in menu if m.probe_id not in seen and m.cost <= budget+EPS]
            if not remaining:
                break
            if policy in {"active","shuffled"}:
                decision=choose_probe(prior,costs,roles,learned,remaining,frozenset(seen),budget)
                if decision is None:
                    break
                probe=available[decision.probe_id]
                decisions.append(decision)
            elif policy == "all":
                probe=available[remaining[0].probe_id]
            else:
                # Precommitted random policy gets ONE probe to serve as the
                # matched cheap-diagnosis control, never uses fault labels.
                if seen:
                    break
                probe=available[rng.choice(remaining).probe_id]
            receipt=run_probe(root,task,probe)
            if not receipt.verify(snapshot):
                raise AssertionError("probe receipt not bound to the original world snapshot")
            observations.append(receipt)
            seen.add(probe.probe_id)
            budget-=probe.cost
            if policy == "shuffled":
                # Ablation: intentionally sever evidence from the true observed
                # outcome while still paying for the real probe execution.
                simulated = bool(rng.getrandbits(1))
                prior=_update(prior,roles,learned,probe.role,simulated)
            else:
                prior=_update(prior,roles,learned,probe.role,receipt.passed)

        if policy == "world":
            order=world.rank(root,task,files)
        else:
            order=_rank(prior,costs)
        predicted_file = order[0] if order else None
    # Repair occurs from a clean replica; diagnostic observations do not mutate
    # the task. WITNESS still owns final admission on withheld challenge tests.
    result=solve_repository(task,world_model=world,file_order=order,
                            max_attempts=max_attempts,verify_repo_tests=verify_repo_tests)
    spent=sum(x.cost for x in observations)
    return InquiryResult(
        task_id=task.task_id,policy=policy,solved=result.solved,
        final_correct=result.final_correct,witness_supported=result.witness_supported,
        candidate_attempts=result.attempts,probes=len(observations),
        probe_cost=round(spent,6),total_proxy_cost=round(result.attempts+spent,6),
        predicted_file=predicted_file,chosen_file=result.chosen_file,
        probe_receipts=tuple(observations),query_decisions=tuple(decisions),
    )


def summarize_inquiry(rows: list[InquiryResult]) -> dict[str, object]:
    return {
        "tasks":len(rows),
        "solved":sum(r.solved for r in rows),
        "final_correct":sum(r.final_correct for r in rows),
        "witness_supported":sum(r.witness_supported for r in rows),
        "mean_candidate_attempts":mean(r.candidate_attempts for r in rows) if rows else 0,
        "mean_probe_count":mean(r.probes for r in rows) if rows else 0,
        "mean_probe_proxy_cost":mean(r.probe_cost for r in rows) if rows else 0,
        "mean_total_proxy_cost":mean(r.total_proxy_cost for r in rows) if rows else 0,
    }
