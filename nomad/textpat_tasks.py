"""TEXT_ABSTRACT catalogues (docs/TEXTPAT.md): training shapes, and a sealed suite of new names.

Training families (inputs ``ua ub uk uj us ut``, separators "-" and ".") are only used
to grow a field's certified concat memory; they are never scored. The sealed catalogue
(inputs ``va vb vk vj vs vt``, separators "|" and "#") is written with the pre-registered
criteria, before any field arm is measured on it. Same construction as
``nomad.text_chain_tasks`` (word lists and case mixing, bridge opset, independent Python
ground truth, a row kept only when the reference tree reproduces it, 5 public / 3
challenge / 3 final rows). Names and separators are disjoint from every other catalogue.
None of the sealed families were chosen by outcome.
"""
from __future__ import annotations

import random

from . import text_invent_tasks as _XT
from .text import FIRST, TextFormula, V, WORDS, _case
from .world import WorldTask, make_task

DOMAIN = "bridge"
DOMAINS = ("bridge",)
N_PUBLIC, N_CHALLENGE, N_FINAL = 5, 3, 3

# ---- sealed generators (new names, new separators) ----
GEN = {
    "va": lambda rng: _case(rng, rng.choice(WORDS)),
    "vb": lambda rng: _case(rng, rng.choice(FIRST)),
    "vk": lambda rng: rng.randint(1, 3),
    "vj": lambda rng: rng.randint(0, 3),
    "vs": lambda rng: "|",
    "vt": lambda rng: "#",
}
TYPES = {"va": "str", "vb": "str", "vk": "int", "vj": "int", "vs": "str", "vt": "str"}

# ---- training generators (disjoint names and separators) ----
TRAIN_GEN = {
    "ua": lambda rng: _case(rng, rng.choice(WORDS)),
    "ub": lambda rng: _case(rng, rng.choice(FIRST)),
    "uk": lambda rng: rng.randint(1, 3),
    "uj": lambda rng: rng.randint(0, 3),
    "us": lambda rng: "-",
    "ut": lambda rng: ".",
}
TRAIN_TYPES = {"ua": "str", "ub": "str", "uk": "int", "uj": "int", "us": "str", "ut": "str"}
TRAIN_SEED = 17   # only draws training rows; not a sealed-suite seed


def _draw(f: TextFormula, rng: random.Random, gen, types) -> list[tuple[dict, object]]:
    old = _XT.GEN, _XT.TYPES
    _XT.GEN, _XT.TYPES = gen, types
    try:
        return _XT.draw_rows(f, rng)
    finally:
        _XT.GEN, _XT.TYPES = old


def draw_rows(f: TextFormula, rng: random.Random) -> list[tuple[dict, object]]:
    return _draw(f, rng, GEN, TYPES)


def draw_train_rows(f: TextFormula, rng: random.Random) -> list[tuple[dict, object]]:
    return _draw(f, rng, TRAIN_GEN, TRAIN_TYPES)


def to_task(entry: dict, types=None) -> WorldTask:
    types = types or TYPES
    rows = [(dict(r), e) for r, e in entry["rows"]]
    a, b = N_PUBLIC, N_PUBLIC + N_CHALLENGE
    return make_task(entry["task_id"], entry["family"], "bridge", {n: types[n] for n in entry["inputs"]},
                     entry["out"], rows[:a], rows[a:b], rows[b:], entry.get("level", 9))


def _f(family, kind, text, inputs, out, truth, tree):
    return TextFormula(family, f"bridge:{kind}", text, inputs, out, truth, tree)


cat = _XT.cat


def _rot(w, n):
    return w[n:] + w[:n]


# ===================================================================== sealed
a, b, k, j, s, t = (V(n) for n in ("va", "vb", "vk", "vj", "vs", "vt"))
L = lambda x: ["strlen", x]  # noqa: E731
take = lambda x, n: ["take", x, n]  # noqa: E731
drop = lambda x, n: ["drop", x, n]  # noqa: E731
tail = lambda x, n: ["drop", x, ["sub", L(x), n]]  # noqa: E731
rot = lambda x, n: cat(drop(x, n), take(x, n))  # noqa: E731
itos = lambda x: ["itos", x]  # noqa: E731

AK = ("va", "vk", "vs")
ABK = ("va", "vb", "vk", "vs")
ABKT = ("va", "vb", "vk", "vs", "vt")
AKJ = ("va", "vk", "vj", "vs")
ABKJ = ("va", "vb", "vk", "vj", "vs", "vt")

