"""SENSE: classify what kind of problem NOMAD is holding, before search starts.

Organ, not learning, and never a judge. From a task's *public* rows and its
declared types only (challenge and final rows are never read), SENSE computes
a small, deterministic, versioned record:

    {"schema": "nomad.sense.v1", "domain": ..., "kind": ..., "features": {...},
     "source": "features" | "tag", "sense_id": <sha256 prefix>}

Domains are the repo's own names for what the worlds hold:

- ``mathematics``  int inputs -> int output (the ``int`` / ``genesis`` worlds)
- ``language``     string tasks (``str`` world)
- ``coding``       int-list tasks (``list`` world)
- ``science``      only when a task carries an explicit metadata tag
                   (``domain="science"``); never guessed from features
- ``other``        anything else

Kinds are honest labels computable from a handful of input/output examples:

- mathematics: ``linear`` (an exact small-integer linear fit), ``polynomial``
  (an exact small-integer degree-2 fit, or growth faster than any linear
  form), ``selection`` (every output equals one of the inputs), ``quotient``
  (outputs bounded by the inputs' scale: div/mod-like), ``piecewise`` (a
  linear form explains most rows but not all; or a constant floor/ceiling
  shows up), ``other``.
- language: ``case`` (case change only), ``reorder`` (output letters drawn
  from the input's letters), ``measure`` (int output), ``text_shaping``.
- coding: ``aggregation`` (int output), ``ordering`` (output is a
  permutation of the input), ``list_shaping``.

What it is for. Later organs (dreams/relabeling, mid-search learning,
task-feature block selection) key on ``kind`` instead of treating every task
the same. Right now WORLD uses it in one place (``lead_ops``): on the field arm's
staged path, right after the cold stage misses, the ``max_size`` level is
first enumerated only for the lead top operator the sense points at
(``sub`` for all-negative outputs, ``mul`` for outputs that outgrow the
inputs), over the cold stage's pools, leaving a reserve for the case split.
Stage 1, the cold search below ``max_size``, is never touched, so anything
cold solves below ``max_size`` costs exactly the same.

SENSE never certifies, never proposes a program and never sees withheld
rows. WITNESS still decides every candidate. ``NOMAD_SENSE=off`` restores the
exact prior behaviour. Extending: add a domain to ``DOMAIN_OF_OPSET`` or a
tag, and a classifier to ``_KINDERS``; unknown domains fall to ``other``.

No transformers. No weights. Deterministic.
"""
from __future__ import annotations

import hashlib
import json
import os
from itertools import product
from typing import Any, Callable

SCHEMA = "nomad.sense.v1"

DOMAIN_OF_OPSET = {"int": "mathematics", "genesis": "mathematics", "str": "language", "list": "coding"}
DOMAINS = ("mathematics", "language", "coding", "science", "other")
KINDS = {
    "mathematics": ("linear", "polynomial", "selection", "quotient", "piecewise", "other"),
    "language": ("case", "reorder", "measure", "text_shaping"),
    "coding": ("aggregation", "ordering", "list_shaping"),
    "science": ("kinematics", "mechanics", "physics_units", "stoich", "other"),  # from nomad.science tags
    "other": ("other",),
}

LIN_COEF = 3      # |a_i| for each int input in a linear fit
LIN_CONST = 12    # |c| for the constant term
POLY_COEF = 2     # |b| for each degree-2 monomial


def enabled() -> bool:
    return os.environ.get("NOMAD_SENSE", "on").strip().lower() not in ("off", "0", "false", "no")


# ---------------------------------------------------------------- helpers

def _int_vars(task) -> list[str]:
    return [n for n, t in task.inputs if t == "int"]


def _rows(task) -> list[tuple[dict, Any]]:
    return [(r, e) for r, e in task.public]          # public rows only, by design


def _lin_fits(rows, names, out) -> tuple[int, tuple | None, int]:
    """Best number of rows a small-integer linear form a.x + c explains.

    Returns (rows explained, coefficients of an exact fit or None, row mask
    of the best partial fit; first best in enumeration order).
    """
    best, exact, mask = 0, None, 0
    n = len(rows)
    for a in product(range(-LIN_COEF, LIN_COEF + 1), repeat=len(names)):
        cs = [o - sum(ai * r[v] for ai, v in zip(a, names)) for r, o in zip(rows, out)]
        counts: dict[int, int] = {}
        for c in cs:
            if abs(c) <= LIN_CONST:
                counts[c] = counts.get(c, 0) + 1
        if not counts:
            continue
        c, k = max(counts.items(), key=lambda kv: (kv[1], -abs(kv[0]), -kv[0]))
        if k > best:
            best = k
            mask = sum(1 << i for i, ci in enumerate(cs) if ci == c)
        if k == n and exact is None:
            exact = tuple(a) + (c,)
    return best, exact, mask


