from __future__ import annotations

import hashlib
import heapq
from dataclasses import dataclass
from typing import Iterable

from .bitstate import FailureState, encode_failure
from .learner import ContextualOperatorLearner
from .ledger import EvidenceLedger
from .model import Candidate, CodeTask
from .operators import FAMILIES, generate_candidates


def _source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SearchStep:
    depth: int
    signature: int
    family: str
    description: str
    source_before: str
    source_after: str
    source_before_sha256: str
    source_after_sha256: str
    failures_before: int
    failures_after: int
    runtime_errors_after: int

    @property
    def improved(self) -> bool:
        return self.failures_after < self.failures_before


@dataclass(frozen=True)
class MultiSolveResult:
    solved: bool
    source: str
    expansions: int
    depth: int
    lineage: tuple[SearchStep, ...]
    root_signature: int
    start_failures: int
    final_failures: int
    frontier_peak: int
    generated_edges: int
    abstained_reason: str | None

    @property
    def operator_sequence(self) -> tuple[str, ...]:
        return tuple(step.family for step in self.lineage)


@dataclass(frozen=True)
class _Node:
    node_id: int
    source: str
    depth: int
    state: FailureState
    lineage: tuple[SearchStep, ...]


@dataclass(frozen=True)
class _Edge:
    parent_id: int
    parent_sha256: str
    candidate: Candidate
    family_score: float
    family_rank: int
    candidate_rank: int
    serial: int


