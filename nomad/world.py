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

import hashlib
import json
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable, Iterable, Sequence

from .witness import Witness, WitnessReceipt

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
}

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
                      opset: Sequence[str], inputs: Sequence[Sequence[str]], harvest: bool = True) -> None:
        if not receipt.supported or not receipt.verify_checksum():
            raise ValueError("Cannot learn from an unverified or failed WITNESS receipt")
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
            self._harvest(tree, [list(i) for i in inputs])
        self.witnessed += 1

    def _harvest(self, tree: list, inputs: list[list[str]]) -> None:
        for sub in subtrees(tree):
            if sub is tree or size(sub) < 3:
                continue
            key = hashlib.sha256(json.dumps(sub).encode()).hexdigest()[:8]
            name = f"L{key}"
            self.library.setdefault(name, sub)
            self.library_sig.setdefault(name, inputs)
            self.library_uses[name] = self.library_uses.get(name, 0.0) + 1.0

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

    # ---- persistence
    def snapshot(self) -> dict:
        return {"schema": "nomad.world-prior.v1", "witnessed": self.witnessed,
                "global": self.global_counts, "families": self.families,
                "library": self.library, "library_uses": self.library_uses,
                "library_sig": self.library_sig, "family_lib": self.family_lib}

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
    """
    opset = OPSETS[task.opset]
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
    if not library and not split and aim is None:
        s = _drive(_search_gen(task, cold_order, {}, max_size, max_eval))
        return _with_sense(_variation_fallback(task, s, mut, max_eval), rec)
    return _with_sense(_drive(_staged_gen(task, cold_order, library, max_size, max_eval, mut, split, aim)), rec)


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


def _variation_stage(task: WorldTask, mut: list[tuple[str, list]], evals: int, max_eval: int):
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
            return t, kind, evals, tried
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


def _staged_gen(task: WorldTask, order: tuple[str, ...], library: dict[str, list],
                max_size: int, max_eval: int, variation: list[tuple[str, list]] | None = None,
                split: bool = False, aim: tuple[str, ...] | None = None):
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
    """
    rows = [r for r, _ in task.public]
    goal = tuple(e for _, e in task.public)
    # pools[sz][type] -> list of (tree, vals, fresh); fresh = entered in stage 2
    pools: dict[int, dict[str, list[tuple[list, tuple, bool]]]] = {}
    best: dict[tuple[str, str], int] = {}  # (type, value key) -> smallest size seen
    evals = 0
    stage1 = max(1, max_size - 1)

    def offer(sz: int, tree: list, vals: tuple, fresh: bool) -> list | None:
        t = type_of(vals[0]) if vals else "bad"
        if t == "bad" or any(type_of(v) != t for v in vals):
            return None
        k = (t, _key(vals))
        if k in best and best[k] <= sz:
            return None
        best[k] = sz
        pools.setdefault(sz, {}).setdefault(t, []).append((tree, vals, fresh))
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

    def level(sz: int, fresh_only: bool, ops: tuple[str, ...] = order, fresh_ops: tuple[str, ...] = (),
              cap: int | None = None):
        """Enumerate one size level; yields per evaluation, returns a hit or None.

        ``fresh_ops``: operators whose stage-1-only combinations at this size
        were already evaluated (the SENSE lead block), so only combinations
        touching a stage-2 entry are evaluated for them.
        """
        nonlocal evals
        lim = max_eval if cap is None else min(cap, max_eval)
        for name in ops:
            op = OPS[name]
            need_fresh = fresh_only or name in fresh_ops
            for split in _compositions(sz - 1, len(op.args)):
                lists = [list((pools.get(s_, {}).get(t) or [])) for s_, t in zip(split, op.args)]
                if any(not l for l in lists):
                    continue
                for combo in product(*lists):
                    if need_fresh and not any(c[2] for c in combo):
                        continue
                    if op.commutative and _key(combo[0][1]) > _key(combo[1][1]):
                        continue
                    if _redundant(name, combo):
                        continue
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
                    hit = offer(sz, [name] + [c[0] for c in combo], vals, need_fresh or any(c[2] for c in combo))
                    if hit is not None:
                        return hit
        return None

    tried: list[dict] = []

    sinfo: dict = {}

    def done(hit):
        libs = [s[1] for s in subtrees(hit) if s[0] == "lib"]
        return Search(hit, evals, None, order, libs, None, tried, sinfo)

    # stage 1: the cold search below max_size
    for a in [["var", n] for n, _ in task.inputs] + [["const", c] for c in INT_CONSTANTS]:
        if evals >= max_eval:
            return Search(None, evals, "candidate_budget", order)
        hit = atom(a, False)
        yield evals
        if hit is not None:
            return done(hit)
    for sz in range(2, stage1 + 1):
        hit = yield from level(sz, fresh_only=False)
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
        ents = [(sz, tr, vs) for sz in sorted(pools) for (tr, vs, _f) in pools[sz].get("int", [])]
        shit, evals, sinfo = yield from split_gen(ents, goal, rows, evals, max_eval)
        if shit is not None:
            return Search(shit, evals, None, order, [], f"casesplit:d{sinfo['depth']}", tried, sinfo)
        if sinfo.get("reason") == "candidate_budget":
            return Search(None, evals, "candidate_budget", order, [], None, tried, sinfo)
    # stage 1.5: mutants of certified patterns (bounded, memory-ordered).
    # Only reached when the cold search below max_size has missed.
    if variation:
        vhit, vkind, evals, tried = yield from _variation_stage(task, variation, evals, max_eval)
        if vhit is not None:
            return Search(vhit, evals, None, order, [], f"variation:{vkind}", tried, sinfo)
    # stage 2: library atoms, resume
    for n in library:
        if evals >= max_eval:
            return Search(None, evals, "candidate_budget", order, [], None, tried, sinfo)
        hit = atom(["lib", n], True)
        yield evals
        if hit is not None:
            return done(hit)
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
             sense: dict | bool | None = None) -> tuple[WorldEvaluation, WitnessReceipt | None]:
    library = (prior.primitives_for(task.inputs)
               if (prior is not None and use_library and prior.wants_library(task.family if use_family else None))
               else {})
    s = synthesize(task, prior=prior, use_family=use_family, use_library=use_library,
                   max_size=max_size, max_eval=max_eval, variation=variation, casesplit=casesplit,
                   sense=sense)
    vt = tuple(s.variation)
    sr = s.sense
    if s.tree is None:
        return WorldEvaluation(task.task_id, task.family, None, None, False, False, False,
                               s.evaluations, s.reason, s.order, (), None, vt, sr), None
    # Certify the standalone program: library calls are inlined first.
    # A mutant only fits the public rows; WITNESS decides here like for any program.
    tree = expand(s.tree, library)
    receipt, public_ok, final_ok = certify(task, tree)
    if receipt is None:
        return WorldEvaluation(task.task_id, task.family, render(tree), tree, False, False, False,
                               s.evaluations, "invalid_on_rows", s.order, tuple(s.library_used), s.via, vt, sr), None
    return WorldEvaluation(task.task_id, task.family, render(tree), tree, public_ok,
                           receipt.supported, final_ok, s.evaluations, None, s.order,
                           tuple(s.library_used), s.via, vt, sr), receipt