def _poly2_fit(rows, names, out) -> bool:
    """Exact small-integer degree-2 fit (two int inputs at most), no linear-only fits."""
    if not 1 <= len(names) <= 2:
        return False
    mons = [(i, j) for i in range(len(names)) for j in range(i, len(names))]
    for b in product(range(-POLY_COEF, POLY_COEF + 1), repeat=len(mons)):
        if not any(b):
            continue
        rest = [o - sum(bk * r[names[i]] * r[names[j]] for bk, (i, j) in zip(b, mons)) for r, o in zip(rows, out)]
        _, ex, _m = _lin_fits(rows, names, rest)
        if ex is not None:
            return True
    return False


# ---------------------------------------------------------------- kinds

def _math_kind(task) -> tuple[str, dict]:
    rows = _rows(task)
    names = _int_vars(task)
    rs = [r for r, _ in rows]
    out = [e for _, e in rows]
    if not names or not all(isinstance(o, int) and not isinstance(o, bool) for o in out):
        return "other", {}
    scale = max(1, max(abs(r[v]) for r in rs for v in names))
    mag = max(abs(o) for o in out)
    f: dict[str, Any] = {
        "n_rows": len(out),
        "sign": "neg" if all(o < 0 for o in out) else "pos" if all(o > 0 for o in out)
        else "nonpos" if all(o <= 0 for o in out) else "nonneg" if all(o >= 0 for o in out) else "mixed",
        "mag_ratio": round(mag / scale, 3),
        "distinct": len(set(out)),
        "selection": all(any(o == r[v] for v in names) for r, o in zip(rs, out)),
        "const_rows": sum(1 for o in out if o in (0, 1, 2, 3)),
    }
    lin_best, lin_exact, lin_mask = _lin_fits(rs, names, out)
    f["lin_rows"] = lin_best
    f["linear"] = lin_exact is not None
    if f["selection"]:
        return "selection", f
    if lin_exact is not None:
        return "linear", f
    if _poly2_fit(rs, names, out):
        f["poly2"] = True
        return "polynomial", f
    if mag > 3 * scale:
        return "polynomial", f                       # grows faster than any small linear form
    # piecewise: a linear form explains most rows, and every other row is a
    # small constant or one of the inputs (a floor, a ceiling, a pick)
    rest = [i for i in range(len(out)) if not lin_mask >> i & 1]
    f["floor_rows"] = all(out[i] in (0, 1, 2, 3) or any(out[i] == rs[i][v] for v in names) for i in rest)
    nonneg = f["sign"] in ("nonneg", "pos")
    if nonneg and 2 * mag <= scale:
        return "quotient", f                         # small remainders / quotients
    if lin_best >= max(3, len(out) - 2) and f["floor_rows"]:
        return "piecewise", f
    if nonneg and mag <= scale:
        return "quotient", f
    return "other", f


def _lang_kind(task) -> tuple[str, dict]:
    rows = _rows(task)
    f: dict[str, Any] = {"out": task.out}
    if task.out == "int":
        return "measure", f
    if task.out != "str":
        return "text_shaping", f
    srcs = [[v for v in r.values() if isinstance(v, str)] for r, _ in rows]
    if all(any(o in (s.upper(), s.lower(), s) for s in ss) for ss, (_, o) in zip(srcs, rows)):
        return "case", f
    def letters(s):
        return sorted(s.lower())
    if all(set(o.lower()) <= set("".join(ss).lower()) and len(o) <= max(len(x) for x in ss)
           for ss, (_, o) in zip(srcs, rows)):
        f["perm"] = all(any(letters(o) == letters(s) for s in ss) for ss, (_, o) in zip(srcs, rows))
        return "reorder", f
    return "text_shaping", f


