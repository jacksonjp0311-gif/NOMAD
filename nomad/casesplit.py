"""CASESPLIT: divide-and-conquer unification for WORLD search (EUSolver-style).

Organ, not learning. After the cold stage of staged search has missed, the
field arm reuses the int-valued programs that stage already enumerated (and
already paid for) and tries to assemble a conditional program

    ite(c, t1, t2)                      (depth 1)
    ite(c1, t1, ite(c2, t2, t3))        (depth 2, opt-in, only if depth 1 finds nothing)
    ite(c1, ite(c2, t1, t2), t3)

from small *terms* that are each right on a subset of the public rows and
*conditions* (``ite`` takes the then-branch exactly when ``c > 0``) that
separate those subsets. Deep conditional programs come from shallow parts.

Honest accounting. Every term tested, every condition tested, every depth-2
condition pair tested and every assembled candidate run on the public rows
costs 1 evaluation, charged against the same budget as the search. The
values themselves were already paid for once in stage 1, so this is a
conservative (double) charge. Only bit-mask table lookups are free, like the
search's own dedup and redundancy skips.

Occam. Depth 1 returns the candidate with the smallest total node count over
every condition and term it has tested (ties: larger smallest branch support,
then enumeration order), and stops scanning terms as soon as no larger term
could produce a smaller program. Every leaf must cover at least one public
row; a branch that no public row takes is never emitted.

Search never certifies. A split only fits the public rows; WITNESS on the
withheld challenge rows and the final split decide (``world.evaluate``), like
for any other program. Only tasks whose opset contains ``ite`` and whose
output is ``int`` are eligible. The cold twin control never runs this.
``NOMAD_CASESPLIT=off`` disables it; ``NOMAD_CASESPLIT=depth2`` also
allows one nested split.

No transformers. No weights. Deterministic.
"""
from __future__ import annotations

import os
from typing import Iterable, Sequence

TERM_MAX = 6     # largest stage-1 term size tried as a branch
PRED_MAX = 4     # largest stage-1 program size tried as a condition
MIN_SUPPORT = 1  # every leaf must be taken by at least this many public rows


def depth2_enabled() -> bool:
    """Nested splits are off by default (``NOMAD_CASESPLIT=depth2`` turns them on).

    Decided on a development suite (seed 7, never the frozen suite, never a
    held-out): with 5 public rows a depth-2 split has 3 leaves over 5 rows,
    and in that run 0 of its 6 depth-2 candidates passed WITNESS, while every
    one of them pre-empted the library stage. Depth 1 alone certified the same
    4 of 40 dev tasks.
    """
    return os.environ.get("NOMAD_CASESPLIT", "on").strip().lower() == "depth2"


def enabled() -> bool:
    return os.environ.get("NOMAD_CASESPLIT", "on").strip().lower() not in ("off", "0", "false", "no")


def applicable(task) -> bool:
    from .world import OPSETS
    return task.out == "int" and "ite" in OPSETS.get(task.opset, ())


def _mask(bits: Iterable[bool]) -> int:
    m = 0
    for i, b in enumerate(bits):
        if b:
            m |= 1 << i
    return m


def _popcount(m: int) -> int:
    return bin(m).count("1")