CATALOGUE: tuple[TextFormula, ...] = (
    # three-part labels / slices (template-shaped; new separators)
    _f("p_name_sep_word", "label", "name, separator, word", ABK, "str",
       lambda a_, b_, k_, s_: b_ + s_ + a_, cat(b, s, a)),
    _f("p_upper_name_sep_lower_word", "label", "name upper-case, separator, word lower-case", ABKT, "str",
       lambda a_, b_, k_, s_, t_: b_.upper() + t_ + a_.lower(), cat(["upper", b], t, ["lower", a])),
    _f("p_first_sep_len", "label", "initial, separator, length", AK, "str",
       lambda a_, k_, s_: a_[0] + s_ + str(len(a_)), cat(["first", a], s, itos(L(a)))),
    _f("p_last_sep_len", "label", "last letter, separator, length", AK, "str",
       lambda a_, k_, s_: a_[-1] + s_ + str(len(a_)), cat(["last", a], s, itos(L(a)))),
    _f("p_take_sep_drop", "slice", "first k letters, separator, the rest", AK, "str",
       lambda a_, k_, s_: a_[:k_] + s_ + a_[k_:], cat(take(a, k), s, drop(a, k))),
    _f("p_drop_sep_take", "slice", "all but the first k, separator, first k letters", AK, "str",
       lambda a_, k_, s_: a_[k_:] + s_ + a_[:k_], cat(drop(a, k), s, take(a, k))),
    _f("p_head_sep_tail", "slice", "first k letters, separator, last k letters", AK, "str",
       lambda a_, k_, s_: a_[:k_] + s_ + a_[len(a_) - k_:], cat(take(a, k), s, tail(a, k))),
    _f("p_rep_last_sep_name", "repeat", "last letter k times, separator, name", ABK, "str",
       lambda a_, b_, k_, s_: a_[-1] * k_ + s_ + b_, cat(["srep", ["last", a], k], s, b)),
    _f("p_len_sum_sep_word", "label", "length plus k, separator, word", AK, "str",
       lambda a_, k_, s_: str(len(a_) + k_) + s_ + a_, cat(itos(["add", L(a), k]), s, a)),
    _f("p_rot_sep_initial", "slice", "rotate by k, separator, initial", AK, "str",
       lambda a_, k_, s_: _rot(a_, k_) + s_ + a_[0], cat(rot(a, k), s, ["first", a])),
    _f("p_lower_initials_sep", "label", "both initials lower-case around a separator", ABK, "str",
       lambda a_, b_, k_, s_: a_[0].lower() + s_ + b_[0].lower(),
       cat(["lower", ["first", a]], s, ["lower", ["first", b]])),
    _f("p_frame_sep", "label", "separator, first k letters, separator", AK, "str",
       lambda a_, k_, s_: s_ + a_[:k_] + s_, cat(s, take(a, k), s)),
    # four and five parts
    _f("p_word_sep_name_sep2_k", "label", "word, separator, name, other separator, k", ABKT, "str",
       lambda a_, b_, k_, s_, t_: a_ + s_ + b_ + t_ + str(k_), cat(a, s, b, t, itos(k))),
    _f("p_name_sep_word_sep2_lens", "label", "name, separator, word, other separator, both lengths summed", ABKT, "str",
       lambda a_, b_, k_, s_, t_: b_ + s_ + a_ + t_ + str(len(a_) + len(b_)),
       cat(b, s, a, t, itos(["add", L(a), L(b)]))),
    _f("p_k_sep2_name_sep2", "label", "k, other separator, name, other separator", ABKT, "str",
       lambda a_, b_, k_, s_, t_: str(k_) + t_ + b_ + t_, cat(itos(k), t, b, t)),
    _f("p_up_head_sep_rest_sep_k", "slice", "first k upper-case, separator, the rest, separator, k", AK, "str",
       lambda a_, k_, s_: a_[:k_].upper() + s_ + a_[k_:] + s_ + str(k_),
       cat(["upper", take(a, k)], s, drop(a, k), s, itos(k))),
    _f("p_initials_len", "label", "both initials, separator, total length", ABK, "str",
       lambda a_, b_, k_, s_: a_[0] + b_[0] + s_ + str(len(a_) + len(b_)),
       cat(["first", a], ["first", b], s, itos(["add", L(a), L(b)]))),
    _f("p_last_first_sep2_name_upper", "label", "last and first letter, other separator, name upper-case", ABKT, "str",
       lambda a_, b_, k_, s_, t_: a_[-1] + a_[0] + t_ + b_.upper(),
       cat(["last", a], ["first", a], t, ["upper", b])),
    _f("p_take_take_mix", "slice", "first k of the word, then of the name, then of the word", ABK, "str",
       lambda a_, b_, k_, s_: a_[:k_] + b_[:k_] + a_[:k_] if k_ <= len(b_) else None,
       cat(take(a, k), take(b, k), take(a, k))),
    _f("p_rot_rot_sep2", "slice", "word rotated by k, other separator, name rotated by j", ABKJ, "str",
       lambda a_, b_, k_, j_, s_, t_: _rot(a_, k_) + t_ + _rot(b_, j_) if j_ <= len(b_) else None,
       cat(rot(a, k), t, rot(b, j))),
    # controls: two-part; top-level wrapper; integer outputs
    _f("p_word_then_k", "label", "word then k (two parts)", AK, "str",
       lambda a_, k_, s_: a_ + str(k_), cat(a, itos(k))),
    _f("p_lower_rot_ctrl", "slice", "rotate by k, lower-case (not a chain at the top)", AK, "str",
       lambda a_, k_, s_: _rot(a_, k_).lower(), ["lower", rot(a, k)]),
    _f("p_len_three_ctrl", "count", "length of word, separator, name (integer)", ABK, "int",
       lambda a_, b_, k_, s_: len(a_ + s_ + b_), L(cat(a, s, b))),
    _f("p_len_k_ctrl", "count", "k times the word's length plus the name's (integer)", ABK, "int",
       lambda a_, b_, k_, s_: k_ * len(a_) + len(b_), ["add", ["mul", k, L(a)], L(b)]),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}


