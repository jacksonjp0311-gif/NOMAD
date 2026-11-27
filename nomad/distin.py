"""DISTIN: a budget-neutral LET2 guarded by refutation on in-domain distinguishing inputs (docs/DISTIN.md).

LET2 (docs/LET2.md) found real gains (its sealed suite 9 -> 13) and lost certifications elsewhere: a let fit
that reproduced every public and challenge row was wrong on the final rows. Three guards were tried:

- DISCRIM (veto by a disagreeing alternative) on *swapped / recombined / spread* inputs: its remaining loss
  (``cl_h_rafts``, ``t // 2 - t // 3`` for ``ceil(t / 6)``) had no alternative at all, so it was "confirmed"
  vacuously; and it was not budget-neutral (48 losses).
- AGREE (positive support, budget-neutral): zero losses, but most correct let fits have no second derivation,
  so it kept none of LET2's sealed gain.
- CERT (evidence-mined properties, positive verification): the good let fits had no adoptable property, so
  nothing could be verified.

DISTIN keeps AGREE's budget-neutral frame and alternative set, and changes two things:

1. **Where it asks.** The distinguishing inputs come from the task's own declared structure, not from
   swaps: CERT's in-domain rows (each int input inside its observed range, a constant column held at its
   constant, a pair ordering that holds on every evidence row kept, one input at a time moved to the
   arithmetic edges of its base row: modulus block edges, range ends, neighbors, ties). Swapping a count
   with a size asks a question the task never poses; rivals that disagree only there are spurious.
2. **What decides.** Refutation instead of positive support. The hit returns early unless it is refuted:
   - ``rival``: an evidence-consistent alternative (independent, or an evidence-preserving simplification)
     disagrees with the hit on an in-domain row, and the largest class of mutually agreeing rivals is at
     least as large as the hit's class (the hit and its independent supporters): the evidence is ambiguous
     exactly where the task's own inputs live;
   - ``relation``: the hit breaks a metamorphic relation the evidence rows adopt (``mono``: output
     monotone in an input over the evidence; ``bound``: |out - x| stays within the evidence's own largest
     deviation + 2) on an in-domain sweep. CERT's ``mod`` property is not used (input-residue coincidences
     make it veto true functions; docs/CERT.md).
   A refuted hit is a miss, and a miss is identical to off (docs/AGREE.md's budget guarantee).

No leakage: only ``task.inputs`` and the public + challenge rows are read. Deterministic, CPU only, pure.
"""
from __future__ import annotations

import os

from . import cert as _C
from . import discrim as _D
from .world import size

DISTIN_MIN_ROWS = 4     # in-domain rows on which hit and a supporter must both be valid (and equal)
RELATIONS = ("mono", "bound")


def enabled() -> bool:
    """NOMAD_DISTIN (default off until its sealed judge passes)."""
    return os.environ.get("NOMAD_DISTIN", "off").strip().lower() not in ("off", "0", "false", "no")


def control() -> str:
    """Judge-only controls: "" | "shuffled" (alternatives' and relation outcomes compared on the wrong
    in-domain rows, rotated by one) | "rewired" (alternatives and relations evaluated on rows whose int
    inputs are rotated and incremented by one: the wrong question)."""
    return os.environ.get("NOMAD_DISTIN_CONTROL", "").strip().lower()


def _rewire(inputs, grows):
    ints = [nm for nm, t in inputs if t == "int"]
    out = []
    for r in grows:
        s = dict(r)
        for i, nm in enumerate(ints):
            s[nm] = r[ints[(i + 1) % len(ints)]] + 1
        out.append(s)
    return out


def drows(inputs, ev_rows) -> list[dict]:
    """The in-domain distinguishing inputs (CERT's generator), each tagged with its sweep."""
    return _C.rows(inputs, ev_rows)


def _strip(rows):
    return [{k: v for k, v in r.items() if k != "_sweep"} for r in rows]


def regroupings(tree) -> list[list]:
    """Rivals the evidence may not separate from ``tree``: the floor division moved across a product
    (``A * (B // k)`` <-> ``(A * B) // k`` <-> ``(A // k) * B``). Equal over the rationals, different under
    floor division exactly when the divisibility the evidence happened to show fails (e.g. handshakes
    ``(n - 1) * (n // 2)`` vs ``n * (n - 1) // 2`` on evidence where n was always even). Veto-only, like
    DISCRIM's simplifications; purely syntactic (no evaluation)."""
    out = []

    def walk(t, path):
        if t[0] in ("var", "const", "lib"):
            return
        if t[0] == "mul":
            for i, j in ((1, 2), (2, 1)):
                d = t[i]
                if d[0] == "div":
                    out.append(_D._replace(tree, path, ["div", ["mul", t[j], d[1]], d[2]]))
        if t[0] == "div" and t[1][0] == "mul":
            a, b = t[1][1], t[1][2]
            out.append(_D._replace(tree, path, ["mul", a, ["div", b, t[2]]]))
            out.append(_D._replace(tree, path, ["mul", ["div", a, t[2]], b]))
        for i, c in enumerate(t[1:], 1):
            walk(c, path + (i,))

    walk(tree, ())
    return out


