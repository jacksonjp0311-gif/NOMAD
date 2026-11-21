"""TEXT_CHAIN sealed catalogue (docs/TEXT_CHAIN.md): string goals of three or more parts, new names.

Written, and committed with the pre-registered criteria, before any field arm is measured on it.
Built like ``nomad.text_invent_tasks.CATALOGUE`` (same word lists and case mixing, bridge opset,
independent Python ground truth, a row kept only when the reference tree reproduces it, 5 public /
3 challenge / 3 final rows) with new input names ``ma mb mk mj ms mt`` (disjoint from every
catalogue), new separators (":" and "/"), and new compositions: mostly 3-5 part concatenations of
slices, case changes, repeats, rotations and number-to-text pieces, plus a few controls (two-part,
integer-output, non-concatenation). None chosen by outcome.
"""
from __future__ import annotations

import random

from . import text_invent_tasks as _XT
from .text import FIRST, TextFormula, V, WORDS, _case
from .world import WorldTask, make_task

DOMAIN = "bridge"
DOMAINS = ("bridge",)
N_PUBLIC, N_CHALLENGE, N_FINAL = 5, 3, 3

GEN = {
    "ma": lambda rng: _case(rng, rng.choice(WORDS)),
    "mb": lambda rng: _case(rng, rng.choice(FIRST)),
    "mk": lambda rng: rng.randint(1, 3),
    "mj": lambda rng: rng.randint(0, 3),
    "ms": lambda rng: ":",
    "mt": lambda rng: "/",
}
TYPES = {"ma": "str", "mb": "str", "mk": "int", "mj": "int", "ms": "str", "mt": "str"}


def draw_rows(f: TextFormula, rng: random.Random) -> list[tuple[dict, object]]:
    """The INVENT_TEXT row drawer with this catalogue's generators."""
    old = _XT.GEN, _XT.TYPES
    _XT.GEN, _XT.TYPES = GEN, TYPES
    try:
        return _XT.draw_rows(f, rng)
    finally:
        _XT.GEN, _XT.TYPES = old


def to_task(entry: dict) -> WorldTask:
    rows = [(dict(r), e) for r, e in entry["rows"]]
    a, b = N_PUBLIC, N_PUBLIC + N_CHALLENGE
    return make_task(entry["task_id"], entry["family"], "bridge", {n: TYPES[n] for n in entry["inputs"]},
                     entry["out"], rows[:a], rows[a:b], rows[b:], entry.get("level", 9))


def _f(family, kind, text, inputs, out, truth, tree):
    return TextFormula(family, f"bridge:{kind}", text, inputs, out, truth, tree)


cat = _XT.cat
a, b, k, j, s, t = (V(n) for n in ("ma", "mb", "mk", "mj", "ms", "mt"))
L = lambda x: ["strlen", x]   # noqa: E731
take = lambda x, n: ["take", x, n]   # noqa: E731
drop = lambda x, n: ["drop", x, n]   # noqa: E731
tail = lambda x, n: ["drop", x, ["sub", L(x), n]]   # noqa: E731
rot = lambda x, n: cat(drop(x, n), take(x, n))   # noqa: E731
itos = lambda x: ["itos", x]   # noqa: E731

AK = ("ma", "mk", "ms")
ABK = ("ma", "mb", "mk", "ms")
ABKT = ("ma", "mb", "mk", "ms", "mt")
AKJ = ("ma", "mk", "mj", "ms")
ABKJ = ("ma", "mb", "mk", "mj", "ms", "mt")


def _rot(w, n):
    return w[n:] + w[:n]


