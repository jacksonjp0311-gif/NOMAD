"""MEMIDX and PRIM (docs/MEMIDX.md): memory indexed by what a block does, not by its input names.

MEMIDX (switch ``NOMAD_MEMIDX``, default off). Every remembered tree (library blocks and whole certified
programs) whose variables are all ints and number at most ``ARITY`` becomes a *function*: its variables
renamed to parameters ``_v0 .. _vk`` by first occurrence (``world._canon_vars``). Functions are indexed by
behavior: a fingerprint of their values on fixed synthetic probe rows (``world._probe_rows``, never a task's
rows), so two blocks that compute the same thing under different input names are one entry whose weight is
the summed learned usage. A function applies to any task with at least as many int inputs as it has
parameters; its parameters are bound to the task's int inputs by every injective assignment (one per
unordered set when the fingerprint shows the function is symmetric). Retrieval order: learned weight, then
size, then the canonical tree. Nothing here reads a task's rows; the search stage that uses the index
(``world._staged_gen`` / ``memidx_stage``) pays for every run on the task's public rows.

PRIM (switch ``NOMAD_PRIM``, default off; needs MEMIDX): small primitives derived from learned functions,
not added by hand to the DSL. For every learned two-parameter function ``f`` that is *not* symmetric (its
fingerprint changes when the arguments swap), the order-invariant combinations ``g(f(a, b), f(b, a))`` for
``g`` in max / min / add are derived; a derived function enters the index only when its fingerprint is new,
non-constant and symmetric, with weight ``PRIM_WEIGHT`` times ``f``'s. The one hand-written thing is that
closure rule (argument swap + max / min / add); the content it acts on is whatever the field certified.
From a learned ``sub(x, y)`` it yields ``max(x - y, y - x) = |x - y|``; from a shuffled field's random
operators it yields whatever those operators give. A derived function is never stored in memory by this
module: if a program that uses it is certified by WITNESS, ``add_witnessed`` harvests it like any block.

Controls (judge only): ``NOMAD_MEMIDX_CONTROL=rewired:<seed>`` permutes the learned weights over the
functions (the index no longer says which behavior was learned how often) and makes PRIM combine ``f(a, b)``
with a seeded *different* function ``h(b, a)``.
"""
from __future__ import annotations

import json
import os
import random

ARITY = 2            # most parameters of an indexed function (dev-chosen)
MAX_SIZE = 7         # largest indexed tree
FUNCS = 16           # functions retrieved per task, best first (dev-chosen: 8 / 12 / 16 / 24 / 40)
PRIM_WEIGHT = 0.5    # a derived primitive's weight relative to its source function
PRIM_OPS = ("max", "min", "add")


def enabled() -> bool:
    return os.environ.get("NOMAD_MEMIDX", "off").strip().lower() not in ("off", "0", "false", "no")


def prim_enabled() -> bool:
    return os.environ.get("NOMAD_PRIM", "off").strip().lower() not in ("off", "0", "false", "no")


def control() -> int | None:
    v = os.environ.get("NOMAD_MEMIDX_CONTROL", "").strip().lower()
    if v.startswith("rewired:"):
        return int(v.split(":", 1)[1])
    return None


def _params(k: int) -> list[tuple[str, str]]:
    return [(f"_v{i}", "int") for i in range(k)]


def _swap(tree: list) -> list:
    if tree[0] == "var":
        return ["var", {"_v0": "_v1", "_v1": "_v0"}.get(tree[1], tree[1])]
    if tree[0] in ("const", "lib"):
        return tree
    return [tree[0]] + [_swap(c) for c in tree[1:]]


def _fp(tree: list, k: int) -> tuple:
    from .world import _probe_rows, probe_fingerprint
    return probe_fingerprint(tree, _probe_rows(_params(k)))


def _trivial(fp: tuple, k: int) -> bool:
    """Constant, everywhere invalid, or equal to a bare parameter."""
    from .world import _probe_rows
    if len(set(fp)) <= 1:
        return True
    rows = _probe_rows(_params(k))
    return any(fp == tuple(repr(r[f"_v{i}"]) for r in rows) for i in range(k))


