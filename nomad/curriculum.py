"""Curriculum: which WORLD family the organism attempts next.

PATIENCE attempts without a win parks a family (it is retried only after
every open family has had as many attempts), so one stubborn family cannot
stall the organism.

A level opens only after the field has *beaten the control* on every family
of the level below: a twin pair where treatment was certified and either
control was not, or treatment needed fewer evaluations. Held-out families
never enter the curriculum. Within the open levels, families not yet beaten
come first, then the least-attempted. Choice is deterministic given the
scoreboard, so a run can be replayed.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .world import WorldTask
from .world_tasks import TRAIN


PATIENCE = 4


def _key(family: str) -> str:
    return f"world:{family}"


def family_records(rows: Iterable[dict]) -> dict[str, dict[str, Any]]:
    rec: dict[str, dict[str, Any]] = defaultdict(lambda: {"attempts": 0, "beaten": False, "certified": 0})
    for row in rows:
        task = str(row.get("task", ""))
        if not task.startswith("world:"):
            continue
        fam = task.split(":", 1)[1]
        r = rec[fam]
        r["attempts"] += 1
        if row.get("treatment"):
            r["certified"] += 1
            better_cert = not row.get("control")
            better_cost = row.get("control") and row.get("evaluations_saved", 0) > 0
            if better_cert or better_cost:
                r["beaten"] = True
    return dict(rec)


def open_levels(records: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Highest open level per domain."""
    out = {}
    for dom, levels in TRAIN.items():
        lvl = min(levels)
        for L in sorted(levels):
            if L == min(levels):
                continue
            prev = levels[L - 1] if (L - 1) in levels else []
            if prev and all(records.get(t.family, {}).get("beaten") for t in prev):
                lvl = L
            else:
                break
        out[dom] = lvl
    return out


def choose(rows: Iterable[dict], domain: str | None = None, step: int = 0) -> tuple[WorldTask, dict[str, Any]]:
    rows = list(rows)
    records = family_records(rows)
    levels = open_levels(records)
    candidates: list[WorldTask] = []
    for dom, levels_map in TRAIN.items():
        if domain and dom != domain:
            continue
        for L, tasks in levels_map.items():
            if L <= levels[dom]:
                candidates.extend(tasks)
    if not candidates:
        raise ValueError(f"no curriculum families for domain {domain!r}")

    def rank(t: WorldTask):
        r = records.get(t.family, {"attempts": 0, "beaten": False})
        parked = (not r["beaten"]) and r["attempts"] >= patience
        return (r["beaten"] or parked, r["attempts"], -t.level, t.family)
    from . import genome
    patience = int(genome.get("patience"))
    candidates.sort(key=rank)
    chosen = candidates[0]
    return chosen, {"open_levels": levels, "records": records, "chosen": chosen.family,
                    "level": chosen.level, "candidates": len(candidates)}