# ===================================================================== training
ua, ub, uk, uj, us, ut = (V(n) for n in ("ua", "ub", "uk", "uj", "us", "ut"))
tL = lambda x: ["strlen", x]  # noqa: E731
ttake = lambda x, n: ["take", x, n]  # noqa: E731
tdrop = lambda x, n: ["drop", x, n]  # noqa: E731
ttail = lambda x, n: ["drop", x, ["sub", tL(x), n]]  # noqa: E731
trot = lambda x, n: cat(tdrop(x, n), ttake(x, n))  # noqa: E731
titos = lambda x: ["itos", x]  # noqa: E731

UAK = ("ua", "uk", "us")
UABK = ("ua", "ub", "uk", "us")
UABKT = ("ua", "ub", "uk", "us", "ut")
UAKJ = ("ua", "uk", "uj", "us")
UABKJ = ("ua", "ub", "uk", "uj", "us", "ut")

TRAIN_CATALOGUE: tuple[TextFormula, ...] = (
    _f("u_name_sep_word", "label", "name, separator, word", UABK, "str",
       lambda a_, b_, k_, s_: b_ + s_ + a_, cat(ub, us, ua)),
    _f("u_upper_name_sep_lower_word", "label", "name upper-case, separator, word lower-case", UABKT, "str",
       lambda a_, b_, k_, s_, t_: b_.upper() + t_ + a_.lower(), cat(["upper", ub], ut, ["lower", ua])),
    _f("u_first_sep_len", "label", "initial, separator, length", UAK, "str",
       lambda a_, k_, s_: a_[0] + s_ + str(len(a_)), cat(["first", ua], us, titos(tL(ua)))),
    _f("u_last_sep_len", "label", "last letter, separator, length", UAK, "str",
       lambda a_, k_, s_: a_[-1] + s_ + str(len(a_)), cat(["last", ua], us, titos(tL(ua)))),
    _f("u_take_sep_drop", "slice", "first k letters, separator, the rest", UAK, "str",
       lambda a_, k_, s_: a_[:k_] + s_ + a_[k_:], cat(ttake(ua, uk), us, tdrop(ua, uk))),
    _f("u_drop_sep_take", "slice", "all but the first k, separator, first k letters", UAK, "str",
       lambda a_, k_, s_: a_[k_:] + s_ + a_[:k_], cat(tdrop(ua, uk), us, ttake(ua, uk))),
    _f("u_head_sep_tail", "slice", "first k letters, separator, last k letters", UAK, "str",
       lambda a_, k_, s_: a_[:k_] + s_ + a_[len(a_) - k_:], cat(ttake(ua, uk), us, ttail(ua, uk))),
    _f("u_rep_last_sep_name", "repeat", "last letter k times, separator, name", UABK, "str",
       lambda a_, b_, k_, s_: a_[-1] * k_ + s_ + b_, cat(["srep", ["last", ua], uk], us, ub)),
    _f("u_len_sum_sep_word", "label", "length plus k, separator, word", UAK, "str",
       lambda a_, k_, s_: str(len(a_) + k_) + s_ + a_, cat(titos(["add", tL(ua), uk]), us, ua)),
    _f("u_rot_sep_initial", "slice", "rotate by k, separator, initial", UAK, "str",
       lambda a_, k_, s_: _rot(a_, k_) + s_ + a_[0], cat(trot(ua, uk), us, ["first", ua])),
    _f("u_lower_initials_sep", "label", "both initials lower-case around a separator", UABK, "str",
       lambda a_, b_, k_, s_: a_[0].lower() + s_ + b_[0].lower(),
       cat(["lower", ["first", ua]], us, ["lower", ["first", ub]])),
    _f("u_frame_sep", "label", "separator, first k letters, separator", UAK, "str",
       lambda a_, k_, s_: s_ + a_[:k_] + s_, cat(us, ttake(ua, uk), us)),
    _f("u_word_sep_name_sep2_k", "label", "word, separator, name, other separator, k", UABKT, "str",
       lambda a_, b_, k_, s_, t_: a_ + s_ + b_ + t_ + str(k_), cat(ua, us, ub, ut, titos(uk))),
    _f("u_name_sep_word_sep2_lens", "label", "name, separator, word, other separator, both lengths summed", UABKT, "str",
       lambda a_, b_, k_, s_, t_: b_ + s_ + a_ + t_ + str(len(a_) + len(b_)),
       cat(ub, us, ua, ut, titos(["add", tL(ua), tL(ub)]))),
    _f("u_k_sep2_name_sep2", "label", "k, other separator, name, other separator", UABKT, "str",
       lambda a_, b_, k_, s_, t_: str(k_) + t_ + b_ + t_, cat(titos(uk), ut, ub, ut)),
    _f("u_up_head_sep_rest_sep_k", "slice", "first k upper-case, separator, the rest, separator, k", UAK, "str",
       lambda a_, k_, s_: a_[:k_].upper() + s_ + a_[k_:] + s_ + str(k_),
       cat(["upper", ttake(ua, uk)], us, tdrop(ua, uk), us, titos(uk))),
    _f("u_initials_len", "label", "both initials, separator, total length", UABK, "str",
       lambda a_, b_, k_, s_: a_[0] + b_[0] + s_ + str(len(a_) + len(b_)),
       cat(["first", ua], ["first", ub], us, titos(["add", tL(ua), tL(ub)]))),
    _f("u_last_first_sep2_name_upper", "label", "last and first letter, other separator, name upper-case", UABKT, "str",
       lambda a_, b_, k_, s_, t_: a_[-1] + a_[0] + t_ + b_.upper(),
       cat(["last", ua], ["first", ua], ut, ["upper", ub])),
    _f("u_take_take_mix", "slice", "first k of the word, then of the name, then of the word", UABK, "str",
       lambda a_, b_, k_, s_: a_[:k_] + b_[:k_] + a_[:k_] if k_ <= len(b_) else None,
       cat(ttake(ua, uk), ttake(ub, uk), ttake(ua, uk))),
    _f("u_rot_rot_sep2", "slice", "word rotated by k, other separator, name rotated by j", UABKJ, "str",
       lambda a_, b_, k_, j_, s_, t_: _rot(a_, k_) + t_ + _rot(b_, j_) if j_ <= len(b_) else None,
       cat(trot(ua, uk), ut, trot(ub, uj))),
)


def train_tasks() -> list[WorldTask]:
    """Training tasks for the TEXT_ABSTRACT field arm (deterministic rows, not sealed)."""
    out = []
    for i, f in enumerate(TRAIN_CATALOGUE):
        rows = draw_train_rows(f, random.Random(f"{TRAIN_SEED}:{f.family}"))
        e = {"task_id": f"u-{i:02d}", "family": f.family, "domain": DOMAIN, "kind": f.kind.split(":", 1)[1],
             "formula": f.text, "inputs": list(f.inputs), "out": f.out, "tree": f.tree,
             "rows": [[r, a] for r, a in rows]}
        out.append(to_task(e, TRAIN_TYPES))
    return out
