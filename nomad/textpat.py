"""TEXT_ABSTRACT: reusable string templates anti-unified from certified text chains (docs/TEXTPAT.md).

Certified TEXT_CHAIN / INVENT_TEXT (and any other concat-shaped string) programs in
the field's PORT memory are anti-unified into templates: variables become holes, and
the least general generalisation of a pair of chains turns the places they differ into
holes too (e.g. upper(a) ':' b '/' itos(n)). Templates live in a small dedicated
library, instantiated onto a new task's inputs by type-preserving binding, so NOMAD
reuses language shapes instead of assembling every chain from scratch.

Application (string goals only, behind NOMAD_TEXT_ABSTRACT, default OFF):

1. **Free assembly** (after the PORT bank is scored, before TEXT_CHAIN peels): a
   template instance whose value can be composed from values already in the probe
   pool -- plus the same free case / itos variants TEXT_CHAIN already computes --
   is offered to WITNESS at 1 evaluation when it equals the public goal. A miss
   costs nothing (lookups on computed values).
2. **Paid instantiation** (after the INVENT / TEXT_CHAIN phase would otherwise
   give up): remaining length-matching instances are run as whole programs (1
   evaluation each, capped), reaching shapes whose intermediate pieces the pool
   never held. Existing tasks solved earlier never reach this pass.

An empty field has no certified chains, so it invents nothing. The cold control
never reads a field. A shuffled-template control (``shuffled(prior, seed)``)
rewires each template's operators and concat argument order, keeping arity and
hole types, so the same number of attempts cannot succeed by hole-permutation
alone (instantiation already tries every type-matching binding).
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import dataclass

from . import invent as I
from . import world as W

TEXTPAT_MIN_USES = 2      # LGG / shared-subtree templates must compress this many programs
TEXTPAT_MAX = 24          # templates kept per field
TEXTPAT_MAX_HOLES = 6     # concat spines are longer than INVENT's MAX_HOLES = 3
TEXTPAT_N = 24            # paid instances per task (1 evaluation each)
TEXTPAT_FREE_N = 64       # free-assembly hits offered per task (1 evaluation when they match)
TEXTPAT_MAX_INSTANCES = 192
TEXTPAT_PER = 64           # instantiations kept per template (prepare length-filters)
TEXTPAT_MIN_OPS = 2       # at least two operators (a concat spine of 3+ parts, or concat + a wrapper)

# Type-preserving operator rewires used by the shuffled-template control.
_REWIRE = {"upper": "lower", "lower": "upper", "first": "last", "last": "first",
           "take": "drop", "drop": "take", "rest": "init", "init": "rest"}


def enabled() -> bool:
    """NOMAD_TEXT_ABSTRACT (docs/TEXTPAT.md): reusable string templates from certified chains.
    Default off until the sealed judge passes (off switch: NOMAD_TEXT_ABSTRACT=off)."""
    return W._flag("NOMAD_TEXT_ABSTRACT", "off")


@dataclass(frozen=True)
class Template:
    name: str
    body: tuple          # JSON-safe tree; holes are ["hole", i]
    args: tuple          # hole types
    uses: int
    example: str

    @property
    def tree(self) -> list:
        return json.loads(json.dumps(self.body))

    def render(self) -> str:
        names = "abcdefgh"
        return f"{self.name}({', '.join(names[:len(self.args)])}) = " + I._render(self.tree)


def _is_chain_tree(t: list) -> bool:
    """True when ``t`` is a concat program, optionally wrapped in upper / lower / srev."""
    if not t or I._is_leaf(t):
        return False
    cur = t
    while not I._is_leaf(cur) and cur[0] in ("upper", "lower", "srev") and len(cur) == 2:
        cur = cur[1]
    if I._is_leaf(cur) or cur[0] != "concat":
        return False
    return True


def _ok_template(b: list) -> bool:
    if I._is_leaf(b) or not _is_chain_tree(b):
        return False
    if any(x[0] in ("lib", "var") for x in I._subtrees(b) if I._is_leaf(x)):
        return False
    h = I._holes(b, [])
    if not (1 <= len(h) <= TEXTPAT_MAX_HOLES):
        return False
    return I._opnodes(b) >= TEXTPAT_MIN_OPS


def chain_corpus(prior) -> list[tuple[str, list]]:
    """Whole certified programs whose trees are concat-shaped string programs."""
    return [(n, t) for n, t in I.corpus(prior) if _is_chain_tree(t)]


def templates(prior) -> list[Template]:
    """Promoted string templates for a field (cached on the prior by memory + shuffle seed)."""
    if prior is None or not getattr(prior, "programs", None):
        return []
    seed = getattr(prior, "_textpat_shuffle_seed", None)
    key = hashlib.sha256(json.dumps([
        sorted(prior.programs.items()), seed, TEXTPAT_MIN_USES, TEXTPAT_MAX, TEXTPAT_MAX_HOLES,
    ]).encode()).hexdigest()
    cache = getattr(prior, "_textpat_cache", None)
    if cache and cache[0] == key:
        return cache[1]
    out = _invent(chain_corpus(prior))
    if seed is not None:
        out = [_rewire_one(t, seed, i) for i, t in enumerate(out)]
    prior._textpat_cache = (key, out)
    return out


def _invent(progs: list[tuple[str, list]]) -> list[Template]:
    if not progs:
        return []
    subs: list[tuple[str, list]] = []
    for n, t in progs:
        for s in I._subtrees(t):
            if _is_chain_tree(s):
                subs.append((n, s))
    cands: dict[str, tuple[list, str, int]] = {}

    def add(b, src, min_uses):
        b = I._canon(b)
        if _ok_template(b):
            k = json.dumps(b)
            if k not in cands or min_uses < cands[k][2]:
                cands[k] = (b, src, min_uses)

    # A certified chain is itself a template (PORT already has the exact program;
    # the abstraction is tried on a reserved string path, bypassing the 400-cut).
    for n, s in subs:
        add(I.abstract_vars(s), W.render(s), 1)
    for i in range(len(subs)):
        for j in range(i + 1, len(subs)):
            a, b = subs[i][1], subs[j][1]
            if a[0] == b[0] and subs[i][0] != subs[j][0]:
                add(I.lgg(a, b), W.render(a), TEXTPAT_MIN_USES)
    wholes = {json.dumps(I._canon(I.abstract_vars(t))) for _n, t in progs}
    scored = []
    for k, (b, src, min_uses) in cands.items():
        users = set()
        for n, t in progs:
            for s in I._subtrees(t):
                if I.match(b, s, {}):
                    users.add(n)
                    break
        if len(users) < min_uses:
            continue
        h = I._holes(b, [])
        ht = I._hole_types(b, {})
        # concat / string wrappers are str-out; hole types must be complete
        if any(i not in ht for i in range(len(h))):
            continue
        types = tuple(ht[i] for i in range(len(h)))
        if any(ty is None for ty in types):
            continue
        scored.append((1 if k in wholes else 0, len(users), I._opnodes(b), len(h), -I._size(b), k, b, types, src))
    scored.sort(key=lambda z: (-z[0], -z[1], -z[2], -z[3], z[4], z[5]))
    out, seen = [], set()
    for _whole, uses, _ops, _nh, _nsz, k, b, types, src in scored:
        fp = I.behaviour(b, types)
        if fp is None or fp in seen:
            continue
        if I.degenerate(b, types):
            continue
        seen.add(fp)
        name = "T" + hashlib.sha256(k.encode()).hexdigest()[:6]
        out.append(Template(name, json.loads(k), types, uses, src))
        if len(out) >= TEXTPAT_MAX:
            break
    return out


def _rewire_one(t: Template, seed: int, idx: int) -> Template:
    """Deterministic type-preserving rewire: swap concat children and flip paired ops.

    At least one concat is swapped (or one paired op is flipped) so the control is
    not a hole permutation -- instantiation already tries every type-matching binding.
    """
    rng = random.Random(f"textpat-shuffle:{seed}:{t.name}:{idx}")
    body = t.tree
    flipped = [False]

    def go(x, force_concat=False):
        if I._is_leaf(x):
            return x
        op, kids = x[0], [go(c) for c in x[1:]]
        if op == "concat" and len(kids) == 2 and (force_concat or not flipped[0] or rng.randrange(2)):
            kids = kids[::-1]
            flipped[0] = True
        elif op in _REWIRE and (not flipped[0] or rng.randrange(2)):
            op = _REWIRE[op]
            flipped[0] = True
        return [op] + kids

    new = go(body, force_concat=True)
    if not flipped[0]:
        new = go(body, force_concat=True)
    new = I._canon(new)
    return Template("S" + t.name[1:], json.loads(json.dumps(new)), t.args, t.uses, "shuffled:" + t.example)


def shuffled(prior, seed: int):
    """Control: a deep copy whose templates are rewired (arity and hole types kept)."""
    p = copy.deepcopy(prior)
    p._textpat_shuffle_seed = int(seed)
    for attr in ("_textpat_cache", "_invent_cache"):
        if hasattr(p, attr):
            delattr(p, attr)
    return p


def instances(pats: list[Template], task, *, limit: int = TEXTPAT_MAX_INSTANCES) -> list[list]:
    """Type-correct instantiations of templates over the task's inputs, smallest first."""
    from itertools import product
    if task.out != "str" or not pats:
        return []
    by_type: dict[str, list] = {}
    for nm, ty in task.inputs:
        by_type.setdefault(ty, []).append(["var", nm])
    out, seen = [], set()
    for t in pats:
        if any(not by_type.get(ty) for ty in t.args):
            continue
        pools = [by_type[ty] for ty in t.args]
        n_here = 0
        cand = []
        for kids in product(*pools):
            tree = I.instantiate(t.tree, list(kids))
            k = json.dumps(tree)
            if k in seen:
                continue
            seen.add(k)
            cand.append(tree)
        # smaller / more-specific bindings first; cap per template so a 3-hole
        # spine cannot crowd out a 5-part certified shape
        cand.sort(key=lambda tr: (I._size(tr), json.dumps(tr)))
        for tree in cand[:TEXTPAT_PER]:
            out.append(tree)
            if len(out) >= limit:
                return out
    return out


