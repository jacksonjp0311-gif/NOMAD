"""BRIDGE: int <-> str bridges, mixed string / integer tasks, a bridge training set (docs/BRIDGE.md).

Do integer and string skills combine? The text suite said no (docs/TEXT.md):
the mixed tasks needed *index* and *length* bridges the DSL did not have.
This module is the domain half of the BRIDGE step (everything is behind
``NOMAD_BRIDGE``, default off):

- ``at take drop srep itos`` (``nomad/world.py``): s[i], first i characters,
  all but the first i, i copies, decimal digits of i. All partial (negative
  or out-of-range indices are ``Invalid``), all mirrored in the standalone
  feed checker (a test pins the tables together).
- ``CATALOGUE``: 30 sealed-candidate families on string / mixed int+str
  inputs (``bw bw2 bk bj bs``; disjoint from every other catalogue), ground
  truth an independent Python function, a row kept only when the reference
  tree reproduces it, exactly like ``nomad/text.py``.
- ``TRAIN_FAMILIES``: 16 small bridge-using WORLD-style training tasks on
  ``s`` / ``x`` with fixed literal rows. Never a sealed family.

Tasks run on the ``bridge`` opset (resolved only when NOMAD_BRIDGE is on;
otherwise the ``text`` opset, so the off switch changes nothing).
"""
from __future__ import annotations

import random

from .text import FIRST, TextFormula, V, WORDS, _c, _case
from .world import Invalid, WorldTask, make_task, run

DOMAIN = "bridge"
N_PUBLIC, N_CHALLENGE, N_FINAL = 5, 3, 3

GEN = {
    "bw": lambda rng: _case(rng, rng.choice(WORDS)),
    "bw2": lambda rng: _case(rng, rng.choice(WORDS + FIRST[:6])),
    "bk": lambda rng: rng.randint(1, 3),
    "bj": lambda rng: rng.randint(0, 3),
    "bs": lambda rng: "-",
}
TYPES = {"bw": "str", "bw2": "str", "bk": "int", "bj": "int", "bs": "str"}


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
    return make_task(entry["task_id"], entry["family"], "bridge", {n: TYPES[n] for n in entry["inputs"]},
                     entry["out"], rows[:a], rows[a:b], rows[b:], entry.get("level", 9))


def _f(family, kind, text, inputs, out, truth, tree):
    return TextFormula(family, f"bridge:{kind}", text, inputs, out, truth, tree)


def _rot(w, k):
    return w[k:] + w[:k]


W1 = ("bw", "bk")
W2 = ("bw", "bw2", "bk", "bj")
SEP = ("bw", "bk", "bs")
L = lambda x: ["strlen", x]                      # noqa: E731
C = lambda n: ["const", n]                       # noqa: E731

