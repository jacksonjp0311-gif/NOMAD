"""CERT: stronger functional certification by distinguishing inputs (docs/CERT.md).

WITNESS reads 8 evidence rows (public + challenge). A program can match all of them by chance and be wrong
elsewhere (docs/NOVEL.md: ``nv_d_round10`` = ``10 * ceil((nn - 1) / 10)`` fit 11 of 11 rows and was wrong on
613 of 2,000 audit inputs). CERT generates extra inputs deterministically from the task's own structure and
checks the fit against **properties derived from the evidence rows themselves** (never from final rows and
never from a reference answer):

Inputs (``rows``): inside the evidence's own domain (each int input's observed hull; a constant column stays
constant; a pair ordering that holds on every evidence row, e.g. ``a <= b``, is kept), one input at a time
moved to arithmetic edges of its base row: the block edges of every small modulus (residues 0, 1, half,
half + 1, m - 1 of the base's block and the next block: rounding, carries), the hull ends and their
neighbors, the base's neighbors; and, for pairs, the two inputs tied / one apart.

Properties (``invariants``), each adopted only when it holds on **every** evidence row and is non-trivial:

- ``bound``: |out - x| <= B for an int input x (B = largest observed deviation; adopted when B is small
  next to the spread of the outputs): a fit must stay as close to x as the evidence did (+ slack);
- ``mod``: out is congruent to one residue mod m (m = 2..12, at least 8 rows);
- ``mono``: out is monotone in x over the evidence (sorted by x, at least 6 distinct values): a fit must not
  reverse along a one-input sweep.

A fit **violates** when it breaks an adopted property on a generated input, or is invalid on one inside the
domain. ``check`` returns ``veto`` (violation), ``verified`` (no violation and at least ``CERT_MIN_PROPS``
properties adopted) or ``unproven``. No expected output exists for a generated input; a property is a
consistency check against evidence, not a label.

Deterministic (sorted iteration, no hash-seed dependence), CPU only, pure functions. Reads only
``task.inputs`` and the public + challenge rows; the final split is never an argument.
"""
from __future__ import annotations

import os

from .world import Invalid, run

MODS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 12)
CERT_MIN_ROWS = 8        # evidence rows needed before any property is adopted
CERT_MAX_ROWS = 240      # most generated inputs per decision
CERT_MIN_PROPS = 2       # properties adopted for ``verified`` (the LET2 early-return bar)
CERT_BASES = 3           # evidence rows used as bases for one-input moves
CERT_MONO_DISTINCT = 6


def enabled() -> bool:
    """NOMAD_CERT (default off until its sealed judge passes)."""
    return os.environ.get("NOMAD_CERT", "off").strip().lower() not in ("off", "0", "false", "no")


def control() -> str:
    """Judge-only controls: "" | "shuffled" (outputs checked against the wrong generated rows, rotated by
    one) | "rewired" (the fit run on rows whose int inputs are rotated and incremented by one)."""
    return os.environ.get("NOMAD_CERT_CONTROL", "").strip().lower()


def _ints(inputs):
    return [nm for nm, t in inputs if t == "int"]


def domain(inputs, ev_rows) -> dict:
    """The evidence's own domain: per int input (lo, hi, const) and the pair orderings that hold on every
    evidence row ({(a, b): "le" | "ge" | "lt" | "gt"}, strongest kept)."""
    ints = _ints(inputs)
    hull = {}
    for nm in ints:
        vs = [r[nm] for r, _e in ev_rows]
        hull[nm] = (min(vs), max(vs))
    rel = {}
    for i, a in enumerate(ints):
        for b in ints[i + 1:]:
            ds = [r[a] - r[b] for r, _e in ev_rows]
            if hull[a][0] == hull[a][1] or hull[b][0] == hull[b][1]:
                continue
            if all(d < 0 for d in ds):
                rel[(a, b)] = "lt"
            elif all(d > 0 for d in ds):
                rel[(a, b)] = "gt"
            elif all(d <= 0 for d in ds):
                rel[(a, b)] = "le"
            elif all(d >= 0 for d in ds):
                rel[(a, b)] = "ge"
    return {"hull": hull, "rel": rel}


def _inside(dom, row) -> bool:
    for nm, (lo, hi) in dom["hull"].items():
        if not lo <= row[nm] <= hi:
            return False
    for (a, b), k in dom["rel"].items():
        d = row[a] - row[b]
        if (k == "lt" and not d < 0) or (k == "gt" and not d > 0) or (k == "le" and not d <= 0) \
                or (k == "ge" and not d >= 0):
            return False
    return True


