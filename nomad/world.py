"""WORLD: a typed, bounded program world for NOMAD (ints, strings, int lists).

GENESIS searches integer expressions over Add/Sub/Mult. WORLD widens what the
organism can build without giving up any discipline:

- Programs are trees over a fixed operator table. There is no Python
  ``eval``; every operator is a total, bounded pure function (division and
  modulo by zero, empty-list max, oversize values all yield "invalid").
- Search is bottom-up enumeration with observational dedup over the public
  rows only. Challenge and final rows are never seen by search.
- WITNESS certifies on withheld challenge rows, then the final split is
  checked independently. Search and memory never certify.
- A ``WorldPrior`` (field) only reorders operators and may contribute
  library primitives (sub-programs harvested from certified solutions).

No transformers. No neural weights. Integer counts and receipts only.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable, Iterable, Sequence

from .witness import ReceiptMismatch, Witness, WitnessReceipt

MAX_INT = 10**6
MAX_STR = 64
MAX_LIST = 32

Value = Any  # int | str | tuple[int, ...]


class Invalid(Exception):
    pass


def _int(v: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or abs(v) > MAX_INT:
        raise Invalid
    return v


def _str(v: str) -> str:
    if len(v) > MAX_STR:
        raise Invalid
    return v


def _lst(v: Sequence[int]) -> tuple[int, ...]:
    t = tuple(v)
    if len(t) > MAX_LIST or any(abs(x) > MAX_INT for x in t):
        raise Invalid
    return t


def _div(a: int, b: int) -> int:
    if b == 0:
        raise Invalid
    return a // b


def _mod(a: int, b: int) -> int:
    if b == 0:
        raise Invalid
    return a % b


def _nonempty(xs: tuple[int, ...]) -> tuple[int, ...]:
    if not xs:
        raise Invalid
    return xs


def _at(s: str, i: int) -> str:
    if not isinstance(i, int) or i < 0 or i >= len(s):
        raise Invalid
    return s[i]


_VOW = "aeiou"


def _sib(s: str) -> int:
    return int(s.endswith(("s", "x", "z", "ch", "sh")))


def _cy(s: str) -> int:
    return int(len(s) >= 2 and s[-1] == "y" and s[-2] not in _VOW)


def _gem(s: str) -> str:
    """The doubled final consonant of a one-syllable consonant-vowel-consonant word (stop -> p, plan -> n)."""
    if len(s) < 3 or s[-1] in _VOW + "wxy" or s[-2] not in _VOW or s[-3] in _VOW:
        return ""
    groups, prev = 0, False
    for ch in s:
        v = ch in _VOW
        groups += v and not prev
        prev = v
    return s[-1] if groups == 1 else ""


def _nonneg(i: int) -> bool:
    """True for an index i >= 0 (the callers slice only then); Invalid otherwise."""
    if not isinstance(i, int) or i < 0:
        raise Invalid
    return True


def _nonneg_i(i: int) -> int:
    if not isinstance(i, int) or i < 0:
        raise Invalid
    return i


def _nonneg_n(i: int) -> int:
    if not isinstance(i, int) or i < 0 or i > MAX_STR:
        raise Invalid
    return i


@dataclass(frozen=True)
class Op:
    name: str
    args: tuple[str, ...]
    out: str
    fn: Callable[..., Value]
    commutative: bool = False


OPS: dict[str, Op] = {o.name: o for o in (
    # integer arithmetic (GENESIS core plus the wider world)
    Op("add", ("int", "int"), "int", lambda a, b: _int(a + b), True),
    Op("sub", ("int", "int"), "int", lambda a, b: _int(a - b)),
    Op("mul", ("int", "int"), "int", lambda a, b: _int(a * b), True),
    Op("div", ("int", "int"), "int", lambda a, b: _int(_div(a, b))),
    Op("mod", ("int", "int"), "int", lambda a, b: _int(_mod(a, b))),
    Op("min", ("int", "int"), "int", lambda a, b: min(a, b), True),
    Op("max", ("int", "int"), "int", lambda a, b: max(a, b), True),
    # conditional: ite(c, a, b) = a if c > 0 else b
    Op("ite", ("int", "int", "int"), "int", lambda c, a, b: a if c > 0 else b),
    # strings
    Op("upper", ("str",), "str", lambda s: s.upper()),
    Op("lower", ("str",), "str", lambda s: s.lower()),
    Op("srev", ("str",), "str", lambda s: s[::-1]),
    Op("concat", ("str", "str"), "str", lambda a, b: _str(a + b)),
    Op("first", ("str",), "str", lambda s: s[:1]),
    Op("last", ("str",), "str", lambda s: s[-1:]),
    Op("strlen", ("str",), "int", lambda s: len(s)),
    Op("rest", ("str",), "str", lambda s: s[1:]),   # TEXT only (docs/TEXT.md): drop the first character
    # BRIDGE (docs/BRIDGE.md): int <-> str bridges. Present in the op table so every
    # interpreter and the standalone checker agree; reachable only through the
    # "bridge" opset, which synthesize resolves only when NOMAD_BRIDGE is on.
    Op("at", ("str", "int"), "str", lambda s, i: _at(s, i)),        # s[i] (0 <= i < len)
    Op("take", ("str", "int"), "str", lambda s, i: _nonneg(i) and s[:i]),   # first i characters
    Op("drop", ("str", "int"), "str", lambda s, i: _nonneg(i) and s[i:]),   # all but the first i
    Op("srep", ("str", "int"), "str", lambda s, i: _str(s * _nonneg_n(i))),  # i copies
    Op("itos", ("int",), "str", lambda i: str(_nonneg_i(i))),       # decimal digits of i >= 0
    # INFLECT (docs/INFLECT.md): word-shape predicates and a choice, reachable only through the
    # "inflect" opset (resolved only when NOMAD_INFLECT is on). Total on every string; the suffixes
    # themselves are never DSL constants (they are input columns, like separators).
    Op("init", ("str",), "str", lambda s: s[:-1]),                      # all but the last character
    Op("sib", ("str",), "int", lambda s: _sib(s)),                      # 1: ends s x z ch sh (takes -es)
    Op("cy", ("str",), "int", lambda s: _cy(s)),                        # 1: ends consonant + y (y -> ies / ied)
    Op("ve", ("str",), "int", lambda s: int(s.endswith("e"))),          # 1: ends silent e
    Op("ens", ("str",), "int", lambda s: int(s.endswith("s"))),         # 1: ends in s
    Op("gem", ("str",), "str", lambda s: _gem(s)),                      # last letter again if the word doubles it, else ""
    Op("one", ("int",), "int", lambda n: int(n == 1)),                  # 1 when the count is exactly one
    Op("sel", ("int", "str", "str"), "str", lambda c, a, b: a if c > 0 else b),   # the string twin of ite
    # int lists
    Op("sort", ("list",), "list", lambda xs: tuple(sorted(xs))),
    Op("lrev", ("list",), "list", lambda xs: xs[::-1]),
    Op("tail", ("list",), "list", lambda xs: xs[1:]),
    Op("sum", ("list",), "int", lambda xs: _int(sum(xs))),
    Op("len", ("list",), "int", lambda xs: len(xs)),
    Op("lmax", ("list",), "int", lambda xs: max(_nonempty(xs))),
    Op("lmin", ("list",), "int", lambda xs: min(_nonempty(xs))),
    Op("head", ("list",), "int", lambda xs: _nonempty(xs)[0]),
)}

INT_CONSTANTS = (0, 1, 2, 3)

# Operator sets ("worlds"). The curriculum and tasks choose one per family.
OPSETS: dict[str, tuple[str, ...]] = {
    "genesis": ("add", "sub", "mul"),
    "int": ("add", "sub", "mul", "div", "mod", "min", "max", "ite"),
    "str": ("upper", "lower", "srev", "concat", "first", "last", "strlen", "add", "sub"),
    "list": ("sort", "lrev", "tail", "sum", "len", "lmax", "lmin", "head", "add", "sub", "mul"),
    # TEXT domain (nomad/text.py, docs/TEXT.md): the str world plus `rest` (the
    # one string block the dev suite showed missing: capitalising and rotating
    # need "all but the first character") and mul / div for mixed
    # string+integer tasks. Used only by text tasks; "str" is unchanged.
    "text": ("upper", "lower", "srev", "concat", "first", "last", "rest", "strlen", "add", "sub", "mul", "div"),
    # BRIDGE (docs/BRIDGE.md): the text world plus index / length / repeat / digit
    # bridges between int and str. Used only by bridge tasks, and only resolved
    # when NOMAD_BRIDGE is on (otherwise such a task runs the "text" opset).
    "bridge": ("upper", "lower", "srev", "concat", "first", "last", "rest", "strlen", "add", "sub", "mul", "div",
               "at", "take", "drop", "srep", "itos"),
    # INFLECT (docs/INFLECT.md): the bridge world plus word-shape predicates and a string choice.
    # Resolved only when NOMAD_INFLECT is on (otherwise such a task runs the "bridge" opset).
    "inflect": ("upper", "lower", "srev", "concat", "first", "last", "rest", "strlen", "add", "sub", "mul", "div",
                "at", "take", "drop", "srep", "itos", "init", "sib", "cy", "ve", "ens", "gem", "one", "sel"),
}


def inflect_enabled() -> bool:
    """NOMAD_INFLECT (default off until the sealed judge passes, docs/INFLECT.md)."""
    return _flag("NOMAD_INFLECT", "off")


def bridge_enabled() -> bool:
    """NOMAD_BRIDGE (default on since the sealed judge passed, docs/BRIDGE.md; set off to restore the text opset)."""
    return _flag("NOMAD_BRIDGE", "on")


def opset_of(task: "WorldTask") -> tuple[str, ...]:
    """The operators a task searches: OPSETS[task.opset], except that the
    bridge world collapses to the text world while NOMAD_BRIDGE is off."""
    if task.opset == "inflect" and not inflect_enabled():
        return OPSETS["bridge"] if bridge_enabled() else OPSETS["text"]
    if task.opset in ("bridge", "inflect") and not bridge_enabled():
        return OPSETS["text"]
    return OPSETS[task.opset]

# ----------------------------------------------------------------- programs
# A tree is JSON-safe: ["var", name] | ["const", k] | ["lib", name] | [op, child, ...]


def render(tree: list) -> str:
    tag = tree[0]
    if tag == "var":
        return tree[1]
    if tag == "const":
        return repr(tree[1])
    if tag == "lib":
        return f"@{tree[1]}"
    return f"{tag}(" + ", ".join(render(c) for c in tree[1:]) + ")"


def size(tree: list) -> int:
    if tree[0] in ("var", "const", "lib"):
        return 1
    return 1 + sum(size(c) for c in tree[1:])


def ops_used(tree: list) -> list[str]:
    if tree[0] in ("var", "const"):
        return []
    if tree[0] == "lib":
        return []
    out = [tree[0]]
    for c in tree[1:]:
        out += ops_used(c)
    return out


def subtrees(tree: list) -> Iterable[list]:
    yield tree
    if tree[0] not in ("var", "const", "lib"):
        for c in tree[1:]:
            yield from subtrees(c)


def run(tree: list, row: dict[str, Value], library: dict[str, list] | None = None, _depth: int = 0) -> Value:
    """Interpret a tree on one input row. Raises Invalid on any out-of-world value."""
    if _depth > 64:
        raise Invalid
    tag = tree[0]
    if tag == "var":
        if tree[1] not in row:
            raise Invalid
        return row[tree[1]]
    if tag == "const":
        return int(tree[1])
    if tag == "lib":
        if not library or tree[1] not in library:
            raise Invalid
        return run(library[tree[1]], row, library, _depth + 1)
    op = OPS.get(tag)
    if op is None or len(tree) - 1 != len(op.args):
        raise Invalid
    args = [run(c, row, library, _depth + 1) for c in tree[1:]]
    for a, t in zip(args, op.args):
        if type_of(a) != t:
            raise Invalid
    try:
        return op.fn(*args)
    except (Invalid, ValueError, TypeError, IndexError, OverflowError):
        raise Invalid


def type_of(v: Value) -> str:
    if isinstance(v, bool):
        return "bad"
    if isinstance(v, int):
        return "int"
    if isinstance(v, str):
        return "str"
    if isinstance(v, tuple):
        return "list"
    return "bad"


def expand(tree: list, library: dict[str, list] | None) -> list:
    """Inline library references so a certified program stands on its own."""
    if tree[0] == "lib":
        if not library or tree[1] not in library:
            raise Invalid
        return expand(library[tree[1]], library)
    if tree[0] in ("var", "const"):
        return tree
    return [tree[0]] + [expand(c, library) for c in tree[1:]]


# ----------------------------------------------------------------- tasks

@dataclass(frozen=True)
class WorldTask:
    task_id: str
    family: str
    opset: str
    inputs: tuple[tuple[str, str], ...]          # (name, type)
    out: str                                      # output type
    public: tuple[tuple[dict, Value], ...]        # (row, expected)
    challenge: tuple[tuple[dict, Value], ...]
    final: tuple[tuple[dict, Value], ...]
    level: int = 0


def _freeze(v: Value) -> Value:
    return tuple(v) if isinstance(v, list) else v


def make_task(task_id: str, family: str, opset: str, inputs: dict[str, str], out: str,
              public: Iterable, challenge: Iterable, final: Iterable, level: int = 0) -> WorldTask:
    def rows(rs):
        return tuple(({k: _freeze(v) for k, v in r.items()}, _freeze(e)) for r, e in rs)
    return WorldTask(task_id, family, opset, tuple(inputs.items()), out,
                     rows(public), rows(challenge), rows(final), level)


# ----------------------------------------------------------------- prior (field)

PROGRAMS_CAP = 512   # whole certified programs kept (least-used evicted)


def route_enabled() -> bool:
    """NOMAD_ROUTE: rank the portable bank by learned relevance x match (docs/ROUTE.md)."""
    return _flag("NOMAD_ROUTE", "off")


def route_key(rec: dict | None) -> str | None:
    """The SENSE key ROUTE learns under: I/O feature kind and output shape
    (domain-free, so a science task and a mathematics task of the same shape
    share evidence)."""
    if not rec:
        return None
    feats = rec.get("features") or {}
    return f"{feats.get('feature_kind', rec.get('kind'))}/{rec.get('shape')}"


def task_route_key(task: "WorldTask") -> str | None:
    from . import sense as _sense
    return route_key(_sense.sense(task))


ROUTE_GRAIN = "group"     # "group": memory kind x source SENSE key; "block": each block up to renaming


def graph_enabled() -> bool:
    """NOMAD_GRAPH: co-occurrence graph proposes two-block anchor pairs (docs/GRAPH.md)."""
    return _flag("NOMAD_GRAPH", "off")


GRAPH_PRUNE = 0.01       # node / edge counts below this are dropped on decay
GRAPH_PAIRS = 64         # most graph-proposed pairs per two-block anchor target (dev-chosen)
GRAPH_PER_NODE = 4       # bank instances per graph node considered for pairs (best seed first)
GRAPH_NESTED = True      # a block and a sub-program of it also co-occur (dev-chosen)
GRAPH_EDGES_ONLY = True  # the GRAPH design: only learned edges propose (False: dev probe, see docs/GRAPH.md)
GRAPH_FREE_N = 120       # dev probe only: best-seeded blocks paired freely
GRAPH_SCORE = "fit"      # pair score: "fit" = goal match of the pair's sum x (1 + edge) x activation; "act"
GRAPH_SPREAD = 0.5       # weight of one spreading-activation step


def graph_key(tree: list) -> str:
    return hashlib.sha256(json.dumps(_canon_vars(tree)).encode()).hexdigest()[:12]


def graph_edge(a: str, b: str) -> str:
    return f"{a}|{b}" if a <= b else f"{b}|{a}"


def graph_nodes_of(tree: list) -> list[tuple[str, tuple]]:
    """(graph_key, path) of every sub-program of size >= 3 without library refs."""
    out: list[tuple[str, tuple]] = []

    def walk(t, path):
        if t[0] in ("var", "const", "lib"):
            return t[0] == "lib"
        has_lib = False
        for i, c in enumerate(t[1:]):
            has_lib = walk(c, path + (i,)) or has_lib
        if not has_lib and size(t) >= 3:
            out.append((graph_key(t), path))
        return has_lib
    walk(tree, ())
    return out


def _seed(v: tuple, goal: tuple) -> float:
    """Goal match of a block's public values in (0, 1] (block_score, scalar)."""
    eq, nd, agree = block_score(v, goal, "int")
    n = len(goal)
    npairs = max(1, n * (n - 1) // 2)
    return (eq / n + agree / npairs + 1.0 / max(1, -nd)) / 3.0


def graph_pairs(prior: "WorldPrior", ranked: list, goal: tuple, cache: dict) -> list[tuple]:
    """Block pairs for the two-block anchor, by spreading activation.

    Seed: each int bank block's goal match. Node activation: best seed of the
    node's instances plus GRAPH_SPREAD x the edge-weighted seeds of its graph
    neighbours (edge weight: co-occurrence Jaccard). Candidates: instance
    pairs whose nodes share an edge, scored edge weight x (activation sum).
    Only learned edges propose: an empty graph proposes nothing."""
    if not prior.graph_edges:
        return []
    inst: dict[str, list] = {}
    seenv: set = set()
    for z in ranked:
        v = z[3]
        if type_of(v[0]) != "int" or _key(v) in seenv:
            continue
        seenv.add(_key(v))
        k = cache.get(z[1])
        if k is None:
            k = cache[z[1]] = graph_key(z[2])
        if k in prior.graph_nodes or not GRAPH_EDGES_ONLY:
            inst.setdefault(k, []).append((_seed(v, goal), z))
    if not inst:
        return []
    for k in inst:
        inst[k].sort(key=lambda sz: (-sz[0], sz[1][1]))
        inst[k] = inst[k][:GRAPH_PER_NODE]
    a0 = {k: l[0][0] for k, l in inst.items()}
    nodes = prior.graph_nodes
    edges = []
    for e, n_ab in prior.graph_edges.items():
        a, b = e.split("|")
        if a in inst and b in inst:
            w = n_ab / max(1e-9, nodes.get(a, 0.0) + nodes.get(b, 0.0) - (n_ab if a != b else 0.0))
            edges.append((a, b, min(1.0, w)))
    if not edges and GRAPH_EDGES_ONLY:
        return []
    act = dict(a0)
    for a, b, w in edges:
        if a != b:
            act[a] += GRAPH_SPREAD * w * a0[b]
            act[b] += GRAPH_SPREAD * w * a0[a]
    cand = []
    for a, b, w in edges:
        for i, (_sa, za) in enumerate(inst[a]):
            for j, (_sb, zb) in enumerate(inst[b]):
                if a == b and j < i:
                    continue
                if GRAPH_SCORE == "fit":
                    # the pair's summed values matched against the goal (the query)
                    vs_ = tuple(x + y for x, y in zip(za[3], zb[3]))
                    sc = _seed(vs_, goal) * (1.0 + w) * (act[a] + act[b])
                else:
                    sc = w * (act[a] + act[b])
                cand.append((sc, za[1], zb[1], za, zb))
    if not GRAPH_EDGES_ONLY:
        # dev probe (not the GRAPH design): every pair of the best-seeded
        # int blocks, scored by the goal match of its sum; edges only boost
        wmap = {graph_edge(a, b): w for a, b, w in edges}
        flat = sorted(((sz, k) for k, l in inst.items() for sz in l), key=lambda x: (-x[0][0], x[0][1][1]))[:GRAPH_FREE_N]
        for i, ((_s1, za), ka) in enumerate(flat):
            for (_s2, zb), kb in flat[i:]:
                vs_ = tuple(x + y for x, y in zip(za[3], zb[3]))
                cand.append((_seed(vs_, goal) * (1.0 + wmap.get(graph_edge(ka, kb), 0.0)), za[1], zb[1], za, zb))
    cand.sort(key=lambda c: (-c[0], c[1], c[2]))
    out, seen = [], set()
    for _sc, _n1, _n2, za, zb in cand:
        pk = frozenset((_key(za[3]), _key(zb[3])))
        if pk in seen:
            continue
        seen.add(pk)
        out.append((za, zb))
        if len(out) >= GRAPH_PAIRS:
            break
    return out


def route_group(kind: str, src: str | None, tree: list | None = None) -> str:
    if ROUTE_GRAIN == "block" and tree is not None:
        return "b:" + hashlib.sha256(json.dumps(_canon_vars(tree)).encode()).hexdigest()[:10]
    return f"{kind}:{src or '?'}"


def _canon_vars(tree: list, m: dict | None = None) -> list:
    """Variables renamed by first occurrence (block identity up to renaming)."""
    m = {} if m is None else m
    if tree[0] == "var":
        return ["var", m.setdefault(tree[1], f"_v{len(m)}")]
    if tree[0] in ("const", "lib"):
        return tree
    return [tree[0]] + [_canon_vars(c, m) for c in tree[1:]]


class WorldPrior:
    """Operator preference and library of certified sub-programs.

    Per-family Beta counts over operators (balance: an untrained family keeps
    the cold default order), a global table used only when no family is
    given, ``decay`` for unlearning, and a library of named sub-programs that
    appeared in certified solutions.
    """

    def __init__(self) -> None:
        self.witnessed = 0
        self.global_counts: dict[str, list[float]] = {}
        self.families: dict[str, dict[str, list[float]]] = {}
        self.library: dict[str, list] = {}
        self.library_uses: dict[str, float] = {}
        self.library_sig: dict[str, list[list[str]]] = {}
        # per family: [certified solutions that reused a library sub-program, ones that did not]
        self.family_lib: dict[str, list[float]] = {}
        self.library_k = 6  # set from the genome by the loop; not persisted
        # PORT (docs/PORT.md): whole certified programs, any signature
        self.programs: dict[str, list] = {}
        self.programs_sig: dict[str, list[list[str]]] = {}
        self.programs_uses: dict[str, float] = {}
        # ROUTE (docs/ROUTE.md): learned routing table. route[task_key][group]
        # = [certified solutions of a task of that SENSE key that contained a
        # block from memory group, ones that did not]; a group is the memory
        # kind ("lib" / "prog") and the SENSE key of the task whose certified
        # solution put the block into memory (library_src / programs_src).
        # Updated only from verified receipts (add_witnessed), decays like the
        # other counts; read only when NOMAD_ROUTE is on.
        self.route: dict[str, dict[str, list[float]]] = {}
        self.library_src: dict[str, str] = {}
        self.programs_src: dict[str, str] = {}
        # GRAPH (docs/GRAPH.md): per-block co-occurrence graph. Nodes are
        # certified sub-programs (size >= 3, up to variable renaming, keyed by
        # graph_key); graph_nodes[k] counts certified programs containing k,
        # graph_edges["a|b"] counts certified programs containing a and b as
        # disjoint sub-programs. Learned only in add_witnessed (verified
        # receipts), decays with the genome; read only when NOMAD_GRAPH is on.
        self.graph_nodes: dict[str, float] = {}
        self.graph_edges: dict[str, float] = {}
        # MEANING (docs/MEANING.md, nomad/meaning.py): words grounded in certified
        # structure. lexicon[token][concept] = evidence that a task described with
        # that token was solved by that concept (a certified program up to variable
        # renaming, kept in concepts[concept]). Learned only in add_witnessed from a
        # verified receipt whose task carried words, and only while NOMAD_MEANING is
        # on; read only by meaning.stage (field arm, NOMAD_MEANING on). An empty
        # field has an empty lexicon; the cold control never reads one.
        self.lexicon: dict[str, dict[str, float]] = {}
        self.concepts: dict[str, dict] = {}

    # ---- ordering
    def order(self, opset: Sequence[str], family: str | None = None) -> tuple[str, ...]:
        names = tuple(opset)
        table = self.global_counts if family is None else self.families.get(family)
        if not table:
            return names

        def score(op: str) -> float:
            s, f = table.get(op, [0.0, 0.0])
            return (s + 1.0) / (s + f + 2.0)
        return tuple(sorted(names, key=lambda op: (-score(op), names.index(op))))

    # ---- learning (only from a verified receipt)
    def add_witnessed(self, tree: list, receipt: WitnessReceipt, *, family: str | None,
                      opset: Sequence[str], inputs: Sequence[Sequence[str]], harvest: bool = True,
                      sense_key: str | None = None, words: str | None = None,
                      out: str | None = None, kind: str | None = None, row: dict | None = None,
                      task_id: str | None = None) -> None:
        if not receipt.supported or not receipt.verify_checksum():
            raise ValueError("Cannot learn from an unverified or failed WITNESS receipt")
        # INTEGRITY (docs/INTEGRITY.md): the receipt admits only the exact program it attests
        # (transmission_id = program_hash of the standalone tree certify() saw) and, when the
        # caller names it, only for the task it was attested on. Checked before anything is learned.
        check_binding(tree, receipt, task_id)
        if words:
            from . import meaning as _meaning
            if _meaning.enabled():
                _meaning.learn(self, tree, inputs, words, out=out, kind=kind)
                if row:   # ROLES (docs/ROLES.md): which number in the story filled which role
                    from . import roles as _roles
                    if _roles.enabled():
                        _roles.learn(self, tree, inputs, words, row)
        if sense_key:
            self._route_learn(tree, sense_key)
        if harvest:
            self._graph_learn(tree)
        used = set(ops_used(tree))
        tables = [self.global_counts]
        if family:
            tables.append(self.families.setdefault(family, {}))
        for table in tables:
            for op in opset:
                pair = table.setdefault(op, [0.0, 0.0])
                pair[0 if op in used else 1] += 1.0
        if family:
            known = list(self.library.values())
            hit = any(sub in known for sub in subtrees(tree) if sub is not tree)
            pair = self.family_lib.setdefault(family, [0.0, 0.0])
            pair[0 if hit else 1] += 1.0
        if harvest:
            self._harvest(tree, [list(i) for i in inputs], sense_key)
            self._keep_program(tree, [list(i) for i in inputs], sense_key)
        self.witnessed += 1

    def _route_learn(self, tree: list, key: str) -> None:
        """ROUTE: which memory groups' blocks (up to variable renaming)
        occur in this certified solution; one Beta update per known group."""
        canon = {json.dumps(_canon_vars(sub)) for sub in subtrees(tree)}
        used: set[str] = set()
        groups: set[str] = set()
        for kind, mem, src in (("lib", self.library, self.library_src), ("prog", self.programs, self.programs_src)):
            for n, t in mem.items():
                g = route_group(kind, src.get(n), t)
                groups.add(g)
                if g not in used and json.dumps(_canon_vars(t)) in canon:
                    used.add(g)
        if not groups:
            return
        table = self.route.setdefault(key, {})
        for g in groups:
            pair = table.setdefault(g, [0.0, 0.0])
            pair[0 if g in used else 1] += 1.0

    def _graph_learn(self, tree: list) -> None:
        """GRAPH: one co-occurrence update from a certified program."""
        nodes = graph_nodes_of(tree)
        keys = sorted({k for k, _p in nodes})
        for k in keys:
            self.graph_nodes[k] = self.graph_nodes.get(k, 0.0) + 1.0
        pairs = set()
        for i, (a, pa) in enumerate(nodes):
            for b, pb in nodes[i + 1:]:
                if a == b and pa == pb:
                    continue
                if not GRAPH_NESTED and (pa[:len(pb)] == pb or pb[:len(pa)] == pa):
                    continue      # nested: one contains the other
                pairs.add(graph_edge(a, b))
        for e in pairs:
            self.graph_edges[e] = self.graph_edges.get(e, 0.0) + 1.0

    def relevance(self, key: str | None, kind: str, name: str) -> float | None:
        """Learned relevance of a memory entry to a task of SENSE key ``key``
        (posterior mean of its group's Beta counts); None when the table has
        no evidence for this key (callers then keep the unrouted order)."""
        table = self.route.get(key) if key else None
        if not table:
            return None
        src = self.library_src if kind == "lib" else self.programs_src
        mem = self.library if kind == "lib" else self.programs
        s, f = table.get(route_group(kind, src.get(name), mem.get(name)), [0.0, 0.0])
        return (s + 1.0) / (s + f + 2.0)

    def _keep_program(self, tree: list, inputs: list[list[str]], src: str | None = None) -> None:
        """Remember a whole certified program (PORT reuses it on other tasks)."""
        if size(tree) < 3:
            return
        name = "W" + hashlib.sha256(json.dumps(tree).encode()).hexdigest()[:8]
        self.programs.setdefault(name, tree)
        self.programs_sig.setdefault(name, inputs)
        if src and name not in self.programs_src:
            self.programs_src[name] = src
        self.programs_uses[name] = self.programs_uses.get(name, 0.0) + 1.0
        if len(self.programs) > PROGRAMS_CAP:
            drop = min(self.programs, key=lambda n: (self.programs_uses.get(n, 0.0), n))
            for d in (self.programs, self.programs_sig, self.programs_uses, self.programs_src):
                d.pop(drop, None)

    def _harvest(self, tree: list, inputs: list[list[str]], src: str | None = None) -> None:
        for sub in subtrees(tree):
            if sub is tree or size(sub) < 3:
                continue
            key = hashlib.sha256(json.dumps(sub).encode()).hexdigest()[:8]
            name = f"L{key}"
            self.library.setdefault(name, sub)
            self.library_sig.setdefault(name, inputs)
            self.library_uses[name] = self.library_uses.get(name, 0.0) + 1.0
            if src and name not in self.library_src:
                self.library_src[name] = src

    def wants_library(self, family: str | None) -> bool:
        """Use the library for unknown families, and for known ones only if it has helped there."""
        if family is None or family not in self.family_lib:
            return True
        hits, misses = self.family_lib[family]
        return hits > 0

    def primitives_for(self, inputs: Sequence[Sequence[str]], k: int | None = None) -> dict[str, list]:
        k = self.library_k if k is None else k
        sig = [list(i) for i in inputs]
        names = [n for n in self.library if self.library_sig.get(n) == sig]
        names.sort(key=lambda n: (-self.library_uses.get(n, 0.0), n))
        return {n: self.library[n] for n in names[:k]}

    def decay(self, gamma: float) -> None:
        if not 0.0 < gamma <= 1.0:
            raise ValueError("gamma must be in (0, 1]")
        for table in [self.global_counts, *self.families.values()]:
            for pair in table.values():
                pair[0] *= gamma
                pair[1] *= gamma
        for n in list(self.library_uses):
            self.library_uses[n] *= gamma
        for n in list(self.programs_uses):
            self.programs_uses[n] *= gamma
        for table in self.route.values():
            for pair in table.values():
                pair[0] *= gamma
                pair[1] *= gamma
        for d in (self.graph_nodes, self.graph_edges):
            for k in list(d):
                d[k] *= gamma
                if d[k] < GRAPH_PRUNE:
                    del d[k]
        if self.lexicon:
            from . import meaning as _meaning
            _meaning.decay(self, gamma)

    # ---- persistence
    def snapshot(self) -> dict:
        return {"schema": "nomad.world-prior.v1", "witnessed": self.witnessed,
                "global": self.global_counts, "families": self.families,
                "library": self.library, "library_uses": self.library_uses,
                "library_sig": self.library_sig, "family_lib": self.family_lib,
                "programs": self.programs, "programs_sig": self.programs_sig,
                "programs_uses": self.programs_uses,
                "route": self.route, "library_src": self.library_src, "programs_src": self.programs_src,
                "graph_nodes": self.graph_nodes, "graph_edges": self.graph_edges,
                # MEANING: present only once a lexicon exists (snapshots without words are unchanged)
                **({"lexicon": self.lexicon, "concepts": self.concepts} if self.lexicon else {})}

    @classmethod
    def from_snapshot(cls, snap: dict) -> "WorldPrior":
        p = cls()
        p.witnessed = int(snap.get("witnessed", 0))
        p.global_counts = {k: [float(a), float(b)] for k, (a, b) in (snap.get("global") or {}).items()}
        p.families = {f: {k: [float(a), float(b)] for k, (a, b) in t.items()}
                      for f, t in (snap.get("families") or {}).items()}
        p.library = dict(snap.get("library") or {})
        p.library_uses = {k: float(v) for k, v in (snap.get("library_uses") or {}).items()}
        p.library_sig = dict(snap.get("library_sig") or {})
        p.family_lib = {k: [float(a), float(b)] for k, (a, b) in (snap.get("family_lib") or {}).items()}
        p.programs = dict(snap.get("programs") or {})
        p.programs_sig = dict(snap.get("programs_sig") or {})
        p.programs_uses = {k: float(v) for k, v in (snap.get("programs_uses") or {}).items()}
        p.route = {k: {g: [float(a), float(b)] for g, (a, b) in t.items()}
                   for k, t in (snap.get("route") or {}).items()}
        p.library_src = dict(snap.get("library_src") or {})
        p.programs_src = dict(snap.get("programs_src") or {})
        p.graph_nodes = {k: float(v) for k, v in (snap.get("graph_nodes") or {}).items()}
        p.graph_edges = {k: float(v) for k, v in (snap.get("graph_edges") or {}).items()}
        p.lexicon = {t: {c: float(v) for c, v in row.items()} for t, row in (snap.get("lexicon") or {}).items()}
        p.concepts = {k: dict(v) for k, v in (snap.get("concepts") or {}).items()}
        return p


# ----------------------------------------------------------------- search

@dataclass
class Search:
    tree: list | None
    evaluations: int
    reason: str | None
    order: tuple[str, ...] = ()
    library_used: list[str] = field(default_factory=list)
    via: str | None = None                                  # "variation:<kind>" when a mutant hit
    variation: list[dict] = field(default_factory=list)     # mutants tried (kind, tree, fitness)
    casesplit: dict = field(default_factory=dict)           # case-split charges/outcome when it ran
    sense: dict | None = None                               # SENSE record (field arm, NOMAD_SENSE on)
    witness: dict = field(default_factory=dict)             # WITNESS_CONTINUE consults (field arm)


def _key(vals: tuple) -> str:
    return json.dumps(vals, separators=(",", ":"))


def _redundant(name: str, combo: Sequence[tuple]) -> bool:
    """True when a combination provably yields nothing new, without running it.

    Decided from the children's cached public-row values only, so it costs no
    candidate evaluation (like the commutative-order skip). Every rule is
    exact: the skipped result is either invalid on some row, or equal to a
    child's values or to an integer-constant atom's values, all of which are
    already in the dedup set at a smaller size. Pools, offers and the program
    found are therefore identical with or without this check; only wasted
    evaluations disappear, for the cold control and the field alike.
    """
    v = [c[1] for c in combo]
    if name == "ite":
        cond = v[0]
        if all(isinstance(x, int) and x > 0 for x in cond) or all(isinstance(x, int) and x <= 0 for x in cond):
            return True  # uniform condition: result is the then- or else-branch
        return v[1] == v[2]
    if len(v) != 2:
        return False
    a, b = v
    if name in ("div", "mod"):
        if any(x == 0 for x in b):
            return True  # division by zero on some row: invalid
        if name == "div" and all(x == 1 for x in b):
            return True  # div(a, 1) = a
        if a == b:
            return True  # 1 or 0 on every row: a constant atom
        return False
    if name in ("sub", "min", "max") and a == b:
        return True  # 0 / a / a
    if name in ("add", "sub") and all(x == 0 for x in b):
        return True  # a + 0, a - 0
    if name == "add" and all(x == 0 for x in a):
        return True  # 0 + b
    if name == "mul" and (all(x == 0 for x in a) or all(x == 0 for x in b)):
        return True  # constant 0
    if name == "mul" and (all(x == 1 for x in a) or all(x == 1 for x in b)):
        return True  # a * 1, 1 * b
    return False


def _search_gen(task: WorldTask, order: tuple[str, ...], library: dict[str, list],
                max_size: int, max_eval: int):
    """Bottom-up typed enumeration over public rows only, as a generator.

    Yields once per candidate evaluation so two searches can share one budget
    in lockstep; the final Search is the generator's return value.
    """
    rows = [r for r, _ in task.public]
    goal = tuple(e for _, e in task.public)
    pools: dict[int, dict[str, dict[str, tuple[list, tuple]]]] = {}
    seen: set[tuple[str, str]] = set()
    evals = 0

    def offer(sz: int, tree: list, vals: tuple) -> list | None:
        t = type_of(vals[0]) if vals else "bad"
        if t == "bad" or any(type_of(v) != t for v in vals):
            return None
        k = _key(vals)
        if (t, k) in seen:
            return None
        seen.add((t, k))
        pools.setdefault(sz, {}).setdefault(t, {})[k] = (tree, vals)
        if t == task.out and vals == goal:
            return tree
        return None

    def evaluate(tree: list) -> tuple | None:
        nonlocal evals
        evals += 1
        try:
            return tuple(run(tree, r, library) for r in rows)
        except Invalid:
            return None

    # size-1 atoms: inputs, int constants, library primitives
    atoms: list[list] = [["var", n] for n, _ in task.inputs]
    atoms += [["const", c] for c in INT_CONSTANTS]
    atoms += [["lib", n] for n in library]
    for a in atoms:
        if evals >= max_eval:
            return Search(None, evals, "candidate_budget", order)
        vals = evaluate(a)
        yield evals
        if vals is None:
            continue
        hit = offer(1, a, vals)
        if hit is not None:
            return Search(hit, evals, None, order, [a[1]] if a[0] == "lib" else [])
    for sz in range(2, max_size + 1):
        for name in order:
            op = OPS[name]
            k = len(op.args)
            for split in _compositions(sz - 1, k):
                lists = []
                for s_, t in zip(split, op.args):
                    lists.append(list((pools.get(s_, {}).get(t) or {}).values()))
                if any(not l for l in lists):
                    continue
                for combo in product(*lists):
                    if op.commutative and _key(combo[0][1]) > _key(combo[1][1]):
                        continue
                    if _redundant(name, combo):
                        continue
                    if evals >= max_eval:
                        return Search(None, evals, "candidate_budget", order)
                    evals += 1
                    yield evals
                    try:
                        vals = tuple(op.fn(*args) for args in zip(*(c[1] for c in combo)))
                        if any(type_of(v) != op.out for v in vals):
                            continue
                        if op.out == "str" and any(len(v) > MAX_STR for v in vals):
                            continue
                    except (Invalid, ValueError, TypeError, IndexError, OverflowError):
                        continue
                    tree = [name] + [c[0] for c in combo]
                    hit = offer(sz, tree, vals)
                    if hit is not None:
                        libs = [s[1] for s in subtrees(hit) if s[0] == "lib"]
                        return Search(hit, evals, None, order, libs)
    return Search(None, evals, "frontier", order)


def _drive(g) -> Search:
    while True:
        try:
            next(g)
        except StopIteration as stop:
            return stop.value


def familiar(prior: WorldPrior | None, family: str | None) -> bool:
    """A family is familiar when the field holds its own operator evidence."""
    return bool(prior is not None and family is not None and prior.families.get(family))


def synthesize(task: WorldTask, *, prior: WorldPrior | None = None, use_family: bool = True,
               use_library: bool = True, max_size: int = 7, max_eval: int = 20000,
               staged: bool = True, variation: Any = None, casesplit: bool | None = None,
               sense: dict | bool | None = None) -> Search:
    """Search with the cold order, the field, or a staged transfer.

    On a familiar family (one the field has certified before) the field's own
    order and library search alone. On an unfamiliar family (held-out, or a
    family's first attempt) the field has no evidence that its cross-family
    order or library atoms apply. Leave-one-family-out validation on the
    training families showed both add cost there (cold 12,972 evaluations in
    total vs 14,955 with the global order and 14,375 with order + library;
    worst single family 13x cold). So ``staged`` transfer first exhausts the
    cold search below ``max_size`` (identical to the control, so it can never
    be beaten there) and only then spends the remaining budget on the cold
    order extended with library atoms, which is where certified sub-programs
    reach programs the cold search cannot. Order evidence still needs
    family evidence, matching the GENESIS balance rule. The library stage
    resumes from the cold stage's pools (``_staged_gen``) rather than
    restarting; see docs/WORLD.md "Cheaper search".

    ``casesplit`` (default: on unless ``NOMAD_CASESPLIT=off``) adds the
    case-split organ (``nomad/casesplit.py``) right after the cold stage
    misses, in the field arm only and only for int tasks whose opset has
    ``ite``. A field with no library for the task then also runs staged
    (cold stage, split, the max_size level), so the split has a cold stage to
    reuse. The cold control (``prior=None``) never splits.

    ``sense`` (default: on unless ``NOMAD_SENSE=off``; pass ``False`` to
    disable or a precomputed record) classifies the task from its public rows
    (``nomad/sense.py``) before search. On the staged path only, the kind
    orders the operators of the levels after stage 1 and gates the case
    split; stage 1 stays the exact cold search. Familiar families and the
    cold control are untouched. SENSE never certifies.

    ``NOMAD_PORT`` (default on; docs/PORT.md): the block probe also draws on
    the portable bank (``port_bank``: learned blocks and whole certified
    programs from any input signature, renamed onto this task's inputs),
    scored by task features, as anchors and extra atoms. An empty field has
    no bank; the cold control never reads one.
    """
    opset = opset_of(task)
    cold_order = tuple(opset)
    if prior is None:
        # The twin cold control: never reads variation state.
        return _drive(_search_gen(task, cold_order, {}, max_size, max_eval))
    fam = task.family if use_family else None
    order = prior.order(opset, fam)
    lib_ok = use_library and prior.wants_library(fam)
    library = prior.primitives_for(task.inputs) if lib_ok else {}
    mut = _variation_candidates(task, prior, variation, fam)
    from . import casesplit as _cs
    split = (_cs.enabled() if casesplit is None else bool(casesplit)) and _cs.applicable(task)
    from . import sense as _sense
    if sense is False:
        rec = None
    elif isinstance(sense, dict):
        rec = sense
    else:
        rec = _sense.sense(task) if (sense is True or _sense.enabled()) else None
    if not staged or familiar(prior, fam):
        s = _drive(_search_gen(task, order, library, max_size, max_eval))
        return _with_sense(_variation_fallback(task, s, mut, max_eval), rec)
    aim = None
    if rec is not None:
        aim = _sense.lead_ops(rec, cold_order) or None
    probe_on = blockprobe_enabled()
    rel: dict | None = None
    rkey = None
    if route_enabled() and prior.route:
        rkey = route_key(rec if rec is not None else _sense.sense(task))
        rel = {} if prior.route.get(rkey) else None
    ckey = None
    if route_cut_enabled() and prior.route and rel is None:
        ckey = route_key(rec if rec is not None else _sense.sense(task))
    bank = port_bank(prior, task, rkey, rel, ckey) if (lib_ok and probe_on and port_enabled()) else []
    if not library and not split and aim is None and not bank:
        s = _drive(_search_gen(task, cold_order, {}, max_size, max_eval))
        return _with_sense(_variation_fallback(task, s, mut, max_eval), rec)
    inv = None
    if bank:
        from . import invent as _invent
        if _invent.enabled():
            inv = _invent.kit(prior, task, bank)   # used only by the INVENT phase (main's path unchanged)
    pats = None
    if bank:
        from . import textpat as _TP
        if _TP.enabled():
            pats = _TP.prepare(prior, task)
    gate = _WitnessGate(task, library) if witness_continue_enabled() else None
    s = _drive(_staged_gen(task, cold_order, library, max_size, max_eval, mut, split, aim,
                           probe_on, gate, bank, inv, rel or None,
                           prior if (graph_enabled() and prior.graph_edges) else None, pats))
    return _with_sense(_witness_finish(s, gate), rec)


def _with_sense(s: Search, rec: dict | None) -> Search:
    s.sense = rec
    return s


def _variation_candidates(task: WorldTask, prior: WorldPrior, variation: Any,
                          family: str | None) -> list[tuple[str, list]]:
    """Bounded, memory-ordered mutants of certified patterns (field arm only)."""
    if variation is None:
        return []
    from .variation import SEARCH_TRIES
    lib = [expand(t, prior.library) for t in prior.primitives_for(task.inputs).values()]
    srcs = variation.sources(task, lib, exclude_family=family)
    return variation.candidates(task, srcs, SEARCH_TRIES)


def _variation_stage(task: WorldTask, mut: list[tuple[str, list]], evals: int, max_eval: int,
                     accept=None):
    """Try mutants as whole programs on the public rows; 1 evaluation each.

    Generator like the searches. Returns (hit tree, kind, evals, tried rows).
    """
    rows = [r for r, _ in task.public]
    goal = tuple(e for _, e in task.public)
    tried: list[dict] = []
    for kind, t in mut:
        if evals >= max_eval:
            break
        evals += 1
        yield evals
        try:
            vals = tuple(run(t, r) for r in rows)
        except Invalid:
            tried.append({"kind": kind, "tree": t, "fitness": 0.0})
            continue
        fit = sum(1 for v, g in zip(vals, goal) if v == g and type_of(v) == task.out) / max(1, len(goal))
        tried.append({"kind": kind, "tree": t, "fitness": round(fit, 4)})
        if fit == 1.0:
            if accept is not None:
                accept.stage = f"variation:{kind}"
            if accept is None or evals >= max_eval or accept(t):
                return t, kind, evals, tried
            evals += 1   # WITNESS rejected this mutant: charge, try the next
            yield evals
    return None, None, evals, tried


def _variation_fallback(task: WorldTask, s: Search, mut: list[tuple[str, list]], max_eval: int) -> Search:
    """After a failed search, spend only the budget it left unused on mutants.

    A search that found a program is returned untouched, so this can never
    cost more than the search alone did on anything that search solves.
    """
    if s.tree is not None or not mut or s.evaluations >= max_eval:
        return s
    g = _variation_stage(task, mut, s.evaluations, max_eval)
    while True:
        try:
            next(g)
        except StopIteration as stop:
            hit, kind, evals, tried = stop.value
            break
    if hit is not None:
        return Search(hit, evals, None, s.order, [], f"variation:{kind}", tried)
    return Search(None, evals, s.reason, s.order, s.library_used, None, tried)


# WITNESS_CONTINUE settings, chosen on uncommitted dev suites only (docs/WITNESS_CONTINUE.md):
WITNESS_MAX_REJECTS = 32     # rejected WITNESS consults per task (dev plateau: 16 -> 19+19, 32 -> 19+20, 64 same)
WITNESS_GATE_STAGE1 = True   # also continue past a rejected stage-1 fit (dev: 8+8 -> 19+20 vs 8+8 without)


def witness_continue_enabled() -> bool:
    import os
    return os.environ.get("NOMAD_WITNESS_CONTINUE", "on").strip().lower() not in ("off", "0", "false", "no")


class _WitnessGate:
    """WITNESS_CONTINUE (docs/WITNESS_CONTINUE.md): field arm only.

    Called on a public-row fit inside the staged search. Returns True when
    search should stop on this fit (WITNESS supports it, or the per-task
    rejection cap is spent) and False when WITNESS rejected it and search
    should go on. Reads only ``receipt.supported``; the final split is never
    consulted here. The caller charges 1 evaluation per rejection.
    """

    def __init__(self, task: WorldTask, library: dict[str, list], max_rejects: int | None = None):
        # INTEGRITY (docs/INTEGRITY.md): the gate holds a challenge view with no final split at all
        self.view, self.library = ChallengeView.of(task), library
        self.max_rejects = WITNESS_MAX_REJECTS if max_rejects is None else max_rejects
        self.rejected: list[list] = []
        self.vias: list[str | None] = []
        self.stage: str | None = None   # set by the staged search: where fits come from

    def __call__(self, tree: list) -> bool:
        if len(self.rejected) >= self.max_rejects:
            return True
        receipt = consult(self.view, expand(tree, self.library))
        if receipt is not None and receipt.supported:
            return True
        self.rejected.append(tree)
        self.vias.append(self.stage)
        return False


def _witness_finish(s: Search, gate: "_WitnessGate | None") -> Search:
    """Record consults; when every fit was rejected, return the first one, so
    the outcome reads as before (public fit, WITNESS rejected)."""
    if gate is None:
        return s
    s.witness = {"rejected": len(gate.rejected)}
    if s.tree is None and gate.rejected:
        t = gate.rejected[0]
        libs = [x[1] for x in subtrees(t) if x[0] == "lib"]
        return Search(t, s.evaluations, None, s.order, libs, gate.vias[0], s.variation, s.casesplit, s.sense,
                      {"rejected": len(gate.rejected), "returned": "first_rejected"})
    return s


BLOCKPROBE_TRIGGER = 0.5   # fraction of max_eval stage 1 may spend before the block probe
BLOCKPROBE_CAP = 0.5       # fraction of max_eval the block probe may spend


# PORT settings, chosen on uncommitted dev suites only (docs/PORT.md)
PORT_K = 24              # extra bank blocks the probe adds as atoms (dev: 12 -> 23, 24 -> 26 of 42)
PORT_ANCHOR_N = 100      # best-scoring bank blocks used as anchors (dev: all -> 25, 100 -> 26)
PORT_ANCHOR_REJECTS = 16 # anchor fits WITNESS may reject per task (inside WITNESS_MAX_REJECTS)
PORT_SCAN = 400          # most bank blocks run per task (1 evaluation each)
PORT_MAPS = 24           # most renamings of one block


def port_enabled() -> bool:
    import os
    return os.environ.get("NOMAD_PORT", "on").strip().lower() not in ("off", "0", "false", "no")


# GROW (docs/GROW.md): program-language growth for PORT. Settings chosen on
# uncommitted dev suites only.
ANCHOR2_M = 40           # best-scoring int bank blocks paired by the two-block anchor


def _flag(name: str, default: str) -> bool:
    import os
    return os.environ.get(name, default).strip().lower() not in ("off", "0", "false", "no")


def anchor2_enabled() -> bool:
    """NOMAD_ANCHOR2: sums of two learned blocks plus a residual (sum-of-products)."""
    return _flag("NOMAD_ANCHOR2", "on")


GROW_CAP = 0.25         # fraction of max_eval the two-block and rescaled anchors may spend, in total
GROW_REJECTS = 8         # two-block and rescaled anchor fits WITNESS may reject per task, in total


def scale_enabled() -> bool:
    """NOMAD_SCALE: constants learned memory divides or multiplies by rescale the goal."""
    return _flag("NOMAD_SCALE", "on")


def bank_scales(bank: list) -> list[tuple[int, list]]:
    """Learned scales: each constant k >= 2 a bank tree divides by, or
    multiplies by (a var-free factor), with its smallest tree. Memory only:
    an empty bank has none."""
    best: dict[int, list] = {}
    for _n, t in bank or ():
        for sub in subtrees(t):
            if sub[0] not in ("div", "mul") or len(sub) != 3:
                continue
            cands = [sub[2]] if sub[0] == "div" else [sub[1], sub[2]]
            for kt in cands:
                if _var_names(kt, []) or any(x[0] == "lib" for x in subtrees(kt)):
                    continue
                try:
                    k = run(kt, {})
                except Invalid:
                    continue
                if type_of(k) == "int" and 2 <= k <= 1000 and (k not in best or size(kt) < size(best[k])):
                    best[k] = kt
    return sorted(best.items())


SPLICE_PIECES = 4        # most pieces a string goal is cut into


def _I_chain() -> bool:
    """NOMAD_TEXT_CHAIN (nomad/invent.chain_enabled; docs/TEXT_CHAIN.md)."""
    from . import invent as _I
    return _I.chain_enabled()


def let2_enabled() -> bool:
    """NOMAD_LET2 (docs/LET2.md): LET's stage as a zero-cost fallback, paid only from the evaluations
    MERGE's skips saved after main's int stages missed; default off until its sealed judge passes."""
    return _flag("NOMAD_LET2", "off")


LET2_RESTORE = True  # LET2: forget the stage's WITNESS rejections on a miss (later stages see main's gate)


def _discrim_on() -> bool:
    """NOMAD_DISCRIM (docs/DISCRIM.md): LET2's fallback let stage, each accepted fit guarded by a
    distinguishing experiment (confirmed / MDL pick / keep searching); default off."""
    return _flag("NOMAD_DISCRIM", "off")


def let_enabled() -> bool:
    """NOMAD_LET: let-bindings over a learned block (docs/LET.md); default off until the sealed judge passes."""
    return _flag("NOMAD_LET", "off")


LET_N = 64           # bank blocks bound as an intermediate ``t`` (distinct values; smallest first, then block_score)
LET_CAP = 0.35       # fraction of max_eval the let stage may spend (new terms + assembled programs), in total
LET_REJECTS = 2      # WITNESS rejections of let fits after which the stage stops (never spends the task's cap)
LET_OPS = ("add", "sub", "rsub", "mul", "div", "rdiv", "mod", "max", "min")


def let_terms(t: list, tv: tuple, rows: list, atoms: list) -> list[tuple[list, tuple]]:
    """The one-step terms over a bound intermediate ``t``: t itself and ``op(t, x)`` / ``op(x, t)`` for
    every atom x (the task's int inputs, the constants 1-3 and t itself), deduplicated by public values.
    The first entry is t itself. The caller charges 1 evaluation per term not already computed."""
    out, seen = [(t, tv)], {_key(tv)}
    for xt in atoms + [t]:
        for op in LET_OPS:
            if op in ("rsub", "rdiv"):
                tree = [op[1:], xt, t]
            else:
                tree = [op, t, xt]
            try:
                v = tuple(run(tree, r) for r in rows)
            except Invalid:
                continue
            if not v or type_of(v[0]) != "int" or any(abs(x) > MAX_INT for x in v):
                continue
            k = _key(v)
            if k in seen:
                continue
            seen.add(k)
            out.append((tree, v))
    return out


def splice_enabled() -> bool:
    """NOMAD_SPLICE: cut a string goal into learned blocks and pool values (docs/TEXT.md)."""
    return _flag("NOMAD_SPLICE", "off")


def const_enabled() -> bool:
    """NOMAD_CONST: learned constants (var-free certified sub-programs, value outside 0-3) enter the bank."""
    return _flag("NOMAD_CONST", "off")


def _rename(tree: list, m: dict) -> list:
    if tree[0] == "var":
        return ["var", m[tree[1]]]
    if tree[0] in ("const", "lib"):
        return tree
    return [tree[0]] + [_rename(c, m) for c in tree[1:]]


def _var_names(tree: list, out: list) -> list:
    if tree[0] == "var":
        if tree[1] not in out:
            out.append(tree[1])
    elif tree[0] not in ("const", "lib"):
        for c in tree[1:]:
            _var_names(c, out)
    return out


ROUTE_ATOMS = True       # PORT_K atoms by (eq, relevance, rest of score); dev-chosen
ROUTE_MODE = "tie"       # how learned relevance combines with block_score (docs/ROUTE.md; dev-chosen)


def route_sort_key(z: tuple, rel: dict | None):
    """Sort key (descending) of a ranked bank entry (score, name, tree, vals).
    Without routing evidence: block_score then name (main's order)."""
    sc, n = z[0], z[1]
    r = rel.get(n, 0.5) if rel else 0.5
    if ROUTE_MODE == "eqr":
        return (sc[:1], r, sc[1:], n)
    if ROUTE_MODE == "mult":
        return ((sc[0] + 1.0) * r, sc, n)
    return (sc, r, n)


def route_cut_enabled() -> bool:
    """NOMAD_ROUTE_CUT: when the portable bank is cut at PORT_SCAN, the usage
    head is kept and the tail is filled in learned-relevance order (docs/ROUTE_CUT.md)."""
    return _flag("NOMAD_ROUTE_CUT", "off")


CUT_HEAD = 350           # ROUTE_CUT: bank instances kept in main's usage order before the learned tail (dev-chosen)
CUT_MIN_REL = 0.5        # ROUTE_CUT: tail sources need learned relevance above the uniform prior (dev-chosen)
CUT_EXTRA = 0            # ROUTE_CUT dev probe: keep all PORT_SCAN of main's and add this many learned (0: off)


def _port_instances(srcs: list, by_type: dict, seen: set, consts: bool):
    """Bank instances of ``srcs`` in order: (name, tree, source name)."""
    from itertools import permutations
    for _u, _n, t, bsig in srcs:
        types = {a: b for a, b in (bsig or [])}
        vs = _var_names(t, [])
        if not vs and consts and size(t) >= 3 and not any(x[0] == "lib" for x in subtrees(t)):
            try:
                c = run(t, {})
            except Invalid:
                continue
            k = json.dumps(t)
            if type_of(c) == "int" and c not in INT_CONSTANTS and k not in seen:
                seen.add(k)
                yield ("K" + hashlib.sha256(k.encode()).hexdigest()[:8], t, _n)
            continue
        if not vs or any(v not in types for v in vs) or any(x[0] == "lib" for x in subtrees(t)):
            continue
        groups: dict[str, list[str]] = {}
        for v in vs:
            groups.setdefault(types[v], []).append(v)
        if any(len(g) > len(by_type.get(ty, [])) for ty, g in groups.items()):
            continue
        maps: list[dict] = [{}]
        for ty, g in groups.items():
            maps = [dict(m, **dict(zip(g, perm))) for m in maps for perm in permutations(by_type[ty], len(g))]
            maps = maps[:PORT_MAPS * 4]
        ident = {v: v for v in vs}
        maps.sort(key=lambda m: m != ident)
        for m in maps[:PORT_MAPS]:
            inst = _rename(t, m)
            k = json.dumps(inst)
            if k in seen:
                continue
            seen.add(k)
            yield ("P" + hashlib.sha256(k.encode()).hexdigest()[:8], inst, _n)


def merge_enabled() -> bool:
    """NOMAD_MERGE (docs/MERGE.md): observationally equivalent portable-bank
    blocks are one idea; the evaluations duplicates cost buy distinct ideas."""
    return _flag("NOMAD_MERGE", "off")


MERGE_PROBES = 16        # fixed synthetic probe rows per input signature (never a task's rows)
MERGE_REJECTS = 4        # WITNESS rejections the merged anchors may cause per task

_PROBE_INTS = (0, 1, 2, 3, 5, 7, -1, -4, 10, 12, 25, 36, 64, 99, 128, 1000)
_PROBE_STRS = ("", "a", "ab", "ba", "abc", "xyz", "aaa", "hello", "Zq", "k", "mm", "abcab", "q r", "1", "ZZ", "nomad")


def _probe_rows(inputs: Sequence[tuple[str, str]], n: int | None = None) -> list[dict]:
    """Deterministic synthetic rows for an input signature: fixed value pools,
    a seeded shuffle per input position. Never a task's data."""
    import random
    n = MERGE_PROBES if n is None else n
    rows: list[dict] = [{} for _ in range(n)]
    for i, (nm, ty) in enumerate(inputs):
        pool = list(_PROBE_STRS if ty == "str" else _PROBE_INTS)
        random.Random(f"nomad-merge-{i}-{ty}").shuffle(pool)
        for r in range(n):
            rows[r][nm] = pool[r % len(pool)]
    return rows


def probe_fingerprint(tree: list, rows: list[dict]) -> tuple:
    """A block's behaviour on the probe rows ('!' where it is invalid)."""
    out = []
    for r in rows:
        try:
            out.append(repr(run(tree, r)))
        except Invalid:
            out.append("!")
    return tuple(out)


class MergedBank(list):
    """MERGE: main's bank, element for element, plus ``dup_of`` (index ->
    index of the earlier probe-equivalent block)."""
    merged = True

    def __init__(self, items, dup_of: dict):
        super().__init__(items)
        self.dup_of = dup_of


def _merge_bank(prior: "WorldPrior", task: WorldTask, out: list) -> list:
    srcs = [(-prior.library_uses.get(n, 0.0), n, t, prior.library_sig.get(n)) for n, t in prior.library.items()]
    srcs += [(-prior.programs_uses.get(n, 0.0), n, t, prior.programs_sig.get(n)) for n, t in prior.programs.items()]
    srcs.sort(key=lambda z: (z[0], z[1]))
    by_type: dict[str, list[str]] = {}
    for nm, ty in task.inputs:
        by_type.setdefault(ty, []).append(nm)
    rows = _probe_rows(task.inputs)
    first: dict[tuple, int] = {}
    dup_of: dict[int, int] = {}
    for i, (nm, t, _src) in enumerate(_port_instances(srcs, by_type, set(), const_enabled())):
        if i >= len(out):
            break
        if out[i][0] != nm:
            return out          # not main's plain order (cannot happen without ROUTE / ROUTE_CUT): leave main's bank
        f = probe_fingerprint(t, rows)
        if f in first:
            dup_of[i] = first[f]
        else:
            first[f] = i
    ctl = merge_control()
    if ctl is not None and dup_of:
        # judge-only control: every duplicate re-pointed to a random earlier
        # block that is NOT probe-equivalent (same number of skips, wrong merges)
        import random
        rng = random.Random(f"merge-rewired-{ctl}-{task.task_id}")
        cls = {i: f for f, i in first.items()}
        heads = sorted(cls)
        for i in sorted(dup_of):
            cand = [j for j in heads if j < i and j != dup_of[i]]
            if cand:
                dup_of[i] = rng.choice(cand)
    return MergedBank(out, dup_of)


def merge_control() -> int | None:
    """NOMAD_MERGE_CONTROL=rewired:<seed> (judge only): wrong merges, same skip count."""
    import os
    v = os.environ.get("NOMAD_MERGE_CONTROL", "").strip().lower()
    if v.startswith("rewired:"):
        return int(v.split(":", 1)[1])
    return None


def port_bank(prior: "WorldPrior", task: WorldTask, key: str | None = None,
              rel: dict | None = None, cut_key: str | None = None) -> list[tuple[str, list]]:
    """The portable bank (``_port_bank_main``). With NOMAD_MERGE on (and
    neither ROUTE nor ROUTE_CUT re-ordering it) the same bank, element for
    element, annotated for the probe with which blocks are probe-equivalent
    to an earlier one."""
    out = _port_bank_main(prior, task, key, rel, cut_key)
    if not out or not (merge_enabled() or let2_enabled() or _discrim_on()) or task.out != "int":
        return out
    if rel is not None and key and route_enabled() and prior.route.get(key):
        return out
    if cut_key and route_cut_enabled() and prior.route.get(cut_key):
        return out
    return _merge_bank(prior, task, out)


def merge_ranked(ranked: list) -> list:
    """One representative per public-value class (the first in ranked order)."""
    seen: set = set()
    out = []
    for z in ranked:
        k = _key(z[3])
        if k not in seen:
            seen.add(k)
            out.append(z)
    return out


def _port_bank_main(prior: "WorldPrior", task: WorldTask, key: str | None = None,
                    rel: dict | None = None, cut_key: str | None = None) -> list[tuple[str, list]]:
    """The portable bank: learned blocks and whole certified programs from any
    input signature, instantiated over this task's inputs by type-preserving
    renaming of their variables. Most-used first; within a source, the
    identity renaming first. Only learned memory enters: an empty field has
    an empty bank. Library references are never in a bank tree.

    ROUTE_CUT (``cut_key``, NOMAD_ROUTE_CUT on, evidence for the key): only
    when the bank reaches PORT_SCAN, its first CUT_HEAD instances are main's
    and the rest of the PORT_SCAN slots go to the remaining sources in
    learned-relevance order (usage breaks ties)."""
    srcs = [(-prior.library_uses.get(n, 0.0), n, t, prior.library_sig.get(n)) for n, t in prior.library.items()]
    srcs += [(-prior.programs_uses.get(n, 0.0), n, t, prior.programs_sig.get(n)) for n, t in prior.programs.items()]
    srcs.sort(key=lambda z: (z[0], z[1]))
    # ROUTE (NOMAD_ROUTE on, evidence for this task's SENSE key): sources in
    # learned-relevance order before the PORT_SCAN cut (usage breaks ties).
    srel: dict[str, float] = {}
    if rel is not None and key and route_enabled() and prior.route.get(key):
        for _u, n, _t, _s in srcs:
            r = prior.relevance(key, "lib" if n in prior.library else "prog", n)
            if r is not None:
                srel[n] = r
        srcs.sort(key=lambda z: (-srel.get(z[1], 0.0), z[0], z[1]))
    by_type: dict[str, list[str]] = {}
    for nm, ty in task.inputs:
        by_type.setdefault(ty, []).append(nm)
    out: list[tuple[str, list]] = []
    seen: set[str] = set()
    consts = const_enabled()
    cut = bool(cut_key) and not srel and route_cut_enabled() and bool(prior.route.get(cut_key))
    keys: list[str] = []
    for nm, t, src in _port_instances(srcs, by_type, seen, consts):
        if len(out) >= PORT_SCAN:
            break           # (cut only) the bank overflows PORT_SCAN
        out.append((nm, t))
        keys.append(json.dumps(t))
        rr = srel.get(src)
        if rr is not None and rel is not None:
            rel[nm] = rr
        if len(out) >= PORT_SCAN and not cut:
            return out
    else:
        return out          # bank within PORT_SCAN: main's bank exactly
    cap = PORT_SCAN
    if CUT_EXTRA:
        cap = PORT_SCAN + CUT_EXTRA
        seen = set(keys)
    else:
        out = out[:CUT_HEAD]
        seen = set(keys[:CUT_HEAD])
    crel: dict[str, float] = {}
    for _u, n, _t, _s in srcs:
        r = prior.relevance(cut_key, "lib" if n in prior.library else "prog", n)
        if r is not None:
            crel[n] = r
    rest = sorted((z for z in srcs if crel.get(z[1], 0.0) > CUT_MIN_REL),
                  key=lambda z: (-crel.get(z[1], 0.0), z[0], z[1]))
    for nm, t, _src in _port_instances(rest, by_type, seen, consts):
        out.append((nm, t))
        if len(out) >= cap:
            return out
    for nm, t, _src in _port_instances(srcs, by_type, seen, consts):
        out.append((nm, t))     # slots the learned sources leave: main's usage order
        if len(out) >= cap:
            break
    return out


def block_score(v: tuple, goal: tuple, out: str) -> tuple:
    """Task-feature relevance of a block's public values to the goal.

    No search: rows already equal, then how few distinct offsets separate
    block and goal, then how often the two order row pairs alike."""
    if type_of(v[0]) != out:
        return (-1, 0, 0)
    eq = sum(1 for a, b in zip(v, goal) if a == b)
    if out != "int":
        return (eq, 0, 0)
    d = len({b - a for a, b in zip(v, goal)})
    agree = 0
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            agree += ((v[i] > v[j]) - (v[i] < v[j])) == ((goal[i] > goal[j]) - (goal[i] < goal[j]))
    return (eq, -d, agree)


def affix_score(v: tuple, goal: tuple) -> tuple:
    """INFLECT (docs/INFLECT.md): string blocks, ranked by how many rows the block's value is a non-empty
    proper prefix (a stem) or suffix (an ending) of the goal -- the shape of every morphological piece.
    Ties on rows already equal; replaces block_score's all-zero string tie only for ``inflect`` tasks."""
    if not v or type_of(v[0]) != "str":
        return block_score(v, goal, "str")
    eq = sum(1 for a, b in zip(v, goal) if a == b)
    aff = sum(1 for a, b in zip(v, goal) if a and a != b and (b.startswith(a) or b.endswith(a)))
    return (eq, aff, 0)


def _residual(op: str, a: tuple, goal: tuple) -> tuple | None:
    """The values b must take so that op(a, b) == goal on every row (rsub: b - a)."""
    if op == "add":
        out = tuple(g - x for x, g in zip(a, goal))
    elif op == "sub":
        out = tuple(x - g for x, g in zip(a, goal))
    elif op == "rsub":
        out = tuple(g + x for x, g in zip(a, goal))
    elif op == "mul":
        if any(x == 0 or g % x for x, g in zip(a, goal)):
            return None
        out = tuple(g // x for x, g in zip(a, goal))
    else:
        return None
    if any(abs(x) > MAX_INT for x in out):
        return None
    return out


def blockprobe_enabled() -> bool:
    import os
    return os.environ.get("NOMAD_BLOCKPROBE", "on").strip().lower() not in ("off", "0", "false", "no")


def _staged_gen(task: WorldTask, order: tuple[str, ...], library: dict[str, list],
                max_size: int, max_eval: int, variation: list[tuple[str, list]] | None = None,
                split: bool = False, aim: tuple[str, ...] | None = None, blockprobe: bool = False,
                gate: "_WitnessGate | None" = None, bank: list | None = None, inv=None,
                rel: dict | None = None, graph: "WorldPrior | None" = None,
                pats=None):
    """Staged transfer as one incremental search (a generator, like _search_gen).

    Stage 1 is exactly the cold search below ``max_size`` (same order, same
    pools, same evaluation count), so it can never be beaten there. Stage 2
    adds the library atoms and *resumes* from stage 1's pools instead of
    restarting: a combination whose children all came from stage 1 and whose
    size is below ``max_size`` was already evaluated in stage 1 (and missed),
    so only combinations that touch a stage-2 entry, plus the whole
    ``max_size`` level, are evaluated. Reach is unchanged: a value first found
    by stage 1 at size s that a library tree now reaches at a smaller size is
    re-entered at that smaller size as a stage-2 entry, so every value of a
    tree of size <= max_size over cold + library atoms is still enumerated.
    Pure cost saving; no held-out task informs it.

    ``blockprobe`` (BLOCKPROBE, docs/SCIENCE.md): when stage 1 has spent
    ``BLOCKPROBE_TRIGGER * max_eval`` evaluations without a hit and the field
    has library blocks for this signature, stage 1 pauses once and a capped
    probe (``BLOCKPROBE_CAP * max_eval``) enumerates, on a copy of stage 1's
    pools, only combinations that contain a library block, up to max_size.
    Then stage 1 resumes unchanged. A task stage 1 solves before the trigger
    is untouched, so cheap tasks can never cost more than the control.

    ``gate`` (WITNESS_CONTINUE, docs/WITNESS_CONTINUE.md): a public-row fit
    from the lead block, the block probe, the case split, a mutant or the
    library stage is shown to WITNESS; a rejection costs 1 evaluation and
    search goes on to the next candidate and the later stages. Stage 1 fits
    are gated only when ``WITNESS_GATE_STAGE1``.
    """
    rows = [r for r, _ in task.public]
    goal = tuple(e for _, e in task.public)
    # pools[sz][type] -> list of (tree, vals, fresh); fresh = entered in stage 2
    pools: dict[int, dict[str, list[tuple[list, tuple, bool]]]] = {}
    best: dict[tuple[str, str], int] = {}  # (type, value key) -> smallest size seen
    evals = 0
    stage1 = max(1, max_size - 1)

    def offer(sz: int, tree: list, vals: tuple, fresh: bool, P=None, B=None) -> list | None:
        P = pools if P is None else P
        B = best if B is None else B
        t = type_of(vals[0]) if vals else "bad"
        if t == "bad" or any(type_of(v) != t for v in vals):
            return None
        k = (t, _key(vals))
        if k in B and B[k] <= sz:
            # After a WITNESS rejection another program with the goal's
            # public values is a new candidate (not re-added to the pools).
            if gate is not None and gate.rejected and t == task.out and vals == goal:
                return tree
            return None
        B[k] = sz
        P.setdefault(sz, {}).setdefault(t, []).append((tree, vals, fresh))
        if t == task.out and vals == goal:
            return tree
        return None

    def atom(a: list, fresh: bool):
        nonlocal evals
        evals += 1
        try:
            vals = tuple(run(a, r, library) for r in rows)
        except Invalid:
            return None
        return offer(1, a, vals, fresh)

    def stop_on(hit: list, gated: bool = True) -> bool:
        """True: return this fit. False: WITNESS rejected it (charge 1, go on)."""
        nonlocal evals
        if gate is None or not gated or evals >= max_eval or gate(hit):
            return True
        evals += 1
        return False

    probe_at = [int(BLOCKPROBE_TRIGGER * max_eval)] if (blockprobe and (library or bank)) else []
    pinfo: dict = {}
    # MERGE (docs/MERGE.md): evaluations saved on equivalent blocks, lookups known to miss
    mstate: dict = {"on": bool(getattr(bank, "merged", False)), "skips": 0, "spent": 0, "miss": set()}

    def vev() -> int:
        """Main's evaluation count: real evaluations plus MERGE's unspent skips (= evals when MERGE is off)."""
        return evals + mstate["skips"] - mstate["spent"]

    def merge_settle():
        """MERGE: charge the skips the merged anchors did not spend, so every
        later stage starts at main's count and runs exactly main's search."""
        nonlocal evals
        left = mstate["skips"] - mstate["spent"]
        if left > 0:
            mstate["spent"] = mstate["skips"]
            evals += left
            yield evals

    def probe():
        """The block probe: library-containing combinations on a copy of the pools."""
        nonlocal evals
        P = {sz_: {t: list(l) for t, l in d.items()} for sz_, d in pools.items()}
        B = dict(best)
        limit = min(max_eval, evals + int(BLOCKPROBE_CAP * max_eval))
        start = evals
        prev = gate.stage if gate is not None else None
        if gate is not None:
            gate.stage = "blockprobe"
        try:
            return (yield from probe_body(P, B, limit, start))
        finally:
            if gate is not None:
                gate.stage = prev

    def port_body(P, B, limit, start):
        """PORT (docs/PORT.md): the probe's atoms come from the portable bank.

        Each bank block is run once on the public rows (1 evaluation). Then
        (a) anchor: for each block, best-scoring first, the residual the goal
        leaves for add / sub / reversed sub / mul is looked up among the
        probe's values (1 evaluation per lookup; a hit is a WITNESS-gated
        fit), and (b) the PORT_K best-scoring blocks enter the probe as atoms.
        Returns a hit, or None after offering the atoms.
        """
        nonlocal evals
        table: dict[str, list] = {}
        for sz_ in sorted(P):
            for tr, vs_, _f in P[sz_].get(task.out, []):
                table.setdefault(_key(vs_), tr)
        ranked = []
        dup_of = getattr(bank, "dup_of", None) if getattr(bank, "merged", False) else None
        vals_at: dict[int, tuple | None] = {}
        for i, (n, t) in enumerate(bank):
            if vev() >= limit:
                return None
            if dup_of is not None and dup_of.get(i) in vals_at:
                # MERGE: probe-equivalent to an earlier block: its values, no evaluation
                v = vals_at[dup_of[i]]
                mstate["skips"] += 1
                if v is None:
                    continue
            else:
                evals += 1
                yield evals
                try:
                    v = tuple(run(t, r) for r in rows)
                except Invalid:
                    vals_at[i] = None
                    continue
                vals_at[i] = v
            if not v or any(type_of(x) != type_of(v[0]) for x in v):
                continue
            if type_of(v[0]) == task.out:
                table.setdefault(_key(v), t)
            ranked.append(((affix_score(v, goal) if (task.opset == "inflect" and inflect_enabled() and task.out == "str")
                            else block_score(v, goal, task.out)), n, t, v))
        if rel:
            ranked.sort(key=lambda z: route_sort_key(z, rel), reverse=True)
        else:
            ranked.sort(key=lambda z: (z[0], z[1]), reverse=True)
        if task.out == "int":
            rej0 = len(gate.rejected) if gate is not None else 0
            gkey = _key(goal)
            for sc, _n, t, v in ranked[:PORT_ANCHOR_N]:
                if sc[0] < 0:
                    break
                if gate is not None and len(gate.rejected) - rej0 >= PORT_ANCHOR_REJECTS:
                    break
                for op in ("add", "sub", "rsub", "mul"):
                    if vev() >= limit:
                        return None
                    mk = (gkey, op, _key(v))
                    if mk in mstate["miss"]:
                        mstate["skips"] += 1    # MERGE: the same lookup already missed (no candidate)
                        continue
                    evals += 1
                    yield evals
                    need = _residual(op, v, goal)
                    b = table.get(_key(need)) if need is not None else None
                    if b is None:
                        if mstate["on"]:
                            mstate["miss"].add(mk)
                        continue
                    hit = ["sub", b, t] if op == "rsub" else [op, t, b]
                    if stop_on(hit):
                        pinfo["port"] = "anchor"
                        return hit
                    yield evals
            glimit = min(limit, vev() + int(GROW_CAP * max_eval))
            if anchor2_enabled():
                hit = yield from anchor2(ranked, table, glimit, goal, None)
                if hit is not None:
                    pinfo["port"] = "anchor2"
                    return hit
            if scale_enabled():
                hit = yield from scaled(ranked, table, glimit)
                if hit is not None:
                    return hit
            if let_enabled():
                hit = yield from let_stage(ranked, P, table, min(limit, vev() + int(LET_CAP * max_eval)))
                if hit is not None:
                    pinfo["port"] = "let"
                    return hit
            if mstate["on"]:
                if (let2_enabled() or _discrim_on()) and mstate["skips"] > mstate["spent"]:
                    # LET2 (docs/LET2.md): LET's stage paid only from the unspent skips; on a miss
                    # the gate's rejection record is restored, so later stages see main's gate.
                    # NOMAD_DISCRIM on runs this stage with its distinguishing-experiment guard
                    # (docs/DISCRIM.md); NOMAD_LET2 alone runs it unguarded
                    e0 = evals
                    g0 = (len(gate.rejected), len(gate.vias)) if gate is not None else None
                    hit = yield from let_stage(ranked, P, table, min(limit, evals + mstate["skips"] - mstate["spent"]), real=True)
                    mstate["spent"] += evals - e0
                    if hit is not None:
                        pinfo["port"] = "let2"
                        return hit
                    if g0 is not None and LET2_RESTORE:
                        del gate.rejected[g0[0]:]
                        del gate.vias[g0[1]:]
                if merge_enabled():
                    hit = yield from merge_extra(ranked, table, limit)
                    if hit is not None:
                        return hit
                yield from merge_settle()
        if task.out == "str" and splice_enabled():
            hit = yield from splice(ranked, P, limit)
            if hit is not None:
                pinfo["port"] = "splice"
                return hit
        # the field's own atoms for this signature first (the plain probe's),
        # then the best-scoring bank blocks
        own = {json.dumps(t) for t in library.values()}
        keep = [z for z in ranked if json.dumps(z[2]) in own]
        rest = [z for z in ranked if json.dumps(z[2]) not in own]
        if rel and ROUTE_ATOMS:
            rest.sort(key=lambda z: (z[0][:1], rel.get(z[1], 0.5), z[0][1:], z[1]), reverse=True)
        keep += rest[:PORT_K]
        for _sc, _n, t, v in keep:
            hit = offer(1, t, v, True, P, B)
            if hit is not None:
                if not stop_on(hit):
                    yield evals
                    continue
                pinfo["port"] = "block"
                return hit
        istate.update(table=table, ranked=ranked)
        if task.out == "str" and text_invent() and inv is not None and invent_applies():
            # INVENT_TEXT early pass: concat anchors on the bank blocks' values (already computed),
            # at most TEXT_ANCHOR_N lookups, only when a block is a proper prefix / suffix of the goal
            istate["ilimit"] = limit
            hit = yield from text_anchors([z for z in ranked if all(type(x) is str for x in z[3])], table)
            if hit is not None:
                return hit
            if pats:
                hit = yield from text_templates(P, [z for z in ranked if all(type(x) is str for x in z[3])],
                                                paid=False)
                if hit is not None:
                    return hit
            if _I_chain():
                hit = yield from text_chain(P, [z for z in ranked if all(type(x) is str for x in z[3])])
                if hit is not None:
                    return hit
        if inv is not None and invent_applies() and not invent_deferred(ranked):
            hit = yield from invent_phase(P, B, limit)
            if hit is not None:
                return hit
        return None

    def merge_extra(ranked, table, limit):
        """MERGE (docs/MERGE.md), after every one of main's int anchors missed.

        The bank merged by public values (one block per value class) is anchored on the goal and on each learned scale target; only
        anchors main's top-PORT_ANCHOR_N cut never reached are tried, and only
        with the evaluations MERGE saved (duplicates not scanned, lookups that
        already missed not repeated). Main's stages before this one see the
        virtual count ``vev()`` (as if every skip had cost its evaluation), so
        they try exactly main's candidates and stop where main stops; this
        stage then spends at most the skips, so every later stage starts no
        later than in main. 1 evaluation per lookup, WITNESS-gated, capped."""
        nonlocal evals
        if gate is not None and len(gate.rejected) + MERGE_REJECTS > gate.max_rejects:
            return None
        rej0 = len(gate.rejected) if gate is not None else 0
        skey = (lambda z: route_sort_key(z, rel)) if rel else (lambda z: (z[0], z[1]))
        targets = [(goal, None, "anchor")]
        if scale_enabled():
            for k, kt in bank_scales(bank):
                targets.append((tuple(g * k for g in goal), (lambda h, kt=kt: ["div", h, kt]), f"div{k}"))
                if all(g % k == 0 for g in goal):
                    targets.append((tuple(g // k for g in goal), (lambda h, kt=kt: ["mul", h, kt]), f"mul{k}"))
        for g2, wrap, tag in targets:
            if any(abs(x) > MAX_INT for x in g2):
                continue
            rm = ranked if wrap is None else sorted(((block_score(z[3], g2, task.out),) + z[1:] for z in ranked),
                                                    key=skey, reverse=True)
            done = {z[1] for z in rm[:PORT_ANCHOR_N]}
            for sc, n, t, v in merge_ranked(rm)[:PORT_ANCHOR_N]:
                if sc[0] < 0:
                    break
                if n in done:
                    continue
                for op in ("add", "sub", "rsub", "mul"):
                    if mstate["spent"] >= mstate["skips"] or evals >= limit:
                        return None
                    if gate is not None and len(gate.rejected) - rej0 >= MERGE_REJECTS:
                        return None
                    mstate["spent"] += 1
                    evals += 1
                    yield evals
                    need = _residual(op, v, g2)
                    b = table.get(_key(need)) if need is not None else None
                    if b is None:
                        continue
                    hit = ["sub", b, t] if op == "rsub" else [op, t, b]
                    hit = wrap(hit) if wrap else hit
                    if stop_on(hit):
                        pinfo["port"] = "merge:" + tag
                        return hit
                    yield evals
        return None

    def scaled(ranked, table, limit):
        """GROW learned scales (docs/GROW.md): a constant k >= 2 that learned
        memory uses as a divisor or a factor (``bank_scales``) rescales the
        goal: goal*k is anchored and wrapped in div(., k); goal/k (where exact)
        is anchored and wrapped in mul(., k). Rescaling costs no evaluation;
        every lookup costs 1 and every fit is WITNESS-gated."""
        targets = []
        for k, kt in bank_scales(bank):
            targets.append((tuple(g * k for g in goal), (lambda h, kt=kt: ["div", h, kt]), f"div{k}"))
            if all(g % k == 0 for g in goal):
                targets.append((tuple(g // k for g in goal), (lambda h, kt=kt: ["mul", h, kt]), f"mul{k}"))
        for g2, wrap, tag in targets:
            if any(abs(x) > MAX_INT for x in g2):
                continue
            rk = sorted(((block_score(z[3], g2, task.out),) + z[1:] for z in ranked),
                        key=(lambda z: route_sort_key(z, rel)) if rel else (lambda z: (z[0], z[1])), reverse=True)
            hit = yield from anchor1(rk, table, limit, g2, wrap)
            if hit is not None:
                pinfo["port"] = "scale:" + tag
                return hit
        if anchor2_enabled():
            for g2, wrap, tag in targets:
                if any(abs(x) > MAX_INT for x in g2):
                    continue
                hit = yield from anchor2(ranked, table, limit, g2, wrap)
                if hit is not None:
                    pinfo["port"] = "scale2:" + tag
                    return hit
        return None

    def let_stage(ranked, P, table, limit, real=False):
        """LET (docs/LET.md): reasoning with an intermediate result ``t`` used twice.

        For each bank block ``t`` (a certified program of the field, already run by PORT; distinct public
        values, smallest tree first, then block_score; at most LET_N), the one-step terms over t
        (``let_terms``: t, op(t, x), op(x, t), op(t, t)) are formed; a term whose public values are already
        in the probe's table is free (the regular levels paid for it), every other term costs 1 evaluation.
        A kept term equal to the goal, or a pair of kept terms over the same t whose add / sub / reversed
        sub / mul gives the goal (residual lookup), or a kept term // a learned scale, is assembled
        (``let t = .. in f(t) op g(t)``, t written out twice); every assembled program costs 1
        evaluation and is WITNESS-gated. The stage stops after LET_REJECTS rejections and is skipped
        when the task's rejection cap could be spent. An empty field has no bank and never gets here."""
        nonlocal evals
        if gate is not None and len(gate.rejected) + LET_REJECTS > gate.max_rejects:
            return None     # never let a let fit through on a spent rejection cap
        rej0 = len(gate.rejected) if gate is not None else 0
        atoms = [["var", n] for n, ty in task.inputs if ty == "int"] + [["const", c] for c in (1, 2, 3)]
        scales = bank_scales(bank)
        src = ranked
        if __import__("os").environ.get("NOMAD_LET_SOURCE", "bank").strip().lower() == "pool":
            # judge-only control (docs/LET.md): bind the probe's own (unlearned) pool values of size >= 2
            # instead of the field's certified blocks; same ranking, same caps
            src = [(block_score(vs_, goal, task.out), "", tr, vs_) for sz_ in sorted(P) if sz_ >= 2
                   for tr, vs_, _f in P[sz_].get("int", [])]
        cands, seenv = [], set()
        for sc, _n, t, v in src:
            if sc[0] < 0 or not v or type_of(v[0]) != "int" or _key(v) in seenv:
                continue
            seenv.add(_key(v))
            cands.append((size(t), tuple(-x for x in sc), t, v))
        cands.sort(key=lambda z: z[:2])
        tried: set = set()
        for _sz, _sc, t, v in cands[:LET_N]:
            if gate is not None and len(gate.rejected) - rej0 >= LET_REJECTS:
                return None
            terms = let_terms(t, v, rows, atoms)
            for i, (tr, tv) in enumerate(terms):
                if i == 0 or _key(tv) in table:
                    continue        # already computed (t by PORT, the rest by the regular levels)
                if (evals if real else vev()) >= limit:
                    return None
                evals += 1          # a new term is one evaluation
                yield evals
            ut = {}
            for tr, tv in terms:
                ut.setdefault(_key(tv), tr)
            fits = []
            for tr, tv in terms:
                if tv == goal and tr is not t:
                    fits.append(tr)
                for op in ("add", "sub", "rsub", "mul"):
                    need = _residual(op, tv, goal)
                    b = ut.get(_key(need)) if need is not None else None
                    if b is not None:
                        fits.append(["sub", b, tr] if op == "rsub" else [op, tr, b])
                for k, kt in scales:
                    if all(x // k == g for x, g in zip(tv, goal)):
                        fits.append(["div", tr, kt])
            for hit in fits:
                if (evals if real else vev()) >= limit or (gate is not None and len(gate.rejected) - rej0 >= LET_REJECTS):
                    return None
                key = json.dumps(hit)
                if key in tried:
                    continue
                tried.add(key)
                evals += 1      # an assembled program is one candidate evaluation
                yield evals
                if stop_on(hit):
                    if real and _discrim_on():
                        # DISCRIM guard (docs/DISCRIM.md): the accepted let fit returns only when no
                        # surviving alternative disagrees with it on distinguishing inputs
                        ok = yield from discrim_guard(hit, fits, limit)
                        if ok is None:
                            return None
                        if ok is not hit and not stop_on(ok):
                            return None
                        return ok
                    return hit
                yield evals
        return None

    def discrim_guard(hit, fits, limit):
        """DISCRIM (docs/DISCRIM.md) for one WITNESS-accepted fallback fit. Alternatives: the stage's
        other fits for the same intermediate and the hit's evidence-preserving simplifications. Each
        alternative checked on the evidence costs 1 evaluation and each signature on the distinguishing
        inputs costs 1 (paid from the same budget; out of budget = not confirmed). Reads only the
        public and challenge rows (never task.final)."""
        nonlocal evals
        from . import discrim as _D
        ev_rows = _D.evidence(task)
        hk = json.dumps(hit)
        alts, keys = [], {hk}
        for a in list(fits) + _D.simplifications(hit, task.inputs, ev_rows):
            k = json.dumps(a)
            if k not in keys:
                keys.add(k)
                alts.append(a)
        alts = alts[:_D.DISCRIM_ALT]
        surv = []
        for a in alts:
            if evals >= limit:
                return None
            evals += 1
            yield evals
            if _D.fits(a, ev_rows):
                surv.append(a)
        need = len(surv) + 1 if surv else 0
        if evals + need > limit:
            return None
        evals += need
        if need:
            yield evals
        d = _D.decide(hit, surv, task.inputs, ev_rows)
        _D.note(task, hit, surv, d)
        if d["verdict"] == "confirmed":
            return hit
        return d["pick"]    # ambiguous: the unique simplest explanation (MDL), or None (keep searching)

    grow_rej = [None]

    def grow_spent() -> bool:
        """True once GROW_REJECTS WITNESS rejections came from GROW anchors."""
        if gate is None:
            return False
        if grow_rej[0] is None:
            grow_rej[0] = len(gate.rejected)
        return len(gate.rejected) - grow_rej[0] >= GROW_REJECTS

    def splice(ranked, P, limit):
        """SPLICE (docs/TEXT.md): the string analogue of the anchor. The goal
        is cut, left to right, into at most SPLICE_PIECES pieces, each the
        public values of a learned bank block or of a probe pool entry, with
        at least one bank block; optionally under an upper / lower wrapper
        when the goal is already in that case on every row. Candidates for
        the next piece are found by an index on their first-row value (no
        evaluation); each candidate checked on all rows costs 1 evaluation;
        every fit is WITNESS-gated. Shares GROW's cap and rejection budget."""
        nonlocal evals
        glimit = min(limit, evals + int(GROW_CAP * max_eval))
        # pool values first; a bank block counts as learned only when it adds
        # a value the probe's pools do not already hold (so a renamed block
        # that merely re-spells an input, e.g. upper(srev(sp)) = " ", does not)
        cands: dict[str, tuple] = {}
        for sz_ in sorted(P):
            for tr, vs_, _f in P[sz_].get("str", []):
                if all(vs_):
                    cands.setdefault(_key(vs_), (tr, vs_, False))
        for _sc, _n, t, v in ranked:
            if type_of(v[0]) == "str" and all(v):
                cands.setdefault(_key(v), (t, v, True))
        for wrap in (None, "upper", "lower"):
            fn = (lambda x: x) if wrap is None else (str.upper if wrap == "upper" else str.lower)
            if wrap is not None and not all(fn(g) == g for g in goal):
                continue
            index: dict[str, list] = {}
            for t, v, isb in cands.values():
                index.setdefault(fn(v[0]), []).append((t, tuple(fn(x) for x in v), isb))

            def dfs(rem, pieces, used):
                nonlocal evals
                if all(r == "" for r in rem):
                    if not used or len(pieces) < 2:
                        return None
                    tree = pieces[-1]
                    for x in reversed(pieces[:-1]):
                        tree = ["concat", x, tree]
                    return [wrap, tree] if wrap else tree
                if len(pieces) >= SPLICE_PIECES or any(r == "" for r in rem):
                    return None
                last = len(pieces) == SPLICE_PIECES - 1
                for L in range(len(rem[0]), 0, -1):
                    for t, fv, isb in index.get(rem[0][:L], ()):
                        if last and not (used or isb):
                            continue
                        if grow_spent() or evals >= glimit:
                            return "stop"
                        evals += 1
                        yield evals
                        if not all(r.startswith(x) for r, x in zip(rem, fv)):
                            continue
                        got = yield from dfs(tuple(r[len(x):] for r, x in zip(rem, fv)), pieces + [t], used or isb)
                        if got == "stop":
                            return "stop"
                        if got is not None:
                            if stop_on(got):
                                return got
                            yield evals
                return None

            got = yield from dfs(tuple(goal), [], False)
            if got == "stop":
                return None
            if got is not None:
                return got
        return None

    istate: dict = {"seen": set(), "done": False}
    gcache: dict = {}

    def invent_applies() -> bool:
        """INVENT runs for int goals; with NOMAD_BRIDGE on also for str goals
        (the text side invents its own primitives; docs/BRIDGE.md)."""
        return task.out == "int" or (task.out == "str" and bridge_enabled() and _flag("NOMAD_BRIDGE_INVENT", "on"))

    def invent_deferred(ranked) -> bool:
        """INVENT runs after the probe's regular levels (not before them)
        when the after-levels mode is set, or when a bank block already
        equals the goal on >= INVENT_EQ_GATE public rows (the regular
        levels are then likely to finish the task; docs/INVENT.md)."""
        from . import invent as _I
        if _I.INVENT_AT == "after" or task.out == "str":
            return True   # str goals (NOMAD_BRIDGE): only the budget the regular levels left
        if _I.INVENT_EQ_GATE and ranked and ranked[0][0][0] >= _I.INVENT_EQ_GATE:
            return True
        return False

    def text_invent() -> bool:
        from . import invent as _I
        return _I.text_enabled()

    def text_split(v) -> str | None:
        """'pre' / 'suf' when the string block value v is a proper prefix / suffix of the goal on every row."""
        if not v or any(type(x) is not str or not x for x in v) or len(v) != len(goal):
            return None
        if all(len(x) < len(g) and g.startswith(x) for x, g in zip(v, goal)):
            return "pre"
        if all(len(x) < len(g) and g.endswith(x) for x, g in zip(v, goal)):
            return "suf"
        return None

    def text_anchors(cands, table):
        """Concat residual anchors, longest matching blocks first: the remainder lookup is free
        (values already computed); an assembled candidate costs 1 evaluation."""
        nonlocal evals
        from . import invent as _I
        local = dict(table)
        for z in cands:
            local.setdefault(_key(z[3]), z[2])
        done = 0
        for z in sorted(cands, key=lambda z: -sum(len(x) for x in z[3])):
            side = text_split(z[3])
            if side is None:
                continue
            if done >= _I.TEXT_ANCHOR_N or evals >= istate.get("ilimit", max_eval):
                return None
            done += 1
            if side == "pre":
                need = tuple(g[len(x):] for x, g in zip(z[3], goal))
            else:
                need = tuple(g[:len(g) - len(x)] for x, g in zip(z[3], goal))
            b = local.get(_key(need))
            if b is None:
                continue   # a lookup on values already computed (no evaluation, like the rescaled targets)
            evals += 1     # the assembled concat program is one candidate evaluation
            yield evals
            hit = ["concat", z[2], b] if side == "pre" else ["concat", b, z[2]]
            if stop_on(hit):
                pinfo["port"] = "invent:text:" + side
                return hit
            yield evals
        return None

    def text_chain(P, learned):
        """TEXT_CHAIN (docs/TEXT_CHAIN.md): concat chains of >= 3 parts by recursive prefix / suffix
        peeling over computed values (probe pools, case / itos variants, bank and invented blocks; at
        least one learned part). Peeling is a lookup (no evaluation); each assembled chain costs 1
        evaluation and is WITNESS-gated; at most TEXT_CHAIN_N chains per task."""
        nonlocal evals
        from . import invent as _I
        tried = istate.setdefault("chain_tried", set())
        if len(tried) >= _I.TEXT_CHAIN_N:
            return None
        ops = opset_of(task)
        pool_s, pool_i = [], []
        for sz_ in sorted(P):
            pool_s += [(tr, vs_) for tr, vs_, _f in P[sz_].get("str", [])]
            pool_i += [(tr, vs_) for tr, vs_, _f in P[sz_].get("int", [])]
        parts = _I.chain_parts(goal, pool_s, [(z[2], z[3]) for z in learned], pool_i, ops)
        if _I.TEXT_CHAIN_LEARNED and not any(e[2] for e in parts):
            return None
        selpool = None
        if "sel" in ops:    # INFLECT: selector completion of a chain's last segment (docs/INFLECT.md)
            selpool = (pool_s + [(z[2], z[3]) for z in learned], pool_i)
        for tree in _I.text_chain(goal, parts, selpool=selpool):
            k = json.dumps(tree)
            if k in tried:
                continue
            if len(tried) >= _I.TEXT_CHAIN_N or evals >= istate.get("ilimit", max_eval):
                return None
            tried.add(k)
            evals += 1     # the assembled chain is one candidate evaluation
            yield evals
            if stop_on(tree):
                pinfo["port"] = "invent:text:chain"
                return tree
            yield evals
        return None

    def text_templates(P, learned, *, paid: bool):
        """TEXT_ABSTRACT (docs/TEXTPAT.md): instantiate anti-unified string templates.

        paid=False: compose an instance from values already in the probe pool (plus free
        case / itos / concat variants); a miss costs nothing; a public-row match costs 1
        evaluation and is WITNESS-gated. paid=True: run length-matching instances as
        whole programs (1 evaluation each, capped), after earlier passes missed.
        """
        nonlocal evals
        if not pats or task.out != "str":
            return None
        from . import textpat as _TP
        tried = istate.setdefault("textpat_tried", set())
        cap = _TP.TEXTPAT_N if paid else _TP.TEXTPAT_FREE_N
        offered = istate.setdefault("textpat_paid" if paid else "textpat_free", 0)
        if offered >= cap or evals >= istate.get("ilimit", max_eval):
            return None
        memo = {} if paid else _TP.memo_from(P, learned, rows, task.inputs)
        ops = set(opset_of(task))
        for tree in pats:
            k = json.dumps(tree)
            if k in tried:
                continue
            if paid:
                if not _TP.length_matches(tree, rows, goal):
                    continue
                if offered >= cap or evals >= istate.get("ilimit", max_eval):
                    return None
                tried.add(k)
                evals += 1
                offered += 1
                istate["textpat_paid"] = offered
                yield evals
                try:
                    v = tuple(run(tree, r) for r in rows)
                except Invalid:
                    continue
                if v != goal:
                    yield evals
                    continue
                if stop_on(tree):
                    pinfo["port"] = "invent:text:template"
                    return tree
                yield evals
            else:
                v = _TP.free_eval(tree, rows, memo, ops)
                if v != goal:
                    continue
                if offered >= cap or evals >= istate.get("ilimit", max_eval):
                    return None
                tried.add(k)
                evals += 1     # assembled template is one candidate evaluation
                offered += 1
                istate["textpat_free"] = offered
                yield evals
                if stop_on(tree):
                    pinfo["port"] = "invent:text:template"
                    return tree
                yield evals
        return None

    def invent_phase(P, B, limit):
        """INVENT (docs/INVENT.md), one capped phase after PORT/GROW and the
        atoms: (1) the field's invented blocks instantiated over the task's
        inputs (1 evaluation each) are anchored (residual lookup add / sub /
        reversed sub / mul, 1 evaluation each) on the goal and on the goal
        rescaled by learned and derived constants; derived constants also
        rescale the bank blocks' anchors; (2) invented primitives (round 1
        and composed rounds) as single nodes over the probe's pools, size
        by size, with direct and residual fits on the same targets. Every
        fit is WITNESS-gated; the phase spends at most INVENT_CAP of the
        budget and PORT_ANCHOR_REJECTS rejections."""
        nonlocal evals
        from . import invent as _I
        if istate["done"]:
            return None
        istate["done"] = True
        table, ranked = istate["table"], istate["ranked"]
        ilimit = min(limit, evals + int(_I.INVENT_CAP * max_eval))
        istate["ilimit"] = ilimit
        rej0 = len(gate.rejected) if gate is not None else 0

        def over():
            if evals >= ilimit:
                return True
            return gate is not None and len(gate.rejected) - rej0 >= PORT_ANCHOR_REJECTS

        learned = bank_scales(bank) if task.out == "int" else []   # str goals: no scales (docs/BRIDGE.md)
        targets = [(goal, None, "", False)]
        for k, kt in learned + list(inv.consts):
            derived = k not in {a for a, _ in learned}
            targets.append((tuple(g * k for g in goal), (lambda h, kt=kt: ["div", h, kt]), f"div{k}", derived))
            if all(g % k == 0 for g in goal):
                targets.append((tuple(g // k for g in goal), (lambda h, kt=kt: ["mul", h, kt]), f"mul{k}", derived))
        targets = [z for z in targets if task.out != "int" or not any(abs(x) > MAX_INT for x in z[0])]
        if _I.LEVEL_TARGETS == "goal":
            ltargets = targets[:1]
        else:
            ltargets = targets
        tset = {_key(g2): (wrap, tag) for g2, wrap, tag, _d in targets}

        def fit(tree, tag, rnd):
            if stop_on(tree):
                pinfo["port"] = f"invent:r{rnd}" + (":" + tag if tag else "")
                return tree
            return None

        # floor-division fit (genome gene inv_floor_fit, docs/SELFEDIT.md): a computed block value v
        # with v // k == goal on every public row is offered as v // k. Like the rescaled targets
        # (goal * k), the test is a lookup on a value already computed (no extra evaluation);
        # only the WITNESS-gated offer counts as a fit.
        floors = [(k, kt) for k, kt in learned + list(getattr(inv, "floor_consts", None) or inv.consts) if k >= 2] \
            if getattr(inv, "floor", False) and task.out == "int" else []
        goal_t = tuple(goal)

        def floor_fit(t, v, rnd):
            for k, kt in floors:
                if all(type(x) is int for x in v) and tuple(x // k for x in v) == goal_t:
                    hit = fit(["div", t, kt], f"floor{k}", rnd)
                    if hit is not None:
                        return hit
                    yield evals
            return None

        # NOMAD_CEIL (docs/CEIL.md): ceiling-division fit, the floor fit's twin. A computed block value v
        # with ceil(v / k) == goal on every public row (not exact on every row: exact division is the
        # rescaled target's) is offered as (v + (k - 1)) // k; the test is a lookup on a value already
        # computed, only the WITNESS-gated offer counts.
        ceils = _I.ceil_constants(learned, inv.consts) if getattr(inv, "ceil", False) and task.out == "int" else []

        def ceil_fit(t, v, rnd):
            for k, kt in ceils:
                if all(type(x) is int for x in v) and not all(x % k == 0 for x in v) \
                        and tuple(-(-x // k) for x in v) == goal_t:
                    hit = fit(["div", ["add", t, ["sub", kt, ["const", 1]]], kt], f"ceil{k}", rnd)
                    if hit is not None:
                        return hit
                    yield evals
            return None

        # (1) invented blocks over the task's inputs
        ri = []
        for n, t in inv.instances:
            if over():
                return None
            evals += 1
            yield evals
            try:
                v = tuple(run(t, r) for r in rows)
            except Invalid:
                continue
            if not v or any(type_of(x) != task.out for x in v):
                continue
            if len(set(v)) == 1 or any(v == tuple(r[nm] for r in rows) for nm, _ty in task.inputs):
                continue   # a constant or just an input (e.g. min(a, a·a) = a): no new block
            table.setdefault(_key(v), t)
            if _key(v) in tset:
                wrap, tag = tset[_key(v)]
                hit = fit(wrap(t) if wrap else t, tag, inv.rounds.get(n, 1))
                if hit is not None:
                    return hit
                yield evals
            elif floors:
                hit = yield from floor_fit(t, v, inv.rounds.get(n, 1))
                if hit is not None:
                    return hit
            if ceils and _key(v) not in tset:
                hit = yield from ceil_fit(t, v, inv.rounds.get(n, 1))
                if hit is not None:
                    return hit
            ri.append((None, n, t, v))
        inst_names = {n for n, _t in inv.instances}
        if floors:
            # floor-division fit on the bank blocks' values (already computed by the probe)
            for z in ranked:
                hit = yield from floor_fit(z[2], z[3], 0)
                if hit is not None:
                    return hit
        if ceils:
            # ceiling-division fit on the bank blocks' values (already computed by the probe)
            for z in ranked:
                hit = yield from ceil_fit(z[2], z[3], 0)
                if hit is not None:
                    return hit
        if task.out == "str" and text_invent():
            # INVENT_TEXT (docs/INVENT_TEXT.md): concat residual anchors on string goals. A block value
            # v that is a proper prefix (suffix) of the goal on every public row leaves a remainder;
            # a pool / block value equal to the remainder completes concat(v, b) (concat(b, v)).
            learned_s = ri + [z for z in ranked if all(type(x) is str for x in z[3])]
            hit = yield from text_anchors(learned_s, table)
            if hit is not None:
                return hit
            if pats:
                hit = yield from text_templates(P, learned_s, paid=False)
                if hit is not None:
                    return hit
            if _I_chain():
                hit = yield from text_chain(P, learned_s)
                if hit is not None:
                    return hit
        for g2, wrap, tag, derived in targets:
            cand = ri + (ranked if derived else [])
            if task.out != "int":
                break   # residual anchors (add / sub / mul) are integer-only
            rk = sorted(((block_score(z[3], g2, task.out),) + z[1:] for z in cand),
                        key=lambda z: (z[0], z[1]), reverse=True)
            for sc, _n, t, v in rk[:PORT_ANCHOR_N]:
                if sc[0] < 0:
                    break
                rnd = inv.rounds.get(_n, 1) if _n in inst_names else 0   # 0: a bank block under a derived constant
                for op in ("add", "sub", "rsub", "mul"):
                    if over():
                        return None
                    evals += 1
                    yield evals
                    need = _residual(op, v, g2)
                    b = table.get(_key(need)) if need is not None else None
                    if b is None:
                        continue
                    hit = ["sub", b, t] if op == "rsub" else [op, t, b]
                    hit = fit(wrap(hit) if wrap else hit, tag, rnd)
                    if hit is not None:
                        return hit
                    yield evals
        # (2) invented primitives as single nodes
        if inv.ops:
            for sz in range(2, max_size + _I.INVENT_SIZE + 1):
                for name, iop in inv.ops.items():
                    for split in _compositions(sz - 1, len(iop.args)):
                        lists = [list((P.get(s_, {}).get(t) or [])) for s_, t in zip(split, iop.args)]
                        if any(not l for l in lists):
                            continue
                        for combo in product(*lists):
                            if any(_key(combo[i][1]) > _key(combo[j][1]) for i, j in iop.symmetric):
                                continue   # the invention's own symmetry: one order is enough
                            if not any(_var_names(c[0], []) for c in combo):
                                continue   # constant arguments only: a constant, not a block
                            if over():
                                return None
                            evals += 1
                            yield evals
                            try:
                                vals = tuple(iop.fn(*args) for args in zip(*(c[1] for c in combo)))
                            except (Invalid, ValueError, TypeError, IndexError, OverflowError):
                                continue
                            if any(type_of(v) != iop.out for v in vals):
                                continue
                            if any(vals == c[1] for c in combo):
                                continue   # the application just returns an argument: no new block
                            tree = iop.build([c[0] for c in combo])
                            k = (iop.out, _key(vals))
                            if iop.out == task.out and _key(vals) in tset:
                                wrap, tag = tset[_key(vals)]
                                hit = fit(wrap(tree) if wrap else tree, tag, iop.round)
                                if hit is not None:
                                    return hit
                                yield evals
                                continue
                            if floors and iop.out == "int":
                                hit = yield from floor_fit(tree, vals, iop.round)
                                if hit is not None:
                                    return hit
                            if ceils and iop.out == "int":
                                hit = yield from ceil_fit(tree, vals, iop.round)
                                if hit is not None:
                                    return hit
                            if k in B or k in istate["seen"]:
                                continue
                            istate["seen"].add(k)
                            offer(sz, tree, vals, True, P, B)
                            if iop.out != "int" or task.out != "int":
                                continue
                            for g2, wrap, tag, _d in ltargets:
                                for op in ("add", "sub", "rsub", "mul"):
                                    if over():
                                        return None
                                    evals += 1
                                    yield evals
                                    need = _residual(op, vals, g2)
                                    b = table.get(_key(need)) if need is not None else None
                                    if b is None:
                                        continue
                                    hit = ["sub", b, tree] if op == "rsub" else [op, tree, b]
                                    hit = fit(wrap(hit) if wrap else hit, tag, iop.round)
                                    if hit is not None:
                                        return hit
                                    yield evals
        if pats and task.out == "str":
            learned_s = ri + [z for z in ranked if all(type(x) is str for x in z[3])]
            hit = yield from text_templates(P, learned_s, paid=True)
            if hit is not None:
                return hit
        return None

    def anchor1(rk, table, limit, g, wrap):
        """Depth-1 anchor on target g (the PORT anchor's loop, generalised)."""
        nonlocal evals
        gk = _key(g)
        for sc, _n, t, v in rk[:PORT_ANCHOR_N]:
            if sc[0] < 0:
                break
            if grow_spent():
                return None
            for op in ("add", "sub", "rsub", "mul"):
                if vev() >= limit:
                    return None
                mk = (gk, op, _key(v))
                if mk in mstate["miss"]:
                    mstate["skips"] += 1        # MERGE: the same lookup already missed (no candidate)
                    continue
                evals += 1
                yield evals
                need = _residual(op, v, g)
                b = table.get(_key(need)) if need is not None else None
                if b is None:
                    if mstate["on"]:
                        mstate["miss"].add(mk)
                    continue
                hit = ["sub", b, t] if op == "rsub" else [op, t, b]
                hit = wrap(hit) if wrap else hit
                if stop_on(hit):
                    return hit
                yield evals
        return None

    def anchor2(ranked, table, limit, goal, wrap):
        """GROW two-block anchor (docs/GROW.md): goal = a + b + c, where a and
        b are two of the ANCHOR2_M most goal-like int bank blocks that fit under the goal and c is looked
        up among the probe's values (1 evaluation per lookup; a hit is a
        WITNESS-gated fit). Reaches sums of three products that no single
        block plus one pool value can."""
        nonlocal evals
        # one block per distinct value; a part of a sum of non-negative parts
        # lies between 0 and the goal on every row; most goal-like order first
        top, seenv = [], set()
        for z in ranked:
            v = z[3]
            if type_of(v[0]) != "int" or _key(v) in seenv:
                continue
            seenv.add(_key(v))
            if all(0 <= x <= g for x, g in zip(v, goal)) and any(x > 0 for x in v):
                top.append(z)
        if rel:
            top.sort(key=lambda z: (-z[0][2], z[0][1], -rel.get(z[1], 0.0), z[1]))
        else:
            top.sort(key=lambda z: (-z[0][2], z[0][1], z[1]))
        top = top[:ANCHOR2_M]
        tried: set = set()
        if graph is not None:
            # GRAPH (docs/GRAPH.md): pairs proposed by spreading activation
            # over the certified co-occurrence graph, tried first; same
            # accounting, same caps. The loop below skips a pair tried here.
            for za, zb in graph_pairs(graph, ranked, goal, gcache):
                a, va = za[2], za[3]
                b, vb = zb[2], zb[3]
                tried.add(frozenset((_key(va), _key(vb))) if _key(va) != _key(vb) else (_key(va),))
                if grow_spent():
                    return None
                if vev() >= limit:
                    return None
                evals += 1
                yield evals
                need = tuple(g - x - y for g, x, y in zip(goal, va, vb))
                c = table.get(_key(need))
                if c is None:
                    continue
                hit = ["add", ["add", a, b], c]
                hit = wrap(hit) if wrap else hit
                if stop_on(hit):
                    pinfo["graph"] = True
                    return hit
                yield evals
        for i in range(len(top)):
            for j in range(i, len(top)):
                a, va = top[i][2], top[i][3]
                b, vb = top[j][2], top[j][3]
                if tried and (frozenset((_key(va), _key(vb))) if _key(va) != _key(vb) else (_key(va),)) in tried:
                    continue
                if grow_spent():
                    return None
                if vev() >= limit:
                    return None
                evals += 1
                yield evals
                need = tuple(g - x - y for g, x, y in zip(goal, va, vb))
                c = table.get(_key(need))
                if c is None:
                    continue
                hit = ["add", ["add", a, b], c]
                hit = wrap(hit) if wrap else hit
                if stop_on(hit):
                    return hit
                yield evals
        return None

    def probe_body(P, B, limit, start):
        nonlocal evals
        if bank:
            hit = yield from port_body(P, B, limit, start)
            if hit is not None:
                pinfo.update(spent=evals - start, hit=True)
                return hit
            yield from merge_settle()
        for n in ({} if bank else library):
            if evals >= limit:
                break
            evals += 1
            yield evals
            try:
                vals = tuple(run(["lib", n], r, library) for r in rows)
            except Invalid:
                continue
            hit = offer(1, ["lib", n], vals, True, P, B)
            if hit is not None:
                if not stop_on(hit):
                    yield evals
                    continue
                pinfo.update(spent=evals - start, hit=True)
                return hit
        for sz_ in range(2, max_size + 1):
            hit = yield from level(sz_, True, cap=limit, P=P, B=B)
            if hit in ("budget", "cap"):
                break
            if hit is not None:
                pinfo.update(spent=evals - start, hit=True)
                return hit
        if inv is not None and invent_applies() and "table" in istate and not istate["done"]:
            # deferred INVENT: only the budget the regular levels left
            hit = yield from invent_phase(P, B, limit)
            if hit is not None:
                pinfo.update(spent=evals - start, hit=True)
                return hit
        pinfo.update(spent=evals - start, hit=False)
        return None

    def level(sz: int, fresh_only: bool, ops: tuple[str, ...] = order, fresh_ops: tuple[str, ...] = (),
              cap: int | None = None, P=None, B=None, gated: bool = True):
        """Enumerate one size level; yields per evaluation, returns a hit or None.

        ``fresh_ops``: operators whose stage-1-only combinations at this size
        were already evaluated (the SENSE lead block), so only combinations
        touching a stage-2 entry are evaluated for them.
        """
        nonlocal evals
        main = P is None
        P = pools if P is None else P
        lim = max_eval if cap is None else min(cap, max_eval)
        for name in ops:
            op = OPS[name]
            need_fresh = fresh_only or name in fresh_ops
            for split in _compositions(sz - 1, len(op.args)):
                lists = [list((P.get(s_, {}).get(t) or [])) for s_, t in zip(split, op.args)]
                if any(not l for l in lists):
                    continue
                for combo in product(*lists):
                    if need_fresh and not any(c[2] for c in combo):
                        continue
                    if op.commutative and _key(combo[0][1]) > _key(combo[1][1]):
                        continue
                    if _redundant(name, combo):
                        continue
                    if main and not need_fresh and probe_at and sz <= stage1 and evals >= probe_at[0]:
                        probe_at.clear()
                        ph = yield from probe()
                        if ph is not None:
                            return ph
                    if evals >= lim:
                        return "budget" if lim >= max_eval else "cap"
                    evals += 1
                    yield evals
                    try:
                        vals = tuple(op.fn(*args) for args in zip(*(c[1] for c in combo)))
                        if any(type_of(v) != op.out for v in vals):
                            continue
                        if op.out == "str" and any(len(v) > MAX_STR for v in vals):
                            continue
                    except (Invalid, ValueError, TypeError, IndexError, OverflowError):
                        continue
                    hit = offer(sz, [name] + [c[0] for c in combo], vals, need_fresh or any(c[2] for c in combo), P, B)
                    if hit is not None:
                        if stop_on(hit, gated):
                            return hit
                        yield evals
        return None

    tried: list[dict] = []

    sinfo: dict = {}

    def done(hit):
        libs = [s[1] for s in subtrees(hit) if s[0] == "lib"]
        via = None
        if pinfo.get("hit"):
            via = ("port:" + pinfo.get("port", "probe")) if bank else "blockprobe"
            if pinfo.get("graph"):
                via += "+graph"
        return Search(hit, evals, None, order, libs, via, tried, sinfo)

    # TEXT_ABSTRACT (docs/TEXTPAT.md): try reusable string templates first, with
    # only input values in the memo. A miss costs nothing, so stage 1 below stays
    # the exact cold search; a public-row hit costs 1 evaluation and is WITNESS-gated.
    if pats and task.out == "str":
        istate["ilimit"] = max_eval
        hit = yield from text_templates({}, [], paid=False)
        if hit is not None:
            pinfo["hit"] = True
            return done(hit)

    # stage 1: the cold search below max_size
    for a in [["var", n] for n, _ in task.inputs] + [["const", c] for c in INT_CONSTANTS]:
        if evals >= max_eval:
            return Search(None, evals, "candidate_budget", order)
        hit = atom(a, False)
        yield evals
        if hit is not None:
            if stop_on(hit, WITNESS_GATE_STAGE1):
                return done(hit)
            yield evals
    for sz in range(2, stage1 + 1):
        hit = yield from level(sz, fresh_only=False, gated=WITNESS_GATE_STAGE1)
        if hit == "budget":
            return Search(None, evals, "candidate_budget", order)
        if hit is not None:
            return done(hit)
    # stage 1.4: SENSE lead block (field arm only, NOMAD_SENSE on). The
    # max_size level restricted to the operators the task's sense points at,
    # over stage 1's pools only, before library atoms enter. Charged 1 per
    # candidate like every level; the rest of that level later skips exactly
    # these combinations, so nothing is evaluated twice.
    # When the case split will run next, the lead block leaves it a reserve
    # (SPLIT_RESERVE of the budget); a block cut short by that reserve is not
    # treated as done, so the full level later re-covers it.
    lead = tuple(o for o in (aim or ()) if o in order)
    lead_done = False
    if lead and max_size > stage1:
        if gate is not None:
            gate.stage = "sense:" + "+".join(lead)
        from .sense import SPLIT_RESERVE
        cap = max_eval - int(SPLIT_RESERVE * max_eval) if split else None
        hit = yield from level(max_size, fresh_only=False, ops=lead, cap=cap)
        lead_done = hit != "cap"
        if hit == "cap":
            hit = None
        if hit == "budget":
            return Search(None, evals, "candidate_budget", order, [], None, tried, sinfo)
        if hit is not None:
            return Search(hit, evals, None, order, [], "sense:" + "+".join(lead), tried, sinfo)
    # stage 1.25: case split over stage 1's int pools (field arm only).
    # Reuses the values stage 1 computed; charges 1 per term/condition tested.
    if split:
        from .casesplit import split_gen
        if gate is not None:
            gate.stage = "casesplit:d1"
        ents = [(sz, tr, vs) for sz in sorted(pools) for (tr, vs, _f) in pools[sz].get("int", [])]
        shit, evals, sinfo = yield from split_gen(ents, goal, rows, evals, max_eval, accept=gate)
        if shit is not None:
            return Search(shit, evals, None, order, [], f"casesplit:d{sinfo['depth']}", tried, sinfo)
        if sinfo.get("reason") == "candidate_budget":
            return Search(None, evals, "candidate_budget", order, [], None, tried, sinfo)
    # stage 1.5: mutants of certified patterns (bounded, memory-ordered).
    # Only reached when the cold search below max_size has missed.
    if variation:
        vhit, vkind, evals, tried = yield from _variation_stage(task, variation, evals, max_eval, accept=gate)
        if vhit is not None:
            return Search(vhit, evals, None, order, [], f"variation:{vkind}", tried, sinfo)
    # GROW (docs/GROW.md): stage 1 exhausted before the probe trigger (few
    # inputs), so the probe has not run; run it now, after the lead block,
    # case split and mutants (which keep their order) and before stage 2.
    if probe_at and bank and (anchor2_enabled() or scale_enabled() or splice_enabled()):
        probe_at.clear()
        ph = yield from probe()
        if ph is not None:
            return done(ph)
    # stage 2: library atoms, resume
    if gate is not None:
        gate.stage = None
    for n in library:
        if evals >= max_eval:
            return Search(None, evals, "candidate_budget", order, [], None, tried, sinfo)
        hit = atom(["lib", n], True)
        yield evals
        if hit is not None:
            if stop_on(hit):
                return done(hit)
            yield evals
    for sz in range(2, max_size + 1):
        hit = yield from level(sz, fresh_only=sz <= stage1,
                               fresh_ops=lead if (lead_done and sz == max_size and max_size > stage1) else ())
        if hit == "budget":
            return Search(None, evals, "candidate_budget", order, [], None, tried, sinfo)
        if hit is not None:
            return done(hit)
    return Search(None, evals, "frontier", order, [], None, tried, sinfo)


def _compositions(total: int, parts: int) -> list[tuple[int, ...]]:
    if parts == 1:
        return [(total,)] if total >= 1 else []
    out = []
    for first in range(1, total - parts + 2):
        for rest in _compositions(total - first, parts - 1):
            out.append((first,) + rest)
    return out


# ----------------------------------------------------------------- WITNESS

def _wv(v: Value) -> float:
    """Encode a value as an exact float for WITNESS. Ints map to themselves;
    strings and lists map to a 48-bit content hash (exact in float64)."""
    if type_of(v) == "int":
        return float(v)
    h = hashlib.sha256(json.dumps([type_of(v), v]).encode()).hexdigest()
    return float(int(h[:12], 16))


_DEFAULT = {"int": 0, "str": "", "list": ()}


@dataclass(frozen=True)
class WorldEvaluation:
    task_id: str
    family: str
    candidate: str | None
    tree: list | None
    public_correct: bool
    witness_supported: bool
    final_correct: bool
    evaluations: int
    reason: str | None
    order: tuple[str, ...]
    library_used: tuple[str, ...]
    via: str | None = None
    variation: tuple = ()
    sense: dict | None = None   # SENSE record; never part of certification

    @property
    def certified(self) -> bool:
        return self.witness_supported and self.final_correct


def evaluate(task: WorldTask, *, prior: WorldPrior | None = None, use_family: bool = True,
             use_library: bool = True, max_size: int = 7, max_eval: int = 20000,
             variation: Any = None, casesplit: bool | None = None,
             sense: dict | bool | None = None,
             words: str | None = None) -> tuple[WorldEvaluation, WitnessReceipt | None]:
    """``words`` (MEANING, docs/MEANING.md): the task's natural-language description.
    Read only when NOMAD_MEANING is on, by a field (``prior``) holding a lexicon:
    concepts the words retrieve are tried first within ``meaning.MEANING_BUDGET``
    evaluations (WITNESS-gated); on a miss the normal search runs unchanged on the
    remaining budget. Without words, with the switch off, for an empty field and for
    the cold control this is exactly the search below."""
    library = (prior.primitives_for(task.inputs)
               if (prior is not None and use_library and prior.wants_library(task.family if use_family else None))
               else {})
    full, task = task, search_view(task)   # INTEGRITY: search never holds the final split
    spent, hit = 0, None
    if words and prior is not None and prior.lexicon:
        from . import meaning as _meaning
        if _meaning.enabled():
            hit, spent, _info = _meaning.stage(task, prior, words, max_eval=max_eval)
            via = "meaning:"
            if hit is None:
                from . import combine as _combine
                if _combine.enabled():   # COMBINE (docs/COMBINE.md): two retrieved concepts composed
                    hit, more, _info = _combine.stage(task, prior, words, max_eval=max_eval - spent)
                    spent += more
                    via = "combine:"
    if hit is not None:
        s = Search(hit[1], spent, None, (), [], via + hit[0])
    else:
        s = synthesize(task, prior=prior, use_family=use_family, use_library=use_library,
                       max_size=max_size, max_eval=max_eval - spent, variation=variation, casesplit=casesplit,
                       sense=sense)
        s.evaluations += spent
    vt = tuple(s.variation)
    sr = s.sense
    if s.tree is None:
        return WorldEvaluation(task.task_id, task.family, None, None, False, False, False,
                               s.evaluations, s.reason, s.order, (), None, vt, sr), None
    # Certify the standalone program: library calls are inlined first.
    # A mutant only fits the public rows; WITNESS decides here like for any program.
    tree = expand(s.tree, library)
    receipt, public_ok, final_ok = certify(full, tree)
    if receipt is None:
        return WorldEvaluation(task.task_id, task.family, render(tree), tree, False, False, False,
                               s.evaluations, "invalid_on_rows", s.order, tuple(s.library_used), s.via, vt, sr), None
    return WorldEvaluation(task.task_id, task.family, render(tree), tree, public_ok,
                           receipt.supported, final_ok, s.evaluations, None, s.order,
                           tuple(s.library_used), s.via, vt, sr), receipt


WORLD_WITNESS_ID = "nomad-witness-world-v1"


def program_hash(tree: list) -> str:
    """The transmission id certify() stamps on a receipt: sha256 of the standalone tree's JSON."""
    return hashlib.sha256(json.dumps(tree).encode()).hexdigest()


def check_binding(tree: list, receipt: WitnessReceipt, task_id: str | None = None) -> None:
    """INTEGRITY: raise ReceiptMismatch unless ``receipt`` attests exactly ``tree`` (and ``task_id``)."""
    if getattr(receipt, "witness_id", None) != WORLD_WITNESS_ID:
        raise ReceiptMismatch("receipt is not a WORLD WITNESS receipt")
    if getattr(receipt, "transmission_id", None) != program_hash(tree):
        raise ReceiptMismatch("submitted program does not match the receipt's program hash")
    if task_id is not None and getattr(receipt, "task_id", None) != task_id:
        raise ReceiptMismatch("receipt was attested on a different task")


@dataclass(frozen=True)
class ChallengeView:
    """INTEGRITY: what a search-time WITNESS consultation may see. There is no final split here."""
    task_id: str
    out: str
    public: tuple
    challenge: tuple

    @classmethod
    def of(cls, task: "WorldTask | ChallengeView") -> "ChallengeView":
        return cls(task.task_id, task.out, task.public, task.challenge)


def search_view(task: WorldTask) -> WorldTask:
    """INTEGRITY: the task as search receives it, with the final split removed (search never read it;
    now it cannot). Certification uses the full task after search returns."""
    return dataclasses.replace(task, final=())


def _attest(view: "WorldTask | ChallengeView", tree: list) -> tuple[WitnessReceipt | None, list]:
    """WITNESS on public + challenge rows only. Returns (receipt or None if invalid there, public values)."""
    def vals(rs):
        out = []
        for r, _ in rs:
            try:
                out.append(run(tree, r))
            except Invalid:
                out.append(None)
        return out

    pub, cha = vals(view.public), vals(view.challenge)
    if any(v is None for v in pub + cha):
        return None, pub
    d = _DEFAULT[view.out]
    receipt = Witness(witness_id=WORLD_WITNESS_ID).attest(
        task_id=view.task_id,
        transmission_id=program_hash(tree),
        world_epoch=0,
        current_public=tuple(_wv(d) for _ in view.public),
        target_public=tuple(_wv(e) for _, e in view.public),
        candidate_public=tuple(_wv(v) for v in pub),
        current_challenge=tuple(_wv(d) for _ in view.challenge),
        target_challenge=tuple(_wv(e) for _, e in view.challenge),
        candidate_challenge=tuple(_wv(v) for v in cha),
    )
    return receipt, pub


def consult(task: "WorldTask | ChallengeView", tree: list) -> WitnessReceipt | None:
    """INTEGRITY: the search-time WITNESS consultation. Reads public and challenge rows only, through
    a ChallengeView, so the final split is structurally unreachable. Same receipt as certify()."""
    return _attest(ChallengeView.of(task), tree)[0]


def final_check(task: WorldTask, tree: list) -> bool:
    """The independent final split: used only by certify(), after search has returned."""
    out = []
    for r, _ in task.final:
        try:
            out.append(run(tree, r))
        except Invalid:
            out.append(None)
    return all(v == e for v, (_, e) in zip(out, task.final))


def certify(task: WorldTask, tree: list) -> tuple[WitnessReceipt | None, bool, bool]:
    """WITNESS-attest a standalone program on a task's rows.

    Deterministic: the same task rows and program always give the same
    receipt_hash, so anyone holding the rows can re-attest and compare.
    Returns (receipt or None if the program is invalid on public/challenge
    rows, public_ok, final_ok). For use after search only (evaluate, the learner,
    feeds); search-time consultation is consult() (docs/INTEGRITY.md).
    """
    receipt, pub = _attest(task, tree)
    if receipt is None:
        return None, False, False
    final_ok = final_check(task, tree)
    public_ok = all(v == e for v, (_, e) in zip(pub, task.public))
    return receipt, public_ok, final_ok
