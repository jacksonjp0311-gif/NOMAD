"""INVENT: NOMAD invents its own building blocks from certified memory (docs/INVENT.md).

PORT reuses a certified program by renaming its variables onto a task's
inputs. INVENT turns certified experience into *new primitives*:

1. **Abstraction by compression** (Stitch / DreamCoder style, MDL). Every
   sub-program of every whole certified program in the field's memory, and
   the anti-unifier (least general generalisation) of every pair of such
   sub-programs with the same root, is a candidate lambda-abstraction: its
   variables (and, for an anti-unifier, the places where the pair differs)
   become typed holes. A candidate's *uses* are the distinct certified
   programs that contain an instance of it (holes bound to any sub-program,
   a repeated hole to equal sub-programs). Rewriting one use with the new
   primitive saves ``size - holes - 1`` nodes; the primitive itself costs
   ``size - holes``. Utility = uses * saving - cost (description length
   saved on the field's own corpus). Candidates with utility >= 0 and at
   least ``MIN_USES`` uses are promoted, best first, behaviourally deduped on
   seeded synthetic rows, at most ``MAX_INVENTIONS``.
2. **Learned constants.** The constants learned memory divides or multiplies
   by (``world.bank_scales``) are closed under pairwise products (4 = 2*2,
   6 = 2*3), smallest first; derived ones are promoted as constant
   primitives (``MAX_CONSTANTS``).

Invented primitives are first-class in the field arm's block probe: the
probe's enumerator applies them to pool entries as single nodes (an
invention of arity k costs 1 node plus its k arguments), and their
instances over the task's inputs join PORT's anchors. A search tree never
contains a hole: an application is expanded to plain operators the moment
it is built, so the interpreter, WITNESS and the final split see ordinary
programs. Inventions are computed from memory only: an empty field invents
nothing, and the cold control never sees an invention. Synthetic rows are
seeded random integers; no task row, held-out or sealed suite is read.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass

from . import world as W

MIN_USES = 2          # distinct certified programs an abstraction must compress
MAX_INVENTIONS = 8    # promoted abstractions kept per field
MAX_HOLES = 3
MAX_CONSTANTS = 2     # derived learned constants kept per field
MAX_CONST_VALUE = 1000
DREAM_ROWS = 12       # synthetic rows for behavioural dedup (seeded; never task rows)


def enabled() -> bool:
    """NOMAD_INVENT: invented primitives in the field arm's block probe."""
    return W._flag("NOMAD_INVENT", "off")


@dataclass(frozen=True)
class Invention:
    name: str
    body: tuple          # JSON-safe tree; holes are ["hole", i]
    args: tuple          # hole types
    out: str
    uses: int
    saving: int
    utility: int
    example: str         # a rendered certified source

    @property
    def tree(self) -> list:
        return json.loads(json.dumps(self.body))

    def render(self) -> str:
        names = "abcdefgh"
        return f"{self.name}({', '.join(names[:len(self.args)])}) = " + _render(self.tree)

    def infix(self) -> str:
        """Readable form, e.g. ``λ a b c. a + b·c``."""
        return "λ " + " ".join("abcdefgh"[:len(self.args)]) + ". " + _infix(self.tree)


def _render(t: list) -> str:
    if t[0] == "hole":
        return "abcdefgh"[t[1]]
    if t[0] in ("var", "const", "lib"):
        return W.render(t)
    return f"{t[0]}(" + ", ".join(_render(c) for c in t[1:]) + ")"


_SYM = {"add": "+", "sub": "-", "mul": "·", "div": "//", "mod": "%"}


def _infix(t: list, top: bool = True) -> str:
    if t[0] == "hole":
        return "abcdefgh"[t[1]]
    if t[0] == "const":
        return str(t[1])
    if t[0] in ("var", "lib"):
        return W.render(t)
    if t[0] in _SYM and len(t) == 3:
        s = f"{_infix(t[1], False)} {_SYM[t[0]]} {_infix(t[2], False)}"
        if t[0] == "mul":
            s = f"{_infix(t[1], False)}·{_infix(t[2], False)}"
        return s if top or t[0] == "mul" else f"({s})"
    return f"{t[0]}(" + ", ".join(_infix(c) for c in t[1:]) + ")"