def _code_kind(task) -> tuple[str, dict]:
    rows = _rows(task)
    f: dict[str, Any] = {"out": task.out}
    if task.out == "int":
        return "aggregation", f
    if task.out == "list":
        ok = all(any(isinstance(v, tuple) and sorted(v) == sorted(o) for v in r.values()) for r, o in rows)
        return ("ordering" if ok else "list_shaping"), f
    return "list_shaping", f


_KINDERS: dict[str, Callable] = {"mathematics": _math_kind, "language": _lang_kind, "coding": _code_kind}


def task_tag(task, tag: Any = None) -> dict | None:
    """The task's metadata tag, if any: the ``tag`` argument, a ``domain`` /
    ``meta`` attribute, or a registered generator (``nomad.science``)."""
    for t in (tag, getattr(task, "meta", None), getattr(task, "domain", None)):
        if isinstance(t, str) and t:
            return {"domain": t}
        if isinstance(t, dict) and isinstance(t.get("domain"), str):
            return t
    try:
        from .science import science_tag
        return science_tag(task)
    except Exception:  # generator absent or unrelated failure: features decide
        return None


def domain_of_task(task, tag: Any = None) -> tuple[str, str]:
    """(domain, source). An explicit tag wins; otherwise the opset decides."""
    t = task_tag(task, tag)
    if t:
        d = t["domain"]
        return (d if d in DOMAINS else "other"), "tag"
    return DOMAIN_OF_OPSET.get(task.opset, "other"), "features"


def sense(task, tag: Any = None) -> dict:
    """Deterministic, versioned sense record from public rows and declared types."""
    domain, source = domain_of_task(task, tag)
    kinder = _KINDERS.get(domain)
    # A tagged domain without its own classifier still gets feature kinds
    # from the world it runs in (e.g. a science task over ints), prefixed.
    if kinder is None:
        base = _KINDERS.get(DOMAIN_OF_OPSET.get(task.opset, ""), None)
        kind, feats = base(task) if base else ("other", {})
    else:
        kind, feats = kinder(task)
    t = task_tag(task, tag) if source == "tag" else None
    tk = t.get("kind") if t else None
    if isinstance(tk, str) and tk:
        # a tagged kind (e.g. science "kinematics") is the kind; the feature
        # kind stays in the record for organs that key on I/O shape
        feats = dict(feats, feature_kind=kind)
        kind = tk
    rec = {"schema": SCHEMA, "domain": domain, "kind": kind, "shape": _shape(domain, kind, feats),
           "source": source,
           "opset": task.opset, "out": task.out, "features": feats}
    rec["sense_id"] = hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return rec


# ---------------------------------------------------------------- aiming

# Lead operator per mathematics shape: the top operator of the max_size
# programs tried first, right after the cold stage (and the case split) miss.
# One operator only: one top-operator block of the size-7 level costs several
# thousand evaluations, so a longer list would not fit a 10k budget anyway.
# Chosen on the uncommitted dev suites (seeds 7 and 11), never the frozen one.
LEAD_NEG = ("sub",)      # every public output <= 0 (and not a pick of an input)
LEAD_GROWTH = ("mul",)   # outputs well above the inputs' scale
GROWTH_RATIO = 2.0
SPLIT_RESERVE = 0.2      # budget share the lead block leaves for the case split

def lead_ops(rec: dict | None, order: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Lead operators for the sensed task (empty: no aiming)."""
    if not rec or rec.get("domain") != "mathematics" or rec.get("kind") == "selection":
        return ()
    lead = {"negative": LEAD_NEG, "growth": LEAD_GROWTH}.get(rec.get("shape"), ())
    return tuple(o for o in lead if not order or o in order)


def _shape(domain: str, kind: str, feats: dict) -> str:
    """Output shape of int tasks: negative, growth, bounded or mixed (else n/a)."""
    if not feats or "sign" not in feats:
        return "n/a"
    if feats.get("sign") in ("neg", "nonpos"):
        return "negative"
    if feats.get("mag_ratio", 0) >= GROWTH_RATIO:
        return "growth"
    if feats.get("mag_ratio", 0) <= 1 and feats.get("sign") in ("nonneg", "pos"):
        return "bounded"
    return "mixed"


def brief(rec: dict | None) -> dict | None:
    """Compact form for logs, packets and the feed (no features)."""
    if not rec:
        return None
    return {k: rec.get(k) for k in ("schema", "domain", "kind", "shape", "source", "sense_id")}
