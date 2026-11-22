"""CLAUSE2: one concept per clause, paid only from savings, binding forward too (docs/CLAUSE2.md).

Switch ``NOMAD_CLAUSE2`` (default OFF). CLAUSE (docs/CLAUSE.md) certified 11 / 16 of its sealed suite
against 2 off, but a CLAUSE miss spent up to 512 evaluations *before* the normal search, so tasks the
normal search solved cost more (32 per-task evaluation increases). Its misses also showed that "the
average of the three ..." stories give the numbers in the NEXT clause, while CLAUSE only bound back.

CLAUSE2 keeps CLAUSE's reading (split, number binding, one concept per clause, compose
``B[slot := A]``) and changes two things.

1. **Budget neutral by construction (the ledger).** CLAUSE2 never runs before the normal search. A
   per-task *ledger* keeps every value a computation has already produced on the public rows, keyed
   exactly by what determines it: an input or constant atom, or ``(operator, the operand value
   vectors)`` (operands of a commutative operator in a fixed order). MEANING's stage records the node
   values of the instances it runs (each already charged 1 evaluation, as off). The normal search then
   runs **unchanged**, with the same order, pools, budget and charges: each candidate still costs it 1
   evaluation exactly as off, but when the ledger already holds that candidate's value it is read
   instead of recomputed, and the computation not done is one *credit*. CLAUSE2 runs in lockstep with
   the normal search (after each of its evaluations) and may compute a value the ledger does not hold
   only by spending one credit (a WITNESS rejection also costs one credit); a value the ledger already
   holds is read for free. When the normal search ends without a fit, CLAUSE2 may go on spending the
   credit left. Therefore:

   - the normal search's steps, program and reported evaluations are identical to off on every
     task (CLAUSE2 only reads and adds ledger values, which are exact);
   - computations actually performed <= evaluations reported (credits are computations the normal
     search was charged for and did not do; CLAUSE2 never spends more than it was credited);
   - a CLAUSE2 miss changes nothing that is reported: program, certification and evaluations equal
     off; a CLAUSE2 hit is returned at the normal search's current count, which is <= off's count.

2. **Forward binding.** A concept named in a clause with fewer quantities than its arity may borrow
   the numbers of the nearest numbered clauses *after* it first ("What is the average of the three?
   The loads are 12, 15 and 9."), as well as before it (CLAUSE's rule); both are candidates, ranked by
   the same arity-gap penalty. An outer concept named in a clause without numbers ranges over the
   inputs outside the inner concept's clause (CLAUSE's rule).

Learns nothing. Runs only with NOMAD_MEANING and NOMAD_CLAUSE2 on, a field holding a lexicon, a story
with numbers, and after MEANING's stage missed. Empty field: no lexicon, no ledger. Cold control: never
reads words. Final rows are never read (search holds only public and challenge rows; WITNESS is
consulted on challenge rows only).
"""
from __future__ import annotations

import math
import os
from typing import Any

from . import clause as _C1

CLAUSE2_K = 3          # inner concepts kept per clause (CLAUSE's dev value)
CLAUSE2_POOL = 8       # per-clause ranks considered before the arity penalty (CLAUSE's dev value)
CLAUSE2_EXT = 6        # rank penalty per unit of arity gap (CLAUSE's dev value)
CLAUSE2_FWD = 0        # extra rank penalty for the forward binding (dev-chosen)
CLAUSE2_MAPS = 360
CLAUSE2_REJECTS = 8
CLAUSE2_CAP = 512      # most credits the stage may spend on one task (dev-chosen)
INF = math.inf
_ERR = None            # filled lazily (world's exception set)


class _Inv:
    __slots__ = ()

    def __repr__(self) -> str:
        return "INVALID"


INVALID = _Inv()
LAST = None            # the most recent task's ledger (judges report its credits; never read by search)


def enabled() -> bool:
    return os.environ.get("NOMAD_CLAUSE2", "on").strip().lower() not in ("off", "0", "false", "no")   # default ON since the sealed PASS


def control() -> str:
    return os.environ.get("NOMAD_CLAUSE2_CONTROL", "").strip().lower()


def applicable(words: str) -> bool:
    return bool(words) and bool(_C1.numbers(words))


# ------------------------------------------------------------------ plan (free: no evaluation)

def pool(items: list[dict], i: int, arity: int, forward: bool = False) -> list[str]:
    """Inputs a concept named in clause ``i`` may bind: its own, then while fewer than ``arity`` those
    of the nearest numbered clauses, earlier ones first (CLAUSE) or, ``forward``, later ones first."""
    names = list(items[i]["inputs"])
    back, fwd = list(range(i - 1, -1, -1)), list(range(i + 1, len(items)))
    for k in (fwd + back if forward else back + fwd):
        if len(names) >= arity:
            break
        for n in items[k]["inputs"]:
            if n not in names:
                names.append(n)
    return sorted(names)