def _is_leaf(t: list) -> bool:
    return t[0] in ("var", "const", "lib", "hole")


def _subtrees(t: list):
    yield t
    if not _is_leaf(t):
        for c in t[1:]:
            yield from _subtrees(c)


def _size(t: list) -> int:
    return 1 if _is_leaf(t) else 1 + sum(_size(c) for c in t[1:])


def _opnodes(t: list) -> int:
    return 0 if _is_leaf(t) else 1 + sum(_opnodes(c) for c in t[1:])


def _holes(t: list, out: list) -> list:
    if t[0] == "hole":
        if t[1] not in out:
            out.append(t[1])
    elif not _is_leaf(t):
        for c in t[1:]:
            _holes(c, out)
    return out


def _canon(t: list) -> list:
    """Renumber holes by first occurrence (left to right)."""
    order = _holes(t, [])
    m = {h: i for i, h in enumerate(order)}

    def go(x):
        if x[0] == "hole":
            return ["hole", m[x[1]]]
        if _is_leaf(x):
            return x
        return [x[0]] + [go(c) for c in x[1:]]
    return go(t)


def _hole_types(t: list, out: dict, want: str | None = None) -> dict:
    if t[0] == "hole":
        out.setdefault(t[1], want or "int")
    elif not _is_leaf(t):
        op = W.OPS[t[0]]
        for c, ty in zip(t[1:], op.args):
            _hole_types(c, out, ty)
    return out


def abstract_vars(t: list) -> list:
    """Each distinct variable becomes a hole (first occurrence order)."""
    m: dict[str, int] = {}

    def go(x):
        if x[0] == "var":
            m.setdefault(x[1], len(m))
            return ["hole", m[x[1]]]
        if _is_leaf(x):
            return x
        return [x[0]] + [go(c) for c in x[1:]]
    return go(t)


def lgg(a: list, b: list) -> list:
    """Least general generalisation; the same differing pair maps to the same hole."""
    pairs: dict[str, int] = {}

    def go(x, y):
        if x == y and not _has_var(x):
            return x
        if not _is_leaf(x) and not _is_leaf(y) and x[0] == y[0] and len(x) == len(y):
            return [x[0]] + [go(p, q) for p, q in zip(x[1:], y[1:])]
        k = json.dumps([x, y])
        pairs.setdefault(k, len(pairs))
        return ["hole", pairs[k]]
    return _canon(go(a, b))


def _has_var(t: list) -> bool:
    if t[0] == "var":
        return True
    return not _is_leaf(t) and any(_has_var(c) for c in t[1:])


def match(body: list, t: list, bind: dict) -> bool:
    """Does ``t`` instantiate ``body``? Commutative operators match in either
    order; a repeated hole must bind equal sub-programs. Updates ``bind``."""
    if body[0] == "hole":
        k = body[1]
        if k in bind:
            return bind[k] == t
        bind[k] = t
        return True
    if _is_leaf(body):
        return body == t
    if _is_leaf(t) or body[0] != t[0] or len(body) != len(t):
        return False
    orders = [t[1:]]
    if W.OPS[t[0]].commutative:
        orders.append(t[1:][::-1])
    for kids in orders:
        b2 = dict(bind)
        if all(match(b, c, b2) for b, c in zip(body[1:], kids)):
            bind.clear()
            bind.update(b2)
            return True
    return False


def instantiate(body: list, args) -> list:
    if body[0] == "hole":
        return args[body[1]]
    if _is_leaf(body):
        return body
    return [body[0]] + [instantiate(c, args) for c in body[1:]]