class MultiNomadEngine:
    """Bounded best-first program-repair search.

    Important v0.2 properties:
      * every executed child gets a fresh failure signature;
      * alternatives remain in a bounded frontier, so a partial improvement does
        not destroy earlier hypotheses;
      * execution is the expensive expansion; proposals are cheap and can be
        ranked before paying for them;
      * budgets cause explicit abstention instead of silent success claims;
      * source hashes bind every edge to the parent evidence that produced it.
    """

    def __init__(
        self,
        learner: ContextualOperatorLearner | None = None,
        fixed_order: Iterable[str] | None = None,
        learn: bool = False,
        ledger: EvidenceLedger | None = None,
    ) -> None:
        self.learner = learner or ContextualOperatorLearner(contextual=True)
        self.fixed_order = tuple(fixed_order) if fixed_order is not None else None
        self.learn = learn
        self.ledger = ledger

    def _family_order(self, signature: int) -> list[str]:
        if self.fixed_order is not None:
            return list(self.fixed_order)
        return self.learner.rank(signature)

    def _family_score(self, signature: int, family: str) -> float:
        if self.fixed_order is not None:
            order = list(self.fixed_order)
            try:
                rank = order.index(family)
            except ValueError:
                return 0.0
            # Deterministic fixed prior in (0, 1].
            return (len(order) - rank) / max(1, len(order))
        return self.learner.score(signature, family)

    @staticmethod
    def _edge_priority(edge: _Edge, parent: _Node, total_examples: int) -> tuple[float, int, int, int]:
        # Lower is better. Parent execution evidence dominates; learned family
        # evidence breaks ties and helps choose which unexecuted edge is worth
        # paying for next. The prior weight is intentionally < one public-test
        # failure step, so a node with strictly better observed behavior cannot
        # be outranked by a merely familiar operator. A small depth cost prevents
        # gratuitous deepening.
        failure_rate = parent.state.failures / max(1, total_examples)
        score = failure_rate + 0.01 * parent.depth - 0.08 * edge.family_score
        return (score, edge.family_rank, edge.candidate_rank, edge.serial)

    def solve(
        self,
        task: CodeTask,
        *,
        max_depth: int = 3,
        max_expansions: int = 96,
        frontier_cap: int = 256,
    ) -> MultiSolveResult:
        root_state = encode_failure(task, task.source)
        if root_state.failures == 0:
            return MultiSolveResult(
                solved=True,
                source=task.source,
                expansions=0,
                depth=0,
                lineage=(),
                root_signature=root_state.key,
                start_failures=0,
                final_failures=0,
                frontier_peak=0,
                generated_edges=0,
                abstained_reason=None,
            )

        nodes: dict[int, _Node] = {
            0: _Node(0, task.source, 0, root_state, ())
        }
        next_node_id = 1
        serial = 0
        generated_edges = 0
        expansions = 0
        frontier_peak = 0
        attempted_sources = {task.source.replace(" ", "")}
        queued_sources: set[str] = set()
        frontier: list[tuple[tuple[float, int, int, int], _Edge]] = []

        def queue_from(node: _Node) -> None:
            nonlocal serial, generated_edges, frontier_peak
            if node.depth >= max_depth:
                return
            grouped = generate_candidates(node.source)
            families = self._family_order(node.state.key)
            rank_map = {fam: i for i, fam in enumerate(families)}
            for family in families:
                candidates = grouped.get(family, ())
                family_score = self._family_score(node.state.key, family)
                for candidate_rank, candidate in enumerate(candidates):
                    key = candidate.source.replace(" ", "")
                    if key in attempted_sources or key in queued_sources:
                        continue
                    serial += 1
                    edge = _Edge(
                        parent_id=node.node_id,
                        parent_sha256=_source_hash(node.source),
                        candidate=candidate,
                        family_score=family_score,
                        family_rank=rank_map.get(family, len(families)),
                        candidate_rank=candidate_rank,
                        serial=serial,
                    )
                    priority = self._edge_priority(edge, node, len(task.examples))
                    heapq.heappush(frontier, (priority, edge))
                    queued_sources.add(key)
                    generated_edges += 1
            if len(frontier) > frontier_cap:
                # Keep only the best proposals. Dropping an unexecuted edge is
                # explicit bounded search, not a correctness claim.
                kept = heapq.nsmallest(frontier_cap, frontier)
                frontier[:] = kept
                heapq.heapify(frontier)
                queued_sources.clear()
                queued_sources.update(e.candidate.source.replace(" ", "") for _, e in frontier)
            frontier_peak = max(frontier_peak, len(frontier))

        queue_from(nodes[0])
        best = nodes[0]
        reason = "frontier_exhausted"

        while frontier:
            if expansions >= max_expansions:
                reason = "expansion_budget"
                break
            _, edge = heapq.heappop(frontier)
            key = edge.candidate.source.replace(" ", "")
            queued_sources.discard(key)
            if key in attempted_sources:
                continue
            parent = nodes[edge.parent_id]
            if _source_hash(parent.source) != edge.parent_sha256:
                # This should be impossible with immutable nodes. Keep the guard
                # because stale-evidence reuse is exactly the failure mode NOMAD
                # is designed not to normalize.
                continue

            attempted_sources.add(key)
            expansions += 1
            child_state = encode_failure(task, edge.candidate.source)
            step = SearchStep(
                depth=parent.depth + 1,
                signature=parent.state.key,
                family=edge.candidate.operator_family,
                description=edge.candidate.description,
                source_before=parent.source,
                source_after=edge.candidate.source,
                source_before_sha256=edge.parent_sha256,
                source_after_sha256=_source_hash(edge.candidate.source),
                failures_before=parent.state.failures,
                failures_after=child_state.failures,
                runtime_errors_after=child_state.runtime_errors,
            )
            child = _Node(
                next_node_id,
                edge.candidate.source,
                parent.depth + 1,
                child_state,
                parent.lineage + (step,),
            )
            nodes[next_node_id] = child
            next_node_id += 1

            if child.state.failures < best.state.failures:
                best = child

            if self.learn:
                # Local execution reward only. Reusable skill promotion is kept
                # separate and requires an external challenge in skills.py.
                improved = child.state.failures < parent.state.failures
                self.learner.update(parent.state.key, edge.candidate.operator_family, improved)
                if self.ledger is not None:
                    self.ledger.append({
                        "kind": "transition",
                        "task_id": task.task_id,
                        "parent_sha256": edge.parent_sha256,
                        "child_sha256": step.source_after_sha256,
                        "signature": parent.state.key,
                        "family": edge.candidate.operator_family,
                        "failures_before": parent.state.failures,
                        "failures_after": child.state.failures,
                        "improved": improved,
                        "depth": child.depth,
                    })

            if child.state.failures == 0:
                return MultiSolveResult(
                    solved=True,
                    source=child.source,
                    expansions=expansions,
                    depth=child.depth,
                    lineage=child.lineage,
                    root_signature=root_state.key,
                    start_failures=root_state.failures,
                    final_failures=0,
                    frontier_peak=frontier_peak,
                    generated_edges=generated_edges,
                    abstained_reason=None,
                )

            queue_from(child)

        if best.depth >= max_depth and not frontier:
            reason = "depth_or_frontier_exhausted"
        return MultiSolveResult(
            solved=False,
            source=best.source,
            expansions=expansions,
            depth=best.depth,
            lineage=best.lineage,
            root_signature=root_state.key,
            start_failures=root_state.failures,
            final_failures=best.state.failures,
            frontier_peak=frontier_peak,
            generated_edges=generated_edges,
            abstained_reason=reason,
        )