def build(prior) -> list[dict]:
    """The function index of a field: [{tree, k, sym, weight, origin}], retrieval order."""
    from .world import _canon_vars, _var_names, size, subtrees, OPS
    srcs = []
    for mem, sig, uses in ((prior.library, prior.library_sig, prior.library_uses),
                           (prior.programs, prior.programs_sig, prior.programs_uses)):
        for n in sorted(mem):
            srcs.append((mem[n], sig.get(n) or [], float(uses.get(n, 0.0))))
    classes: dict[tuple, dict] = {}
    for t, sig, u in srcs:
        if not (3 <= size(t) <= MAX_SIZE) or any(x[0] == "lib" for x in subtrees(t)):
            continue
        if any(x[0] in OPS and OPS[x[0]].out != "int" for x in subtrees(t) if x[0] not in ("var", "const")):
            continue
        types = {a: b for a, b in sig}
        vs = _var_names(t, [])
        if not vs or len(vs) > ARITY or any(types.get(v) != "int" for v in vs):
            continue
        c = _canon_vars(t)
        k = len(vs)
        fp = _fp(c, k)
        if _trivial(fp, k):
            continue
        key = (k, fp)
        e = classes.get(key)
        if e is None:
            classes[key] = {"tree": c, "k": k, "weight": u, "origin": "learned", "fp": fp}
        else:
            e["weight"] += u
            if (size(c), json.dumps(c)) < (size(e["tree"]), json.dumps(e["tree"])):
                e["tree"] = c
    out = list(classes.values())
    ctl = control()
    rng = random.Random(f"memidx-rewired-{ctl}") if ctl is not None else None
    if rng is not None and out:
        out.sort(key=lambda e: (e["k"], e["fp"]))
        w = [e["weight"] for e in out]
        rng.shuffle(w)
        for e, x in zip(out, w):
            e["weight"] = x
    for e in out:
        e["sym"] = e["k"] == 2 and _fp(_swap(e["tree"]), 2) == e["fp"]
    if prim_enabled():
        twos = sorted((e for e in out if e["k"] == 2 and not e["sym"]), key=lambda e: json.dumps(e["tree"]))
        for e in twos:
            f = e["tree"]
            g = _swap(f)
            if rng is not None:
                others = [x for x in twos if x is not e]
                if not others:
                    continue
                g = _swap(rng.choice(others)["tree"])
            for op in PRIM_OPS:
                d = [op, f, g]
                fp = _fp(d, 2)
                if _trivial(fp, 2) or _fp(_swap(d), 2) != fp:
                    continue
                have = classes.get((2, fp))
                if have is not None:
                    if have["origin"] == "prim":    # the same primitive derived again: more support
                        have["weight"] += PRIM_WEIGHT * e["weight"]
                        if (size(d), json.dumps(d)) < (size(have["tree"]), json.dumps(have["tree"])):
                            have["tree"] = d
                    continue
                classes[(2, fp)] = n = {"tree": d, "k": 2, "weight": PRIM_WEIGHT * e["weight"],
                                        "origin": "prim", "fp": fp, "sym": True}
                out.append(n)
    out.sort(key=lambda e: (-e["weight"], size(e["tree"]), json.dumps(e["tree"])))
    return out


def bindings(entry: dict, ints: list[str]) -> list[dict]:
    """Injective assignments of the task's int inputs to the function's parameters."""
    from itertools import combinations, permutations
    k = entry["k"]
    if len(ints) < k:
        return []
    pick = combinations(ints, k) if entry.get("sym") else permutations(ints, k)
    return [{f"_v{i}": n for i, n in enumerate(p)} for p in pick]


def instances(index: list[dict], task_inputs, limit: int = FUNCS) -> list[tuple[list, dict]]:
    """Bound trees in retrieval order (deduplicated by tree)."""
    from .world import _rename
    ints = [n for n, ty in task_inputs if ty == "int"]
    out, seen = [], set()
    for e in index[:limit]:
        for m in bindings(e, ints):
            t = _rename(e["tree"], m)
            k = json.dumps(t)
            if k not in seen:
                seen.add(k)
                out.append((t, e))
    return out


def substitute(tree: list, m: dict) -> list:
    """The function's parameters replaced by trees (a function applied to other programs)."""
    if tree[0] == "var":
        return m.get(tree[1], tree)
    if tree[0] in ("const", "lib"):
        return tree
    return [tree[0]] + [substitute(c, m) for c in tree[1:]]