def _ok_body(b: list) -> bool:
    if _is_leaf(b):
        return False
    occ = sum(1 for x in _subtrees(b) if x[0] == "hole")
    if _opnodes(b) + (occ - len(_holes(b, []))) < 2:
        return False   # saves nothing over a plain operator
    if any(x[0] in ("lib", "var") for x in _subtrees(b) if _is_leaf(x)):
        return False
    h = _holes(b, [])
    return 1 <= len(h) <= MAX_HOLES


def _rows(types: tuple, seed: str) -> list[list]:
    rng = random.Random(f"invent:{seed}")
    out = []
    for _ in range(DREAM_ROWS):
        out.append([rng.randint(1, 30) if ty == "int" else "".join(rng.choice("abcXYZ ")
                    for _ in range(rng.randint(1, 6))) for ty in types])
    return out


def behaviour(body: list, types: tuple) -> str | None:
    """Fingerprint on seeded synthetic rows (no task data), invariant under
    reordering same-typed holes; None if never valid."""
    from itertools import permutations
    fps = [_fp(body, types, p) for p in permutations(range(len(types)))
           if all(types[i] == types[j] for i, j in enumerate(p))]
    fps = [f for f in fps if f is not None]
    return min(fps) if fps else None


def _fp(body: list, types: tuple, perm) -> str | None:
    t = instantiate(body, [["var", f"_h{perm[i]}"] for i in range(len(types))])
    vals = []
    for r in _rows(types, json.dumps(list(types))):
        try:
            vals.append(W.run(t, {f"_h{i}": v for i, v in enumerate(r)}))
        except W.Invalid:
            vals.append(None)
    if all(v is None for v in vals):
        return None
    return json.dumps(vals)


def symmetries(body: list, types: tuple) -> tuple:
    """Hole pairs (i, j), i < j, of one type whose swap gives the same values
    on the synthetic rows (the invention's own commutativity)."""
    n = len(types)
    base = _fp(body, types, tuple(range(n)))
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            if types[i] != types[j]:
                continue
            p = list(range(n))
            p[i], p[j] = p[j], p[i]
            if _fp(body, types, tuple(p)) == base:
                out.append((i, j))
    return tuple(out)


def corpus(prior) -> list[tuple[str, list]]:
    """The field's whole certified programs (PORT memory), most used first."""
    items = sorted(prior.programs.items(), key=lambda z: (-prior.programs_uses.get(z[0], 0.0), z[0]))
    return [(n, t) for n, t in items if not any(x[0] == "lib" for x in W.subtrees(t))]


def inventions(prior) -> list[Invention]:
    """Promoted abstractions for a field (cached on the prior by memory content)."""
    if prior is None or not prior.programs:
        return []
    key = hashlib.sha256(json.dumps(sorted(prior.programs.items())).encode()).hexdigest()
    cache = getattr(prior, "_invent_cache", None)
    if cache and cache[0] == key:
        return cache[1]
    out = _invent(corpus(prior))
    prior._invent_cache = (key, out)
    return out


def _invent(progs: list[tuple[str, list]]) -> list[Invention]:
    subs: list[tuple[str, list]] = []
    for n, t in progs:
        for s in W.subtrees(t):
            if not _is_leaf(s) and _opnodes(s) >= 1:
                subs.append((n, s))
    cands: dict[str, tuple[list, str]] = {}

    def add(b, src):
        b = _canon(b)
        if _ok_body(b):
            cands.setdefault(json.dumps(b), (b, src))

    for n, s in subs:
        add(abstract_vars(s), W.render(s))
    for i in range(len(subs)):
        for j in range(i + 1, len(subs)):
            a, b = subs[i][1], subs[j][1]
            if a[0] == b[0] and subs[i][0] != subs[j][0]:
                add(lgg(a, b), W.render(a))
    scored = []
    for k, (b, src) in cands.items():
        users = set()
        for n, t in progs:
            for s in W.subtrees(t):
                if match(b, s, {}):
                    users.add(n)
                    break
        h = len(_holes(b, []))
        sz = _size(b)
        saving = sz - h - 1
        util = len(users) * saving - (sz - h)
        if len(users) < MIN_USES or util < 0:
            continue
        ht = _hole_types(b, {})
        types = tuple(ht[i] for i in range(h))
        scored.append((util, len(users), -sz, k, b, types, src, saving))
    scored.sort(key=lambda z: (-z[0], -z[1], z[2], z[3]))
    out, seen = [], set()
    for util, uses, _nsz, k, b, types, src, saving in scored:
        fp = behaviour(b, types)
        if fp is None or fp in seen:
            continue
        seen.add(fp)
        name = "I" + hashlib.sha256(k.encode()).hexdigest()[:6]
        out.append(Invention(name, json.loads(k), types, W.OPS[b[0]].out, uses, saving, util, src))
        if len(out) >= MAX_INVENTIONS:
            break
    return out


