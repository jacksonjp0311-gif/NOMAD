"""CERT sealed catalogue (docs/CERT.md): arithmetic-edge tasks whose evidence can be matched by a lucky wrong fit.

Written, and committed with the pre-registered criteria, before any field arm is measured on it (only the cold
control is run by the generator). Domains no other catalogue uses (loom, quay, bakery); named int inputs
``ka kb kc`` and a stated constant column ``kt`` (disjoint from every catalogue); family prefix ``ce_``.
Same construction as ``nomad.agree_tasks``: Fraction ground truth written independently of the reference tree
(a row whose answer is not an integer the tree reproduces is skipped), 5 public / 3 challenge / 3 final rows.

Four groups, none chosen by outcome:

- ``round``: rounding to the nearest unit / ceiling to a unit (the NOVEL ``nv_d_round10`` failure mode: a
  ceiling or a shifted floor equals the rounding on every residue the evidence happens to show);
- ``carry``: carries and digit arithmetic (residues that wrap);
- ``edge``: zero floors, clamps and absolute differences (a branch the evidence may never exercise);
- ``stage``: two-stage computations with an intermediate used twice (LET2's gains) and ceilings of them.

Ten of the 26 formulas take the constant column ``kt`` (its value is the stated unit), the rest are plain.
``build`` parameterizes names and constants so an uncommitted dev catalogue (other names, other units) can be
built from the same shapes; the sealed one is ``CATALOGUE``.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("loom", "quay", "bakery")
NO = F(1, 2)     # not an integer: the row is skipped


def add(a, b):
    return ["add", a, b]


def sub(a, b):
    return ["sub", a, b]


def mul(a, b):
    return ["mul", a, b]


def div(a, b):
    return ["div", a, b]


def mod(a, b):
    return ["mod", a, b]


def mx(a, b):
    return ["max", a, b]


def mn(a, b):
    return ["min", a, b]


def build(prefix: str, names: tuple[str, str, str, str], units: dict, domains: tuple[str, str, str]) -> tuple[Formula, ...]:
    """The catalogue on input names (a, b, c, t) with units: ``u`` (round/ceil unit, column t), ``w`` (wrap
    modulus, a plain constant tree), ``k`` (ceiling divisor for staged tasks)."""
    na, nb, nc, nt = names
    a, b, c, t = V(na), V(nb), V(nc), V(nt)
    u, w, k = units["u"], units["w"], units["k"]
    d1, d2, d3 = domains
    ru = {na: (units["lo"], units["hi"]), nt: ("const", u)}
    r2 = {na: (1, 60), nb: (1, 60)}
    r3 = {na: (1, 40), nb: (1, 30), nc: (1, 12)}
    rc = {na: (0, 40), nb: (0, 14), nc: (15, 40)}
    wt = {na: (0, 60), nb: (0, 60), nt: ("const", w)}
    ceil_ = lambda x, n: -(-x // n)  # noqa: E731

    def _f(name, dom, text, inputs, ranges, truth, tree):
        return Formula(f"{prefix}{name}", f"{dom}:cert", text, inputs, ranges, truth, tree)

    half = div(t, C(2))
    ceil_k = lambda x: div(add(x, sub(C(k), C(1))), C(k))  # noqa: E731
    kk = C(k) if k <= 3 else add(C(k - 3), C(3))
    ceil_kk = lambda x: div(add(x, sub(kk, C(1))), kk)  # noqa: E731
    bc = mul(b, c)
    return (
        # round: nearest / ceiling to the unit u (column t)
        _f("round_near", d1, f"{na} rounded to the nearest {u} (halves up)", (na, nt), ru,
           lambda x, tt: F(((x + tt // 2) // tt) * tt), mul(div(add(a, half), t), t)),
        _f("round_ceil", d1, f"{na} rounded up to a multiple of {u}", (na, nt), ru,
           lambda x, tt: F(ceil_(x, tt) * tt), mul(div(add(a, sub(t, C(1))), t), t)),
        _f("round_floor_gap", d1, f"{na} minus its rounding down to a multiple of {u}", (na, nt), ru,
           lambda x, tt: F(x % tt), mod(a, t)),
        _f("round_near_err", d1, f"distance from {na} to the nearest multiple of {u} (halves up)", (na, nt), ru,
           lambda x, tt: F(abs(x - ((x + tt // 2) // tt) * tt)),
           sub(mx(a, mul(div(add(a, half), t), t)), mn(a, mul(div(add(a, half), t), t)))),
        _f("round_half_down", d1, f"{na} rounded to the nearest {u} (halves down)", (na, nt), ru,
           lambda x, tt: F(((x + (tt - 1) // 2) // tt) * tt),
           mul(div(add(a, div(sub(t, C(1)), C(2))), t), t)),
        _f("round_pair", d1, f"sum of {na} and {nb} rounded to the nearest {u}", (na, nb, nt),
           {na: (units["lo"], units["hi"]), nb: (units["lo"], units["hi"]), nt: ("const", u)},
           lambda x, y, tt: F(((x + y + tt // 2) // tt) * tt), mul(div(add(add(a, b), half), t), t)),
        # carry: wraps and digits
        _f("carry_units", d2, f"carry out of the units digits of {na} and {nb} (base {w})", (na, nb, nt), wt,
           lambda x, y, tt: F((x % tt + y % tt) // tt), div(add(mod(a, t), mod(b, t)), t)),
        _f("wrap_diff", d2, f"({na} - {nb}) wrapped into 0..{w - 1}", (na, nb, nt), wt,
           lambda x, y, tt: F((x - y) % tt), mod(add(a, sub(t, mod(b, t))), t)),
        _f("wrap_sum", d2, f"({na} + {nb}) wrapped into 0..{w - 1}", (na, nb, nt), wt,
           lambda x, y, tt: F((x + y) % tt), mod(add(a, b), t)),
        _f("digit_pair_sum", d2, f"quotient plus remainder of {na} by {w}", (na, nt), {na: (1, 99), nt: ("const", w)},
           lambda x, tt: F(x // tt + x % tt), add(div(a, t), mod(a, t))),
        _f("carry_total", d2, f"sum of both units digits of {na}, {nb} and the carry", (na, nb, nt), wt,
           lambda x, y, tt: F(x % tt + y % tt + (x % tt + y % tt) // tt),
           add(add(mod(a, t), mod(b, t)), div(add(mod(a, t), mod(b, t)), t))),
        _f("tens_gap", d2, f"{na} minus the units digit of {nb} (base {w})", (na, nb, nt), wt,
           lambda x, y, tt: F(x - y % tt) if x - y % tt >= 0 else NO, sub(a, mod(b, t))),
        # edge: floors, clamps, absolute differences
        _f("floor_zero", d3, f"{na} - {nb} floored at zero", (na, nb), r2,
           lambda x, y: F(max(x - y, 0)), mx(sub(a, b), C(0))),
        _f("clamp", d3, f"{na} clamped between {nb} and {nc}", (na, nb, nc), rc,
           lambda x, y, z: F(max(y, min(x, z))), mx(b, mn(a, c))),
        _f("absdiff", d3, f"|{na} - {nb}|", (na, nb), r2,
           lambda x, y: F(abs(x - y)), sub(mx(a, b), mn(a, b))),
        _f("absdiff_plus", d3, f"|{na} - {nb}| + {nc}", (na, nb, nc), r3,
           lambda x, y, z: F(abs(x - y) + z), add(sub(mx(a, b), mn(a, b)), c)),
        _f("spread3", d3, f"largest minus smallest of {na}, {nb}, {nc}", (na, nb, nc), r3,
           lambda x, y, z: F(max(x, y, z) - min(x, y, z)), sub(mx(a, mx(b, c)), mn(a, mn(b, c)))),
        _f("over_cap", d3, f"{na} over a cap of {nb} {nc}", (na, nb, nc), r3,
           lambda x, y, z: F(max(x - y * z, 0)), mx(sub(a, bc), C(0))),
        # stage: an intermediate used twice, ceilings of it
        _f("stage_sum_half", d1, f"s = {na} + {nb} {nc}; s plus half of s", (na, nb, nc), r3,
           lambda x, y, z: F((x + y * z) + (x + y * z) // 2), add(add(a, bc), div(add(a, bc), C(2)))),
        _f("stage_div_rem", d2, f"s = {na} + {nb}; s // {k} + s mod {k}", (na, nb), r2,
           lambda x, y: F((x + y) // k + (x + y) % k), add(div(add(a, b), kk), mod(add(a, b), kk))),
        _f("stage_ceil", d3, f"s = {na} {nb}; ceil(s / {k})", (na, nb, nc), r3,
           lambda x, y, z: F(ceil_(x * y, k)), ceil_kk(mul(a, b))),
        _f("stage_ceil_sum", d1, f"s = {na} + {nb}; ceil(s / {k})", (na, nb), r2,
           lambda x, y: F(ceil_(x + y, k)), ceil_kk(add(a, b))),
        _f("stage_min_pair", d2, f"s = {na} {nb}; min(s, {nc}) + s", (na, nb, nc), r3,
           lambda x, y, z: F(min(x * y, z) + x * y), add(mn(mul(a, b), c), mul(a, b))),
        _f("stage_cap_twice", d3, f"s = {na} + {nb}; min(s, {nc}) times s mod {w}", (na, nb, nc), r3,
           lambda x, y, z: F(min(x + y, z) * ((x + y) % w)), mul(mn(add(a, b), c), mod(add(a, b), C(w) if w <= 3 else add(C(w - 3), C(3))))),
        # controls: one step
        _f("ctl_one_step", d1, f"control: {na} + {nb} {nc}", (na, nb, nc), r3,
           lambda x, y, z: F(x + y * z), add(a, bc)),
        _f("ctl_one_step2", d2, f"control: {na} {nb} - {nc}", (na, nb, nc), r3,
           lambda x, y, z: F(x * y - z), sub(mul(a, b), c)),
    )


CATALOGUE: tuple[Formula, ...] = build("ce_", ("ka", "kb", "kc", "kt"),
                                       {"u": 10, "w": 7, "k": 5, "lo": 100, "hi": 999}, DOMAINS)
BY_FAMILY = {f.family: f for f in CATALOGUE}