def prepare(prior, task) -> list[list]:
    """Template instances for one task (empty when the field has none, or the goal is not a string).

    Bindings whose predicted length already disagrees with the public goal are dropped
    (a length homomorphism, no evaluation), so a 5-hole template is not truncated at
    TEXTPAT_PER before the matching binding is reached.
    """
    if task.out != "str" or prior is None:
        return []
    # generous cap, then keep only length-matching bindings (sorted, stable)
    inst = instances(templates(prior), task, limit=max(TEXTPAT_MAX_INSTANCES, 800))
    rows = [r for r, _ in task.public]
    goal = tuple(e for _, e in task.public)
    keep = [tr for tr in inst if length_matches(tr, rows, goal)]
    return keep[:TEXTPAT_MAX_INSTANCES]


def _memo_from_pools(P, extras) -> dict[str, tuple]:
    """tree-json -> public values, from probe pools plus already-run bank / learned blocks."""
    memo: dict[str, tuple] = {}
    for sz in P or ():
        for typ in P[sz]:
            for tr, vs, *_ in P[sz][typ]:
                memo[json.dumps(tr)] = tuple(vs)
    for item in extras or ():
        if len(item) >= 2:
            tr, vs = item[0], item[1]
            memo[json.dumps(tr)] = tuple(vs)
    return memo


