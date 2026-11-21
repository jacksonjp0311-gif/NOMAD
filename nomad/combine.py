"""COMBINE: answer an unseen word problem by composing two retrieved concepts (docs/COMBINE.md).
Switch ``NOMAD_COMBINE`` (default OFF).

MEANING (nomad/meaning.py) retrieves one certified concept from a story's words. A story that
chains two ideas ("three machines make 30, 7 and 5 bolts an hour; the average for 7 hours")
matches no single concept and MEANING's stage misses. COMBINE runs only after that miss:

1. The top ``COMBINE_K`` concepts the words retrieve form compositions ``B[slot := A]``: the
   output of an inner concept A fills one variable of an outer concept B (A = B allowed), in order
   of the two concepts' retrieval ranks (sum, then the outer's rank).
2. Meet in the middle, goal-directed: every instance of A over the task's inputs (MEANING's
   type-preserving renamings) is run once on the public rows (1 evaluation, cached across
   compositions); every binding of B's other variables (1 evaluation) is *inverted* along the path
   to the slot (add / sub / mul / floor-div by a known value; exact intervals), giving, per public
   row, the interval the slot's value must lie in for B to hit the goal. Only A instances whose
   values lie in every interval, on disjoint inputs, are composed and run (1 evaluation each). Where
   the path is not invertible (mod, min, max, ite, a slot used twice, a divisor slot) every A
   instance is a candidate. The filter is exact: it never drops a composition that fits.
3. A public fit goes to WITNESS (a rejection costs 1 evaluation, at most ``COMBINE_REJECTS``).

The stage spends at most ``COMBINE_BUDGET`` evaluations; on a miss the normal search runs on the
remaining budget, unchanged. Learns nothing new: reads MEANING's lexicon and concepts only. Empty
field: no lexicon, no stage. Cold control: never reads words. Switch off: never runs. Final and
challenge rows are never read here (WITNESS decides).
"""
from __future__ import annotations

import math
import os
from typing import Any

COMBINE_K = 10         # concepts drawn into compositions (dev-chosen: 5 / 6 / 8 worse, 12 equal)
COMBINE_BUDGET = 1536  # most evaluations the stage spends (dev-chosen)
COMBINE_MAPS = 360     # most renamings of one concept / of one outer binding set
COMBINE_REJECTS = 8

INF = math.inf


def enabled() -> bool:
    return os.environ.get("NOMAD_COMBINE", "off").strip().lower() in ("on", "1", "true", "yes")


def _relabel(tree: list, pre: str) -> list:
    if tree[0] == "var":
        return ["var", pre + tree[1]]
    if tree[0] in ("const", "lib"):
        return tree
    return [tree[0]] + [_relabel(c, pre) for c in tree[1:]]


def _subst(tree: list, var: str, sub: list) -> list:
    if tree[0] == "var":
        return sub if tree[1] == var else tree
    if tree[0] in ("const", "lib"):
        return tree
    return [tree[0]] + [_subst(c, var, sub) for c in tree[1:]]


def _count(tree: list, var: str) -> int:
    if tree[0] == "var":
        return int(tree[1] == var)
    if tree[0] in ("const", "lib"):
        return 0
    return sum(_count(c, var) for c in tree[1:])


class _Empty(Exception):
    pass


def _ceil(x):
    return x if x in (INF, -INF) else math.ceil(x)


def _floor(x):
    return x if x in (INF, -INF) else math.floor(x)


def _invert(node: list, slot: str, lo, hi, row: dict):
    """Interval the slot's value must lie in for ``node`` to land in [lo, hi] on ``row``; None = any.
    The slot occurs exactly once in ``node``. Raises _Empty (no value works) or Invalid (siblings)."""
    from .world import run
    if lo > hi:
        raise _Empty
    if node[0] == "var":
        return (lo, hi)
    op, kids = node[0], node[1:]
    i = next(k for k, c in enumerate(kids) if _count(c, slot))
    if len(kids) != 2 or op not in ("add", "sub", "mul", "div"):
        return None
    y = run(kids[1 - i], row)
    if op == "add":
        return _invert(kids[i], slot, lo - y, hi - y, row)
    if op == "sub":
        return (_invert(kids[0], slot, lo + y, hi + y, row) if i == 0
                else _invert(kids[1], slot, y - hi, y - lo, row))
    if op == "mul":
        if y == 0:
            if lo <= 0 <= hi:
                return None
            raise _Empty
        a, b = sorted((lo / y, hi / y))
        return _invert(kids[i], slot, _ceil(a), _floor(b), row)
    # floor division, slot in the dividend
    if i != 0 or y == 0:
        return None
    if y > 0:
        return _invert(kids[0], slot, lo * y if lo != -INF else -INF, hi * y + y - 1 if hi != INF else INF, row)
    return _invert(kids[0], slot, (hi + 1) * y + 1 if hi != INF else -INF, lo * y if lo != -INF else INF, row)