DEV_CATALOGUE: tuple[TextFormula, ...] = (
    # slicing by an integer
    _f("b_rot_upper", "slice", "rotate the word left by k, upper-case", W1, "str",
       lambda w, k: _rot(w, k).upper(), ["upper", ["concat", ["drop", V("bw"), V("bk")], ["take", V("bw"), V("bk")]]]),
    _f("b_rot_rev", "slice", "rotate left by k, then reverse", W1, "str",
       lambda w, k: _rot(w, k)[::-1], ["srev", ["concat", ["drop", V("bw"), V("bk")], ["take", V("bw"), V("bk")]]]),
    _f("b_tail_upper", "slice", "last k letters, upper-case", W1, "str",
       lambda w, k: w[len(w) - k:].upper(), ["upper", ["drop", V("bw"), ["sub", L(V("bw")), V("bk")]]]),
    _f("b_ends_k", "slice", "first k letters then last k letters", W1, "str",
       lambda w, k: w[:k] + w[len(w) - k:],
       ["concat", ["take", V("bw"), V("bk")], ["drop", V("bw"), ["sub", L(V("bw")), V("bk")]]]),
    _f("b_chop_upper_tag", "slice", "drop the last k letters, upper-case, then k", W1, "str",
       lambda w, k: w[:len(w) - k].upper() + str(k),
       ["concat", ["upper", ["take", V("bw"), ["sub", L(V("bw")), V("bk")]]], ["itos", V("bk")]]),
    _f("b_pick_two", "slice", "letter k then letter j", W2, "str",
       lambda w, w2, k, j: w[k] + w[j], ["concat", ["at", V("bw"), V("bk")], ["at", V("bw"), V("bj")]]),
    _f("b_pick_mirror", "slice", "letter k of the word and of the reversed word", W1, "str",
       lambda w, k: w[k] + w[::-1][k], ["concat", ["at", V("bw"), V("bk")], ["at", ["srev", V("bw")], V("bk")]]),
    _f("b_two_takes", "slice", "first k letters of one word, first j of another", W2, "str",
       lambda w, w2, k, j: w[:k] + w2[:j], ["concat", ["take", V("bw"), V("bk")], ["take", V("bw2"), V("bj")]]),
    _f("b_two_drops", "slice", "drop k from one word, j from another, join", W2, "str",
       lambda w, w2, k, j: w[k:] + w2[j:], ["concat", ["drop", V("bw"), V("bk")], ["drop", V("bw2"), V("bj")]]),
    # split / join with a separator column
    _f("b_split_at", "split", "split at k with a dash: ab-cde", SEP, "str",
       lambda w, k, s: w[:k] + s + w[k:],
       ["concat", ["take", V("bw"), V("bk")], ["concat", V("bs"), ["drop", V("bw"), V("bk")]]]),
    _f("b_split_upper", "split", "upper-case split at k with a dash", SEP, "str",
       lambda w, k, s: (w[:k] + s + w[k:]).upper(),
       ["upper", ["concat", ["take", V("bw"), V("bk")], ["concat", V("bs"), ["drop", V("bw"), V("bk")]]]]),
    _f("b_swap_split", "split", "swap the parts around a dash at k", SEP, "str",
       lambda w, k, s: w[k:] + s + w[:k],
       ["concat", ["drop", V("bw"), V("bk")], ["concat", V("bs"), ["take", V("bw"), V("bk")]]]),
    # repeats
    _f("b_stretch_first", "repeat", "repeat the first letter k times, then the rest", W1, "str",
       lambda w, k: w[0] * k + w[1:], ["concat", ["srep", ["first", V("bw")], V("bk")], ["rest", V("bw")]]),
    _f("b_tail_echo", "repeat", "the word then its last letter k times", W1, "str",
       lambda w, k: w + w[-1] * k, ["concat", V("bw"), ["srep", ["last", V("bw")], V("bk")]]),
    _f("b_echo_sep", "repeat", "word, dash, then the word k times", SEP, "str",
       lambda w, k, s: w + s + w * k, ["concat", V("bw"), ["concat", V("bs"), ["srep", V("bw"), V("bk")]]]),
    _f("b_rep_initial_tag", "repeat", "initial repeated k times then the length", W1, "str",
       lambda w, k: w[0] * k + str(len(w)), ["concat", ["srep", ["first", V("bw")], V("bk")], ["itos", L(V("bw"))]]),
    # int -> str labels
    _f("b_label", "label", "k, dash, word", SEP, "str",
       lambda w, k, s: str(k) + s + w, ["concat", ["itos", V("bk")], ["concat", V("bs"), V("bw")]]),
    _f("b_len_tag_upper", "label", "upper-case word followed by its length", ("bw",), "str",
       lambda w: w.upper() + str(len(w)), ["concat", ["upper", V("bw")], ["itos", L(V("bw"))]]),
    _f("b_k_of_n", "label", "k, dash, length of the word", SEP, "str",
       lambda w, k, s: str(k) + s + str(len(w)), ["concat", ["itos", V("bk")], ["concat", V("bs"), ["itos", L(V("bw"))]]]),
    _f("b_total_len", "label", "combined length of two words as digits", W2, "str",
       lambda w, w2, k, j: str(len(w) + len(w2)), ["itos", ["add", L(V("bw")), L(V("bw2"))]]),
    _f("b_prod_tag", "label", "word followed by k times its length", W1, "str",
       lambda w, k: w + str(k * len(w)), ["concat", V("bw"), ["itos", ["mul", V("bk"), L(V("bw"))]]]),
    _f("b_initial_left", "label", "initial then the letters left after dropping k", W1, "str",
       lambda w, k: w[0] + str(len(w) - k), ["concat", ["first", V("bw")], ["itos", ["sub", L(V("bw")), V("bk")]]]),
    _f("b_sq_digits", "label", "square of the length as digits, then the word", ("bw",), "str",
       lambda w: str(len(w) * len(w)) + w, ["concat", ["itos", ["mul", L(V("bw")), L(V("bw"))]], V("bw")]),
    # str -> int through a bridge
    _f("b_len_rep_join", "length", "length of k copies of one word joined to another", W2, "int",
       lambda w, w2, k, j: len(w) * k + len(w2), ["add", ["mul", L(V("bw")), V("bk")], L(V("bw2"))]),
    _f("b_digits_of_product", "length", "digits in len(w) * len(w2) * k", W2, "int",
       lambda w, w2, k, j: len(str(len(w) * len(w2) * k)),
       ["strlen", ["itos", ["mul", ["mul", L(V("bw")), L(V("bw2"))], V("bk")]]]),
    _f("b_digits_of_cube", "length", "digits in len(w)^3", ("bw", "bk"), "int",
       lambda w, k: len(str(len(w) ** 3)),
       ["strlen", ["itos", ["mul", L(V("bw")), ["mul", L(V("bw")), L(V("bw"))]]]]),
    _f("b_len_after_drop", "length", "k times the letters left after dropping j", W2, "int",
       lambda w, w2, k, j: k * (len(w) - j) if j <= len(w) else None,
       ["mul", V("bk"), L(["drop", V("bw"), V("bj")])]),
    _f("b_len_split", "length", "length of the dashed split of w at k, plus j", ("bw", "bk", "bj", "bs"), "int",
       lambda w, k, j, s: len(w) + len(s) + j,
       ["add", L(["concat", ["take", V("bw"), V("bk")], ["concat", V("bs"), ["drop", V("bw"), V("bk")]]]), V("bj")]),
    _f("b_label_len", "length", "length of 'k-word' labels times j", W2, "int",
       lambda w, w2, k, j: (1 + len(w) + 1) * j,
       ["mul", L(["concat", ["itos", V("bk")], ["concat", ["first", V("bw2")], V("bw")]]), V("bj")]),
)