def constants(scales: list[tuple[int, list]]) -> list[tuple[int, list]]:
    """Derived learned constants: pairwise products of learned scales, smallest first."""
    have = {k for k, _ in scales}
    out: dict[int, list] = {}
    for i, (a, ta) in enumerate(scales):
        for b, tb in scales[i:]:
            v = a * b
            if v in have or v > MAX_CONST_VALUE:
                continue
            t = ["mul", ta, tb]
            if v not in out or W.size(t) < W.size(out[v]):
                out[v] = t
    return sorted(out.items())[:MAX_CONSTANTS]


INVENT_CAP = 0.15     # fraction of max_eval the invention pass in the probe may spend
INVENT_SIZE = 1       # the invention pass reaches max_size + INVENT_SIZE (an invented node is one node)
PROBE_OPS = True      # inventions as single-node operators in the probe's enumerator
INSTANCES = True      # invented blocks over the task's inputs join PORT's anchors
MAX_INSTANCES = 160   # invented blocks instantiated over a task's inputs (1 evaluation each in the probe)


@dataclass
class InvOp:
    """An invention as a probe operator: typed, total, expands to plain operators."""
    name: str
    args: tuple
    out: str
    body: list
    template: list
    commutative: bool = False
    symmetric: tuple = ()   # hole pairs (i, j) whose swap leaves behaviour unchanged


    def fn(self, *vals):
        return W.run(self.template, {f"_h{i}": v for i, v in enumerate(vals)})

    def build(self, kids: list) -> list:
        return instantiate(self.body, kids)


@dataclass
class Kit:
    ops: dict            # name -> InvOp
    consts: list         # derived learned constants [(k, tree)]
    instances: list      # [(name, expanded tree)] over the task's inputs


def kit(prior, task, bank: list) -> Kit | None:
    """The field's inventions prepared for one task (None when it has none)."""
    invs = inventions(prior)
    consts = constants(W.bank_scales(bank)) if task.out == "int" else []
    if not invs and not consts:
        return None
    from itertools import product
    ops = {}
    for x in invs:
        b = x.tree
        ops[x.name] = InvOp(x.name, x.args, x.out,
                            b, instantiate(b, [["var", f"_h{i}"] for i in range(len(x.args))]),
                            symmetric=symmetries(b, x.args))
    by_type: dict[str, list] = {}
    for nm, ty in task.inputs:
        by_type.setdefault(ty, []).append(["var", nm])
    inst, seen = [], set()
    for x in invs:
        if x.out != task.out:
            continue
        pools = [by_type.get(ty, []) for ty in x.args]
        sym = symmetries(x.tree, x.args)
        for kids in product(*pools):
            if any(json.dumps(kids[i]) > json.dumps(kids[j]) for i, j in sym):
                continue
            t = instantiate(x.tree, list(kids))
            k = json.dumps(t)
            if k in seen:
                continue
            seen.add(k)
            inst.append(("N" + hashlib.sha256(k.encode()).hexdigest()[:8], t))
            if len(inst) >= MAX_INSTANCES:
                break
    return Kit(ops if PROBE_OPS else {}, consts, inst if INSTANCES else [])