def _bases(ev_rows) -> list[dict]:
    n = len(ev_rows)
    idx = sorted({0, n // 2, n - 1})[:CERT_BASES]
    return [dict(ev_rows[i][0]) for i in idx]


def rows(inputs, ev_rows) -> list[dict]:
    """The generated inputs (see the module docstring), deduplicated, never an evidence row, in a fixed
    order, at most CERT_MAX_ROWS. Each is tagged by ``_sweep`` = (base index, input) for monotone checks."""
    ints = _ints(inputs)
    names = [nm for nm, _t in inputs]
    dom = domain(inputs, ev_rows)
    seen = {tuple(r.get(k) for k in names) for r, _e in ev_rows}
    out: list[dict] = []

    def push(r, tag):
        k = tuple(r.get(x) for x in names)
        if k in seen or not _inside(dom, r) or len(out) >= CERT_MAX_ROWS:
            return
        seen.add(k)
        s = dict(r)
        s["_sweep"] = tag
        out.append(s)

    for bi, base in enumerate(_bases(ev_rows)):
        for nm in ints:
            lo, hi = dom["hull"][nm]
            if lo == hi:
                continue
            x0 = base[nm]
            vals = [x0 - 1, x0 + 1, lo, lo + 1, hi, hi - 1]
            for m in MODS:
                blk = x0 - x0 % m
                for r in (0, 1, m // 2, m // 2 + 1, m - 1):
                    vals.append(blk + r)
                    vals.append(blk + m + r)
            for v in sorted(set(vals)):
                push({**base, nm: v}, (bi, nm))
        for i, a in enumerate(ints):
            for b in ints[i + 1:]:
                if dom["hull"][a][0] == dom["hull"][a][1] or dom["hull"][b][0] == dom["hull"][b][1]:
                    continue
                for d in (0, 1, -1):
                    push({**base, a: base[b] + d}, (bi, "pair"))
                    push({**base, b: base[a] + d}, (bi, "pair"))
    return out


def invariants(inputs, ev_rows) -> list[dict]:
    """The properties the evidence rows hold (see the module docstring)."""
    ints = _ints(inputs)
    props: list[dict] = []
    if len(ev_rows) < CERT_MIN_ROWS:
        return props
    outs = [e for _r, e in ev_rows]
    if not all(isinstance(e, int) and not isinstance(e, bool) for e in outs):
        return props
    spread = max(outs) - min(outs)
    for nm in ints:
        xs = [r[nm] for r, _e in ev_rows]
        if min(xs) == max(xs):
            continue
        b = max(abs(e - x) for x, e in zip(xs, outs))
        if b * 4 <= spread:
            props.append({"kind": "bound", "x": nm, "b": b})
        order = sorted(range(len(xs)), key=lambda i: (xs[i], i))
        if len(set(xs)) >= CERT_MONO_DISTINCT and len(set(xs)) == len(xs) and spread:
            seq = [outs[i] for i in order]
            if all(p <= q for p, q in zip(seq, seq[1:])):
                props.append({"kind": "mono", "x": nm, "dir": 1})
            elif all(p >= q for p, q in zip(seq, seq[1:])):
                props.append({"kind": "mono", "x": nm, "dir": -1})
    if spread:
        for m in MODS:
            if len({e % m for e in outs}) == 1:
                props.append({"kind": "mod", "m": m, "r": outs[0] % m})
    return props


def _wire(inputs, grows):
    """Judge control "rewired": the wrong question."""
    ints = _ints(inputs)
    res = []
    for r in grows:
        s = dict(r)
        for i, nm in enumerate(ints):
            s[nm] = r[ints[(i + 1) % len(ints)]] + 1
        res.append(s)
    return res


def check(tree, inputs, ev_rows, out_type: str = "int", library=None) -> dict:
    """{"verdict": "veto" | "verified" | "unproven", "props": n, "rows": n, "why": first violation}."""
    props = invariants(inputs, ev_rows) if out_type == "int" else []
    if not props:
        return {"verdict": "unproven", "props": 0, "rows": 0, "why": None}
    grows = rows(inputs, ev_rows)
    ctl = control()
    qrows = _wire(inputs, grows) if ctl == "rewired" else grows
    vals = []
    for r in qrows:
        try:
            vals.append(run(tree, {k: v for k, v in r.items() if k != "_sweep"}, library))
        except Invalid:
            vals.append(None)
    if ctl == "shuffled" and vals:
        vals = vals[1:] + vals[:1]
    why = None
    for r, v in zip(grows, vals):
        if v is None:
            why = ("invalid", r)
            break
        for p in props:
            if p["kind"] == "bound":
                x = r[p["x"]]
                if abs(v - x) > p["b"] + 2:
                    why = ("bound", p["x"], r)
                    break
            elif p["kind"] == "mod":
                if v % p["m"] != p["r"]:
                    why = ("mod", p["m"], r)
                    break
        if why:
            break
    if why is None:
        sweeps: dict = {}
        for r, v in zip(grows, vals):
            sweeps.setdefault(r["_sweep"], []).append((r, v))
        for p in props:
            if p["kind"] != "mono":
                continue
            for (bi, nm), lst in sorted(sweeps.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
                if nm != p["x"]:
                    continue
                lst = sorted(lst, key=lambda z: z[0][nm])
                for (r1, v1), (r2, v2) in zip(lst, lst[1:]):
                    if (v2 - v1) * p["dir"] < 0:
                        why = ("mono", nm, r2)
                        break
                if why:
                    break
            if why:
                break
    if why:
        return {"verdict": "veto", "props": len(props), "rows": len(grows), "why": why}
    return {"verdict": "verified" if len(props) >= CERT_MIN_PROPS else "unproven", "props": len(props),
            "rows": len(grows), "why": None}


__all__ = ["enabled", "control", "domain", "rows", "invariants", "check", "CERT_MIN_PROPS"]