def plan(task: Any, prior: Any, words: str) -> dict:
    row0 = task.public[0][0]
    types = dict(task.inputs)
    cl = _C1.split(words)
    bound = [_C1.clause_inputs(text, row0) for text in cl]
    if control() == "rewire":
        # control: each clause gets the inputs of the next numbered clause (same retrieval, wrong binding)
        idx = [i for i, b in enumerate(bound) if b]
        rot = {i: bound[idx[(k + 1) % len(idx)]] for k, i in enumerate(idx)}
        bound = [rot.get(i, b) for i, b in enumerate(bound)]
    items = []
    for text, ins in zip(cl, bound):
        ranked = [(s, c) for s, c in _C1._retrieve(prior, text) if c in prior.concepts]
        items.append({"text": text, "inputs": ins, "ranked": ranked, "n": len(_C1.numbers(text))})
    for i, it in enumerate(items):
        n_i = it["n"]
        prev = next((items[k]["n"] for k in range(i - 1, -1, -1) if items[k]["inputs"]), 0)
        nxt = next((items[k]["n"] for k in range(i + 1, len(items)) if items[k]["inputs"]), 0)
        cand = []
        for r, (_s, c) in enumerate(it["ranked"][:CLAUSE2_POOL]):
            ar = len(prior.concepts[c]["types"])
            best: dict = {}
            for fwd in (False, True):
                pl = tuple(pool(items, i, ar, fwd))
                if not pl or not _C1._fits(prior.concepts[c], [(n, types[n]) for n in pl]):
                    continue
                # the quantities of the clauses the pool borrows from first: the previous numbered
                # clause (back) or the next one (forward); a clause with none on that side borrows
                # from the other side, so that side's count applies
                m = (nxt or prev) if fwd else (prev or nxt)
                gap = min(abs(ar - n_i), 1 + abs(ar - m), 1 + abs(ar - n_i - m))
                adj = r + CLAUSE2_EXT * gap + (CLAUSE2_FWD if fwd else 0)
                if pl not in best or adj < best[pl][0]:
                    best[pl] = (adj, int(fwd))
            for pl, (adj, f) in best.items():
                cand.append((adj, r, f, c, pl))
        cand.sort()
        it["inner"] = [(c, pl) for _a, _r, _f, c, pl in cand[:CLAUSE2_K]]
        it["adj"] = {(c, pl): a for a, _r, _f, c, pl in cand[:CLAUSE2_K]}
        it["outer"] = [c for _s, c in it["ranked"] if prior.concepts[c].get("out", "int") == task.out][:CLAUSE2_K]
    pairs = []
    for i, ci in enumerate(items):
        for j, cj in enumerate(items):
            if i == j:
                continue
            for a, apl in ci["inner"]:
                for rb, b in enumerate(cj["outer"]):
                    for slot in sorted(prior.concepts[b]["types"]):
                        if prior.concepts[b]["types"][slot] != prior.concepts[a].get("out", "int"):
                            continue
                        pairs.append((ci["adj"][(a, apl)] + rb, rb, i, j, a, apl, b, slot))
    pairs.sort()
    return {"clauses": items, "pairs": pairs}


# ------------------------------------------------------------------ the ledger

class _Hit(Exception):
    pass


