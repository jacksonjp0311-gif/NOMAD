"""DISCRIM: active distinguishing experiments (docs/DISCRIM.md).

When several distinct programs fit all the observed evidence (the public and challenge rows, i.e. exactly
what WITNESS reads), the data cannot tell them apart. DISCRIM does not commit to the first one: it builds
**distinguishing inputs** deterministically from the task's input domain, runs every surviving candidate
on them, and groups the candidates by behavior. A fit is *confirmed* when no surviving alternative
disagrees with it there; otherwise the evidence is *ambiguous* and the caller keeps searching.

No leakage: everything here reads only ``task.inputs`` (names and types) and the rows of ``task.public``
and ``task.challenge`` (the WITNESS evidence). ``task.final`` is never read: the functions take the
evidence rows as arguments, never the task's final split, and ``evidence()`` builds them from the public
and challenge splits only (tests/test_discrim.py checks that a task whose final rows are poisoned gives
byte-identical results).

Pure functions, deterministic (no hash-seed dependence: the generator's state is a sha256 of the
evidence inputs), CPU only.
"""
from __future__ import annotations

import hashlib
import json
import os

from .world import MAX_INT, Invalid, run, size, type_of

DISCRIM_N = 24        # distinguishing rows built per task (swap / recombined / spread)
DISCRIM_ALT = 48      # most alternatives checked against the evidence per decision
DISCRIM_CONSTS = (0, 1, 2, 3)


def enabled() -> bool:
    """NOMAD_DISCRIM (default off until its sealed judge passes)."""
    return os.environ.get("NOMAD_DISCRIM", "off").strip().lower() not in ("off", "0", "false", "no")


def evidence(task) -> list[tuple[dict, object]]:
    """The WITNESS evidence: public + challenge rows (never the final split)."""
    return list(task.public) + list(task.challenge)


def _rng(seed: bytes):
    """A tiny deterministic generator (sha256 counter mode)."""
    i = 0
    while True:
        h = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        for j in range(0, 32, 4):
            yield int.from_bytes(h[j:j + 4], "big")
        i += 1


