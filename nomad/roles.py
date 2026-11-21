"""ROLES: read numbers and their roles from a word problem (docs/ROLES.md). Switch ``NOMAD_ROLES`` (default OFF).

MEANING (nomad/meaning.py) retrieves the *concept* a story means, but then tries up to
``MEANING_MAPS`` renamings of the concept's variables onto the task's inputs blind. ROLES
reads the story instead:

- **Numbers**: a story that states its quantities (``"laid in 7 rows with 4 tiles in each
  row"``) is parsed for number mentions; each mention is linked to the task input(s) whose
  value on the first *public* row equals it (never challenge / final rows).
- **Role features** of a mention: the words around it (``L1:in``, ``R1:row``, ``R2:with``,
  ...) and the relational words of its clause (``C:each``, ``C:per``, ``C:left``, ...).
- **Learning** (``learn``, called only from ``WorldPrior.add_witnessed``, i.e. from a
  verified receipt, only while the switch is on): for the certified concept, the canonical
  variable an input fills is known, so each unambiguous mention counts its features for that
  role: ``concepts[key]["roles"][var][feature]``. Decays with the lexicon.
- **Use** (``ranked_maps``, from ``meaning.stage``): every type-preserving renaming of the
  retrieved concept (up to ``ROLES_POOL``) is scored by how well each role's features fit the
  mention of the input it is bound to (log-odds against all role mentions of all concepts,
  Laplace-smoothed); the stage tries the best ``ROLES_FIRST`` renamings of every retrieved
  concept first, then the rest in score order, within the unchanged MEANING budget and
  WITNESS gate.

Switch off, no numbers in the words, or a concept with no role table: the stage is
MEANING's, byte for byte. ``shuffled`` is the control: each concept's role table is
re-pointed through a seeded random bijection over its variables (same features, same
counts, roles scrambled). No neural nets: counts.
"""
from __future__ import annotations

import math
import os
import random
import re
from itertools import permutations
from typing import Any

ROLES_POOL = 20160     # most renamings scored per concept (8 inputs, 5 roles: 6,720)
ROLES_FIRST = 6        # best renamings of each retrieved concept tried before the rest (dev-chosen)
ROLES_ALPHA = 0.05     # Laplace smoothing on frequencies (dev-chosen)
ROLES_WINDOW = 3       # words each side of a number

RELATIONAL = frozenset("""
each per every all total altogether left over remain remaining shared equally among between split
divided into plus more extra less fewer minus spend spent use used away back there twice double
average mean by times rows row around edge both start starting saved
""".split())


def enabled() -> bool:
    return os.environ.get("NOMAD_ROLES", "off").strip().lower() in ("on", "1", "true", "yes")


def _stem(w: str) -> str:
    from .meaning import _stem as s
    return s(w)


_TOK = re.compile(r"\d+|[a-z]+|[.,;:?!]")


def mentions(text: str) -> list[tuple[int, frozenset]]:
    """[(value, features)] for every number written in the text, in order."""
    toks = _TOK.findall(text.lower())
    out = []
    # clause boundaries: punctuation and 'and'
    clause_id, cid = [], 0
    for t in toks:
        if t in ".,;:?!" or t == "and":
            cid += 1
        clause_id.append(cid)
    words = [(_stem(t) if t.isalpha() else t) for t in toks]
    for i, t in enumerate(toks):
        if not t.isdigit():
            continue
        f = set()
        k = 0
        for j in range(i - 1, -1, -1):          # left context, punctuation stops it
            if toks[j] in ".,;:?!":
                break
            if toks[j].isdigit():
                f.add(f"L{k + 1}:#")
            else:
                f.add(f"L{k + 1}:{words[j]}")
            k += 1
            if k >= ROLES_WINDOW:
                break
        k = 0
        for j in range(i + 1, len(toks)):
            if toks[j] in ".,;:?!":
                break
            if toks[j].isdigit():
                f.add(f"R{k + 1}:#")
            else:
                f.add(f"R{k + 1}:{words[j]}")
            k += 1
            if k >= ROLES_WINDOW:
                break
        for j, w in enumerate(words):
            if clause_id[j] == clause_id[i] and w in RELATIONAL:
                f.add(f"C:{w}")
        out.append((int(t), frozenset(f)))
    return out


def _bindings(task_or_row: Any, inputs) -> dict[str, int]:
    return {n: task_or_row.get(n) for n, _t in inputs}


