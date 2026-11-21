"""LET sealed catalogue (docs/LET.md): two-stage everyday word problems, new names.

Written, and committed with the pre-registered criteria, before any field arm is measured on it.
Every formula first computes an intermediate result ``t`` (a head count, an amount, a total) and
then uses it again -- once more inside a second step (``t + t // 3``, ``t (t - 1) // 2``,
``|t - xc|``, ``t // 4 + t mod 4``) or as the input of a second calculation (money left, then items
it buys). Same construction as ``nomad.selfedit_tasks`` / ``nomad.transfer4``: named int inputs
``xa xb xc xd`` (disjoint from every catalogue), Fraction ground truth written independently of the
reference tree (a row whose answer is not a valid integer is skipped), 5 public / 3 challenge / 3
final rows. Two controls (one-step formulas). None chosen by outcome.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("farm", "school", "kitchen")

X3 = ("xa", "xb", "xc")
X4 = ("xa", "xb", "xc", "xd")
R3 = {"xa": (1, 12), "xb": (1, 12), "xc": (1, 30)}
R4 = {"xa": (1, 12), "xb": (1, 12), "xc": (1, 30), "xd": (1, 9)}
NO = F(1, 2)     # not an integer: the row is skipped


def _f(family, domain, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:chain", text, inputs, ranges, truth, tree)


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


xa, xb, xc, xd = V("xa"), V("xb"), V("xc"), V("xd")
FOUR = add(C(2), C(2))
ab = mul(xa, xb)

CATALOGUE: tuple[Formula, ...] = (
    _f("l_feed_third_more", "farm", "sheep t = xa pens x xb; feed = t + t // 3", X3, R3,
       lambda a, b, c: F(a * b + (a * b) // 3), add(ab, div(ab, C(3)))),
    _f("l_class_pairs", "school", "students t = xa rows x xb; pairs among them = t (t - 1) // 2", X3, R3,
       lambda a, b, c: F(a * b * (a * b - 1) // 2), div(mul(ab, sub(ab, C(1))), C(2))),
    _f("l_gap_to_goal", "school", "points t = xa x xb; distance to the goal xc = |t - xc|", X3, R3,
       lambda a, b, c: F(abs(a * b - c)), sub(mx(ab, xc), mn(ab, xc))),
    _f("l_items_after_buy", "kitchen", "money left t = xc xd - xa xb; then items at price xb = t // xb", X4, R4,
       lambda a, b, c, d: F((c * d - a * b) // b) if c * d >= a * b else NO, div(sub(mul(xc, xd), ab), xb)),
    _f("l_square_of_total", "farm", "animals t = xa + xb; t squared minus xc sold", X3, R3,
       lambda a, b, c: F((a + b) ** 2 - c), sub(mul(add(xa, xb), add(xa, xb)), xc)),
    _f("l_double_and_half", "kitchen", "eggs t = xa xb + xc; twice t plus half of t", X3, R3,
       lambda a, b, c: F(2 * (a * b + c) + (a * b + c) // 2),
       add(mul(add(ab, xc), C(2)), div(add(ab, xc), C(2)))),
    _f("l_boxes_and_loose", "kitchen", "cookies t = xa xb + xc; boxes of 4 plus loose = t // 4 + t mod 4", X3, R3,
       lambda a, b, c: F((a * b + c) // 4 + (a * b + c) % 4), add(div(add(ab, xc), FOUR), mod(add(ab, xc), FOUR))),
    _f("l_trip_two_legs", "school", "pupils t = xa + xb; cost t xc + t xd", X4, R4,
       lambda a, b, c, d: F((a + b) * c + (a + b) * d), add(mul(add(xa, xb), xc), mul(add(xa, xb), xd))),
    _f("l_tiles_minus_rug", "farm", "t = xa xb; t squared minus t xc", X3, R3,
       lambda a, b, c: F((a * b) ** 2 - a * b * c), sub(mul(ab, ab), mul(ab, xc))),
    _f("l_cap_plus_t", "farm", "milk t = xa xc; min(t, xb xd) + t", X4, R4,
       lambda a, b, c, d: F(min(a * c, b * d) + a * c), add(mn(mul(xa, xc), mul(xb, xd)), mul(xa, xc))),
    _f("l_thirds_and_rest", "school", "t = xa + xb + xc; t // 3 + t mod 3", X3, R3,
       lambda a, b, c: F((a + b + c) // 3 + (a + b + c) % 3),
       add(div(add(add(xa, xb), xc), C(3)), mod(add(add(xa, xb), xc), C(3)))),
    _f("l_diff_sq_plus", "school", "lead t = xa - xb; t t + t", X3, R3,
       lambda a, b, c: F((a - b) ** 2 + (a - b)), add(mul(sub(xa, xb), sub(xa, xb)), sub(xa, xb))),
    _f("l_overflow_half", "kitchen", "t = xa xb; overflow over xc plus half of t", X3, R3,
       lambda a, b, c: F(max(a * b - c, 0) + (a * b) // 2), add(mx(sub(ab, xc), C(0)), div(ab, C(2)))),
    _f("l_border_tiles", "farm", "half perimeter t = xa + xb; border 2 t + 4", X3, R3,
       lambda a, b, c: F(2 * (a + b) + 4), add(mul(add(xa, xb), C(2)), FOUR)),
    _f("l_square_times", "farm", "t = xa + xc; t t xb", X3, R3,
       lambda a, b, c: F((a + c) ** 2 * b), mul(mul(add(xa, xc), add(xa, xc)), xb)),
    _f("l_crates_and_rest", "kitchen", "t = xa xb xc; full crates of xd plus the rest = t // xd + t mod xd", X4, R4,
       lambda a, b, c, d: F((a * b * c) // d + (a * b * c) % d),
       add(div(mul(ab, xc), xd), mod(mul(ab, xc), xd))),
    _f("l_mean_pay", "school", "t = xa xc; mean of t and xb xc = (t + xb xc) // 2", X3, R3,
       lambda a, b, c: F((a * c + b * c) // 2), div(add(mul(xa, xc), mul(xb, xc)), C(2))),
    _f("l_extra_needed", "farm", "t = xa xc; max(t, xb xd) - t", X4, R4,
       lambda a, b, c, d: F(max(a * c, b * d) - a * c), sub(mx(mul(xa, xc), mul(xb, xd)), mul(xa, xc))),
    _f("l_triangle_total", "school", "t = xa + xb; 1 + 2 + ... + t = t (t + 1) // 2", X3, R3,
       lambda a, b, c: F((a + b) * (a + b + 1) // 2), div(mul(add(xa, xb), add(add(xa, xb), C(1))), C(2))),
    _f("l_rounds_needed", "kitchen", "t = xa xb; trays of xd needed = ceil(t / xd)", X4, R4,
       lambda a, b, c, d: F(-(-(a * b) // d)), div(add(ab, sub(xd, C(1))), xd)),
    _f("l_leftover_jars", "kitchen", "t = xa xb; jars left when xc xd are packed t at a time = (xc xd) mod t", X4, R4,
       lambda a, b, c, d: F((c * d) % (a * b)), mod(mul(xc, xd), ab)),
    _f("l_t_plus_quarter", "farm", "t = xa xb + xc; t + t // 4", X3, R3,
       lambda a, b, c: F(a * b + c + (a * b + c) // 4), add(add(ab, xc), div(add(ab, xc), FOUR))),
    # controls: one step (no intermediate reused)
    _f("l_ctl_one_step", "farm", "control: xa xb + xc", X3, R3,
       lambda a, b, c: F(a * b + c), add(ab, xc)),
    _f("l_ctl_one_step2", "school", "control: xa + xb xc", X3, R3,
       lambda a, b, c: F(a + b * c), add(xa, mul(xb, xc))),
)
