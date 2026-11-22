"""CLAUSE: one concept per clause (docs/CLAUSE.md). Switch ``NOMAD_CLAUSE`` (default OFF).

MEANING retrieves a concept from the whole story's bag of words; COMBINE composes pairs of those
whole-story concepts and ranks the pairs by rank sum. Both FAILed on stories that chain two ideas,
for the same reason: retrieval of the whole story is dominated by one idea, so the other (often the
generic "times", "boxes", "average") is not in the top ten and the right pair is reached too late.
CLAUSE reads the story the way a person does, clause by clause:

1. **Split** the story at sentence ends, ``;`` ``:`` and commas (a comma between two numbers is
   part of a list: "30, 7 and 5").
2. **Number binding**: every number in a clause is linked to the input(s) holding that value on
   the first public row (a value two inputs share binds to both; same rule as ROLES).
3. **One concept per clause**: each clause's own tokens retrieve concepts from MEANING's lexicon
   (same scoring, ``CLAUSE_K`` per clause). A clause with numbers can supply an *inner* concept A
   whose variables are renamed over only that clause's inputs; any clause can supply the *outer*
   concept B (output type = the goal's), whose other variables range over its own clause's inputs
   (a question clause with no numbers: every input A does not use).
4. **Compose** ``B[slot := A]`` for clause pairs i != j in order of the sum of the two per-clause
   ranks, with COMBINE's exact interval inversion, WITNESS-gated through ``consult`` (challenge
   rows only). A rejection costs 1 evaluation, at most ``CLAUSE_REJECTS``; the stage spends at most
   ``CLAUSE_BUDGET`` evaluations; on a miss the normal search runs unchanged on the rest.

Runs only after MEANING's stage misses, only with NOMAD_MEANING and NOMAD_CLAUSE on and a field
holding a lexicon, and only on a story that contains numbers (the clause binding needs them; a
description without numbers costs nothing). Learns nothing. Empty field: no lexicon, no stage.
Cold control: never reads words. Final and challenge rows are never read here.
"""
from __future__ import annotations

import math
import os
import re
from types import SimpleNamespace
from typing import Any

CLAUSE_K = 3          # concepts retrieved per clause (dev-chosen)
CLAUSE_BUDGET = 512   # most evaluations the stage spends (dev-chosen)
CLAUSE_MAPS = 360
CLAUSE_POOL = 8       # per-clause ranks considered before the arity penalty
CLAUSE_EXT = 6        # rank penalty when an inner concept must borrow numbers from other clauses (dev-chosen)
CLAUSE_REJECTS = 8
INF = math.inf


def enabled() -> bool:
    return os.environ.get("NOMAD_CLAUSE", "off").strip().lower() in ("on", "1", "true", "yes")


def split(text: str) -> list[str]:
    """Clauses of a story: split at . ? ! ; : and at commas that do not join two numbers."""
    out, cur, n = [], [], len(text)
    for i, ch in enumerate(text):
        if ch in ".?!;:" and not (ch == "." and 0 < i < n - 1 and text[i - 1].isdigit() and text[i + 1].isdigit()):
            out.append("".join(cur))
            cur = []
        elif ch == ",":
            nxt = text[i + 1:].lstrip()[:1]
            if i > 0 and text[i - 1].isdigit() and nxt.isdigit():
                cur.append(ch)
            else:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [c.strip() for c in out if c.strip()]


def numbers(clause: str) -> list[int]:
    return [int(x) for x in re.findall(r"(?<![\w.])\d+(?![\w])", clause)]


def clause_inputs(clause: str, row: dict) -> list[str]:
    """Inputs holding the clause's numbers on one public row (sorted, de-duplicated)."""
    got: set[str] = set()
    for v in numbers(clause):
        got.update(k for k, x in row.items() if x == v)
    return sorted(got)


def _retrieve(prior: Any, text: str, need_types: dict | None = None) -> list[tuple[float, str]]:
    from . import meaning as M
    n = max(1, len(prior.concepts))
    score: dict[str, float] = {}
    for t in M.tokens(text):
        row = prior.lexicon.get(t)
        if not row:
            continue
        tot = sum(row.values())
        if tot <= 0:
            continue
        idf = math.log(1.0 + n / len(row))
        for c, v in row.items():
            score[c] = score.get(c, 0.0) + (v / tot) * idf
    ranked = []
    for c, sc in score.items():
        rec = prior.concepts.get(c)
        if rec is None:
            continue
        ranked.append((-sc, -float(rec.get("uses", 0.0)), c))
    ranked.sort()
    return [(-z[0], z[2]) for z in ranked]


def _fits(rec: dict, inputs: list[tuple[str, str]]) -> bool:
    need: dict[str, int] = {}
    for ty in rec["types"].values():
        need[ty] = need.get(ty, 0) + 1
    have: dict[str, int] = {}
    for _n, ty in inputs:
        have[ty] = have.get(ty, 0) + 1
    return all(have.get(ty, 0) >= k for ty, k in need.items())


def pool(items: list[dict], i: int, arity: int) -> list[str]:
    """Inputs a concept named in clause ``i`` may bind: the clause's own, and while fewer than
    ``arity``, those of the nearest numbered clauses (earlier ones first: "the average of the
    three" refers back to the numbers just given)."""
    names = list(items[i]["inputs"])
    order = list(range(i - 1, -1, -1)) + list(range(i + 1, len(items)))
    for k in order:
        if len(names) >= arity:
            break
        for n in items[k]["inputs"]:
            if n not in names:
                names.append(n)
    return sorted(names)


