"""INVENT_TEXT sealed catalogue (docs/INVENT_TEXT.md): string + mixed int/str tasks, new names.

Written, and committed with the pre-registered criteria, before any field arm is measured on it.
Built exactly like ``nomad.bridge.CATALOGUE`` (same word list and case mixing, bridge opset, independent
Python ground truth, a row kept only when the reference tree reproduces it, 5 public / 3 challenge /
3 final rows) but with new input names ``xw xv xk xj xq`` (disjoint from every catalogue), a new
separator ("_"), new compositions, and a few integer-output and non-concatenation controls. None
chosen by outcome.
"""
from __future__ import annotations

import random

from .text import FIRST, TextFormula, V, WORDS, _case
from .world import Invalid, WorldTask, make_task, run

DOMAIN = "bridge"
DOMAINS = ("bridge",)
N_PUBLIC, N_CHALLENGE, N_FINAL = 5, 3, 3

GEN = {
    "xw": lambda rng: _case(rng, rng.choice(WORDS)),
    "xv": lambda rng: _case(rng, rng.choice(WORDS + FIRST[:6])),
    "xk": lambda rng: rng.randint(1, 3),
    "xj": lambda rng: rng.randint(0, 3),
    "xq": lambda rng: "_",
}
TYPES = {"xw": "str", "xv": "str", "xk": "int", "xj": "int", "xq": "str"}


def exact_answer(f: TextFormula, row: dict):
    try:
        want = f.truth(*(row[n] for n in f.inputs))
    except IndexError:
        return None
    if want is None:
        return None
    try:
        got = run(f.tree, row)
    except Invalid:
        return None
    return want if got == want else None


def draw_rows(f: TextFormula, rng: random.Random, n: int = N_PUBLIC + N_CHALLENGE + N_FINAL,
              tries: int = 20000) -> list[tuple[dict, object]]:
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
    return make_task(entry["task_id"], entry["family"], "bridge", {n: TYPES[n] for n in entry["inputs"]},
                     entry["out"], rows[:a], rows[a:b], rows[b:], entry.get("level", 9))


def _f(family, kind, text, inputs, out, truth, tree):
    return TextFormula(family, f"bridge:{kind}", text, inputs, out, truth, tree)


W1 = ("xw", "xk")
W2 = ("xw", "xv", "xk", "xj")
SEP = ("xw", "xk", "xq")
PSEP = ("xw", "xv", "xq")
L = lambda x: ["strlen", x]   # noqa: E731
w, v, k, j, q = V("xw"), V("xv"), V("xk"), V("xj"), V("xq")


def cat(*xs):
    out = xs[-1]
    for x in reversed(xs[:-1]):
        out = ["concat", x, out]
    return out


CATALOGUE: tuple[TextFormula, ...] = (
    _f("x_initial_sep_word", "label", "initial, separator, word", SEP, "str",
       lambda w_, k_, q_: w_[0] + q_ + w_, cat(["first", w], q, w)),
    _f("x_word_sep_len", "label", "word, separator, its length", SEP, "str",
       lambda w_, k_, q_: w_ + q_ + str(len(w_)), cat(w, q, ["itos", L(w)])),
    _f("x_upper_head_lower_tail", "slice", "first k letters upper-case, the rest lower-case", W1, "str",
       lambda w_, k_: w_[:k_].upper() + w_[k_:].lower(), cat(["upper", ["take", w, k]], ["lower", ["drop", w, k]])),
    _f("x_tail_then_initial", "slice", "last k letters then the initial", W1, "str",
       lambda w_, k_: w_[len(w_) - k_:] + w_[0], cat(["drop", w, ["sub", L(w), k]], ["first", w])),
    _f("x_stutter_initial", "repeat", "initial of one word k times, then the initial of another", W2, "str",
       lambda w_, v_, k_, j_: w_[0] * k_ + v_[0], cat(["srep", ["first", w], k], ["first", v])),
    _f("x_word_k", "label", "the word followed by k", W1, "str",
       lambda w_, k_: w_ + str(k_), cat(w, ["itos", k])),
    _f("x_k_sep_word", "label", "k, separator, word", SEP, "str",
       lambda w_, k_, q_: str(k_) + q_ + w_, cat(["itos", k], q, w)),
    _f("x_rev_head", "slice", "first k letters reversed, then the rest", W1, "str",
       lambda w_, k_: w_[:k_][::-1] + w_[k_:], cat(["srev", ["take", w, k]], ["drop", w, k])),
    _f("x_delete_kth", "slice", "delete letter k", W1, "str",
       lambda w_, k_: w_[:k_] + w_[k_ + 1:] if k_ < len(w_) else None, cat(["take", w, k], ["drop", w, ["add", k, ["const", 1]]])),
    _f("x_double_kth", "slice", "double letter k", W1, "str",
       lambda w_, k_: w_[:k_ + 1] + w_[k_:] if k_ < len(w_) else None, cat(["take", w, ["add", k, ["const", 1]]], ["drop", w, k])),
    _f("x_cross_tail", "slice", "first k letters of one word, all but the first j of another", W2, "str",
       lambda w_, v_, k_, j_: w_[:k_] + v_[j_:] if j_ <= len(v_) else None, cat(["take", w, k], ["drop", v, j])),
    _f("x_pair_sep", "label", "word, separator, other word", PSEP, "str",
       lambda w_, v_, q_: w_ + q_ + v_, cat(w, q, v)),
    _f("x_len_pair", "label", "both lengths around the separator", PSEP, "str",
       lambda w_, v_, q_: str(len(w_)) + q_ + str(len(v_)), cat(["itos", L(w)], q, ["itos", L(v)])),
    _f("x_rest_stutter", "repeat", "the rest of the word, then its initial k times", W1, "str",
       lambda w_, k_: w_[1:] + w_[0] * k_, cat(["rest", w], ["srep", ["first", w], k])),
    _f("x_last_sep_first", "label", "last letter, separator, first letter", SEP, "str",
       lambda w_, k_, q_: w_[-1] + q_ + w_[0], cat(["last", w], q, ["first", w])),
    _f("x_echo_sep", "repeat", "the word k times then the separator", SEP, "str",
       lambda w_, k_, q_: w_ * k_ + q_, cat(["srep", w, k], q)),
    _f("x_frame", "label", "separator, word, separator", SEP, "str",
       lambda w_, k_, q_: q_ + w_ + q_, cat(q, w, q)),
    _f("x_digits_then_word", "label", "digits of k times the length, then the word", W1, "str",
       lambda w_, k_: str(k_ * len(w_)) + w_, cat(["itos", ["mul", k, L(w)]], w)),
    _f("x_lower_rot", "slice", "rotate left by k, lower-case", W1, "str",
       lambda w_, k_: (w_[k_:] + w_[:k_]).lower(), ["lower", cat(["drop", w, k], ["take", w, k])]),
    _f("x_upper_kth", "slice", "letter k upper-case", W1, "str",
       lambda w_, k_: w_[k_].upper() if k_ < len(w_) else None, ["upper", ["at", w, k]]),
    _f("x_len_pair_k", "count", "length of one word plus k times the other's", W2, "int",
       lambda w_, v_, k_, j_: len(w_) + k_ * len(v_), ["add", L(w), ["mul", k, L(v)]]),
    _f("x_len_joined", "count", "length of word, separator, other word", PSEP, "int",
       lambda w_, v_, q_: len(w_ + q_ + v_), L(cat(w, q, v))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
