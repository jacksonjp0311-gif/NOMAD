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
import os
import math
import random
from dataclasses import dataclass

from . import world as W

ROUNDS = 2            # invention rounds (round >= 2 composes earlier primitives)
MAX_COMPOSED = 6      # composed primitives kept per round
PER_HEAD = 2          # composed primitives per outer part (diversity)
MIN_SAVING = 1        # nodes a composed primitive saves per application
COMPOSE_CONSTS = True # wrap round>=1 primitives by learned / derived constants (// k, * k)
MIN_USES = 2          # distinct certified programs an abstraction must compress
MAX_INVENTIONS = 8    # promoted abstractions kept per field
MAX_HOLES = 3
MAX_CONSTANTS = 2     # derived learned constants kept per field
MAX_CONST_VALUE = 1000
DREAM_MAX = 1000      # synthetic ints are log-uniform in 1..DREAM_MAX (so nested division is not all zeros)
DREAM_ROWS = 12       # synthetic rows for behavioural dedup (seeded; never task rows)


def selfedit_on() -> bool:
    """NOMAD_SELFEDIT (docs/SELFEDIT.md): the invention knobs below are read from the
    bounded genome genes (data/genome.json, or the sandbox's in-process override)
    instead of the module constants. The genome defaults equal the constants, so
    with an untouched genome nothing changes."""
    return W._flag("NOMAD_SELFEDIT", "on")   # default ON since SELFEDIT round 2 PASS (docs/SELFEDIT.md)


def _gene(name: str, default):
    if not selfedit_on():
        return default
    from . import genome
    return genome.load()[name]


def max_constants() -> int:
    return int(_gene("inv_max_constants", MAX_CONSTANTS))


def const_depth() -> int:
    return int(_gene("inv_const_depth", 1))


def floor_fit() -> bool:
    """Floor-division fit (genome gene ``inv_floor_fit``, off by default): in the INVENT
    phase a block value v with v // k equal to the goal on every public row, k a learned
    or derived constant, is offered as ``v // k`` (WITNESS-gated, 1 evaluation each)."""
    return bool(_gene("inv_floor_fit", 0))


def text_enabled() -> bool:
    """NOMAD_INVENT_TEXT (docs/INVENT_TEXT.md): concat residual anchors and an evidence-gated early
    INVENT phase on string goals. Default on since its sealed judge passed (docs/INVENT_TEXT.md)."""
    return W._flag("NOMAD_INVENT_TEXT", "on")


TEXT_ANCHOR_N = 24    # string blocks tried as concat anchors per task (1 evaluation each)


def enabled() -> bool:
    """NOMAD_INVENT: invented primitives in the field arm's block probe.
    Default on since the round-2 sealed judge passed (docs/INVENT.md)."""
    return W._flag("NOMAD_INVENT", "on")