def plan(task: Any, prior: Any, words: str) -> dict:
    """Free (no evaluation): clauses, their inputs, per-clause concepts, and the ordered pairs."""
    row0 = task.public[0][0]
    types = dict(task.inputs)
    cl = split(words)
    items = []
    bound = [clause_inputs(text, row0) for text in cl]
    if os.environ.get("NOMAD_CLAUSE_CONTROL", "").strip().lower() == "rewire":
        # control: each clause gets the inputs of the next numbered clause (same retrieval, wrong binding)
        idx = [i for i, b in enumerate(bound) if b]
        rot = {i: bound[idx[(k + 1) % len(idx)]] for k, i in enumerate(idx)}
        bound = [rot.get(i, b) for i, b in enumerate(bound)]
    for text, ins in zip(cl, bound):
        sub = [(n, types[n]) for n in ins]
        ranked = [(s, c) for s, c in _retrieve(prior, text) if c in prior.concepts]
        items.append({"text": text, "inputs": ins, "sub": sub, "ranked": ranked})
    for i, it in enumerate(items):   # inner candidates: any clause; its concept binds the clause's (or nearby) numbers
        n_i = len(numbers(it["text"]))
        prev = next((len(numbers(items[k]["text"])) for k in range(i - 1, -1, -1) if items[k]["inputs"]), 0)
        cand = []
        for r, (_s, c) in enumerate(it["ranked"][:CLAUSE_POOL]):
            ar = len(prior.concepts[c]["types"])
            pl = pool(items, i, ar)
            if pl and _fits(prior.concepts[c], [(n, types[n]) for n in pl]):
                # penalty: how far the concept's arity is from the clause's own quantities, or from
                # the quantities of the clause before it (a concept named after its numbers were given)
                gap = min(abs(ar - n_i), 1 + abs(ar - prev), 1 + abs(ar - n_i - prev))
                cand.append((r + CLAUSE_EXT * gap, r, c))
        cand.sort()
        it["inner"] = [c for _a, _r, c in cand[:CLAUSE_K]]
        it["adj"] = {c: a for a, _r, c in cand[:CLAUSE_K]}
        it["outer"] = [c for _s, c in it["ranked"] if prior.concepts[c].get("out", "int") == task.out][:CLAUSE_K]
    pairs = []
    for i, ci in enumerate(items):
        for j, cj in enumerate(items):
            if i == j:
                continue
            for a in ci["inner"]:
                for rb, b in enumerate(cj["outer"]):
                    for slot in sorted(prior.concepts[b]["types"]):
                        if prior.concepts[b]["types"][slot] != prior.concepts[a].get("out", "int"):
                            continue
                        pairs.append((ci["adj"][a] + rb, rb, i, j, a, b, slot))
    pairs.sort()
    return {"clauses": items, "pairs": pairs}


def stage(task: Any, prior: Any, words: str, *, max_eval: int | None = None) -> tuple[tuple[str, list] | None, int, dict]:
    """Per-clause concepts composed, after a MEANING miss. ((label, tree) | None, evaluations, info)."""
    from . import combine as C
    from . import meaning as _meaning
    from .world import Invalid, _rename, consult, run
    budget = CLAUSE_BUDGET if max_eval is None else min(CLAUSE_BUDGET, max_eval)
    info: dict = {"clauses": 0, "pairs": 0, "rejected": 0}
    if not numbers(words):
        return None, 0, info
    pl = plan(task, prior, words)
    items, pairs = pl["clauses"], pl["pairs"]
    info.update(clauses=len(items), pairs=len(pairs), retrieved=[it["inner"] + it["outer"] for it in items])
    rows = [r for r, _e in task.public]
    goal = [e for _r, e in task.public]
    all_inputs = [n for n, _t in task.inputs]
    types = dict(task.inputs)
    st = {"evals": 0, "rejects": 0}
    seen: set[str] = set()
    inner_cache: dict[tuple, list] = {}

    class _Out(Exception):
        pass

    def pay():
        if st["evals"] >= budget:
            raise _Out
        st["evals"] += 1

    def sub_task(names):
        return SimpleNamespace(inputs=[(n, types[n]) for n in names])

    def inner(c: str, i: int) -> list:
        key = (c, i)
        if key in inner_cache:
            return inner_cache[key]
        rec, out, keys = prior.concepts[c], [], set()
        inner_cache[key] = out
        for m in _meaning._maps(rec["types"], sub_task(pool(items, i, len(rec["types"]))))[:CLAUSE_MAPS]:
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

    try:
        for _s, _rb, i, j, a_key, b_key, slot in pairs:
            info['pairs_tried'] = info.get('pairs_tried', 0) + 1
            A = inner(a_key, i)
            if not A:
                continue
            b = prior.concepts[b_key]
            once = C._count(b["tree"], slot) == 1
            others = {v: t for v, t in b["types"].items() if v != slot}
            bpool = (pool(items, j, len(others)) if items[j]["inputs"]
                     else [n for n in all_inputs if n not in items[i]["inputs"]])
            bkeys: set[str] = set()
            for m in _meaning._maps(others, sub_task(bpool))[:CLAUSE_MAPS]:
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
                        bounds = [C._invert(partial, "__slot__", e, e, r) for r, e in zip(rows, goal)]
                    except (C._Empty, Invalid):
                        continue
                for a_used, a_tree, vec in A:
                    if a_used & used:
                        continue
                    if bounds is not None and not all(bd is None or bd[0] <= v <= bd[1] for bd, v in zip(bounds, vec)):
                        continue
                    inst = C._subst(partial, "__slot__", a_tree)
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
                    if st["rejects"] >= CLAUSE_REJECTS:
                        raise _Out
    except _Out:
        pass
    info["rejected"] = st["rejects"]
    return None, st["evals"], info