def rows(inputs, ev_rows, n: int = DISCRIM_N) -> list[dict]:
    """Distinguishing inputs from the task's input domain (inputs = ((name, type), ...); ev_rows = the
    evidence rows). Three kinds, in this order, deduplicated and never equal to an evidence row:

    1. swaps: an evidence row with the values of two same-typed inputs exchanged (tests an implicit
       order between inputs that the evidence happens to satisfy, e.g. max(a, b) = a);
    2. recombinations: each input's value taken from a different evidence row (keeps every input's
       observed values, breaks correlations the evidence happens to have);
    3. spread: int inputs drawn from the pooled range of all observed int values (low to high).
    """
    names = [nm for nm, _t in inputs]
    seen = {json.dumps([r.get(k) for k in names], default=str) for r, _e in ev_rows}
    src = [dict(r) for r, _e in ev_rows]
    out: list[dict] = []

    def push(r: dict) -> bool:
        k = json.dumps([r.get(x) for x in names], default=str)
        if k in seen:
            return False
        seen.add(k)
        out.append(r)
        return len(out) >= n

    if not src:
        return out
    seed = hashlib.sha256(json.dumps([[r.get(k) for k in names] for r in src], default=str).encode()).digest()
    g = _rng(seed)
    third = max(1, n // 3)
    # 1. swaps
    pairs = [(a, b) for i, (a, ta) in enumerate(inputs) for (b, tb) in inputs[i + 1:] if ta == tb]
    k = 0
    for r in src:
        for a, b in pairs:
            if r[a] == r[b]:
                continue
            s = dict(r)
            s[a], s[b] = r[b], r[a]
            if push(s):
                return out
            k += 1
            if k >= third:
                break
        if k >= third:
            break
    # 2. recombinations
    lim = len(out) + third
    for _ in range(4 * third):
        r = {nm: src[next(g) % len(src)][nm] for nm in names}
        if push(r) or len(out) >= lim:
            break
    # 3. spread (int inputs only; other inputs recombined)
    ints = [r[nm] for r in src for nm, t in inputs if t == "int" and type_of(r[nm]) == "int"]
    if ints:
        lo, hi = min(ints), max(ints)
        for _ in range(4 * n):
            r = {}
            for nm, t in inputs:
                if t == "int":
                    r[nm] = lo + next(g) % (hi - lo + 1)
                else:
                    r[nm] = src[next(g) % len(src)][nm]
            if push(r):
                break
    return out


def signature(tree: list, drows: list[dict]) -> tuple:
    """The candidate's values on the distinguishing rows (None where it is invalid or out of range)."""
    sig = []
    for r in drows:
        try:
            v = run(tree, r)
        except Invalid:
            v = None
        if type_of(v) == "int" and abs(v) > MAX_INT:
            v = None
        sig.append(v)
    return tuple(sig)


def disagree(a: tuple, b: tuple) -> bool:
    """Two candidates disagree when some distinguishing row gives both a valid, different value."""
    return any(x is not None and y is not None and x != y for x, y in zip(a, b))


def fits(tree: list, ev_rows) -> bool:
    """WITNESS's own bar (receipt.supported): every evidence row reproduced exactly."""
    try:
        return all(run(tree, r) == e for r, e in ev_rows)
    except Invalid:
        return False


def _replace(tree: list, path: tuple, new: list) -> list:
    if not path:
        return new
    i = path[0]
    return tree[:i] + [_replace(tree[i], path[1:], new)] + tree[i + 1:]


def _paths(tree: list, p: tuple = ()):
    yield p, tree
    if tree[0] not in ("var", "const", "lib"):
        for i, c in enumerate(tree[1:], 1):
            yield from _paths(c, p + (i,))


def simplifications(tree: list, inputs, ev_rows) -> list[list]:
    """Alternatives the evidence cannot rule out by itself: one sub-program replaced by a strictly smaller
    one (one of its own children, an input, or a constant 0-3) that has the same values on every evidence
    row. Each such alternative fits the evidence exactly as well as ``tree`` (it is a different explanation
    of the same observations)."""
    rs = [r for r, _e in ev_rows]
    atoms = [["var", nm] for nm, _t in inputs] + [["const", c] for c in DISCRIM_CONSTS]
    out, keys = [], {json.dumps(tree)}
    for path, sub in _paths(tree):
        if sub[0] in ("var", "const", "lib") or not path:
            continue
        try:
            sv = [run(sub, r) for r in rs]
        except Invalid:
            continue
        sz = size(sub)
        for rep in list(sub[1:]) + atoms:
            if size(rep) >= sz:
                continue
            try:
                if [run(rep, r) for r in rs] != sv:
                    continue
            except Invalid:
                continue
            alt = _replace(tree, path, rep)
            k = json.dumps(alt)
            if k not in keys:
                keys.add(k)
                out.append(alt)
    return out


def decide(hit: list, alts: list[list], inputs, ev_rows) -> dict:
    """The distinguishing experiment for one accepted fit.

    ``alts``: other candidate programs (already known to fit the evidence, or checked here). Returns
    {"verdict": "confirmed" | "ambiguous", "survivors": n, "agree": n, "disagree": n, "rows": n}.
    Confirmed: no surviving alternative disagrees with ``hit`` on the distinguishing inputs."""
    mode = rows_mode()
    drows = [dict(r) for r, _e in ev_rows] if mode == "evidence" else rows(inputs, ev_rows)
    hs = signature(hit, drows)
    agree = dis = 0
    for a in alts[:DISCRIM_ALT]:
        if not fits(a, ev_rows):
            continue
        sa = signature(a, drows)
        if mode == "shuffled" and sa:
            sa = sa[1:] + sa[:1]     # control: the alternative's outcomes compared on the wrong rows
        if disagree(hs, sa):
            dis += 1
        else:
            agree += 1
    out = {"verdict": "ambiguous" if dis else "confirmed", "survivors": agree + dis,
           "agree": agree, "disagree": dis, "rows": len(drows), "pick": None}
    if dis and pick_mode() == "mdl":
        out["pick"] = mdl_pick(hit, [a for a in alts[:DISCRIM_ALT] if fits(a, ev_rows)], drows)
    return out


def pick_mode() -> str:
    """What an ambiguous decision returns: "mdl" (the strictly smallest surviving explanation, when it is
    unique in size and agrees with every other survivor of its size or smaller; docs/DISCRIM.md) or
    "fall" (nothing: the caller keeps searching). Chosen on dev suites only."""
    return os.environ.get("NOMAD_DISCRIM_PICK", DISCRIM_PICK).strip().lower()


DISCRIM_PICK = "mdl"


def mdl_pick(hit: list, surv: list[list], drows: list[dict]) -> list | None:
    """Occam on an ambiguous decision: the candidate with the fewest nodes among the hit and its surviving
    alternatives, only when it is strictly smaller than every candidate that disagrees with it on the
    distinguishing inputs (otherwise None)."""
    cands = [hit] + surv
    best = min(cands, key=size)
    bs = signature(best, drows)
    for c in cands:
        if c is best:
            continue
        sc = signature(c, drows)
        if rows_mode() == "shuffled" and sc:
            sc = sc[1:] + sc[:1]
        if disagree(bs, sc) and size(c) <= size(best):
            return None
    return best


def rows_mode() -> str:
    """Judge-only controls (docs/DISCRIM.md): "domain" (default, the distinguishing inputs), "evidence"
    (blind: the experiment reuses the evidence rows, so it can never disagree) or "shuffled" (each
    alternative's outcomes are compared on the wrong distinguishing rows)."""
    return os.environ.get("NOMAD_DISCRIM_ROWS", "domain").strip().lower()


TRACE: list = []   # filled only when NOMAD_DISCRIM_TRACE is set (dev diagnostics; never read by search)


def note(task, hit, surv, d) -> None:
    if os.environ.get("NOMAD_DISCRIM_TRACE"):
        TRACE.append({"task": task.task_id, "hit": hit, "survivors": surv, **d})
        print("DISCRIM", task.task_id, json.dumps(hit), d, [json.dumps(a) for a in surv][:6], flush=True)
