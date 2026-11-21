"""INFLECT: a morphology / expression domain in the string world (docs/INFLECT.md).

Everything is behind ``NOMAD_INFLECT`` (default off). The domain half of the step:

- eight small operators in ``nomad/world.py`` (reachable only through the ``inflect`` opset, which
  ``opset_of`` resolves only when the switch is on): word-shape predicates ``sib cy ve ens`` (ends
  in s/x/z/ch/sh; consonant + y; silent e; s), the string-level ``init`` (all but the last letter),
  ``gem`` (the doubled final consonant of a one-syllable consonant-vowel-consonant word, else ""),
  ``one`` (count == 1) and ``sel`` (the string twin of ``ite``). Suffixes are never DSL constants:
  they are named input columns ("s", "es", "ies", "ed", "'s", ...), exactly like separators.
- ``train_tasks()``: small rule-block training families (size <= 7: a suffix chooser, a stem
  rule, a doubling rule, a possessive, a count-agreement form, a number phrase) with fixed literal
  rows on the word lists below. Rules are learned by the existing machinery (the field's certified
  programs, INVENT's blocks, PORT) -- no inflection rule lives in the search.
- ``CATALOGUE``: the sealed candidate families -- compositions of those blocks on words and
  templates never trained (full plural / past / -ing / third person, number agreement, computed
  counts expressed in words) -- with independent Python ground truth (regular expressions, never the
  op code), a row kept only when the reference tree reproduces it.

Word lists are disjoint across train / dev / sealed. No transformer, no LLM.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Callable

from .text import V, _c
from .world import Invalid, WorldTask, make_task, run

DOMAIN = "inflect"
N_PUBLIC, N_CHALLENGE, N_FINAL = 5, 3, 3

# ----------------------------------------------------------------- independent ground truth
_Y = re.compile(r"[^aeiou]y$")
_SIB = re.compile(r"(s|x|z|ch|sh)$")
_CVC = re.compile(r"^[^aeiou]+[aeiou][^aeiouwxy]$")   # one syllable, consonant-vowel-consonant


def py_plural(w: str) -> str:
    if _SIB.search(w):
        return w + "es"
    if _Y.search(w):
        return w[:-1] + "ies"
    return w + "s"


def py_third(w: str) -> str:
    return py_plural(w)


def _ed_stem(w: str, suffix_vowel: bool = True) -> str:
    if _CVC.match(w):
        return w + w[-1]
    return w


def py_past(w: str) -> str:
    if _Y.search(w):
        return w[:-1] + "ied"
    if w.endswith("e"):
        return w + "d"
    return _ed_stem(w) + "ed"


def py_ing(w: str) -> str:
    if w.endswith("e") and not w.endswith("ee"):
        return w[:-1] + "ing"
    return _ed_stem(w) + "ing"


def py_poss(w: str) -> str:
    return w + ("'" if w.endswith("s") else "'s")


def py_count(n: int, w: str) -> str:
    return f"{n} {w if n == 1 else py_plural(w)}"


# ----------------------------------------------------------------- word lists (disjoint)
# Each category is chosen so the independent rules above and the one-syllable doubling rule agree.
TRAIN_NOUNS = dict(sib=("box", "bus", "dish", "church"), cy=("city", "baby", "berry"), vy=("day", "key"),
                   plain=("apple", "river", "nomad"))
TRAIN_VERBS = dict(plain=("walk", "jump"), e=("make", "bake"), gem=("stop", "plan", "hug"), cy=("carry", "try"),
                   vy=("play", "stay"))
SEALED_NOUNS = dict(sib=("brush", "class", "watch", "tax", "dress", "lunch", "crash", "lens"),
                    cy=("cherry", "fly", "pony", "candy", "bunny", "jelly"),
                    vy=("monkey", "tray", "valley", "turkey"),
                    plain=("planet", "garden", "pencil", "basket", "ticket", "window", "pillow", "rocket"))
SEALED_VERBS = dict(plain=("paint", "open", "listen", "visit", "wait", "cook", "pull", "rain"),
                    e=("smile", "move", "close", "dance", "share"),
                    gem=("drop", "tap", "rub", "slam", "grab", "stir", "jog"),
                    cy=("empty", "cry", "marry", "hurry"), vy=("enjoy", "annoy"),
                    sib=("wash", "fix", "pass", "reach", "push"))


def flat(d: dict) -> tuple[str, ...]:
    return tuple(w for ws in d.values() for w in ws)


# ----------------------------------------------------------------- formulas and rows
@dataclass(frozen=True)
class IFormula:
    family: str
    kind: str
    text: str
    inputs: tuple[str, ...]
    out: str
    truth: Callable[..., object]
    tree: list
    words: tuple[str, ...] = ()                      # the pool the word input(s) draw from
    consts: tuple[tuple[str, str], ...] = ()         # constant string columns (suffixes, separators)
    ints: tuple[tuple[str, int, int], ...] = ()      # integer inputs and their ranges
    types: tuple[tuple[str, str], ...] = ()          # name -> type for every input


def gen_row(f: IFormula, rng: random.Random) -> dict:
    row = {}
    consts, ints = dict(f.consts), {n: (lo, hi) for n, lo, hi in f.ints}
    for n, t in f.types:
        if n in consts:
            row[n] = consts[n]
        elif n in ints:
            row[n] = rng.randint(*ints[n])
        else:
            row[n] = rng.choice(f.words)
    return row


def exact_answer(f: IFormula, row: dict):
    want = f.truth(*(row[n] for n in f.inputs))
    try:
        got = run(f.tree, row)
    except Invalid:
        return None
    return want if got == want else None


def draw_rows(f: IFormula, rng: random.Random, n: int = N_PUBLIC + N_CHALLENGE + N_FINAL,
              tries: int = 20000) -> list[tuple[dict, object]]:
    """n distinct rows with exact answers; public outputs not constant; a count input must take 1 and
    another value among the public rows (agreement needs both forms)."""
    for _ in range(50):
        rows, seen = [], set()
        for _ in range(tries):
            if len(rows) == n:
                break
            r = gen_row(f, rng)
            key = tuple(r[k] for k in f.inputs)
            if key in seen:
                continue
            ans = exact_answer(f, r)
            if ans is None:
                continue
            seen.add(key)
            rows.append((r, ans))
        ok = len(rows) == n and len({a for _, a in rows[:N_PUBLIC]}) > 1
        ok = ok and _branches_covered(f.tree, [r for r, _ in rows[:N_PUBLIC]])
        for name, _lo, _hi in f.ints:
            ok = ok and any(r[name] == 1 for r, _ in rows[:N_PUBLIC]) and any(r[name] != 1 for r, _ in rows[:N_PUBLIC])
        if ok:
            return rows
    raise RuntimeError(f"could not draw rows for {f.family}")


def _branches_covered(tree: list, rows: list[dict]) -> bool:
    """Every ``sel`` condition of the reference tree takes both branches on the public rows, so the public
    rows can tell the rule from a shortcut that ignores it."""
    if tree[0] in ("var", "const", "lib"):
        return True
    if tree[0] == "sel":
        try:
            cs = [run(tree[1], r) for r in rows]
        except Invalid:
            return False
        if not (any(c > 0 for c in cs) and any(c <= 0 for c in cs)):
            return False
    return all(_branches_covered(c, rows) for c in tree[1:])


def to_task(entry: dict, types: dict | None = None) -> WorldTask:
    rows = [(dict(r), e) for r, e in entry["rows"]]
    ty = types or {n: ("int" if isinstance(rows[0][0][n], int) else "str") for n in entry["inputs"]}
    a, b = N_PUBLIC, N_PUBLIC + N_CHALLENGE
    return make_task(entry["task_id"], entry["family"], "inflect", {n: ty[n] for n in entry["inputs"]},
                     entry["out"], rows[:a], rows[a:b], rows[b:], entry.get("level", 9))


def make(family, kind, text, inputs, out, truth, tree, words=(), consts=(), ints=()):
    types = tuple((n, "int" if n in {i[0] for i in ints} else "str") for n in inputs)
    return IFormula(family, f"inflect:{kind}", text, tuple(inputs), out, truth, tree, tuple(words),
                    tuple(consts), tuple(ints), types)


# ----------------------------------------------------------------- tree helpers
def sel(c, a, b):
    return ["sel", c, a, b]


def cc(*xs):
    return _c(*xs)


def pl_sfx(w, es, s):          # -es after a sibilant else -s
    return sel(["sib", w], es, s)


def y_stem(w):                 # drop a consonant + y
    return sel(["cy", w], ["init", w], w)


def e_stem(w):                 # drop a silent e
    return sel(["ve", w], ["init", w], w)


# ----------------------------------------------------------------- training families
# Fixed literal rows, signature (iw word, ia / ib suffix columns, ix count). Never a sealed family.
def _train_rows(words, fn, consts, counts=None):
    rows = []
    for i, w in enumerate(words):
        r = {"iw": w, **consts}
        if counts is not None:
            r["ix"] = counts[i % len(counts)]
        rows.append((r, fn(r)))
    return rows


def _tt(tid, fam, inputs, out, words, fn, consts, counts=None, level=3):
    allw = list(words)
    rows = _train_rows(allw, fn, consts, counts)
    types = {n: ("int" if n == "ix" else "str") for n in inputs}
    return make_task(tid, fam, "inflect", types, out, rows[:5], rows[5:8], rows[8:11], level)


def _w11(*pools):
    """Eleven training words: the pools interleaved (public rows cover every rule)."""
    out, i = [], 0
    pools = [list(p) for p in pools]
    while len(out) < 11:
        p = pools[i % len(pools)]
        if p:
            out.append(p.pop(0))
        i += 1
        if i > 200:
            break
    return out


_N, _V = TRAIN_NOUNS, TRAIN_VERBS
_NOUN11 = _w11(_N["sib"], _N["cy"], _N["plain"], _N["vy"])
_VERB11 = _w11(_V["gem"], _V["e"], _V["plain"], _V["cy"], _V["vy"])
_ALL11 = _w11(_N["sib"], _N["plain"], _N["cy"], _N["vy"])


def train_tasks() -> list[WorldTask]:
    iw, ia, ib, ix = V("iw"), V("ia"), V("ib"), V("ix")
    specs = [
        ("in-sfx", "in_sib_suffix", ("iw", "ia", "ib"), "str", _NOUN11,
         lambda r: r["ia"] if _SIB.search(r["iw"]) else r["ib"], dict(ia="es", ib="s"), None, pl_sfx(iw, ia, ib)),
        ("in-plain", "in_plural_sib", ("iw", "ia", "ib"), "str", _NOUN11,
         lambda r: r["iw"] + (r["ia"] if _SIB.search(r["iw"]) else r["ib"]), dict(ia="es", ib="s"), None,
         cc(iw, pl_sfx(iw, ia, ib))),
        ("in-ystem", "in_y_stem", ("iw",), "str", _NOUN11,
         lambda r: r["iw"][:-1] if _Y.search(r["iw"]) else r["iw"], {}, None, y_stem(iw)),
        ("in-estem", "in_e_stem", ("iw",), "str", _VERB11,
         lambda r: r["iw"][:-1] if r["iw"].endswith("e") else r["iw"], {}, None, e_stem(iw)),
        ("in-gem", "in_double", ("iw", "ia"), "str", _VERB11,
         lambda r: r["iw"] + (r["iw"][-1] if _CVC.match(r["iw"]) else "") + r["ia"], dict(ia="ed"), None,
         cc(iw, ["gem", iw], ia)),
        ("in-poss", "in_possessive", ("iw", "ia", "ib"), "str", _NOUN11,
         lambda r: r["iw"] + (r["ia"] if r["iw"].endswith("s") else r["ib"]), dict(ia="'", ib="'s"), None,
         cc(iw, sel(["ens", iw], ia, ib))),
        ("in-agree", "in_count_form", ("iw", "ia", "ix"), "str", _ALL11,
         lambda r: r["iw"] if r["ix"] == 1 else r["iw"] + r["ia"], dict(ia="s"), (1, 2, 3, 1, 4),
         sel(["one", ix], iw, cc(iw, ia))),
        ("in-numw", "in_number_phrase", ("iw", "ia", "ix"), "str", _ALL11,
         lambda r: f"{r['ix']}{r['ia']}{r['iw']}", dict(ia=" "), (2, 3, 1, 4, 5),
         cc(["itos", ix], ia, iw)),
        ("in-iessfx", "in_y_suffix", ("iw", "ia", "ib"), "str", _NOUN11,
         lambda r: r["ia"] if _Y.search(r["iw"]) else r["ib"], dict(ia="ies", ib="s"), None, sel(["cy", iw], ia, ib)),
        ("in-dsfx", "in_e_suffix", ("iw", "ia", "ib"), "str", _VERB11,
         lambda r: r["ia"] if r["iw"].endswith("e") else r["ib"], dict(ia="d", ib="ed"), None, sel(["ve", iw], ia, ib)),
        ("in-isare", "in_is_are", ("ia", "ib", "ix"), "str", _ALL11,
         lambda r: r["ia"] if r["ix"] == 1 else r["ib"], dict(ia="is", ib="are"), (1, 3, 2, 1, 4),
         sel(["one", ix], ia, ib)),
    ]
    out = []
    for tid, fam, inputs, o, words, fn, consts, counts, tree in specs:
        t = _tt(tid, fam, inputs, o, words, fn, consts, counts)
        for rows in (t.public, t.challenge, t.final):
            for r, e in rows:
                assert run(tree, r) == e, (fam, r, run(tree, r), e)
        out.append(t)
    return out


TRAIN_FAMILIES = ("in_sib_suffix", "in_plural_sib", "in_y_stem", "in_e_stem", "in_double", "in_possessive",
                  "in_count_form", "in_number_phrase", "in_y_suffix", "in_e_suffix", "in_is_are")


# ----------------------------------------------------------------- sealed catalogue
# New input names (qw word, qn count, qk count, qs qe qi qd qg qa qb qp qz suffix / separator columns),
# new words, new templates. Written, and committed with the pre-registered criteria, before any field
# arm is measured on it.
SW = flat(SEALED_NOUNS)
SV = flat(SEALED_VERBS)
qw, qn, qk = V("qw"), V("qn"), V("qk")
qs, qe, qi, qd, qg, qa, qb, qz = (V(x) for x in ("qs", "qe", "qi", "qd", "qg", "qa", "qb", "qz"))
C_S, C_ES, C_IES = ("qs", "s"), ("qe", "es"), ("qi", "ies")
C_D, C_ED, C_IED, C_ING = ("qd", "d"), ("qe", "ed"), ("qi", "ied"), ("qg", "ing")
C_SP = ("qz", " ")


def _gemw(w):
    return w[-1] if _CVC.match(w) else ""


CATALOGUE: tuple[IFormula, ...] = (
    make("q_plural_full", "plural", "plural: -ies after consonant+y, -es after a sibilant, else -s",
         ("qw", "qs", "qe", "qi"), "str", lambda w, s, e, i: py_plural(w),
         cc(y_stem(qw), sel(["cy", qw], qi, pl_sfx(qw, qe, qs))), SW, (C_S, C_ES, C_IES)),
    make("q_past_full", "past", "past tense: -ied after consonant+y, -d after e, doubled consonant, else -ed",
         ("qw", "qe", "qd", "qi"), "str", lambda w, e, d, i: py_past(w),
         cc(y_stem(qw), ["gem", qw], sel(["cy", qw], qi, sel(["ve", qw], qd, qe))), SV, (("qe", "ed"), C_D, C_IED)),
    make("q_ing_form", "progressive", "-ing: drop a silent e, double a final consonant when it doubles",
         ("qw", "qg"), "str", lambda w, g: py_ing(w), cc(e_stem(qw), ["gem", qw], qg), SV, (C_ING,)),
    make("q_third_person", "agreement", "third person singular of a verb (-ies / -es / -s)",
         ("qw", "qs", "qe", "qi"), "str", lambda w, s, e, i: py_third(w),
         cc(y_stem(qw), sel(["cy", qw], qi, pl_sfx(qw, qe, qs))), SV, (C_S, C_ES, C_IES)),
    make("q_count_simple", "agreement", "number agreement with a regular -s noun: '1 pencil' / '3 pencils'",
         ("qw", "qn", "qs", "qz"), "str", lambda w, n, s, z: f"{n}{z}{w if n == 1 else w + s}",
         cc(["itos", qn], qz, sel(["one", qn], qw, cc(qw, qs))),
         ("planet", "garden", "pencil", "basket", "ticket", "window", "pillow", "rocket", "monkey", "tray",
          "valley", "turkey"), (C_S, C_SP), (("qn", 0, 5),)),
    make("q_count_noun", "agreement", "'<n> <noun>' with the full plural rule: '1 cherry' / '4 cherries'",
         ("qw", "qn", "qs", "qe", "qi", "qz"), "str", lambda w, n, s, e, i, z: py_count(n, w).replace(" ", z, 1),
         cc(["itos", qn], qz, sel(["one", qn], qw, cc(y_stem(qw), sel(["cy", qw], qi, pl_sfx(qw, qe, qs))))),
         SW, (C_S, C_ES, C_IES, C_SP), (("qn", 0, 5),)),
    make("q_count_computed", "express", "compute k boxes of n and say the total: '6 pencils' (1 -> '1 pencil')",
         ("qw", "qn", "qk", "qs", "qz"), "str",
         lambda w, n, k, s, z: f"{n * k}{z}{w if n * k == 1 else w + s}",
         cc(["itos", ["mul", qn, qk]], qz, sel(["one", ["mul", qn, qk]], qw, cc(qw, qs))),
         ("planet", "garden", "pencil", "basket", "ticket", "window", "pillow", "rocket"), (C_S, C_SP),
         (("qn", 1, 3), ("qk", 1, 3))),
    make("q_sentence_be", "express", "'<n> <noun> is/are': agreement of the count word and the verb",
         ("qw", "qn", "qs", "qa", "qb", "qz"), "str",
         lambda w, n, s, a, b, z: f"{n}{z}{w if n == 1 else w + s}{z}{a if n == 1 else b}",
         cc(["itos", qn], qz, sel(["one", qn], qw, cc(qw, qs)), qz, sel(["one", qn], qa, qb)),
         ("planet", "garden", "pencil", "basket", "ticket", "window", "pillow", "rocket"),
         (C_S, ("qa", "is"), ("qb", "are"), C_SP), (("qn", 0, 5),)),
    make("q_possessive_count", "possessive", "possessive of the count form: '1 brush' -> \"brush's\", 3 -> \"brushes'\"",
         ("qw", "qn", "qs", "qe", "qa", "qb"), "str",
         lambda w, n, s, e, a, b: py_poss(w if n == 1 else py_plural(w)),
         cc(sel(["one", qn], qw, cc(qw, pl_sfx(qw, qe, qs))),
            sel(["ens", sel(["one", qn], qw, cc(qw, pl_sfx(qw, qe, qs)))], qa, qb)),
         flat(dict(sib=SEALED_NOUNS["sib"], plain=SEALED_NOUNS["plain"])), (C_S, C_ES, ("qa", "'"), ("qb", "'s")),
         (("qn", 0, 4),)),
    make("q_plural_len", "length", "letters in the plural form (integer output)",
         ("qw", "qs", "qe", "qi"), "int", lambda w, s, e, i: len(py_plural(w)),
         ["strlen", cc(y_stem(qw), sel(["cy", qw], qi, pl_sfx(qw, qe, qs)))], SW, (C_S, C_ES, C_IES)),
    make("q_past_len", "length", "letters in the past form (integer output)",
         ("qw", "qe", "qd", "qi"), "int", lambda w, e, d, i: len(py_past(w)),
         ["strlen", cc(y_stem(qw), ["gem", qw], sel(["cy", qw], qi, sel(["ve", qw], qd, qe)))], SV,
         (("qe", "ed"), C_D, C_IED)),
    # controls: no rule block needed (a plain concatenation and a plain count phrase)
    make("q_ctl_pair", "control", "word, separator, word length",
         ("qw", "qz"), "str", lambda w, z: w + z + str(len(w)), cc(qw, qz, ["itos", ["strlen", qw]]), SW, (C_SP,)),
)
BY_FAMILY = {f.family: f for f in CATALOGUE}


def is_inflect(family: str | None) -> bool:
    return bool(family) and (family in BY_FAMILY or family in TRAIN_FAMILIES)
