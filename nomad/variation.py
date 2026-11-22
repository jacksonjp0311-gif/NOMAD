"""VARIATION: perturb certified patterns, reward novelty, remember what paid.

Three small organs layered onto WORLD search. None of them certifies anything.

1. Variation operator (``mutants``). Takes a certified pattern (a whole
   program the sleep learner kept, or a certified library block) and makes
   one-step perturbations instead of only re-emitting it verbatim:

   - ``op_swap``     replace an operator by another one in the task's opset
                     with the same signature (``min`` -> ``max``, ``add`` -> ``sub``)
   - ``const_flip``  change an integer constant to another world constant
   - ``var_swap``    rename an input variable to another input of the same type
   - ``reorder``     swap two same-typed arguments of a non-commutative
                     operator (``sub(x, y)`` -> ``sub(y, x)``, ``ite`` branches)

   Every mutant is a plain tree for ``world.run``. A mutant that fits the
   public rows is returned by search like any other candidate and must then
   pass WITNESS on withheld rows and the final split. Mutation alone never
   certifies.

2. Novelty reward (``NoveltyArchive``). Each mutant has a behaviour
   signature: its outputs on fixed probe inputs per input signature
   (literals below, independent of every task and every held-out). Novelty is
   the mean normalised distance to the k nearest behaviours already known
   (archive, elites, library). Retention score = fitness + NOVELTY_WEIGHT *
   novelty, where fitness is the fraction of the public rows the mutant got
   right. A mutant with high novelty is kept even when its fitness is 0, so
   it can serve as a stepping stone for a later one-step mutation. The archive
   is capped (ARCHIVE_CAP) and evicts the lowest score, so it can never grow
   the search: search tries at most SEARCH_TRIES mutants in total.

3. Payoff memory (``PayoffMemory``). Per situation (cheap task features:
   opset, arity, output type, output sign, output-size relation) and per
   mutation kind: [paid, tried]. The kind order is by Laplace-smoothed rate
   shrunk toward the pooled rate, so perturbation is biased toward what has
   paid before in similar situations rather than chosen blindly. Ties break by
   a seeded hash, so runs are deterministic.

Actor/learner split: awake search and awake exploration only *read* this
state and emit traces. The single sleep learner (``consolidate``) is the only
writer. It re-attests a "paid" mutant itself with ``world.certify`` on the
frozen training task before counting it, recomputes behaviours itself, and
refuses anything from a held-out family. No transformers, no weights.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Sequence

from .world import (INT_CONSTANTS, OPS, OPSETS, Invalid, WorldTask, certify, consult, opset_of, run, search_view,
                    size, type_of)

KINDS: tuple[str, ...] = ("op_swap", "const_flip", "var_swap", "reorder")

SEARCH_TRIES = 32       # max mutants one search may evaluate (each = 1 evaluation)
EXPLORE_TRIES = 12      # max mutants one awake exploration may evaluate
ARCHIVE_CAP = 48        # novelty archive size bound
ELITE_CAP = 64          # certified whole programs kept as variation sources
SOURCE_CAP = 16         # max sources considered per task
NOVELTY_K = 3
NOVELTY_MIN = 0.34      # retain a mutant only if it is at least this novel
NOVELTY_WEIGHT = 0.5
MAX_MUTANT_SIZE = 9
SEED = 1337

# Fixed probe inputs per input signature. Chosen once, independent of every
# task row and every held-out family; used only to tell behaviours apart.
PROBES: dict[str, list[dict[str, Any]]] = {
    "x:int,y:int": [{"x": x, "y": y} for x, y in
                    ((1, 0), (0, 1), (-3, 2), (6, 6), (12, 5), (5, 12), (-4, -7), (20, 3))],
    "s:str": [{"s": s} for s in ("", "a", "Ab", "zebra", "NoMaD", "qq", "Sand dune")],
    "xs:list": [{"xs": xs} for xs in ((), (5,), (2, 9, 4), (7, 7, 1, 3), (0, -2, 8), (11, 3))],
}

# SCIENCE signatures (nomad/science.py): named int inputs. Probe values are a
# fixed pattern chosen once, independent of every science row; a stated
# constant column (k, c, kH, kO, kW) keeps its stated value, as in every task.
_SCI_PATTERN = ((1, 0, 2), (0, 1, 3), (3, 2, 1), (6, 6, 6), (12, 5, 2), (5, 12, 4), (2, -3, 7), (20, 3, 5))
for _names, _const in ((("u", "a", "t"), {}), (("u", "a", "d"), {}), (("u", "v", "t"), {}),
                       (("m", "u", "v"), {}), (("I", "R", "t"), {}),
                       (("h", "m", "s", "k"), {"k": 60}), (("v", "t", "k", "c"), {"k": 1000, "c": 3600}),
                       (("gH", "gO", "kH", "kO", "kW"), {"kH": 2, "kO": 32, "kW": 18})):
    _free = [n for n in _names if n not in _const]
    PROBES[",".join(f"{n}:int" for n in _names)] = [
        {**{n: pat[i % 3] * (i + 1) for i, n in enumerate(_free)}, **_const} for pat in _SCI_PATTERN]
del _names, _const, _free


def sig_key(inputs: Iterable[Sequence[str]]) -> str:
    return ",".join(f"{n}:{t}" for n, t in inputs)


def _tkey(tree: list) -> str:
    return json.dumps(tree, separators=(",", ":"))


def _hash(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, separators=(",", ":"), default=str).encode()).hexdigest()


# ---------------------------------------------------------------- 1. variation operator

def _paths(tree: list, path: tuple[int, ...] = ()) -> Iterable[tuple[tuple[int, ...], list]]:
    yield path, tree
    if tree[0] not in ("var", "const", "lib"):
        for i, c in enumerate(tree[1:], start=1):
            yield from _paths(c, path + (i,))


def _replace(tree: list, path: tuple[int, ...], new: list) -> list:
    if not path:
        return new
    out = list(tree)
    out[path[0]] = _replace(tree[path[0]], path[1:], new)
    return out


def mutants(tree: list, opset: Sequence[str], inputs: Sequence[Sequence[str]]) -> list[tuple[str, list]]:
    """All one-step perturbations of ``tree`` in a fixed order, deduplicated.

    Library references are not perturbed (sources are expanded trees). Only
    operators of ``opset`` are introduced; the original tree is excluded.
    """
    types = {n: t for n, t in inputs}
    seen = {_tkey(tree)}
    out: list[tuple[str, list]] = []

    def emit(kind: str, t: list) -> None:
        k = _tkey(t)
        if k not in seen and size(t) <= MAX_MUTANT_SIZE:
            seen.add(k)
            out.append((kind, t))

    for path, node in _paths(tree):
        tag = node[0]
        if tag == "const":
            for c in INT_CONSTANTS:
                if c != node[1]:
                    emit("const_flip", _replace(tree, path, ["const", c]))
        elif tag == "var":
            for n, t in inputs:
                if n != node[1] and t == types.get(node[1]):
                    emit("var_swap", _replace(tree, path, ["var", n]))
        elif tag in OPS:
            op = OPS[tag]
            for name in opset:
                o = OPS[name]
                if name != tag and o.args == op.args and o.out == op.out:
                    emit("op_swap", _replace(tree, path, [name] + node[1:]))
            if not op.commutative:
                n = len(op.args)
                for i in range(n):
                    for j in range(i + 1, n):
                        if op.args[i] == op.args[j] and node[i + 1] != node[j + 1]:
                            kids = list(node[1:])
                            kids[i], kids[j] = kids[j], kids[i]
                            emit("reorder", _replace(tree, path, [tag] + kids))
    return out


# ---------------------------------------------------------------- situations

def situation(task: WorldTask) -> str:
    """Cheap features of a task from its public rows only."""
    outs = [e for _, e in task.public]
    if task.out == "int":
        sign = "nonneg" if all(v >= 0 for v in outs) else "mixed"
        mags = []
        for r, e in task.public:
            ins = [abs(v) for v in r.values() if isinstance(v, int)] or [len(v) for v in r.values()]
            mags.append(abs(e) > max(ins) if ins else False)
        rel = "grow" if all(mags) else ("shrink" if not any(mags) else "mixed")
    else:
        sign = "na"
        rels = set()
        for r, e in task.public:
            n = max((len(v) for v in r.values() if not isinstance(v, int)), default=0)
            rels.add("longer" if len(e) > n else "shorter" if len(e) < n else "same")
        rel = rels.pop() if len(rels) == 1 else "mixed"
    return f"{task.opset}|{len(task.inputs)}|{task.out}|{sign}|{rel}"


# ---------------------------------------------------------------- 3. payoff memory

class PayoffMemory:
    """Per (situation, kind) counts [paid, tried]; Laplace-smoothed, pooled prior."""

    def __init__(self) -> None:
        self.counts: dict[str, dict[str, list[float]]] = {}

    def _pooled(self, kind: str) -> float:
        p = t = 0.0
        for table in self.counts.values():
            a, b = table.get(kind, [0.0, 0.0])
            p += a
            t += b
        return (p + 1.0) / (t + 2.0)

    def score(self, sit: str, kind: str) -> float:
        g = self._pooled(kind)
        p, t = self.counts.get(sit, {}).get(kind, [0.0, 0.0])
        return (p + 2.0 * g) / (t + 2.0)

    def order(self, sit: str, seed: int = SEED) -> tuple[str, ...]:
        return tuple(sorted(KINDS, key=lambda k: (-self.score(sit, k), _hash(seed, sit, k))))

    def record(self, sit: str, kind: str, paid: bool) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown mutation kind {kind!r}")
        pair = self.counts.setdefault(sit, {}).setdefault(kind, [0.0, 0.0])
        pair[0] += 1.0 if paid else 0.0
        pair[1] += 1.0

    def decay(self, gamma: float) -> None:
        for table in self.counts.values():
            for pair in table.values():
                pair[0] *= gamma
                pair[1] *= gamma


# ---------------------------------------------------------------- 2. novelty

def behaviour(tree: list, sig: str) -> list[str]:
    out = []
    for row in PROBES.get(sig, []):
        try:
            v = run(tree, row)
            out.append(json.dumps([type_of(v), v]))
        except Invalid:
            out.append("!")
    return out


def _dist(a: Sequence[str], b: Sequence[str]) -> float:
    if not a:
        return 0.0
    return sum(1 for x, y in zip(a, b) if x != y) / len(a)


def novelty(beh: Sequence[str], others: Sequence[Sequence[str]], k: int = NOVELTY_K) -> float:
    if not others:
        return 1.0
    ds = sorted(_dist(beh, o) for o in others)
    near = ds[:k]
    return sum(near) / len(near)


class VariationState:
    """Elites (certified sources), bounded novelty archive, payoff memory."""

    def __init__(self) -> None:
        self.elites: dict[str, dict[str, Any]] = {}    # tkey hash -> {tree, sig, family, n}
        self.archive: list[dict[str, Any]] = []        # {tree, sig, kind, fitness, novelty, score}
        self.memory = PayoffMemory()
        self.applied = 0

    # ---- sources (read by search and exploration)
    def sources(self, task: WorldTask, library: Iterable[list] = (), *, exclude_family: str | None = None,
                cap: int = SOURCE_CAP) -> list[list]:
        sig = sig_key(task.inputs)
        out: list[list] = []
        seen: set[str] = set()

        def add(t: list) -> None:
            k = _tkey(t)
            if k not in seen and len(out) < cap:
                seen.add(k)
                out.append(t)
        elites = [e for e in self.elites.values() if e["sig"] == sig and e.get("family") != exclude_family]
        elites.sort(key=lambda e: (-e.get("n", 0), _tkey(e["tree"])))
        for e in elites:
            add(e["tree"])
        for t in library:
            add(t)
        arch = [a for a in self.archive if a["sig"] == sig]
        arch.sort(key=lambda a: (-a["score"], _tkey(a["tree"])))
        for a in arch:
            add(a["tree"])
        return out

    def candidates(self, task: WorldTask, sources: Sequence[list], limit: int, seed: int = SEED
                   ) -> list[tuple[str, list]]:
        """Mutants of ``sources`` ordered by payoff memory for this situation."""
        sit = situation(task)
        rank = {k: i for i, k in enumerate(self.memory.order(sit, seed))}
        opset = opset_of(task)
        pool: list[tuple[tuple, str, list]] = []
        seen = {_tkey(s) for s in sources}
        for si, src in enumerate(sources):
            for kind, t in mutants(src, opset, task.inputs):
                k = _tkey(t)
                if k in seen:
                    continue
                seen.add(k)
                pool.append(((rank[kind], si, _hash(seed, k)), kind, t))
        pool.sort(key=lambda p: p[0])
        return [(kind, t) for _, kind, t in pool[:limit]]

    # ---- learner-only writes
    def add_elite(self, tree: list, sig: str, family: str | None) -> None:
        h = _hash(tree)[:12]
        e = self.elites.get(h)
        if e is None:
            self.elites[h] = {"tree": tree, "sig": sig, "family": family, "n": 1.0}
        else:
            e["n"] = e.get("n", 0.0) + 1.0
        if len(self.elites) > ELITE_CAP:
            worst = sorted(self.elites, key=lambda k: (self.elites[k].get("n", 0.0), k))[0]
            del self.elites[worst]

    def known_behaviours(self, sig: str, library: Iterable[list] = ()) -> list[list[str]]:
        out = [a["behaviour"] for a in self.archive if a["sig"] == sig]
        out += [behaviour(e["tree"], sig) for e in self.elites.values() if e["sig"] == sig]
        out += [behaviour(t, sig) for t in library]
        return out

    def consider(self, tree: list, sig: str, kind: str, fitness: float,
                 library: Iterable[list] = ()) -> bool:
        """Novelty reward: retain a mutant if novel enough, even with low fitness."""
        if sig not in PROBES or kind not in KINDS:
            return False
        beh = behaviour(tree, sig)
        if all(b == "!" for b in beh):
            return False  # invalid everywhere: no behaviour to be novel with
        if any(_tkey(a["tree"]) == _tkey(tree) for a in self.archive):
            return False
        nov = novelty(beh, self.known_behaviours(sig, library))
        if nov < NOVELTY_MIN:
            return False
        fitness = max(0.0, min(1.0, float(fitness)))
        entry = {"tree": tree, "sig": sig, "kind": kind, "fitness": round(fitness, 4),
                 "novelty": round(nov, 4), "score": round(fitness + NOVELTY_WEIGHT * nov, 4),
                 "behaviour": beh}
        self.archive.append(entry)
        if len(self.archive) > ARCHIVE_CAP:
            self.archive.sort(key=lambda a: (-a["score"], _tkey(a["tree"])))
            del self.archive[ARCHIVE_CAP:]
        return any(a is entry for a in self.archive)

    def decay(self, gamma: float) -> None:
        self.memory.decay(gamma)

    # ---- persistence
    def snapshot(self) -> dict:
        return {"schema": "nomad.variation.v1", "applied": self.applied, "elites": self.elites,
                "archive": self.archive, "memory": self.memory.counts}

    @classmethod
    def from_snapshot(cls, snap: dict) -> "VariationState":
        if snap.get("schema") != "nomad.variation.v1":
            raise ValueError("unknown variation schema")
        s = cls()
        s.applied = int(snap.get("applied", 0))
        s.elites = {k: dict(v) for k, v in (snap.get("elites") or {}).items()}
        s.archive = [dict(a) for a in (snap.get("archive") or [])][:ARCHIVE_CAP]
        s.memory.counts = {sit: {k: [float(a), float(b)] for k, (a, b) in t.items() if k in KINDS}
                           for sit, t in (snap.get("memory") or {}).items()}
        return s


# ---------------------------------------------------------------- persistence

def state_path() -> Path:
    from .paths import data_root
    return data_root() / "continuous" / "variation.json"


def load_state() -> VariationState:
    p = state_path()
    for path in (p, p.with_suffix(".prev.json")):
        if path.exists():
            try:
                return VariationState.from_snapshot(json.loads(path.read_text()))
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                continue
    return VariationState()


def save_state(state: VariationState) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(".prev.json").write_text(p.read_text())
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state.snapshot(), indent=1, sort_keys=True))
    os.replace(tmp, p)


# ---------------------------------------------------------------- awake: exploration (actor)

def _fitness(tree: list, task: WorldTask) -> float:
    ok = 0
    for r, e in task.public:
        try:
            if run(tree, r) == e:
                ok += 1
        except Invalid:
            pass
    return ok / max(1, len(task.public))


def enabled() -> bool:
    """Kill switch: NOMAD_VARIATION=off disables search-time mutants and exploration."""
    return os.environ.get("NOMAD_VARIATION", "on") != "off"


def library_trees(prior: Any, inputs: Sequence[Sequence[str]]) -> list[list]:
    """The field's certified library blocks for an input signature, inlined."""
    from .world import expand
    return [expand(t, prior.library) for t in prior.primitives_for(inputs).values()]


