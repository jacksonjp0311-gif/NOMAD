"""TEXT: a never-trained string / language domain for the transfer test (Phase 3 B).

Name and word tasks with exact truth: renaming, casing, slicing, joining,
initials, lengths, plus a few mixed string+integer tasks. Built like
``nomad.science`` / ``nomad.transfer``:

- named inputs (``fn`` first name, ``ln`` last name, ``w`` word, ``rep`` a
  count); a stated separator (space, dot, comma) is a constant input column
  (``sp``, ``dt``, ``cm``), never a DSL constant (the DSL has no string
  constants);
- ground truth is a plain Python function written independently of the
  reference tree; a row is kept only when the reference tree, run by the
  WORLD interpreter, reproduces it exactly (WITNESS stays exact-match);
- 5 public / 3 challenge / 3 final rows (the final split is never read by
  search); names drawn from fixed vocabularies with seeded mixed casing.

Input names are disjoint from every training signature (WORLD ``s``, ``xs``,
``x``, ``y``; science; both integer transfer catalogues). No field arm is
ever trained on these families. Tasks run on the ``text`` opset (the ``str``
opset plus ``mul``, and the building blocks a dev suite showed missing; see
docs/TEXT.md); the WORLD ``str`` opset and every existing task are unchanged.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from .world import Invalid, WorldTask, make_task, run

DOMAIN = "language"
N_PUBLIC, N_CHALLENGE, N_FINAL = 5, 3, 3

FIRST = ("anna", "ben", "carl", "dana", "eve", "finn", "gus", "hana", "ivan", "jo", "kai", "lena",
         "mo", "nora", "otto", "pia", "quinn", "rosa", "sam", "tess", "uma", "vic", "wes", "zoe")
LAST = ("smith", "jones", "garcia", "kim", "lopez", "brown", "nguyen", "patel", "rossi", "silva",
        "weber", "moreau", "tanaka", "olsen", "costa", "novak", "haddad", "ivers")
WORDS = ("river", "desert", "nomad", "atlas", "wind", "stone", "cedar", "ember", "grove", "harbor",
         "lumen", "quartz", "orbit", "pixel", "tundra", "vapor", "signal", "meadow")
CASES = ("lower", "title", "upper", "mixed")


def V(n: str) -> list:
    return ["var", n]


def _case(rng: random.Random, w: str) -> str:
    c = rng.choice(CASES)
    if c == "lower":
        return w
    if c == "title":
        return w[:1].upper() + w[1:]
    if c == "upper":
        return w.upper()
    return "".join(ch.upper() if rng.random() < 0.5 else ch for ch in w)


GEN = {
    "fn": lambda rng: _case(rng, rng.choice(FIRST)),
    "ln": lambda rng: _case(rng, rng.choice(LAST)),
    "w": lambda rng: _case(rng, rng.choice(WORDS)),
    "w2": lambda rng: _case(rng, rng.choice(WORDS)),
    "rep": lambda rng: rng.randint(1, 6),
    "sp": lambda rng: " ",
    "dt": lambda rng: ".",
    "cm": lambda rng: ",",
}
TYPES = {"fn": "str", "ln": "str", "w": "str", "w2": "str", "rep": "int", "sp": "str", "dt": "str", "cm": "str"}


@dataclass(frozen=True)
class TextFormula:
    family: str
    kind: str                    # "language:<kind>"
    text: str
    inputs: tuple[str, ...]
    out: str
    truth: Callable[..., object]
    tree: list


def exact_answer(f: TextFormula, row: dict):
    want = f.truth(*(row[n] for n in f.inputs))
    try:
        got = run(f.tree, row)
    except Invalid:
        return None
    return want if got == want else None


def draw_rows(f: TextFormula, rng: random.Random, n: int = N_PUBLIC + N_CHALLENGE + N_FINAL,
              tries: int = 20000) -> list[tuple[dict, object]]:
    """n distinct rows with exact answers; public outputs not constant."""
    for _ in range(50):
        rows, seen = [], set()
        for _ in range(tries):
            if len(rows) == n:
                break
            r = {k: GEN[k](rng) for k in f.inputs}
            key = tuple(r[k] for k in f.inputs)
            if key in seen:
                continue
            ans = exact_answer(f, r)
            if ans is None:
                continue
            seen.add(key)
            rows.append((r, ans))
        if len(rows) == n and len({a for _, a in rows[:N_PUBLIC]}) > 1:
            return rows
    raise RuntimeError(f"could not draw rows for {f.family}")


def to_task(entry: dict) -> WorldTask:
    rows = [(dict(r), e) for r, e in entry["rows"]]
    a, b = N_PUBLIC, N_PUBLIC + N_CHALLENGE
    return make_task(entry["task_id"], entry["family"], "text", {n: TYPES[n] for n in entry["inputs"]},
                     entry["out"], rows[:a], rows[a:b], rows[b:], entry.get("level", 9))


def _c(*xs):
    """Right-nested concat of trees."""
    t = xs[-1]
    for x in reversed(xs[:-1]):
        t = ["concat", x, t]
    return t


NAME = ("fn", "ln", "sp", "dt", "cm")
WORD = ("w", "w2", "sp")
MIX = ("w", "sp", "rep")


def _f(family, kind, text, inputs, out, truth, tree):
    return TextFormula(family, f"language:{kind}", text, inputs, out, truth, tree)


CATALOGUE: tuple[TextFormula, ...] = (
    # initials
    _f("t_initials", "initials", "first letters of first and last name", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[:1] + ln[:1], _c(["first", V("fn")], ["first", V("ln")])),
    _f("t_initials_upper", "initials", "upper-case initials", NAME, "str",
       lambda fn, ln, sp, dt, cm: (fn[:1] + ln[:1]).upper(), ["upper", _c(["first", V("fn")], ["first", V("ln")])]),
    _f("t_initials_dot", "initials", "initials with dots: F.L.", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[:1] + "." + ln[:1] + ".",
       _c(["first", V("fn")], V("dt"), ["first", V("ln")], V("dt"))),
    _f("t_initials_dot_upper", "initials", "upper-case initials with dots: F.L.", NAME, "str",
       lambda fn, ln, sp, dt, cm: (fn[:1] + "." + ln[:1] + ".").upper(),
       ["upper", _c(["first", V("fn")], V("dt"), ["first", V("ln")], V("dt"))]),
    _f("t_short_name", "initials", "first initial, dot, space, last name: F. Last", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[:1] + ". " + ln, _c(["first", V("fn")], V("dt"), V("sp"), V("ln"))),
    _f("t_ends_both", "initials", "first and last letter of each name", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[:1] + fn[-1:] + ln[:1] + ln[-1:],
       _c(["first", V("fn")], ["last", V("fn")], ["first", V("ln")], ["last", V("ln")])),
    # joining / renaming
    _f("t_full_name", "joining", "first space last", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn + " " + ln, _c(V("fn"), V("sp"), V("ln"))),
    _f("t_last_first", "joining", "last, comma, space, first", NAME, "str",
       lambda fn, ln, sp, dt, cm: ln + ", " + fn, _c(V("ln"), V("cm"), V("sp"), V("fn"))),
    _f("t_handle", "joining", "lower-case first.last", NAME, "str",
       lambda fn, ln, sp, dt, cm: (fn + "." + ln).lower(), ["lower", _c(V("fn"), V("dt"), V("ln"))]),
    _f("t_username", "joining", "lower-case first initial + last name", NAME, "str",
       lambda fn, ln, sp, dt, cm: (fn[:1] + ln).lower(), ["lower", _c(["first", V("fn")], V("ln"))]),
    _f("t_echo_words", "joining", "word space word", WORD, "str",
       lambda w, w2, sp: w + " " + w, _c(V("w"), V("sp"), V("w"))),
    _f("t_pair_words", "joining", "word-two space word", WORD, "str",
       lambda w, w2, sp: w2 + " " + w, _c(V("w2"), V("sp"), V("w"))),
    # casing
    _f("t_shout_name", "casing", "upper-case full name", NAME, "str",
       lambda fn, ln, sp, dt, cm: (fn + " " + ln).upper(), ["upper", _c(V("fn"), V("sp"), V("ln"))]),
    _f("t_quiet_last_first", "casing", "lower-case last, first", NAME, "str",
       lambda fn, ln, sp, dt, cm: (ln + ", " + fn).lower(), ["lower", _c(V("ln"), V("cm"), V("sp"), V("fn"))]),
    _f("t_upper_last", "casing", "first name then upper-case last name", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn + " " + ln.upper(), _c(V("fn"), V("sp"), ["upper", V("ln")])),
    _f("t_shout_rev_both", "casing", "each name reversed and upper-cased", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[::-1].upper() + " " + ln[::-1].upper(),
       _c(["upper", ["srev", V("fn")]], V("sp"), ["upper", ["srev", V("ln")]])),
    _f("t_mirror", "casing", "word followed by itself reversed", WORD, "str",
       lambda w, w2, sp: w + w[::-1], _c(V("w"), ["srev", V("w")])),
    _f("t_mirror_lower", "casing", "lower-case word + reversed", WORD, "str",
       lambda w, w2, sp: (w + w[::-1]).lower(), ["lower", _c(V("w"), ["srev", V("w")])]),
    _f("t_rev_each", "casing", "each word reversed, space between", WORD, "str",
       lambda w, w2, sp: w[::-1] + " " + w2[::-1], _c(["srev", V("w")], V("sp"), ["srev", V("w2")])),
    # lengths (string -> int)
    _f("t_name_len", "lengths", "letters in first + last name", NAME, "int",
       lambda fn, ln, sp, dt, cm: len(fn) + len(ln), ["add", ["strlen", V("fn")], ["strlen", V("ln")]]),
    _f("t_full_len", "lengths", "characters in 'first last'", NAME, "int",
       lambda fn, ln, sp, dt, cm: len(fn) + 1 + len(ln),
       ["add", ["add", ["strlen", V("fn")], ["strlen", V("sp")]], ["strlen", V("ln")]]),
    _f("t_len_gap", "lengths", "letters in first minus letters in last", NAME, "int",
       lambda fn, ln, sp, dt, cm: len(fn) - len(ln), ["sub", ["strlen", V("fn")], ["strlen", V("ln")]]),
    _f("t_double_len_plus", "lengths", "2*len(first) + len(last)", NAME, "int",
       lambda fn, ln, sp, dt, cm: 2 * len(fn) + len(ln),
       ["add", ["add", ["strlen", V("fn")], ["strlen", V("fn")]], ["strlen", V("ln")]]),
    _f("t_card_len", "lengths", "characters in 'Last, First'", NAME, "int",
       lambda fn, ln, sp, dt, cm: len(ln) + 2 + len(fn),
       ["add", ["add", ["strlen", V("ln")], ["add", ["strlen", V("cm")], ["strlen", V("sp")]]], ["strlen", V("fn")]]),
    # mixed string + integer
    _f("t_banner_len", "mixed", "characters in rep copies of 'word ' = rep*(len(w)+1)", MIX, "int",
       lambda w, sp, rep: rep * (len(w) + 1), ["mul", V("rep"), ["add", ["strlen", V("w")], ["strlen", V("sp")]]]),
    _f("t_rep_letters", "mixed", "rep*len(w) + rep", MIX, "int",
       lambda w, sp, rep: rep * len(w) + rep, ["add", ["mul", V("rep"), ["strlen", V("w")]], V("rep")]),
    _f("t_square_len", "mixed", "len(w)^2 + rep", MIX, "int",
       lambda w, sp, rep: len(w) ** 2 + rep, ["add", ["mul", ["strlen", V("w")], ["strlen", V("w")]], V("rep")]),
    # slicing (needs `rest`)
    _f("t_capitalize", "slicing", "capitalise a word: upper first letter, lower the rest", WORD, "str",
       lambda w, w2, sp: w[:1].upper() + w[1:].lower(), _c(["upper", ["first", V("w")]], ["lower", ["rest", V("w")]])),
    _f("t_title_name", "slicing", "capitalise first and last name", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[:1].upper() + fn[1:].lower() + " " + ln[:1].upper() + ln[1:].lower(),
       _c(["upper", ["first", V("fn")]], ["lower", ["rest", V("fn")]], V("sp"),
          ["upper", ["first", V("ln")]], ["lower", ["rest", V("ln")]])),
    _f("t_rotate", "slicing", "move the first letter to the end", WORD, "str",
       lambda w, w2, sp: w[1:] + w[:1], _c(["rest", V("w")], ["first", V("w")])),
    _f("t_rotate_both", "slicing", "rotate each word by one, space between", WORD, "str",
       lambda w, w2, sp: w[1:] + w[:1] + " " + w2[1:] + w2[:1],
       _c(["rest", V("w")], ["first", V("w")], V("sp"), ["rest", V("w2")], ["first", V("w2")])),
    _f("t_drop_first_both", "slicing", "each word without its first letter, lower-case, joined", WORD, "str",
       lambda w, w2, sp: (w[1:] + w2[1:]).lower(), ["lower", _c(["rest", V("w")], ["rest", V("w2")])]),
    _f("t_formal_cap", "slicing", "capitalised last name, comma, space, first initial, dot", NAME, "str",
       lambda fn, ln, sp, dt, cm: ln[:1].upper() + ln[1:].lower() + ", " + fn[:1].upper() + ".",
       _c(["upper", ["first", V("ln")]], ["lower", ["rest", V("ln")]], V("cm"), V("sp"), ["upper", ["first", V("fn")]], V("dt"))),
    # longer joins and casings
    _f("t_initial_upper_last", "joining", "F. LAST", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[:1] + ". " + ln.upper(), _c(["first", V("fn")], V("dt"), V("sp"), ["upper", V("ln")])),
    _f("t_shout_last_first", "casing", "upper-case LAST, FIRST", NAME, "str",
       lambda fn, ln, sp, dt, cm: (ln + ", " + fn).upper(), ["upper", _c(V("ln"), V("cm"), V("sp"), V("fn"))]),
    _f("t_quiet_initials_dot", "initials", "lower-case initials with dots: f.l.", NAME, "str",
       lambda fn, ln, sp, dt, cm: (fn[:1] + "." + ln[:1] + ".").lower(),
       ["lower", _c(["first", V("fn")], V("dt"), ["first", V("ln")], V("dt"))]),
    _f("t_ends_upper_both", "initials", "upper-case first and last letter of each name", NAME, "str",
       lambda fn, ln, sp, dt, cm: (fn[:1] + fn[-1:] + ln[:1] + ln[-1:]).upper(),
       ["upper", _c(["first", V("fn")], ["last", V("fn")], ["first", V("ln")], ["last", V("ln")])]),
    _f("t_double_first", "joining", "lower first name twice, space, last name", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn.lower() + fn.lower() + " " + ln,
       _c(["lower", V("fn")], ["lower", V("fn")], V("sp"), V("ln"))),
    _f("t_ends_name", "joining", "first and last letter of first name, space, last name", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[:1] + fn[-1:] + " " + ln, _c(["first", V("fn")], ["last", V("fn")], V("sp"), V("ln"))),
    _f("t_rev_upper_first", "casing", "first name reversed upper-case, dot, last name", NAME, "str",
       lambda fn, ln, sp, dt, cm: fn[::-1].upper() + "." + ln, _c(["upper", ["srev", V("fn")]], V("dt"), V("ln"))),
    # more lengths and mixed
    _f("t_len_product", "lengths", "len(first) * len(last)", NAME, "int",
       lambda fn, ln, sp, dt, cm: len(fn) * len(ln), ["mul", ["strlen", V("fn")], ["strlen", V("ln")]]),
    _f("t_badge_len", "mixed", "rep badges of 'first last' = rep*(len(fn)+len(ln)+1)", ("fn", "ln", "sp", "rep"), "int",
       lambda fn, ln, sp, rep: rep * (len(fn) + len(ln) + 1),
       ["mul", V("rep"), ["add", ["strlen", V("fn")], ["add", ["strlen", V("ln")], ["strlen", V("sp")]]]]),
    _f("t_line_len", "mixed", "rep words joined by spaces = rep*len(w) + rep - 1", MIX, "int",
       lambda w, sp, rep: rep * len(w) + rep - 1, ["sub", ["mul", V("rep"), ["add", ["strlen", V("w")], ["const", 1]]], ["const", 1]]),
    _f("t_pyramid_len", "mixed", "letters in a pyramid of 1..rep words = rep(rep+1)/2 * len(w)", MIX, "int",
       lambda w, sp, rep: rep * (rep + 1) // 2 * len(w),
       ["div", ["mul", ["mul", V("rep"), ["add", V("rep"), ["const", 1]]], ["strlen", V("w")]], ["const", 2]]),
    _f("t_sq_plus_len", "mixed", "len(w)^2 + rep*len(w)", MIX, "int",
       lambda w, sp, rep: len(w) ** 2 + rep * len(w), ["mul", ["strlen", V("w")], ["add", ["strlen", V("w")], V("rep")]]),
    _f("t_half_len_rep", "mixed", "rep*len(w)*(rep+1)/2 letters in a staircase of words", MIX, "int",
       lambda w, sp, rep: rep * (rep + 1) // 2 * len(w),
       ["mul", ["div", ["mul", V("rep"), ["add", V("rep"), ["const", 1]]], ["const", 2]], ["strlen", V("w")]]),
)
BY_FAMILY = {f.family: f for f in CATALOGUE}


def is_text(family: str | None) -> bool:
    return bool(family) and family in BY_FAMILY