def relation_veto(sig, grows, props, ev_rows=()):
    """The first adopted relation the signature breaks on the in-domain rows, or None. A monotone sweep
    also includes the evidence rows lying on the same line (every other input equal to the sweep's base),
    with their observed outputs (the hit reproduces them)."""
    for r, v in zip(grows, sig):
        if v is None:
            continue
        for p in props:
            if p["kind"] == "bound" and abs(v - r[p["x"]]) > p["b"] + 2:
                return ("bound", p["x"])
    sweeps: dict = {}
    for r, v in zip(grows, sig):
        if v is not None:
            sweeps.setdefault(r["_sweep"], []).append((r, v))
    for p in props:
        if p["kind"] != "mono":
            continue
        for (bi, nm), lst in sorted(sweeps.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
            if nm != p["x"]:
                continue
            others = [k for k in lst[0][0] if k not in (nm, "_sweep")]
            line = [(r, e) for r, e in ev_rows if all(r.get(k) == lst[0][0][k] for k in others)]
            lst = sorted(lst + line, key=lambda z: z[0][nm])
            for (_r1, v1), (_r2, v2) in zip(lst, lst[1:]):
                if (v2 - v1) * p["dir"] < 0:
                    return ("mono", nm)
    return None


def decide(hit, indep, simp, inputs, ev_rows, out_type: str = "int") -> dict:
    """The refutation decision for one WITNESS-accepted let fit (alternatives already filtered to those that
    fit the evidence). {"verdict": "kept" | "rival" | "relation", "support", "veto", "rival_class", "rows",
    "why", "pick"}."""
    grows = drows(inputs, ev_rows)
    ctl = control()
    plain = _strip(grows)
    hs = _D.signature(hit, plain)
    arows = _rewire(inputs, plain) if ctl == "rewired" else plain

    def sig(a):
        s = _D.signature(a, arows)
        if ctl == "shuffled" and s:
            s = s[1:] + s[:1]
        return s

    si = [sig(a) for a in indep]
    ss = [sig(a) for a in simp]

    def both(a, b):
        return sum(1 for x, y in zip(a, b) if x is not None and y is not None)

    support = sum(1 for s in si if not _D.disagree(hs, s) and both(hs, s) >= DISTIN_MIN_ROWS)
    rivals = [s for s in si + ss if _D.disagree(hs, s)]
    rival = max((sum(1 for y in rivals if not _D.disagree(x, y)) for x in rivals), default=0)
    why = None
    if rival and rival >= 1 + support:
        verdict = "rival"
    else:
        props = [p for p in _C.invariants(inputs, ev_rows) if p["kind"] in RELATIONS] if out_type == "int" else []
        rs = hs
        if props and ctl:
            rs = _D.signature(hit, arows)
            if ctl == "shuffled" and rs:
                rs = rs[1:] + rs[:1]
        why = relation_veto(rs, grows, props, ev_rows) if props else None
        verdict = "relation" if why else "kept"
    pick = hit
    if verdict == "kept":
        for a, s in zip(indep + simp, si + ss):
            if not _D.disagree(hs, s) and both(hs, s) >= DISTIN_MIN_ROWS and size(a) < size(pick):
                pick = a
    return {"verdict": verdict, "support": support, "veto": len(rivals), "rival_class": rival,
            "rows": len(grows), "why": why, "pick": pick}


TRACE: list = []   # filled only when NOMAD_DISTIN_TRACE is set (dev diagnostics; never read by search)


def note(task, hit, d) -> None:
    if os.environ.get("NOMAD_DISTIN_TRACE"):
        import json
        TRACE.append({"task": task.task_id, "hit": hit, **{k: v for k, v in d.items() if k != "pick"}})
        print("DISTIN", task.task_id, json.dumps(hit), {k: v for k, v in d.items() if k != "pick"}, flush=True)


__all__ = ["enabled", "control", "drows", "decide", "relation_veto", "note", "DISTIN_MIN_ROWS"]