def free_eval(tree, rows, memo: dict[str, tuple], ops=None):
    """Compose ``tree`` from already-computed pool values and free case / itos / concat variants.

    Returns a tuple of per-row values, or None when a sub-tree is not determined by the
    pool (running take / drop / arithmetic from inputs would be a new evaluation).
    """
    ops = ops or set(W.OPS)
    n = len(rows)

    def go(t):
        k = json.dumps(t)
        if k in memo:
            v = memo[k]
            return v if len(v) == n else None
        if t[0] == "var":
            try:
                return tuple(r[t[1]] for r in rows)
            except KeyError:
                return None
        if t[0] == "const":
            return tuple(t[1] for _ in rows)
        if I._is_leaf(t):
            return None
        if t[0] == "concat" and len(t) == 3:
            a, b = go(t[1]), go(t[2])
            if a is None or b is None:
                return None
            if any(type(x) is not str or type(y) is not str for x, y in zip(a, b)):
                return None
            return tuple(x + y for x, y in zip(a, b))
        if t[0] in ("upper", "lower") and t[0] in ops and len(t) == 2:
            a = go(t[1])
            if a is None or any(type(x) is not str for x in a):
                return None
            fn = str.upper if t[0] == "upper" else str.lower
            return tuple(fn(x) for x in a)
        if t[0] in ("first", "last", "rest", "init") and t[0] in ops and len(t) == 2:
            a = go(t[1])
            if a is None or any(type(x) is not str or not x for x in a):
                return None
            if t[0] == "first":
                return tuple(x[0] for x in a)
            if t[0] == "last":
                return tuple(x[-1] for x in a)
            if t[0] == "rest":
                return tuple(x[1:] for x in a)
            return tuple(x[:-1] for x in a)
        if t[0] == "itos" and "itos" in ops and len(t) == 2:
            a = go(t[1])
            if a is None:
                # integer expressions over inputs (strlen, + - *) are lookups, like itos of a pool int
                try:
                    a = tuple(_int_of(t[1], r) for r in rows)
                except Exception:
                    a = None
            if a is None or any(type(x) is not int for x in a):
                return None
            return tuple(str(x) for x in a)
        return None

    return go(tree)