# ----------------------------------------------------------------- the sealed catalogue
# Written blind (before any search ran on it), as compositions of the training blocks.
# DEV_CATALOGUE above is what the mechanism was tuned on (uncommitted dev suites only).
def _lens(x):
    return ["strlen", x]


def _cut(w, k):
    return ["sub", _lens(V(w)), V(k)]


CATALOGUE: tuple[TextFormula, ...] = (
    _f("s_rot_tag", "slice", "rotate left by k then append k", W1, "str",
       lambda w, k: _rot(w, k) + str(k),
       ["concat", ["drop", V("bw"), V("bk")], ["concat", ["take", V("bw"), V("bk")], ["itos", V("bk")]]]),
    _f("s_rot_lower_sep", "slice", "lower-case: the rest, a dash, the first k", SEP, "str",
       lambda w, k, s: (w[k:] + s + w[:k]).lower(),
       ["lower", ["concat", ["drop", V("bw"), V("bk")], ["concat", V("bs"), ["take", V("bw"), V("bk")]]]]),
    _f("s_cap_prefix", "slice", "upper-case the first k letters", W1, "str",
       lambda w, k: w[:k].upper() + w[k:], ["concat", ["upper", ["take", V("bw"), V("bk")]], ["drop", V("bw"), V("bk")]]),
    _f("s_rot_right", "slice", "rotate right by k", W1, "str",
       lambda w, k: w[len(w) - k:] + w[:len(w) - k],
       ["concat", ["drop", V("bw"), _cut("bw", "bk")], ["take", V("bw"), _cut("bw", "bk")]]),
    _f("s_cut_gap", "slice", "delete the j letters after the first k", W2, "str",
       lambda w, w2, k, j: w[:k] + w[k + j:] if k + j <= len(w) else None,
       ["concat", ["take", V("bw"), V("bk")], ["drop", V("bw"), ["add", V("bk"), V("bj")]]]),
    _f("s_from_end", "slice", "the k-th letter from the end", W1, "str",
       lambda w, k: w[len(w) - k], ["at", V("bw"), _cut("bw", "bk")]),
    _f("s_pick_cross", "slice", "letter k of one word, letter j of another", W2, "str",
       lambda w, w2, k, j: w[k] + w2[j] if j < len(w2) else None,
       ["concat", ["at", V("bw"), V("bk")], ["at", V("bw2"), V("bj")]]),
    _f("s_rev_prefix", "slice", "reverse the first k letters", W1, "str",
       lambda w, k: w[:k][::-1] + w[k:], ["concat", ["srev", ["take", V("bw"), V("bk")]], ["drop", V("bw"), V("bk")]]),
    _f("s_rev_suffix", "slice", "reverse the last k letters", W1, "str",
       lambda w, k: w[:len(w) - k] + w[len(w) - k:][::-1],
       ["concat", ["take", V("bw"), _cut("bw", "bk")], ["srev", ["drop", V("bw"), _cut("bw", "bk")]]]),
    _f("s_first_last_rep", "repeat", "first letter, then the last letter k times", W1, "str",
       lambda w, k: w[0] + w[-1] * k, ["concat", ["first", V("bw")], ["srep", ["last", V("bw")], V("bk")]]),
    _f("s_rep_pair", "repeat", "first letter k times then last letter j times", W2, "str",
       lambda w, w2, k, j: w[0] * k + w[-1] * j,
       ["concat", ["srep", ["first", V("bw")], V("bk")], ["srep", ["last", V("bw")], V("bj")]]),
    _f("s_rep_prefix", "repeat", "the first k letters, j times", W2, "str",
       lambda w, w2, k, j: w[:k] * j, ["srep", ["take", V("bw"), V("bk")], V("bj")]),
    _f("s_underline", "repeat", "the word, then a dash for every letter", SEP, "str",
       lambda w, k, s: w + s * len(w), ["concat", V("bw"), ["srep", V("bs"), _lens(V("bw"))]]),
    _f("s_frame", "repeat", "the word framed by k dashes each side", SEP, "str",
       lambda w, k, s: s * k + w + s * k,
       ["concat", ["srep", V("bs"), V("bk")], ["concat", V("bw"), ["srep", V("bs"), V("bk")]]]),
    _f("s_bar_len", "repeat", "a dash for every letter of the word", SEP, "str",
       lambda w, k, s: s * len(w), ["srep", V("bs"), _lens(V("bw"))]),
    _f("s_len_pair", "label", "length of one word, dash, length of another", ("bw", "bw2", "bs"), "str",
       lambda w, w2, s: str(len(w)) + s + str(len(w2)),
       ["concat", ["itos", _lens(V("bw"))], ["concat", V("bs"), ["itos", _lens(V("bw2"))]]]),
    _f("s_upper_len", "label", "upper-case word, dash, its length", ("bw", "bs"), "str",
       lambda w, s: w.upper() + s + str(len(w)),
       ["concat", ["upper", V("bw")], ["concat", V("bs"), ["itos", _lens(V("bw"))]]]),
    _f("s_affine_label", "label", "len*k + j as digits", W2, "str",
       lambda w, w2, k, j: str(len(w) * k + j), ["itos", ["add", ["mul", _lens(V("bw")), V("bk")], V("bj")]]),
    _f("s_last_square", "label", "last letter then len + k*k", W1, "str",
       lambda w, k: w[-1] + str(len(w) + k * k),
       ["concat", ["last", V("bw")], ["itos", ["add", _lens(V("bw")), ["mul", V("bk"), V("bk")]]]]),
    _f("s_two_labels", "label", "k, dash, j, dash, word", ("bw", "bk", "bj", "bs"), "str",
       lambda w, k, j, s: str(k) + s + str(j) + s + w,
       ["concat", ["itos", V("bk")], ["concat", V("bs"), ["concat", ["itos", V("bj")], ["concat", V("bs"), V("bw")]]]]),
    _f("s_len_of_edit", "length", "length after keeping the first k and the last j letters", W2, "int",
       lambda w, w2, k, j: min(k, len(w)) + j if j <= len(w) else None,
       ["strlen", ["concat", ["take", V("bw"), V("bk")], ["drop", V("bw"), _cut("bw", "bj")]]]),
    _f("s_digit_count", "length", "digits in (len(w)*len(w2)+k)*k", W2, "int",
       lambda w, w2, k, j: len(str((len(w) * len(w2) + k) * k)),
       ["strlen", ["itos", ["mul", ["add", ["mul", _lens(V("bw")), _lens(V("bw2"))], V("bk")], V("bk")]]]),
    _f("s_rep_total", "length", "total letters in k copies of one word and j of another", W2, "int",
       lambda w, w2, k, j: len(w) * k + len(w2) * j,
       ["add", _lens(["srep", V("bw"), V("bk")]), _lens(["srep", V("bw2"), V("bj")])]),
    _f("s_kept_after_cut", "length", "k times the letters kept after cutting the last j", W2, "int",
       lambda w, w2, k, j: k * (len(w) - j),
       ["mul", V("bk"), _lens(["take", V("bw"), _cut("bw", "bj")])]),
    _f("s_tail_len_sq", "length", "(letters after the first k) squared", W1, "int",
       lambda w, k: (len(w) - k) ** 2, ["mul", _lens(["drop", V("bw"), V("bk")]), _lens(["drop", V("bw"), V("bk")])]),
    _f("s_label_width", "length", "width of 'k-word-j'", ("bw", "bk", "bj", "bs"), "int",
       lambda w, k, j, s: 1 + len(s) + len(w) + len(s) + 1,
       ["strlen", ["concat", ["itos", V("bk")], ["concat", V("bs"), ["concat", V("bw"), ["concat", V("bs"), ["itos", V("bj")]]]]]]),
    _f("s_cross_len_digits", "length", "digits in (len(w)+j) * (len(w2)+k) * k", W2, "int",
       lambda w, w2, k, j: len(str((len(w) + j) * (len(w2) + k) * k)),
       ["strlen", ["itos", ["mul", ["mul", ["add", _lens(V("bw")), V("bj")], ["add", _lens(V("bw2")), V("bk")]], V("bk")]]]),
)
BY_FAMILY = {f.family: f for f in CATALOGUE + DEV_CATALOGUE}


