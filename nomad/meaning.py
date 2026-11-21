"""MEANING: words grounded in verified structure (docs/MEANING.md). Switch ``NOMAD_MEANING`` (default ON since the sealed judge passed; ``off`` restores the plain search).

A first, testable rung of "understanding": NOMAD links the words a task is
described with to the certified program that solved it, so a new task
described in words pulls up the right *concept* before any search starts.

- **Concept**: a WITNESS-certified program up to variable renaming (its
  variables renamed by first occurrence, ``world._canon_vars``), with the
  types of its variables, its output type and the SENSE kinds of the tasks it
  solved.
- **Lexicon**: ``prior.lexicon[token][concept]`` counts how often a task whose
  description contained ``token`` was certified by ``concept``. Tokens are a
  bag of lower-cased words (stop words, numbers and ``{placeholders}``
  dropped, a light plural strip) plus adjacent-word bigrams. No neural nets,
  no embeddings: counts, like every other piece of the field.
- **Learning** (``learn``) happens only inside ``WorldPrior.add_witnessed``,
  i.e. only from a verified receipt, only when the task carried words and
  only while the switch is on. It decays with the rest of the field.
- **Use** (``stage``): ``world.evaluate(..., words=...)`` on a field with a
  lexicon. Concepts are scored by the task's tokens (``sum_t p(c | t) *
  idf(t)``, SENSE-kind agreement breaks ties), filtered by type
  feasibility; the top ``MEANING_K`` are instantiated over the task's inputs
  by every type-preserving injective renaming (PORT-style), each run once on
  the public rows (1 evaluation). A public fit is offered to WITNESS (a
  rejection costs 1 evaluation, at most ``MEANING_REJECTS``). The stage
  spends at most ``MEANING_BUDGET`` evaluations; on a miss the normal search
  runs unchanged with the remaining budget.

The empty field has an empty lexicon (the stage never runs); the cold control
(``prior=None``) never reads one; with the switch off nothing is learned or
read. Final rows are never read here: WITNESS and the final split decide.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
from itertools import permutations
from typing import Any, Sequence

MEANING_K = 4          # concepts tried per task (dev-chosen)
MEANING_BUDGET = 384   # most evaluations the stage spends, WITNESS rejections included (dev-chosen)
MEANING_REJECTS = 8    # public fits WITNESS may reject inside the stage
MEANING_MAPS = 360     # most renamings of one concept (6 inputs, 4 roles: 360)
LEXICON_PRUNE = 0.01   # lexicon / concept counts below this are dropped on decay
BIGRAMS = True         # adjacent-word bigrams as tokens (dev-chosen)

STOP = frozenset("""
a an the of to in on at by for from with and or but is are was were be been being has have had
do does did it its this that these those there here what which who whom how many much
if then than so as into onto per each every all any some one can will would should could
""".split()) - {"each", "per", "every", "all"}   # relational words carry meaning; keep them


def enabled() -> bool:
    return os.environ.get("NOMAD_MEANING", "on").strip().lower() not in ("off", "0", "false", "no")   # default ON since the sealed PASS


# ---------------------------------------------------------------- tokens

def _stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def tokens(text: str) -> list[str]:
    """Bag of words + adjacent bigrams; stop words, numbers and {placeholders} dropped."""
    text = re.sub(r"\{[^}]*\}", " ", text.lower())
    words = [_stem(w) for w in re.findall(r"[a-z]+", text)]
    kept = [w for w in words if w not in STOP and len(w) > 1]
    out = list(dict.fromkeys(kept))
    if BIGRAMS:
        out += list(dict.fromkeys(f"{a}_{b}" for a, b in zip(kept, kept[1:])))
    return out


# ---------------------------------------------------------------- concepts

def simplify(tree: list) -> list:
    """Exact identities only (x + 0, 0 + x, x - 0, x * 1, 1 * x, x // 1), bottom-up: padding a
    variation mutant may carry is not part of a concept. The result computes the same value
    on every row where the original is valid."""
    if tree[0] in ("var", "const", "lib"):
        return tree
    t = [tree[0]] + [simplify(c) for c in tree[1:]]
    zero, one = ["const", 0], ["const", 1]
    if t[0] == "add" and t[2] == zero:
        return t[1]
    if t[0] == "add" and t[1] == zero:
        return t[2]
    if t[0] == "sub" and t[2] == zero:
        return t[1]
    if t[0] == "mul" and t[2] == one:
        return t[1]
    if t[0] == "mul" and t[1] == one:
        return t[2]
    if t[0] == "div" and t[2] == one:
        return t[1]
    return t


def concept_of(tree: list, inputs: Sequence[Sequence[str]]) -> tuple[str, list, dict[str, str]]:
    """(key, canonical tree, canonical variable -> type) of a certified program."""
    from .world import _canon_vars
    m: dict[str, str] = {}
    canon = _canon_vars(simplify(tree), m)
    types = dict((a, b) for a, b in inputs)
    ctypes = {cv: types.get(v, "int") for v, cv in m.items()}
    key = "M" + hashlib.sha256(json.dumps([canon, sorted(ctypes.items())]).encode()).hexdigest()[:10]
    return key, canon, ctypes


def learn(prior: Any, tree: list, inputs: Sequence[Sequence[str]], words: str, *,
          out: str | None = None, kind: str | None = None) -> str | None:
    """One lexicon update from a verified, certified program (called from add_witnessed only)."""
    from .world import size
    if not words or size(tree) < 3:
        return None
    key, canon, ctypes = concept_of(tree, inputs)
    rec = prior.concepts.setdefault(key, {"tree": canon, "types": ctypes, "out": out or "int",
                                          "kinds": {}, "uses": 0.0})
    rec["uses"] = float(rec.get("uses", 0.0)) + 1.0
    if kind:
        rec["kinds"][kind] = float(rec["kinds"].get(kind, 0.0)) + 1.0
    for t in tokens(words):
        row = prior.lexicon.setdefault(t, {})
        row[key] = row.get(key, 0.0) + 1.0
    return key


def decay(prior: Any, gamma: float) -> None:
    for t in list(prior.lexicon):
        row = prior.lexicon[t]
        for c in list(row):
            row[c] *= gamma
            if row[c] < LEXICON_PRUNE:
                del row[c]
        if not row:
            del prior.lexicon[t]
    for c in list(prior.concepts):
        rec = prior.concepts[c]
        rec["uses"] = float(rec.get("uses", 0.0)) * gamma
        if rec.get("roles"):
            from . import roles as _roles
            _roles.decay(rec, gamma)
        for k in list(rec["kinds"]):
            rec["kinds"][k] *= gamma


def shuffled(prior: Any, seed: int) -> Any:
    """Control: a deep copy whose lexicon rows point at randomly reassigned concepts
    (a seeded bijection over concept keys). Counts, tokens and concepts are kept;
    only which concept a word means is scrambled."""
    import copy
    p = copy.deepcopy(prior)
    keys = sorted(p.concepts)
    perm = keys[:]
    random.Random(seed).shuffle(perm)
    pi = dict(zip(keys, perm))
    p.lexicon = {t: {pi.get(c, c): v for c, v in row.items()} for t, row in p.lexicon.items()}
    return p


# ---------------------------------------------------------------- retrieval

def _feasible(rec: dict, task: Any) -> bool:
    if rec.get("out", "int") != task.out:
        return False
    need: dict[str, int] = {}
    for ty in rec["types"].values():
        need[ty] = need.get(ty, 0) + 1
    have: dict[str, int] = {}
    for _n, ty in task.inputs:
        have[ty] = have.get(ty, 0) + 1
    return all(have.get(ty, 0) >= k for ty, k in need.items())


def retrieve(prior: Any, task: Any, words: str, kind: str | None = None) -> list[tuple[float, str]]:
    """Concepts ranked by the task's words: sum over tokens of p(concept | token) * idf(token)."""
    n = max(1, len(prior.concepts))
    score: dict[str, float] = {}
    for t in tokens(words):
        row = prior.lexicon.get(t)
        if not row:
            continue
        tot = sum(row.values())
        if tot <= 0:
            continue
        idf = math.log(1.0 + n / len(row))
        for c, v in row.items():
            score[c] = score.get(c, 0.0) + (v / tot) * idf
    ranked = []
    for c, sc in score.items():
        rec = prior.concepts.get(c)
        if rec is None or not _feasible(rec, task):
            continue
        km = float(rec["kinds"].get(kind, 0.0)) if kind else 0.0
        ranked.append((-sc, -km, -float(rec.get("uses", 0.0)), c))
    ranked.sort()
    return [(-z[0], z[3]) for z in ranked]


def _maps(ctypes: dict[str, str], task: Any) -> list[dict]:
    by_type: dict[str, list[str]] = {}
    for nm, ty in task.inputs:
        by_type.setdefault(ty, []).append(nm)
    groups: dict[str, list[str]] = {}
    for v in sorted(ctypes, key=lambda x: int(x[2:]) if x[2:].isdigit() else 0):
        groups.setdefault(ctypes[v], []).append(v)
    maps: list[dict] = [{}]
    for ty, g in groups.items():
        maps = [dict(m, **dict(zip(g, perm))) for m in maps for perm in permutations(by_type.get(ty, []), len(g))]
        maps = maps[:MEANING_MAPS]
    return maps


_COMM = ("add", "mul", "min", "max")


def _comm_key(tree: list) -> str:
    """Instance identity up to argument order of commutative ops (exact: same value on every row)."""
    def norm(t):
        if t[0] in ("var", "const", "lib"):
            return t
        kids = [norm(c) for c in t[1:]]
        if t[0] in _COMM:
            kids.sort(key=lambda k: json.dumps(k))
        return [t[0]] + kids
    return json.dumps(norm(tree))


def stage(task: Any, prior: Any, words: str, *, max_eval: int | None = None) -> tuple[tuple[str, list] | None, int, dict]:
    """Try the concepts the words retrieve, first. Returns ((concept, tree) | None, evaluations, info)."""
    from .world import Invalid, _rename, consult, run
    budget = MEANING_BUDGET if max_eval is None else min(MEANING_BUDGET, max_eval)
    kind = None
    try:
        from . import sense as _sense
        kind = _sense.sense(task).get("kind")
    except Exception:
        kind = None
    ranked = retrieve(prior, task, words, kind)[:MEANING_K]
    goal = [e for _r, e in task.public]
    evals = rejects = 0
    seen: set[str] = set()
    info: dict = {"retrieved": [c for _s, c in ranked], "rejected": 0}
    plan: list[tuple[str, dict]] = []
    from . import roles as _roles
    if _roles.enabled():   # ROLES (docs/ROLES.md): renamings in the order the story's numbers imply
        lists = []
        for _sc, c in ranked:
            rm = _roles.ranked_maps(prior.concepts[c], task, words, prior)
            lists.append((c, rm[:MEANING_MAPS] if rm is not None else _maps(prior.concepts[c]["types"], task),
                          rm is not None))
            info["roles"] = info.get("roles", 0) + (rm is not None)
        f = _roles.ROLES_FIRST   # first pass: the best renamings of every role-read concept; then the rest
        plan = ([(c, m) for c, ms, read in lists if read for m in ms[:f]]
                + [(c, m) for c, ms, read in lists for m in (ms[f:] if read else ms)])
    else:
        plan = [(c, m) for _sc, c in ranked for m in _maps(prior.concepts[c]["types"], task)]
    for c, m in plan:
        rec = prior.concepts[c]
        if evals >= budget:
            info["rejected"] = rejects
            return None, evals, info
        inst = _rename(rec["tree"], m)
        k = _comm_key(inst)
        if k in seen:
            continue
        seen.add(k)
        evals += 1
        try:
            vals = [run(inst, r) for r, _e in task.public]
        except Invalid:
            continue
        if vals != goal:
            continue
        receipt = consult(task, inst)   # INTEGRITY: challenge only, never final
        if receipt is not None and receipt.supported:
            info["rejected"] = rejects
            return (c, inst), evals, info
        rejects += 1
        evals += 1
        if rejects >= MEANING_REJECTS:
            info["rejected"] = rejects
            return None, evals, info
    info["rejected"] = rejects
    return None, evals, info