def learn(prior: Any, tree: list, inputs, words: str, row: dict) -> str | None:
    """Role counts for the certified concept from one verified receipt (add_witnessed only)."""
    from .meaning import concept_of, simplify
    from .world import _canon_vars, size
    if not words or not row or size(tree) < 3:
        return None
    ms = mentions(words)
    if not ms:
        return None
    key, _canon, _ct = concept_of(tree, inputs)
    rec = prior.concepts.get(key)
    if rec is None:
        return None
    m: dict[str, str] = {}
    _canon_vars(simplify(tree), m)            # input name -> canonical variable
    vals = [v for v, _f in ms]
    roles = rec.setdefault("roles", {})
    for v, feats in ms:
        cands = [n for n, _t in inputs if row.get(n) == v]
        if len(cands) != 1 or vals.count(v) != 1 or cands[0] not in m:
            continue                               # ambiguous or a quantity the answer does not use
        tab = roles.setdefault(m[cands[0]], {})
        tab["#"] = tab.get("#", 0.0) + 1.0
        for f in feats:
            tab[f] = tab.get(f, 0.0) + 1.0
    return key


def decay(rec: dict, gamma: float) -> None:
    for tab in rec.get("roles", {}).values():
        for f in list(tab):
            tab[f] *= gamma


def shuffled(prior: Any, seed: int) -> Any:
    """Control: every concept's role table re-pointed through a seeded bijection over its variables."""
    import copy
    p = copy.deepcopy(prior)
    rng = random.Random(seed)
    for key in sorted(p.concepts):
        rec = p.concepts[key]
        if not rec.get("roles"):
            continue
        vs = sorted(rec["types"], key=lambda x: int(x[2:]) if x[2:].isdigit() else 0)
        perm = vs[:]
        rng.shuffle(perm)
        pi = dict(zip(vs, perm))
        rec["roles"] = {pi.get(v, v): t for v, t in rec["roles"].items()}
    return p


def _background(prior: Any) -> dict:
    tot: dict[str, float] = {}
    for rec in prior.concepts.values():
        for tab in rec.get("roles", {}).values():
            for f, c in tab.items():
                tot[f] = tot.get(f, 0.0) + c
    return tot


def _role_score(tab: dict, bg: dict, feats) -> float:
    a = ROLES_ALPHA
    n, b = tab.get("#", 0.0), bg.get("#", 0.0)
    if n <= 0 or b <= 0:
        return 0.0
    s = 0.0
    for f in feats:
        if f not in bg:
            continue                                   # a word never seen beside any role
        p = (tab.get(f, 0.0) / n + a) / (1 + 2 * a)    # frequencies, so decay does not change the score
        q = (bg[f] / b + a) / (1 + 2 * a)
        s += math.log(p / q)
    return s


def ranked_maps(rec: dict, task: Any, words: str, prior: Any) -> list[dict] | None:
    """Renamings of ``rec`` onto ``task`` in role order, or None (stage stays MEANING's)."""
    roles = rec.get("roles")
    if not roles or not task.public:
        return None
    ms = mentions(words)
    if not ms:
        return None
    row = task.public[0][0]
    by_input: dict[str, list] = {}
    for v, feats in ms:
        for n, _t in task.inputs:
            if row.get(n) == v:
                by_input.setdefault(n, []).append(feats)
    if not by_input:
        return None
    bg = _background(prior)
    cache: dict[tuple[str, str], float] = {}

    def fit(var: str, inp: str) -> float:
        k = (var, inp)
        if k not in cache:
            fs = by_input.get(inp)
            tab = roles.get(var)
            cache[k] = (sum(_role_score(tab, bg, f) for f in fs) / len(fs)) if (fs and tab) else 0.0
        return cache[k]

    by_type: dict[str, list[str]] = {}
    for nm, ty in task.inputs:
        by_type.setdefault(ty, []).append(nm)
    groups: dict[str, list[str]] = {}
    for v in sorted(rec["types"], key=lambda x: int(x[2:]) if x[2:].isdigit() else 0):
        groups.setdefault(rec["types"][v], []).append(v)
    maps: list[dict] = [{}]
    for ty, g in groups.items():
        maps = [dict(m, **dict(zip(g, perm))) for m in maps for perm in permutations(by_type.get(ty, []), len(g))]
        maps = maps[:ROLES_POOL]
    scored = [(-sum(fit(v, i) for v, i in m.items()), j, m) for j, m in enumerate(maps)]
    scored.sort(key=lambda z: (z[0], z[1]))
    return [m for _s, _j, m in scored]