def split_gen(entries: Sequence[tuple[int, list, tuple]], goal: tuple, rows: Sequence[dict],
              evals: int, max_eval: int, *, term_max: int = TERM_MAX, pred_max: int = PRED_MAX,
              depth2: bool | None = None):
    """Generator: yields once per charged evaluation, like the searches.

    ``entries``: (size, tree, public-row values) of int-typed programs from
    the cold stage, in enumeration order (sizes ascending). Returns
    ``(tree | None, evals, info)``. ``info`` has the depth found, charges by
    kind and the reason for a miss.
    """
    from .world import Invalid, run, type_of

    if depth2 is None:
        depth2 = depth2_enabled()

    n = len(goal)
    full = (1 << n) - 1
    info = {"terms": 0, "conditions": 0, "pairs": 0, "candidates": 0, "depth": None, "reason": None,
            "charged": 0}
    start = evals
    ents = [(sz, t, v) for sz, t, v in entries if len(v) == n and all(type_of(x) == "int" for x in v)]
    ents.sort(key=lambda e: e[0])  # stable: keeps enumeration order inside a size

    def finish(tree, reason=None):
        info["reason"] = reason
        info["charged"] = evals - start
        return tree, evals, info

    # ---- conditions: positivity mask on public rows, smallest program per mask
    preds: dict[int, tuple[int, list]] = {}
    for sz, t, v in ents:
        if sz > pred_max:
            break
        if evals >= max_eval:
            return finish(None, "candidate_budget")
        evals += 1
        info["conditions"] += 1
        yield evals
        p = _mask(x > 0 for x in v)
        if p in (0, full) or p in preds:
            continue
        preds[p] = (sz, t)
    if not preds:
        return finish(None, "no_condition")
    min_pred = min(s for s, _ in preds.values())

    # ---- terms: correctness mask; cover[R] = smallest term right on every row of R
    cover: list[tuple[int, list, int] | None] = [None] * (full + 1)

    def add_term(sz: int, t: list, m: int) -> None:
        sub = m
        while True:
            if cover[sub] is None:
                cover[sub] = (sz, t, m)
            if sub == 0:
                break
            sub = (sub - 1) & m

    def check(tree: list):
        """Run an assembled candidate on the public rows (1 evaluation)."""
        info["candidates"] += 1
        try:
            vals = tuple(run(tree, r) for r in rows)
        except Invalid:
            return False
        return vals == tuple(goal)

    def cands_depth1():
        out = []
        for p, (ps, pt) in preds.items():
            a, b = cover[p], cover[full & ~p]
            if a is None or b is None:
                continue
            supp = min(_popcount(p), _popcount(full & ~p))
            if supp < MIN_SUPPORT:
                continue
            out.append(((1 + ps + a[0] + b[0], -supp), p, ["ite", pt, a[1], b[1]]))
        out.sort(key=lambda c: c[0])
        return out

    def best_depth1():
        cs = cands_depth1()
        return (cs[0][0], cs[0][2]) if cs else None

    levels = sorted({sz for sz, _, _ in ents if sz <= term_max})
    i = 0
    for li, lv in enumerate(levels):
        while i < len(ents) and ents[i][0] < lv:
            i += 1
        while i < len(ents) and ents[i][0] == lv:
            sz, t, v = ents[i]
            i += 1
            if evals >= max_eval:
                return finish(None, "candidate_budget")
            evals += 1
            info["terms"] += 1
            yield evals
            m = _mask(a == g for a, g in zip(v, goal))
            if m and m != full:
                add_term(sz, t, m)
        best = best_depth1()
        if best is None:
            continue
        nxt = levels[li + 1] if li + 1 < len(levels) else None
        # Any candidate using a not-yet-seen term has total >= 1 + min_pred + 1 + nxt.
        if nxt is None or best[0][0] <= 1 + min_pred + 1 + nxt:
            if evals >= max_eval:
                return finish(None, "candidate_budget")
            evals += 1
            yield evals
            if check(best[1]):
                info["depth"] = 1
                return finish(best[1])
            return finish(None, "assembled_mismatch")  # defensive; cannot happen by construction

    if not depth2:
        return finish(None, "no_split")

    # ---- depth 2: one nested split on either branch
    plist = sorted(preds.items(), key=lambda kv: (kv[1][0], kv[0]))
    best = None
    for p1, (s1, c1) in plist:
        for p2, (s2, c2) in plist:
            if p2 == p1 or p2 == (full & ~p1):
                continue
            if evals >= max_eval:
                return finish(None, "candidate_budget")
            evals += 1
            info["pairs"] += 1
            yield evals
            q1 = full & ~p1
            for nest_else in (True, False):
                side, keep = (q1, p1) if nest_else else (p1, q1)
                r1, r2 = side & p2, side & ~p2 & full
                if not keep or not r1 or not r2:
                    continue
                k, a, b = cover[keep], cover[r1], cover[r2]
                if k is None or a is None or b is None:
                    continue
                inner = ["ite", c2, a[1], b[1]]
                tree = ["ite", c1, k[1], inner] if nest_else else ["ite", c1, inner, k[1]]
                total = 2 + s1 + s2 + k[0] + a[0] + b[0]
                supp = min(_popcount(keep), _popcount(r1), _popcount(r2))
                if supp < MIN_SUPPORT:
                    continue
                key = (total, -supp)
                if best is None or key < best[0]:
                    best = (key, tree)
    if best is None:
        return finish(None, "no_split")
    if evals >= max_eval:
        return finish(None, "candidate_budget")
    evals += 1
    yield evals
    if check(best[1]):
        info["depth"] = 2
        return finish(best[1])
    return finish(None, "assembled_mismatch")