CATALOGUE: tuple[TextFormula, ...] = (
    # three parts
    _f("m_name_colon_word", "label", "name, colon, word", ABK, "str",
       lambda a_, b_, k_, s_: b_ + s_ + a_, cat(b, s, a)),
    _f("m_head_colon_tail", "slice", "first k letters, colon, last k letters", AK, "str",
       lambda a_, k_, s_: a_[:k_] + s_ + a_[len(a_) - k_:], cat(take(a, k), s, tail(a, k))),
    _f("m_initial_colon_len", "label", "initial, colon, length", AK, "str",
       lambda a_, k_, s_: a_[0] + s_ + str(len(a_)), cat(["first", a], s, itos(L(a)))),
    _f("m_upper_name_slash_lower_word", "label", "name upper-case, slash, word lower-case", ABKT, "str",
       lambda a_, b_, k_, s_, t_: b_.upper() + t_ + a_.lower(), cat(["upper", b], t, ["lower", a])),
    _f("m_rot_colon_initial", "slice", "rotate by k, colon, initial", AK, "str",
       lambda a_, k_, s_: _rot(a_, k_) + s_ + a_[0], cat(rot(a, k), s, ["first", a])),
    _f("m_k_slash_name_slash", "label", "k, slash, name, slash", ABKT, "str",
       lambda a_, b_, k_, s_, t_: str(k_) + t_ + b_ + t_, cat(itos(k), t, b, t)),
    _f("m_take_take_mix", "slice", "first k letters of the word, then of the name, then of the word", ABK, "str",
       lambda a_, b_, k_, s_: a_[:k_] + b_[:k_] + a_[:k_] if k_ <= len(b_) else None, cat(take(a, k), take(b, k), take(a, k))),
    _f("m_rep_last_colon_name", "repeat", "last letter k times, colon, name", ABK, "str",
       lambda a_, b_, k_, s_: a_[-1] * k_ + s_ + b_, cat(["srep", ["last", a], k], s, b)),
    _f("m_drop_colon_rev_take", "slice", "all but the first k, colon, first k reversed", AK, "str",
       lambda a_, k_, s_: a_[k_:] + s_ + a_[:k_][::-1], cat(drop(a, k), s, ["srev", take(a, k)])),
    _f("m_lower_initials_colon", "label", "both initials lower-case around a colon", ABK, "str",
       lambda a_, b_, k_, s_: a_[0].lower() + s_ + b_[0].lower(), cat(["lower", ["first", a]], s, ["lower", ["first", b]])),
    _f("m_len_sum_colon_word", "label", "length plus k, colon, word", AK, "str",
       lambda a_, k_, s_: str(len(a_) + k_) + s_ + a_, cat(itos(["add", L(a), k]), s, a)),
    _f("m_tail_colon_tail", "slice", "last k letters of both around a colon", ABK, "str",
       lambda a_, b_, k_, s_: a_[len(a_) - k_:] + s_ + b_[len(b_) - k_:] if k_ <= len(b_) else None,
       cat(tail(a, k), s, tail(b, k))),
    # four and five parts
    _f("m_word_colon_name_slash_k", "label", "word, colon, name, slash, k", ABKT, "str",
       lambda a_, b_, k_, s_, t_: a_ + s_ + b_ + t_ + str(k_), cat(a, s, b, t, itos(k))),
    _f("m_frame_colon_head", "label", "colon, first k letters, colon", AK, "str",
       lambda a_, k_, s_: s_ + a_[:k_] + s_, cat(s, take(a, k), s)),
    _f("m_initials_len", "label", "both initials, colon, total length", ABK, "str",
       lambda a_, b_, k_, s_: a_[0] + b_[0] + s_ + str(len(a_) + len(b_)),
       cat(["first", a], ["first", b], s, itos(["add", L(a), L(b)]))),
    _f("m_up_head_colon_rest_colon_k", "slice", "first k upper-case, colon, the rest, colon, k", AK, "str",
       lambda a_, k_, s_: a_[:k_].upper() + s_ + a_[k_:] + s_ + str(k_), cat(["upper", take(a, k)], s, drop(a, k), s, itos(k))),
    _f("m_rot_rot_slash", "slice", "word rotated by k, slash, name rotated by j", ABKJ, "str",
       lambda a_, b_, k_, j_, s_, t_: _rot(a_, k_) + t_ + _rot(b_, j_) if j_ <= len(b_) else None,
       cat(rot(a, k), t, rot(b, j))),
    _f("m_name_word_lens", "label", "name, colon, word, slash, both lengths summed", ABKT, "str",
       lambda a_, b_, k_, s_, t_: b_ + s_ + a_ + t_ + str(len(a_) + len(b_)),
       cat(b, s, a, t, itos(["add", L(a), L(b)]))),
    _f("m_head_mid_tail", "slice", "first j letters, colon, letters j..k+j, colon, the rest", AKJ, "str",
       lambda a_, k_, j_, s_: a_[:j_] + s_ + a_[j_:j_ + k_] + s_ + a_[j_ + k_:] if j_ + k_ < len(a_) else None,
       cat(take(a, j), s, take(drop(a, j), k), s, drop(a, ["add", j, k]))),
    _f("m_last_first_slash_name_upper", "label", "last and first letter, slash, name upper-case", ABKT, "str",
       lambda a_, b_, k_, s_, t_: a_[-1] + a_[0] + t_ + b_.upper(), cat(["last", a], ["first", a], t, ["upper", b])),
    # controls
    _f("m_word_then_k", "label", "word then k (two parts)", AK, "str",
       lambda a_, k_, s_: a_ + str(k_), cat(a, itos(k))),
    _f("m_lower_rot_ctrl", "slice", "rotate by k, lower-case (not a chain at the top)", AK, "str",
       lambda a_, k_, s_: _rot(a_, k_).lower(), ["lower", rot(a, k)]),
    _f("m_len_three_ctrl", "count", "length of word, colon, name (integer)", ABK, "int",
       lambda a_, b_, k_, s_: len(a_ + s_ + b_), L(cat(a, s, b))),
    _f("m_len_k_ctrl", "count", "k times the word's length plus the name's (integer)", ABK, "int",
       lambda a_, b_, k_, s_: k_ * len(a_) + len(b_), ["add", ["mul", k, L(a)], L(b)]),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