# ----------------------------------------------------------------- training families
# WORLD-style: fixed literal rows, signature (s: str, x: int). Disjoint from the sealed names
# and programs; the sealed families are compositions of these blocks, not copies.
_S_PUB = ["abcdef", "hello", "nomad", "tundra", "Xylem"]
_S_CHA = ["river", "Grokly", "desert"]
_S_FIN = ["camels", "window", "Atlas5"]
_X_PUB = [2, 1, 3, 2, 4]
_X_CHA = [3, 1, 2]
_X_FIN = [2, 4, 1]


def _train(tid, fam, fn, tree, out="str", level=3):
    rows = lambda ss, xs: [({"s": s, "x": x}, fn(s, x)) for s, x in zip(ss, xs)]   # noqa: E731
    t = make_task(tid, fam, "bridge", {"s": "str", "x": "int"}, out,
                  rows(_S_PUB, _X_PUB), rows(_S_CHA, _X_CHA), rows(_S_FIN, _X_FIN), level)
    return t, tree


_TRAIN_SPECS = (
    ("br-take", "br_take", lambda s, x: s[:x], ["take", V("s"), V("x")]),
    ("br-drop", "br_drop", lambda s, x: s[x:], ["drop", V("s"), V("x")]),
    ("br-at", "br_at", lambda s, x: s[x], ["at", V("s"), V("x")]),
    ("br-rep", "br_rep", lambda s, x: s * x, ["srep", V("s"), V("x")]),
    ("br-itos", "br_itos_len", lambda s, x: str(len(s)), ["itos", ["strlen", V("s")]]),
    ("br-tag", "br_len_tag", lambda s, x: s + str(len(s)), ["concat", V("s"), ["itos", ["strlen", V("s")]]]),
    ("br-rot", "br_rotate", lambda s, x: s[x:] + s[:x], ["concat", ["drop", V("s"), V("x")], ["take", V("s"), V("x")]]),
    ("br-tail", "br_tail", lambda s, x: s[len(s) - x:], ["drop", V("s"), ["sub", ["strlen", V("s")], V("x")]]),
    ("br-chop", "br_chop", lambda s, x: s[:len(s) - x], ["take", V("s"), ["sub", ["strlen", V("s")], V("x")]]),
    ("br-num", "br_num_first", lambda s, x: str(x) + s, ["concat", ["itos", V("x")], V("s")]),
    ("br-headrep", "br_head_rep", lambda s, x: s[0] * x, ["srep", ["first", V("s")], V("x")]),
    ("br-rotup", "br_rot_up", lambda s, x: (s[x:] + s[:x]).upper(),
     ["upper", ["concat", ["drop", V("s"), V("x")], ["take", V("s"), V("x")]]]),
    ("br-rotrev", "br_rot_rev", lambda s, x: (s[x:] + s[:x])[::-1],
     ["srev", ["concat", ["drop", V("s"), V("x")], ["take", V("s"), V("x")]]]),
    ("br-uptake", "br_up_take", lambda s, x: s[:x].upper(), ["upper", ["take", V("s"), V("x")]]),
    ("br-sumlen", "br_sum_len", lambda s, x: str(len(s) + x), ["itos", ["add", ["strlen", V("s")], V("x")]]),
    ("br-digits", "br_digits", lambda s, x: len(str(len(s) * x)), ["strlen", ["itos", ["mul", ["strlen", V("s")], V("x")]]]),
)


def train_tasks() -> list[WorldTask]:
    """The bridge training tasks; every reference tree is checked against its truth on all rows."""
    out = []
    for tid, fam, fn, tree in _TRAIN_SPECS:
        t, tr = _train(tid, fam, fn, tree, "int" if fam == "br_digits" else "str")
        for rows in (t.public, t.challenge, t.final):
            for r, e in rows:
                assert run(tr, r) == e, (fam, r)
        out.append(t)
    return out


TRAIN_FAMILIES = tuple(f for _t, f, _fn, _tr in _TRAIN_SPECS)


def is_bridge(family: str | None) -> bool:
    return bool(family) and (family in BY_FAMILY or family in TRAIN_FAMILIES)