def explore(task: WorldTask, state: VariationState, library: Iterable[list] = (),
            budget: int = EXPLORE_TRIES, seed: int = SEED) -> dict[str, Any]:
    """Bounded awake exploration on a *training* task. Reads state, writes nothing.

    Mutates certified patterns from other families, scores fitness on the
    task's public rows, and consults WITNESS (public + challenge rows only)
    on any mutant that fits them all. Returns a trace for the sleep learner.
    Its evaluations are reported separately and never count toward the twin
    comparison.

    INTEGRITY (docs/INTEGRITY.md): exploration never reads the final split.
    It works on ``search_view(task)`` (final=()) and uses ``consult()``, so a
    "paid" row means "supported on public + challenge rows". The sleep
    learner (``apply_trace``) re-attests every paid row with ``certify()``,
    including the final split, before anything is counted or learned.
    """
    view = search_view(task)
    srcs = state.sources(view, library, exclude_family=view.family)
    cands = state.candidates(view, srcs, budget, seed)
    tried, paid = [], []
    for kind, t in cands:
        fit = _fitness(t, view)
        tried.append({"kind": kind, "tree": t, "fitness": round(fit, 4)})
        if fit == 1.0:
            receipt = consult(view, t)
            if receipt is not None and receipt.supported:
                paid.append({"kind": kind, "tree": t})
    return {"family": view.family, "situation": situation(view), "evaluations": len(cands),
            "tried": tried, "paid": paid}


