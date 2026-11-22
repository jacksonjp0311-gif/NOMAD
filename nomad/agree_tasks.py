"""AGREE sealed catalogue (docs/AGREE.md): two-stage word problems plus ceiling and branch traps; new names.

Written, and committed with the pre-registered criteria, before any field arm is measured on it (only the
cold control is run by the generator). Domains no other catalogue uses (canal, saltworks, kiteworks);
named int inputs ``ga gb gc gd`` (disjoint from every catalogue); family prefix ``ag_``. Same construction
as ``nomad.discrim_tasks``: Fraction ground truth written independently of the reference tree (a row whose
answer is not a valid integer is skipped), 5 public / 3 challenge / 3 final rows.

Three groups, none chosen by outcome:

- plain two-stage computations (an intermediate t used twice: LET2's gains);
- ceilings ``ceil(t / k)`` (the LET2 / DISCRIM certification loss ``cl_h_rafts``: a let fit such as
  ``t // 2 - t // 3`` can equal ``ceil(t / 6)`` on every evidence row and be wrong elsewhere);
- comparisons and remainders whose branch the evidence may never exercise (input ranges overlap only
  partly: ``ga`` 1-30, ``gb`` ``gc`` 1-12, ``gd`` 1-9).

Two one-step controls.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("canal", "saltworks", "kiteworks")

G3 = ("ga", "gb", "gc")
G4 = ("ga", "gb", "gc", "gd")
R3 = {"ga": (1, 30), "gb": (1, 12), "gc": (1, 12)}
R4 = {"ga": (1, 30), "gb": (1, 12), "gc": (1, 12), "gd": (1, 9)}
NO = F(1, 2)     # not an integer: the row is skipped


def _f(family, domain, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:agree", text, inputs, ranges, truth, tree)


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


def ceil_div(a, k):
    return div(add(a, sub(k, C(1))), k)


def cl(n: int, k: int) -> int:
    return -(-n // k)


ga, gb, gc, gd = V("ga"), V("gb"), V("gc"), V("gd")
bc = mul(gb, gc)
ad = mul(ga, gd)
FOUR = mul(C(2), C(2))
FIVE = add(C(2), C(3))
SIX = mul(C(2), C(3))
EIGHT = mul(C(2), FOUR)
NINE = mul(C(3), C(3))

CATALOGUE: tuple[Formula, ...] = (
    # plain two-stage (an intermediate t used twice)
    _f("ag_lock_spare_third", "canal", "lock fills t = gb gc; t plus a third spare", G3, R3,
       lambda a, b, c: F(b * c + (b * c) // 3), add(bc, div(bc, C(3)))),
    _f("ag_barge_sq_less", "canal", "barge t = ga + gb; t squared minus gc", G3, R3,
       lambda a, b, c: F((a + b) ** 2 - c), sub(mul(add(ga, gb), add(ga, gb)), gc)),
    _f("ag_toll_two_rates", "canal", "boats t = gb + gc; tolls t ga + t gd", G4, R4,
       lambda a, b, c, d: F((b + c) * a + (b + c) * d), add(mul(add(gb, gc), ga), mul(add(gb, gc), gd))),
    _f("ag_pan_pairs", "saltworks", "pans t = gb + gd; pairs of pans t (t - 1) // 2", G4, R4,
       lambda a, b, c, d: F((b + d) * (b + d - 1) // 2), div(mul(add(gb, gd), sub(add(gb, gd), C(1))), C(2))),
    _f("ag_kite_triple_half", "kiteworks", "spars t = gb gc + ga; 3 t plus half of t", G3, R3,
       lambda a, b, c: F(3 * (b * c + a) + (b * c + a) // 2), add(mul(add(bc, ga), C(3)), div(add(bc, ga), C(2)))),
    _f("ag_brine_sq_plus", "saltworks", "t = gb + gd; t t + t", G4, R4,
       lambda a, b, c, d: F((b + d) ** 2 + (b + d)), add(mul(add(gb, gd), add(gb, gd)), add(gb, gd))),
    _f("ag_spool_sets_loose", "kiteworks", "string t = gb gc + ga; spools of 4 plus loose = t // 4 + t mod 4", G3, R3,
       lambda a, b, c: F((b * c + a) // 4 + (b * c + a) % 4), add(div(add(bc, ga), FOUR), mod(add(bc, ga), FOUR))),
    _f("ag_canal_gap", "canal", "t = gb gc; gap to depth ga = |t - ga|", G3, R3,
       lambda a, b, c: F(abs(b * c - a)), sub(mx(bc, ga), mn(bc, ga))),
    _f("ag_salt_bags_left", "saltworks", "salt t = gb gc; bags of gd plus salt left = t // gd + t mod gd", G4, R4,
       lambda a, b, c, d: F((b * c) // d + (b * c) % d), add(div(bc, gd), mod(bc, gd))),
    _f("ag_tail_double_less", "kiteworks", "tails t = ga + gb gc; 2 t minus a third of t", G3, R3,
       lambda a, b, c: F(2 * (a + b * c) - (a + b * c) // 3), sub(mul(add(ga, bc), C(2)), div(add(ga, bc), C(3)))),
    # ceilings ceil(t / k)
    _f("ag_crate_six", "saltworks", "crates of 6 for t = gb gc sacks = ceil(t / 6)", G3, R3,
       lambda a, b, c: F(cl(b * c, 6)), ceil_div(bc, SIX)),
    _f("ag_boat_four", "canal", "boats of 4 for t = ga + gb travelers = ceil(t / 4)", G3, R3,
       lambda a, b, c: F(cl(a + b, 4)), ceil_div(add(ga, gb), FOUR)),
    _f("ag_roll_five", "kiteworks", "rolls of 5 for t = gb gc panels = ceil(t / 5)", G3, R3,
       lambda a, b, c: F(cl(b * c, 5)), ceil_div(bc, FIVE)),
    _f("ag_trip_three", "canal", "trips of 3 for t = gb gc + gd loads = ceil(t / 3)", G4, R4,
       lambda a, b, c, d: F(cl(b * c + d, 3)), ceil_div(add(bc, gd), C(3))),
    _f("ag_bin_eight", "saltworks", "bins of 8 for t = gb gd + gc scoops = ceil(t / 8)", G4, R4,
       lambda a, b, c, d: F(cl(b * d + c, 8)), ceil_div(add(mul(gb, gd), gc), EIGHT)),
    _f("ag_span_nine", "kiteworks", "spans of 9 for t = ga gd cords = ceil(t / 9)", G4, R4,
       lambda a, b, c, d: F(cl(a * d, 9)), ceil_div(ad, NINE)),
    # comparisons / remainders whose branch the evidence may never exercise (traps)
    _f("ag_overflow", "canal", "inflow t = gb gc; overflow above ga = max(t - ga, 0)", G3, R3,
       lambda a, b, c: F(max(b * c - a, 0)), mx(sub(bc, ga), C(0))),
    _f("ag_cap_load", "saltworks", "t = gb gc capped at ga, times gd", G4, R4,
       lambda a, b, c, d: F(min(b * c, a) * d), mul(mn(bc, ga), gd)),
    _f("ag_over_line", "kiteworks", "t = ga gd; over the line gb gc = max(t, gb gc) - gb gc", G4, R4,
       lambda a, b, c, d: F(max(a * d, b * c) - b * c), sub(mx(ad, bc), bc)),
    _f("ag_pairs_and_odd", "kiteworks", "t = ga + gb; pairs of gd: 2 (t // gd) + t mod gd", G4, R4,
       lambda a, b, c, d: F(2 * ((a + b) // d) + (a + b) % d), add(mul(div(add(ga, gb), gd), C(2)), mod(add(ga, gb), gd))),
    _f("ag_least_plus", "canal", "t = gb gc; min(t, ga gd) + t", G4, R4,
       lambda a, b, c, d: F(min(b * c, a * d) + b * c), add(mn(bc, ad), bc)),
    _f("ag_spill_mod", "saltworks", "t = ga gd; spill t mod gc, plus gb", G4, R4,
       lambda a, b, c, d: F((a * d) % c + b), add(mod(ad, gc), gb)),
    # controls: one step (no intermediate reused)
    _f("ag_ctl_one_step", "canal", "control: gb gc + ga", G3, R3,
       lambda a, b, c: F(b * c + a), add(bc, ga)),
    _f("ag_ctl_one_step2", "kiteworks", "control: ga + gb gc - gc", G3, R3,
       lambda a, b, c: F(a + b * c - c), sub(add(ga, bc), gc)),
)