def _int_of(tree, row):
    """Integer value of a small tree on a row (inputs / strlen / + - * only); no interpreter."""
    t = tree
    if t[0] == "var":
        v = row.get(t[1])
        return v if type(v) is int else None
    if t[0] == "const":
        return t[1] if type(t[1]) is int else None
    if t[0] == "strlen" and len(t) == 2 and t[1][0] == "var":
        v = row.get(t[1][1])
        return len(v) if type(v) is str else None
    if t[0] in ("add", "sub", "mul") and len(t) == 3:
        a, b = _int_of(t[1], row), _int_of(t[2], row)
        if a is None or b is None:
            return None
        if t[0] == "add":
            return a + b
        if t[0] == "sub":
            return a - b
        return a * b
    return None


def pred_len(tree, row) -> int | None:
    """Output length of a string tree on one row, or None when invalid / not a string.

    Uses input values and a length homomorphism (no ``world.run``): a miss skips the
    paid instantiation; a hit still costs 1 evaluation when the program is offered.
    """
    def go(t):
        if t[0] == "var":
            v = row.get(t[1])
            return len(v) if type(v) is str else None
        if t[0] == "const" or I._is_leaf(t):
            return None
        op = t[0]
        if op in ("upper", "lower", "srev") and len(t) == 2:
            return go(t[1])
        if op in ("first", "last") and len(t) == 2:
            n = go(t[1])
            return 1 if n and n >= 1 else None
        if op in ("rest", "init") and len(t) == 2:
            n = go(t[1])
            return None if n is None or n < 1 else n - 1
        if op == "concat" and len(t) == 3:
            a, b = go(t[1]), go(t[2])
            return None if a is None or b is None else a + b
        if op == "itos" and len(t) == 2:
            v = _int_of(t[1], row)
            return len(str(v)) if type(v) is int else None
        if op in ("take", "drop", "srep", "at") and len(t) == 3:
            n, k = go(t[1]), _int_of(t[2], row)
            if n is None or type(k) is not int:
                return None
            if op == "take":
                return k if 0 <= k <= n else None
            if op == "drop":
                return n - k if 0 <= k <= n else None
            if op == "srep":
                return n * k if k >= 0 else None
            if op == "at":
                return 1 if 0 <= k < n else None
        return None
    return go(tree)


def length_matches(tree, rows, goal) -> bool:
    if len(rows) != len(goal):
        return False
    for r, g in zip(rows, goal):
        if type(g) is not str:
            return False
        n = pred_len(tree, r)
        if n is None or n != len(g):
            return False
    return True


def memo_from(P, learned, rows=None, inputs=None) -> dict[str, tuple]:
    extras = []
    for z in learned or ():
        # learned entries are (tree, values) or ranked tuples (_, n, tree, values)
        if len(z) == 2:
            extras.append(z)
        elif len(z) >= 4:
            extras.append((z[2], z[3]))
        elif len(z) == 3 and isinstance(z[2], list):
            extras.append((z[2], z[1]) if isinstance(z[1], tuple) else (z[2], z[2]))
    memo = _memo_from_pools(P, extras)
    if rows and inputs:
        for nm, _ty in inputs:
            memo.setdefault(json.dumps(["var", nm]), tuple(r[nm] for r in rows))
    return memo