# ---------------------------------------------------------------- sleep: learner apply

def apply_trace(state: VariationState, trace: dict[str, Any], *, certified_tree: list | None = None,
                library: Iterable[list] = ()) -> dict[str, int]:
    """Single-learner update from one awake trace. Re-checks everything itself.

    - The task is looked up by family from the frozen training set; held-out
      or unknown families are refused.
    - "paid" counts only when the learner re-attests the tree with WITNESS
      (``certify``) on that task: supported and final-correct.
    - The certified treatment tree (already receipt-verified by the caller)
      becomes an elite source.

    A search-time variation win arrives as a "paid" row as well as a "tried"
    row, so it is counted once, after re-attestation, like any other.
    """
    from .world_tasks import HELDOUT, by_family
    fam = trace.get("family")
    held = {h["task"].family for h in HELDOUT.values()}
    task = by_family(fam) if isinstance(fam, str) else None
    if task is None or fam in held:
        return {"refused": 1}
    sit = situation(task)
    sig = sig_key(task.inputs)
    library = list(library)
    n = {"tried": 0, "paid": 0, "archived": 0, "elite": 0}
    paid_keys = set()
    for p in trace.get("paid") or []:
        t, kind = p.get("tree"), p.get("kind")
        if not isinstance(t, list) or kind not in KINDS:
            continue
        try:
            receipt, _, final_ok = certify(task, t)
        except (Invalid, KeyError, TypeError, IndexError, ValueError):
            continue
        if receipt is not None and receipt.supported and receipt.verify_checksum() and final_ok:
            paid_keys.add(_tkey(t))
    for row in (trace.get("tried") or [])[: SEARCH_TRIES + EXPLORE_TRIES]:
        t, kind = row.get("tree"), row.get("kind")
        if not isinstance(t, list) or kind not in KINDS:
            continue
        ok = _tkey(t) in paid_keys
        state.memory.record(sit, kind, ok)
        n["tried"] += 1
        n["paid"] += int(ok)
        if not ok:
            try:
                fit = _fitness(t, task)  # recomputed, not trusted
            except (KeyError, TypeError, IndexError, ValueError):
                continue
            if state.consider(t, sig, kind, fit, library):
                n["archived"] += 1
    if certified_tree is not None:
        state.add_elite(certified_tree, sig, fam)
        n["elite"] += 1
    state.applied += 1
    return n