def compositions(prior: Any, ranked: list[str], n_inputs: int) -> list[tuple[str, str, str]]:
    """(inner A, outer B, slot of B) in rank order, at most ``n_inputs`` variables in all."""
    out = []
    order = sorted(((i + j, j, i) for i in range(len(ranked)) for j in range(len(ranked))))
    for _s, j, i in order:
        a, b = prior.concepts[ranked[i]], prior.concepts[ranked[j]]
        for slot in sorted(b["types"]):
            if b["types"][slot] != a.get("out", "int"):
                continue
            if len(a["types"]) + len(b["types"]) - 1 > n_inputs:
                continue
            out.append((ranked[i], ranked[j], slot))
    return out


def stage(task: Any, prior: Any, words: str, *, max_eval: int | None = None) -> tuple[tuple[str, list] | None, int, dict]:
    """Compositions of retrieved concepts, after a MEANING miss. ((label, tree) | None, evaluations, info)."""
    from . import meaning as _meaning
    from .world import Invalid, _rename, consult, run
    budget = COMBINE_BUDGET if max_eval is None else min(COMBINE_BUDGET, max_eval)
    kind = None
    try:
        from . import sense as _sense
        kind = _sense.sense(task).get("kind")
    except Exception:
        kind = None
    ranked = [c for _s, c in _meaning.retrieve(prior, task, words, kind)[:COMBINE_K]]
    comps = compositions(prior, ranked, len(task.inputs))
    rows = [r for r, _e in task.public]
    goal = [e for _r, e in task.public]
    st = {"evals": 0, "rejects": 0}
    info: dict = {"retrieved": ranked, "compositions": len(comps), "rejected": 0}
    inner_cache: dict[str, list] = {}      # concept -> [(inputs used, tree, vector)]
    seen: set[str] = set()

    class _Out(Exception):
        pass

    def pay():
        if st["evals"] >= budget:
            raise _Out
        st["evals"] += 1

    def inner(c: str) -> list:
        if c in inner_cache:
            return inner_cache[c]
        rec, out, keys = prior.concepts[c], [], set()
        inner_cache[c] = out
        for m in _meaning._maps(rec["types"], task)[:COMBINE_MAPS]:
            inst = _rename(rec["tree"], m)
            k = _meaning._comm_key(inst)
            if k in keys:
                continue
            keys.add(k)
            pay()
            try:
                vec = [run(inst, r) for r in rows]
            except Invalid:
                continue
            out.append((frozenset(m.values()), inst, vec))
        return out

    def outer_maps(b: dict, slot: str) -> list[dict]:
        others = {v: t for v, t in b["types"].items() if v != slot}
        return _meaning._maps(others, task)[:COMBINE_MAPS]

    try:
        for a_key, b_key, slot in comps:
            A = inner(a_key)
            if not A:
                continue
            b = prior.concepts[b_key]
            once = _count(b["tree"], slot) == 1
            bkeys: set[str] = set()
            for m in outer_maps(b, slot):
                partial = _rename(b["tree"], dict(m, **{slot: "__slot__"}))
                k = _meaning._comm_key(partial)
                if k in bkeys:
                    continue
                bkeys.add(k)
                used = frozenset(m.values())
                bounds = None
                if once:
                    pay()
                    try:
                        bounds = [_invert(partial, "__slot__", e, e, r) for r, e in zip(rows, goal)]
                    except (_Empty, Invalid):
                        continue
                for a_used, a_tree, vec in A:
                    if a_used & used:
                        continue
                    if bounds is not None and not all(bd is None or bd[0] <= v <= bd[1] for bd, v in zip(bounds, vec)):
                        continue
                    inst = _subst(partial, "__slot__", a_tree)
                    ck = _meaning._comm_key(inst)
                    if ck in seen:
                        continue
                    seen.add(ck)
                    pay()
                    try:
                        vals = [run(inst, r) for r in rows]
                    except Invalid:
                        continue
                    if vals != goal:
                        continue
                    receipt = consult(task, inst)   # INTEGRITY: challenge only, never final
                    if receipt is not None and receipt.supported:
                        info["rejected"] = st["rejects"]
                        return (f"{b_key}[{slot}:={a_key}]", inst), st["evals"], info
                    st["rejects"] += 1
                    pay()
                    if st["rejects"] >= COMBINE_REJECTS:
                        raise _Out
    except _Out:
        pass
    info["rejected"] = st["rejects"]
    return None, st["evals"], info
