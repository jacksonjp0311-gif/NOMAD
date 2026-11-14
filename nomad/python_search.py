from __future__ import annotations

import hashlib
import heapq
from dataclasses import dataclass
from typing import Iterable

from .python_model import PythonCandidate, PythonTask
from .python_operators import PY_FAMILIES, generate_python_candidates
from .resonance import ResonanceState, encode_resonance
from .sensory_learner import SensoryOperatorLearner
from .resonance_learner import ResonanceOperatorLearner


def _sha(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PythonSearchStep:
    depth: int
    signature: int
    family: str
    description: str
    source_before: str
    source_after: str
    parent_sha256: str
    child_sha256: str
    evidence_before: float
    evidence_after: float
    failures_before: int
    failures_after: int
    runtime_errors_after: int

    @property
    def improved(self) -> bool:
        return self.evidence_after < self.evidence_before


@dataclass(frozen=True)
class PythonSolveResult:
    solved: bool
    source: str
    expansions: int
    depth: int
    lineage: tuple[PythonSearchStep, ...]
    root_signature: int
    start_failures: int
    final_failures: int
    frontier_peak: int
    abstained_reason: str | None

    @property
    def operator_sequence(self) -> tuple[str, ...]:
        return tuple(step.family for step in self.lineage)


@dataclass(frozen=True)
class _Node:
    node_id: int
    source: str
    depth: int
    state: ResonanceState
    lineage: tuple[PythonSearchStep, ...]


@dataclass(frozen=True)
class _Edge:
    parent_id: int
    parent_sha256: str
    candidate: PythonCandidate
    family_score: float
    family_rank: int
    candidate_rank: int
    serial: int


class ResonanceSearchEngine:
    """v0.3 bounded repair search over fused coding telemetry.

    Search-time state can be `fusion` (all sensor channels) or `test_only`
    (weaker control). Execution evidence always dominates learned preference.
    """

    def __init__(
        self,
        learner: SensoryOperatorLearner | ResonanceOperatorLearner | None = None,
        *,
        mode: str = "fusion",
        fixed_order: Iterable[str] | None = None,
        learn: bool = False,
    ) -> None:
        self.learner = learner or SensoryOperatorLearner(contextual=True)
        self.mode = mode
        self.fixed_order = tuple(fixed_order) if fixed_order is not None else None
        self.learn = learn

    def _key(self, state: ResonanceState) -> int:
        return state.key(self.mode)

    def _families(self, state: ResonanceState) -> list[str]:
        if self.fixed_order is not None:
            return list(self.fixed_order)
        if hasattr(self.learner, "rank_state"):
            return self.learner.rank_state(state)
        return self.learner.rank(self._key(state))

    def _family_score(self, state: ResonanceState, family: str) -> float:
        if self.fixed_order is not None:
            order = list(self.fixed_order)
            return (len(order) - order.index(family)) / len(order) if family in order else 0.0
        if hasattr(self.learner, "score_state"):
            return self.learner.score_state(state, family)
        return self.learner.score(self._key(state), family)

    @staticmethod
    def _priority(edge: _Edge, parent: _Node) -> tuple[float, int, int, int]:
        # Max prior contribution is 0.05, smaller than one ordinary test-failure
        # step in the registered benchmark. Parser/runtime improvements are much
        # larger. This preserves the v0.2 evidence-dominance invariant.
        score = parent.state.evidence_score + 0.01 * parent.depth - 0.05 * edge.family_score
        return (score, edge.family_rank, edge.candidate_rank, edge.serial)

    def solve(
        self,
        task: PythonTask,
        *,
        max_depth: int = 4,
        max_expansions: int = 160,
        frontier_cap: int = 384,
    ) -> PythonSolveResult:
        root_state = encode_resonance(task, task.source)
        root_key = self._key(root_state)
        if root_state.parse_ok and root_state.failures == 0:
            return PythonSolveResult(True, task.source, 0, 0, (), root_key, 0, 0, 0, None)

        nodes = {0: _Node(0, task.source, 0, root_state, ())}
        next_node_id = 1
        serial = 0
        expansions = 0
        frontier_peak = 0
        attempted = {task.source.strip()}
        queued: set[str] = set()
        frontier: list[tuple[tuple[float, int, int, int], _Edge]] = []
        best = nodes[0]

        def queue(node: _Node) -> None:
            nonlocal serial, frontier_peak
            if node.depth >= max_depth:
                return
            grouped = generate_python_candidates(node.source)
            sig = self._key(node.state)
            families = self._families(node.state)
            rank = {f: i for i, f in enumerate(families)}
            for family in families:
                score = self._family_score(node.state, family)
                for cidx, candidate in enumerate(grouped.get(family, ())):
                    key = candidate.source.strip()
                    if key in attempted or key in queued:
                        continue
                    serial += 1
                    edge = _Edge(node.node_id, _sha(node.source), candidate, score, rank.get(family, 999), cidx, serial)
                    heapq.heappush(frontier, (self._priority(edge, node), edge))
                    queued.add(key)
            if len(frontier) > frontier_cap:
                kept = heapq.nsmallest(frontier_cap, frontier)
                frontier[:] = kept
                heapq.heapify(frontier)
                queued.clear()
                queued.update(e.candidate.source.strip() for _, e in frontier)
            frontier_peak = max(frontier_peak, len(frontier))

        queue(nodes[0])
        reason = "frontier_exhausted"
        while frontier:
            if expansions >= max_expansions:
                reason = "expansion_budget"
                break
            _, edge = heapq.heappop(frontier)
            key = edge.candidate.source.strip()
            queued.discard(key)
            if key in attempted:
                continue
            parent = nodes[edge.parent_id]
            if _sha(parent.source) != edge.parent_sha256:
                continue
            attempted.add(key)
            expansions += 1
            child_state = encode_resonance(task, edge.candidate.source)
            child_key_parent = self._key(parent.state)
            step = PythonSearchStep(
                depth=parent.depth + 1,
                signature=child_key_parent,
                family=edge.candidate.operator_family,
                description=edge.candidate.description,
                source_before=parent.source,
                source_after=edge.candidate.source,
                parent_sha256=edge.parent_sha256,
                child_sha256=_sha(edge.candidate.source),
                evidence_before=parent.state.evidence_score,
                evidence_after=child_state.evidence_score,
                failures_before=parent.state.failures,
                failures_after=child_state.failures,
                runtime_errors_after=child_state.runtime_errors,
            )
            child = _Node(next_node_id, edge.candidate.source, parent.depth + 1, child_state, parent.lineage + (step,))
            nodes[next_node_id] = child
            next_node_id += 1

            if child.state.evidence_score < best.state.evidence_score:
                best = child

            improved = child.state.evidence_score < parent.state.evidence_score
            if self.learn:
                if hasattr(self.learner, "update_state"):
                    self.learner.update_state(parent.state, edge.candidate.operator_family, improved)
                else:
                    self.learner.update(child_key_parent, edge.candidate.operator_family, improved)

            if child.state.parse_ok and child.state.failures == 0:
                return PythonSolveResult(
                    True,
                    child.source,
                    expansions,
                    child.depth,
                    child.lineage,
                    root_key,
                    root_state.failures,
                    0,
                    frontier_peak,
                    None,
                )
            queue(child)

        return PythonSolveResult(
            False,
            best.source,
            expansions,
            best.depth,
            best.lineage,
            root_key,
            root_state.failures,
            best.state.failures,
            frontier_peak,
            reason,
        )