def certify(task: WorldTask, tree: list) -> tuple[WitnessReceipt | None, bool, bool]:
    """WITNESS-attest a standalone program on a task's rows.

    Deterministic: the same task rows and program always give the same
    receipt_hash, so anyone holding the rows can re-attest and compare.
    Returns (receipt or None if the program is invalid on public/challenge
    rows, public_ok, final_ok).
    """
    def vals(rs):
        out = []
        for r, _ in rs:
            try:
                out.append(run(tree, r))
            except Invalid:
                out.append(None)
        return out

    pub, cha, fin = vals(task.public), vals(task.challenge), vals(task.final)
    if any(v is None for v in pub + cha):
        return None, False, False
    d = _DEFAULT[task.out]
    receipt = Witness(witness_id="nomad-witness-world-v1").attest(
        task_id=task.task_id,
        transmission_id=hashlib.sha256(json.dumps(tree).encode()).hexdigest(),
        world_epoch=0,
        current_public=tuple(_wv(d) for _ in task.public),
        target_public=tuple(_wv(e) for _, e in task.public),
        candidate_public=tuple(_wv(v) for v in pub),
        current_challenge=tuple(_wv(d) for _ in task.challenge),
        target_challenge=tuple(_wv(e) for _, e in task.challenge),
        candidate_challenge=tuple(_wv(v) for v in cha),
    )
    final_ok = all(v == e for v, (_, e) in zip(fin, task.final))
    public_ok = all(v == e for v, (_, e) in zip(pub, task.public))
    return receipt, public_ok, final_ok