@dataclass(frozen=True)
class Invention:
    name: str
    body: tuple          # JSON-safe tree; holes are ["hole", i]
    args: tuple          # hole types
    out: str
    uses: int
    saving: int
    utility: int
    example: str         # a rendered certified source (round 1) or the composition (round >= 2)
    round: int = 1
    parts: tuple = ()    # names of the primitives / frames / constants it is built from

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
    if "str" in types and "int" in types:
        # mixed int/str holes (BRIDGE ops only): indices must be small to be valid
        for _ in range(DREAM_ROWS):
            out.append([rng.randint(0, 6) if ty == "int" else "".join(rng.choice("abcXYZ ") for _ in range(rng.randint(1, 6)))
                        for ty in types])
        return out
    for _ in range(DREAM_ROWS):
        out.append([int(round(math.exp(rng.uniform(0, math.log(DREAM_MAX))))) if ty == "int" else "".join(rng.choice("abcXYZ ")
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


def degenerate(body: list, types: tuple) -> bool:
    """True when, on the seeded synthetic rows, the body is a constant or
    just one of its holes (e.g. (a·a // a) // a = 1): no new block."""
    t = instantiate(body, [["var", f"_h{i}"] for i in range(len(types))])
    rows, vals = _rows(types, json.dumps(list(types))), []
    for r in rows:
        try:
            vals.append((r, W.run(t, {f"_h{i}": v for i, v in enumerate(r)})))
        except W.Invalid:
            pass
    if len(vals) < 2:
        return True
    if len({json.dumps(v) for _r, v in vals}) == 1:
        return True
    return any(all(r[i] == v for r, v in vals) for i in range(len(types)))


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
    settings = (rounds(), MAX_COMPOSED, PER_HEAD, MIN_SAVING, COMPOSE_CONSTS, MIN_USES, MAX_INVENTIONS,
                rounds())
    key = hashlib.sha256(json.dumps([sorted(prior.programs.items()), settings]).encode()).hexdigest()
    cache = getattr(prior, "_invent_cache", None)
    if cache and cache[0] == key:
        return cache[1]
    out = _rounds(corpus(prior))
    prior._invent_cache = (key, out)
    return out


def rounds() -> int:
    """Invention rounds; NOMAD_INVENT_ROUNDS overrides ROUNDS (report-only ablations);
    with NOMAD_SELFEDIT on the default is the genome gene ``inv_rounds``."""
    return int(os.environ.get("NOMAD_INVENT_ROUNDS", _gene("inv_rounds", ROUNDS)))


def memory_scales(progs: list[tuple[str, list]]) -> list[tuple[int, list]]:
    """Learned scales (GROW) plus derived constants, from memory only."""
    scales = W.bank_scales(progs)
    return scales + constants(scales)


def _rounds(progs: list[tuple[str, list]]) -> list[Invention]:
    """Round 1: abstraction by compression. Rounds 2..ROUNDS: compositions."""
    r1 = _invent(progs)
    out = list(r1)
    if rounds() < 2 or not progs:
        return out
    fr = frames(progs)
    allk = memory_scales(progs)
    seen = {behaviour(x.tree, x.args) for x in r1 + fr}
    prev, parts = r1 + fr, r1 + fr
    for rnd in range(2, rounds() + 1):
        new = compose(prev, parts, allk, seen, rnd)
        if not new:
            break
        out += new
        prev = new
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


FRAME_OPS = ("add", "sub", "mul", "div", "mod", "min", "max")


def frames(progs: list[tuple[str, list]]) -> list[Invention]:
    """Learned operator frames: each binary int operator used, with at least
    one non-constant argument, in >= MIN_USES distinct certified programs.
    A frame alone saves nothing (it is one operator); it only enters
    compositions (round >= 2)."""
    users: dict[str, set] = {}
    for n, t in progs:
        for x in W.subtrees(t):
            if x[0] in FRAME_OPS and any(_has_var(c) for c in x[1:]):
                users.setdefault(x[0], set()).add(n)
    out = []
    for op in FRAME_OPS:
        u = len(users.get(op, ()))
        if u >= MIN_USES:
            out.append(Invention("F" + op, (op, ["hole", 0], ["hole", 1]), ("int", "int"), "int", u, 0, 0,
                                 f"{op}(a, b)", 0, ()))
    return out


def _subst_hole(body: list, i: int, sub: list, shift: int) -> list:
    """Replace hole i of ``body`` by ``sub`` whose holes are shifted by ``shift``."""
    def sh(x):
        if x[0] == "hole":
            return ["hole", x[1] + shift]
        if _is_leaf(x):
            return x
        return [x[0]] + [sh(c) for c in x[1:]]

    def go(x):
        if x[0] == "hole":
            return sh(sub) if x[1] == i else x
        if _is_leaf(x):
            return x
        return [x[0]] + [go(c) for c in x[1:]]
    return go(body)


def compose(prev: list[Invention], parts: list[Invention], scales: list[tuple[int, list]],
            seen: set, rnd: int) -> list[Invention]:
    """Iterated invention (round ``rnd`` >= 2): a primitive of the previous
    round with one hole filled by a round-1 primitive or a learned frame, or
    wrapped by a learned / derived constant (``// k``, ``* k``). Kept when it
    has at most MAX_HOLES holes, saves >= MIN_SAVING nodes per application and
    behaves unlike every primitive so far (seeded synthetic rows). Ranked
    by evidence x saving, evidence = the smaller use count of its parts."""
    cands = {}
    for A in prev:
        a = A.tree
        ah = len(A.args)
        for B in parts:
            if A.round == 0 and B.round == 0 and A.body[0] != B.body[0]:
                continue   # two frames compose only with themselves (nested division, a - b - c, ...)
            for i in range(ah):
                if A.args[i] != B.out:
                    continue
                body = _canon(_subst_hole(a, i, B.tree, ah))
                cands.setdefault(json.dumps(body), (body, min(A.uses, B.uses), (A.name, B.name),
                                                    f"{A.name}[{'abcdefgh'[i]} := {B.name}]", 0))
        if COMPOSE_CONSTS and A.out == "int" and A.round >= 1:   # a learned constant wraps primitives, not bare frames
            for k, kt in scales:
                for op in ("div", "mul"):
                    body = _canon([op, a, kt])
                    cands.setdefault(json.dumps(body), (body, A.uses, (A.name, f"k{k}"),
                                                        f"{A.name} {'//' if op == 'div' else '*'} {k}",
                                                        _size(kt) - 1))
    scored = []
    for k, (body, ev, pn, desc, kx) in cands.items():
        h = len(_holes(body, []))
        if not 1 <= h <= MAX_HOLES:
            continue
        saving = _size(body) - kx - h - 1     # a learned constant counts as one node
        if saving < MIN_SAVING:
            continue
        ht = _hole_types(body, {})
        scored.append((-(ev * saving), _size(body), k, body, tuple(ht[j] for j in range(h)), ev, saving, pn, desc))
    scored.sort(key=lambda z: z[:3])
    out, heads = [], {}
    for _sc, _sz, k, body, types, ev, saving, pn, desc in scored:
        if heads.get(pn[0], 0) >= PER_HEAD:
            continue
        fp = behaviour(body, types)
        if fp is None or fp in seen or degenerate(body, types):
            continue
        seen.add(fp)
        heads[pn[0]] = heads.get(pn[0], 0) + 1
        out.append(Invention("I" + hashlib.sha256(k.encode()).hexdigest()[:6], json.loads(k), types,
                             W.OPS[body[0]].out, ev, saving, ev * saving, desc, rnd, pn))
        if len(out) >= MAX_COMPOSED:
            break
    return out


def constants(scales: list[tuple[int, list]], *, for_floor: bool = False) -> list[tuple[int, list]]:
    """Derived learned constants: pairwise products of learned scales, smallest first.
    ``const_depth()`` closure rounds (round 2 multiplies round-1 products by the
    pool again: 8 = 2*4, 12 = 2*6, ...); ``max_constants()`` kept. Both are the
    module defaults (1 round, MAX_CONSTANTS) unless NOMAD_SELFEDIT reads the genome."""
    # SELFEDIT round 2: the genome's constant genes reach only the free floor-division fit
    # (for_floor=True). Rescaled targets, residual anchors and compositions always use the
    # INVENT round-2 set (1 round, MAX_CONSTANTS), so a gene change cannot slow them.
    depth = const_depth() if for_floor else 1
    cap = max_constants() if for_floor else MAX_CONSTANTS
    have = {k for k, _ in scales}
    pool = list(scales)
    out: dict[int, list] = {}
    for _rnd in range(max(1, depth)):
        new: dict[int, list] = {}
        for i, (a, ta) in enumerate(pool):
            for b, tb in pool[i:]:
                v = a * b
                if v in have or v > MAX_CONST_VALUE:
                    continue
                t = ["mul", ta, tb]
                if v not in out and (v not in new or W.size(t) < W.size(new[v])):
                    new[v] = t
                elif v in out and W.size(t) < W.size(out[v]):
                    out[v] = t
        if not new:
            break
        out.update(new)
        pool = sorted(dict(pool + list(new.items())).items())
    return sorted(out.items())[:cap]


INVENT_AT = "grow"    # "grow": the INVENT phase runs after PORT/GROW and the atoms; "after": after the regular levels
INVENT_EQ_GATE = 2    # defer the phase when a bank block already equals the goal on >= this many public rows
LEVEL_TARGETS = "all" # residual targets for invented-node values: "goal" or "all" (goal and rescaled goals)
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
    round: int = 1


    def fn(self, *vals):
        return W.run(self.template, {f"_h{i}": v for i, v in enumerate(vals)})

    def build(self, kids: list) -> list:
        return instantiate(self.body, kids)


@dataclass
class Kit:
    ops: dict            # name -> InvOp
    consts: list         # derived learned constants [(k, tree)]
    instances: list      # [(name, expanded tree)] over the task's inputs
    rounds: dict = None  # instance name -> invention round
    floor: bool = False  # floor-division fit by learned / derived constants (genome gene inv_floor_fit)
    floor_consts: list = None   # derived constants for the floor fit only (genome genes)


def kit(prior, task, bank: list) -> Kit | None:
    """The field's inventions prepared for one task (None when it has none)."""
    invs = inventions(prior)
    consts = constants(W.bank_scales(bank)) if task.out == "int" else []
    if not invs and not consts:
        return None
    floor = floor_fit() and task.out == "int"
    fconsts = constants(W.bank_scales(bank), for_floor=True) if floor else []
    from itertools import product
    ops = {}
    for x in invs:
        b = x.tree
        ops[x.name] = InvOp(x.name, x.args, x.out,
                            b, instantiate(b, [["var", f"_h{i}"] for i in range(len(x.args))]),
                            symmetric=symmetries(b, x.args), round=x.round)
    by_type: dict[str, list] = {}
    for nm, ty in task.inputs:
        by_type.setdefault(ty, []).append(["var", nm])
    inst, seen, rnd = [], set(), {}
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
            nm = "N" + hashlib.sha256(k.encode()).hexdigest()[:8]
            inst.append((nm, t))
            rnd[nm] = x.round
            if len(inst) >= MAX_INSTANCES:
                break
    return Kit(ops if PROBE_OPS else {}, consts, inst if INSTANCES else [], rnd, floor, fconsts)