class Ledger:
    """Per-task values already computed on the public rows, the credits they earn, and CLAUSE2's search."""

    def __init__(self, task: Any, prior: Any, words: str):
        self.task, self.prior, self.words = task, prior, words
        self.rows = [r for r, _e in task.public]
        self.goal = tuple(e for _r, e in task.public)
        self.memo: dict = {}
        self.credit = 0      # computations main was charged for and read from the ledger, not yet spent
        self.banked = 0      # all credits earned
        self.spent = 0       # credits CLAUSE2 spent (new computations + WITNESS rejections)
        self.gen = None
        self.pending = False
        self.done = False
        self.result = None
        self.info: dict = {}
        global LAST
        LAST = self

    # keys -----------------------------------------------------------
    @staticmethod
    def _leaf_key(tree: list):
        if tree[0] == "var":
            return ("var", tree[1])
        if tree[0] == "const":
            return ("const", int(tree[1]))
        return None

    @staticmethod
    def _node_key(name: str, comm: bool, kids: tuple):
        if comm and len(kids) == 2 and repr(kids[0]) > repr(kids[1]):
            kids = (kids[1], kids[0])
        return (name, kids)

    # main's hooks (world._search_gen / _staged_gen): identical values, credits on reads ------------
    def leaf(self, tree: list, compute):
        from .world import Invalid
        k = self._leaf_key(tree)
        if k is None:
            return compute()
        if k in self.memo:
            self.credit += 1
            self.banked += 1
            v = self.memo[k]
            if v is INVALID:
                raise Invalid
            return v
        try:
            v = compute()
        except Invalid:
            self.memo[k] = INVALID
            raise
        self.memo[k] = v
        return v

    def node(self, name: str, comm: bool, kids: tuple, compute):
        from .world import Invalid
        k = self._node_key(name, comm, kids)
        if k in self.memo:
            self.credit += 1
            self.banked += 1
            v = self.memo[k]
            if v is INVALID:
                raise Invalid
            return v
        try:
            v = compute()
        except (Invalid, ValueError, TypeError, IndexError, OverflowError):
            self.memo[k] = INVALID
            raise Invalid
        self.memo[k] = v
        return v

    # values computed node by node (exactly run's semantics), recorded --------------------------
    def _veval(self, tree: list, paid: bool, depth: int = 0):
        """Generator: the public-row values of ``tree`` (tuple), or raises Invalid. Yields once per
        value the ledger does not hold when ``paid`` (CLAUSE2 pays one credit per yield)."""
        from .world import OPS, Invalid, type_of
        if depth > 64:
            raise Invalid
        tag = tree[0]
        if tag in ("var", "const"):
            k = self._leaf_key(tree)
            if k not in self.memo:
                if paid:
                    yield 1
                if tag == "var":
                    v = (tuple(r[tree[1]] for r in self.rows) if all(tree[1] in r for r in self.rows) else INVALID)
                else:
                    v = tuple(int(tree[1]) for _ in self.rows)
                self.memo[k] = v
            v = self.memo[k]
            if v is INVALID:
                raise Invalid
            return v
        op = OPS.get(tag)
        if op is None or len(tree) - 1 != len(op.args):
            raise Invalid
        kids = []
        for c in tree[1:]:
            kv = yield from self._veval(c, paid, depth + 1)
            kids.append(kv)
        for kv, t in zip(kids, op.args):
            if any(type_of(a) != t for a in kv):
                raise Invalid          # run: argument of the wrong type (not recorded)
        k = self._node_key(tag, op.commutative, tuple(kids))
        if k not in self.memo:
            if paid:
                yield 1
            try:
                v = tuple(op.fn(*args) for args in zip(*kids))
            except (Invalid, ValueError, TypeError, IndexError, OverflowError):
                v = INVALID
            self.memo[k] = v
        v = self.memo[k]
        if v is INVALID:
            raise Invalid
        return v

    def record(self, inst: list) -> list:
        """MEANING's evaluation of one instance (charged 1 by MEANING, as off): run's values, recorded."""
        from .world import run, subtrees
        if any(s[0] == "lib" for s in subtrees(inst)):
            return [run(inst, r) for r in self.rows]
        g = self._veval(inst, False)
        try:
            while True:
                next(g)
        except StopIteration as st:
            return list(st.value)

    # the lockstep driver -------------------------------------------------------------------
    def _advance(self):
        """Run CLAUSE2 while it can (free reads; new values while credit lasts). A hit or None."""
        if self.done:
            return None
        if self.gen is None:
            self.gen = self._search()
        while True:
            if self.pending:
                if self.credit < 1 or self.spent >= CLAUSE2_CAP:
                    return None
                self.credit -= 1
                self.spent += 1
                self.pending = False
            try:
                next(self.gen)
            except StopIteration as st:
                self.done = True
                self.result = st.value
                return st.value
            self.pending = True

    def drive(self, g, order: tuple):
        """Main's generator, unchanged, with CLAUSE2 advanced after each of main's evaluations."""
        from .world import Search
        count = 0
        while True:
            try:
                y = next(g)
            except StopIteration as stop:
                return stop.value
            if isinstance(y, int) and not isinstance(y, bool):
                count = y
            hit = self._advance()
            if hit is not None:
                g.close()
                self.info.update(at=count, phase="lockstep")
                return Search(hit[1], count, None, order, [], "clause2:" + hit[0])

    def drain(self, s):
        """After main (and anything synthesize runs after it) ended without a fit: the credit left.
        The reported count stays main's."""
        from .world import Search
        if s.tree is not None:
            return s
        hit = self._advance()
        if hit is None:
            return s
        self.info.update(at=s.evaluations, phase="after_miss")
        return Search(hit[1], s.evaluations, None, s.order, [], "clause2:" + hit[0],
                      s.variation, s.casesplit, s.sense, s.witness)

    # CLAUSE2's search (a generator; one yield = one credit) --------------------------------
    def _search(self):
        from . import combine as C
        from . import meaning as _meaning
        from .world import Invalid, _rename, consult
        from types import SimpleNamespace
        task, prior = self.task, self.prior
        pl = plan(task, prior, self.words)
        items, pairs = pl["clauses"], pl["pairs"]
        self.info.update(clauses=len(items), pairs=len(pairs))
        types = dict(task.inputs)
        all_inputs = [n for n, _t in task.inputs]
        seen: set = set()
        inner_cache: dict = {}
        rejects = 0
        goal = self.goal

        def sub_task(names):
            return SimpleNamespace(inputs=[(n, types[n]) for n in names])

        def inner(c, apl):
            key = (c, apl)
            if key in inner_cache:
                return inner_cache[key]
            rec, out, keys = prior.concepts[c], [], set()
            for m in _meaning._maps(rec["types"], sub_task(list(apl)))[:CLAUSE2_MAPS]:
                inst = _rename(rec["tree"], m)
                k = _meaning._comm_key(inst)
                if k in keys:
                    continue
                keys.add(k)
                out.append((frozenset(m.values()), inst))
            inner_cache[key] = out
            return out

        def bounds(partial):
            """Per-row interval the slot must lie in (None = any), from sibling values (paid like any
            value) and exact interval arithmetic on them (free, like world._redundant)."""
            path = []
            node = partial
            while node[0] != "var":
                kids = node[1:]
                i = next(k for k, c in enumerate(kids) if C._count(c, "__slot__"))
                if len(kids) != 2 or node[0] not in ("add", "sub", "mul", "div"):
                    path.append((node[0], i, None))
                    break
                y = yield from self._veval(kids[1 - i], True)
                path.append((node[0], i, y))
                node = kids[i]
            out = []
            for r in range(len(goal)):
                lo, hi = goal[r], goal[r]
                free = False
                for opn, i, y in path:
                    if y is None:
                        free = True
                        break
                    yv = y[r]
                    if lo > hi:
                        raise C._Empty
                    if opn == "add":
                        lo, hi = lo - yv, hi - yv
                    elif opn == "sub":
                        lo, hi = (lo + yv, hi + yv) if i == 0 else (yv - hi, yv - lo)
                    elif opn == "mul":
                        if yv == 0:
                            if lo <= 0 <= hi:
                                free = True
                                break
                            raise C._Empty
                        a, b = sorted((lo / yv, hi / yv))
                        lo, hi = C._ceil(a), C._floor(b)
                    else:   # floor division, slot in the dividend
                        if i != 0 or yv == 0:
                            free = True
                            break
                        if yv > 0:
                            lo, hi = (lo * yv if lo != -INF else -INF), (hi * yv + yv - 1 if hi != INF else INF)
                        else:
                            lo, hi = ((hi + 1) * yv + 1 if hi != INF else -INF), (lo * yv if lo != -INF else INF)
                if free:
                    out.append(None)
                    continue
                if lo > hi:
                    raise C._Empty
                out.append((lo, hi))
            return out

        for _s, _rb, i, j, a_key, apl, b_key, slot in pairs:
            self.info["pairs_tried"] = self.info.get("pairs_tried", 0) + 1
            A = inner(a_key, apl)
            if not A:
                continue
            b = prior.concepts[b_key]
            once = C._count(b["tree"], slot) == 1
            others = {v: t for v, t in b["types"].items() if v != slot}
            bpool = (pool(items, j, len(others)) if items[j]["inputs"]
                     else [n for n in all_inputs if n not in items[i]["inputs"]])
            bkeys: set = set()
            for m in _meaning._maps(others, sub_task(bpool))[:CLAUSE2_MAPS]:
                partial = _rename(b["tree"], dict(m, **{slot: "__slot__"}))
                k = _meaning._comm_key(partial)
                if k in bkeys:
                    continue
                bkeys.add(k)
                used = frozenset(m.values())
                bd = None
                if once:
                    try:
                        bd = yield from bounds(partial)
                    except (C._Empty, Invalid):
                        continue
                for a_used, a_tree in A:
                    if a_used & used:
                        continue
                    try:
                        vec = yield from self._veval(a_tree, True)
                    except Invalid:
                        continue
                    if bd is not None and not all(x is None or x[0] <= v <= x[1] for x, v in zip(bd, vec)):
                        continue
                    inst = C._subst(partial, "__slot__", a_tree)
                    ck = _meaning._comm_key(inst)
                    if ck in seen:
                        continue
                    seen.add(ck)
                    try:
                        vals = yield from self._veval(inst, True)
                    except Invalid:
                        continue
                    if vals != goal:
                        continue
                    receipt = consult(task, inst)   # INTEGRITY: challenge rows only, never final
                    if receipt is not None and receipt.supported:
                        self.info["rejected"] = rejects
                        return (f"{b_key}[{slot}:={a_key}]", inst)
                    rejects += 1
                    yield 1                          # a WITNESS rejection costs one credit
                    if rejects >= CLAUSE2_REJECTS:
                        self.info["rejected"] = rejects
                        return None
        self.info["rejected"] = rejects
        return None
