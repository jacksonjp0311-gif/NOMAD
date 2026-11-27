"""DISTIN sealed catalogue (docs/DISTIN.md): two-stage word problems plus ceiling, rounding and
floor-division traps; new names.

Written, and committed with the pre-registered criteria, before any field arm is measured on it (only the
cold control is run by the generator). Domains no other catalogue uses (orchard, foundry, apiary); named
int inputs ``fa fb fc fd`` (disjoint from every catalogue); family prefix ``ds_``. Same construction as
``nomad.agree_tasks``: Fraction ground truth written independently of the reference tree (a row whose
answer is not a valid integer is skipped), 5 public / 3 challenge / 3 final rows.

Five groups, none chosen by outcome:

- plain two-stage computations (an intermediate t used twice: LET2's gains);
- ceilings ``ceil(t / k)`` (the ``cl_h_rafts`` failure mode);
- rounding t to the nearest k, halves up (the NOVEL ``nv_d_round10`` failure mode);
- floor-division placement: a quotient of a product (pairs ``t (t - 1) / 2``, quarters of a product),
  where ``(t - 1) * (t // 2)`` equals the truth whenever t happens to be even;
- comparisons and remainders whose branch the evidence may never exercise.

Two one-step controls. Ranges: ``fa`` 1-40, ``fb`` ``fc`` 1-12, ``fd`` 1-9.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("orchard", "foundry", "apiary")

G3 = ("fa", "fb", "fc")
G4 = ("fa", "fb", "fc", "fd")
R3 = {"fa": (1, 40), "fb": (1, 12), "fc": (1, 12)}
R4 = {"fa": (1, 40), "fb": (1, 12), "fc": (1, 12), "fd": (1, 9)}


def _f(family, domain, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:distin", text, inputs, ranges, truth, tree)


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


def round_to(a, k):
    """nearest multiple of k, halves up: (a + k // 2) // k * k (k even) or (a + (k - 1) // 2) // k * k."""
    return mul(div(add(a, div(k, C(2))), k), k)


def cl(n: int, k: int) -> int:
    return -(-n // k)


def rnd(n: int, k: int) -> int:
    return int((F(n, k) + F(1, 2)) // 1) * k


fa, fb, fc, fd = V("fa"), V("fb"), V("fc"), V("fd")
bc = mul(fb, fc)
ad = mul(fa, fd)
FOUR = mul(C(2), C(2))
FIVE = add(C(2), C(3))
SIX = mul(C(2), C(3))
SEVEN = add(FOUR, C(3))
TEN = mul(C(2), FIVE)

CATALOGUE: tuple[Formula, ...] = (
    # plain two-stage (an intermediate t used twice)
    _f("ds_row_spare_half", "orchard", "trees t = fb fc; t plus half of t spare", G3, R3,
       lambda a, b, c: F(b * c + (b * c) // 2), add(bc, div(bc, C(2)))),
    _f("ds_crate_sq_less", "orchard", "crates t = fa + fb; t squared minus fc", G3, R3,
       lambda a, b, c: F((a + b) ** 2 - c), sub(mul(add(fa, fb), add(fa, fb)), fc)),
    _f("ds_cast_two_rates", "foundry", "casts t = fb + fc; t fa + t fd", G4, R4,
       lambda a, b, c, d: F((b + c) * a + (b + c) * d), add(mul(add(fb, fc), fa), mul(add(fb, fc), fd))),
    _f("ds_hive_twice_less_third", "apiary", "frames t = fb fc + fa; 2 t minus a third of t", G3, R3,
       lambda a, b, c: F(2 * (b * c + a) - (b * c + a) // 3), sub(mul(add(bc, fa), C(2)), div(add(bc, fa), C(3)))),
    _f("ds_ingot_sets_loose", "foundry", "ingots t = fb fc + fa; sets of 5 plus loose = t // 5 + t mod 5", G3, R3,
       lambda a, b, c: F((b * c + a) // 5 + (b * c + a) % 5), add(div(add(bc, fa), FIVE), mod(add(bc, fa), FIVE))),
    _f("ds_comb_sq_plus", "apiary", "t = fb + fd; t t + t", G4, R4,
       lambda a, b, c, d: F((b + d) ** 2 + (b + d)), add(mul(add(fb, fd), add(fb, fd)), add(fb, fd))),
    _f("ds_orchard_gap", "orchard", "t = fb fc; gap to the quota fa = |t - fa|", G3, R3,
       lambda a, b, c: F(abs(b * c - a)), sub(mx(bc, fa), mn(bc, fa))),
    _f("ds_mold_bags_left", "foundry", "sand t = fb fc; molds of fd plus sand left = t // fd + t mod fd", G4, R4,
       lambda a, b, c, d: F((b * c) // d + (b * c) % d), add(div(bc, fd), mod(bc, fd))),
    # ceilings ceil(t / k)
    _f("ds_box_six", "orchard", "boxes of 6 for t = fb fc apples = ceil(t / 6)", G3, R3,
       lambda a, b, c: F(cl(b * c, 6)), ceil_div(bc, SIX)),
    _f("ds_cart_four", "foundry", "carts of 4 for t = fa + fb bars = ceil(t / 4)", G3, R3,
       lambda a, b, c: F(cl(a + b, 4)), ceil_div(add(fa, fb), FOUR)),
    _f("ds_jar_five", "apiary", "jars of 5 for t = fb fc pours = ceil(t / 5)", G3, R3,
       lambda a, b, c: F(cl(b * c, 5)), ceil_div(bc, FIVE)),
    _f("ds_trip_seven", "orchard", "trips of 7 for t = fb fc + fd bins = ceil(t / 7)", G4, R4,
       lambda a, b, c, d: F(cl(b * c + d, 7)), ceil_div(add(bc, fd), SEVEN)),
    # rounding t to the nearest k (halves up)
    _f("ds_round_ten", "foundry", "t = fb fc + fa kilograms rounded to the nearest ten", G3, R3,
       lambda a, b, c: F(rnd(b * c + a, 10)), round_to(add(bc, fa), TEN)),
    _f("ds_round_four", "apiary", "t = fa fd grams rounded to the nearest four", G4, R4,
       lambda a, b, c, d: F(rnd(a * d, 4)), round_to(ad, FOUR)),
    _f("ds_round_six", "orchard", "t = fb fc + fd rounded to the nearest six", G4, R4,
       lambda a, b, c, d: F(rnd(b * c + d, 6)), round_to(add(bc, fd), SIX)),
    # floor-division placement
    _f("ds_hive_pairs", "apiary", "bees t = fb + fd; pairs among them t (t - 1) / 2", G4, R4,
       lambda a, b, c, d: F((b + d) * (b + d - 1) // 2), div(mul(add(fb, fd), sub(add(fb, fd), C(1))), C(2))),
    _f("ds_tree_pairs", "orchard", "trees t = fb fc; pairs t (t - 1) / 2", G3, R3,
       lambda a, b, c: F((b * c) * (b * c - 1) // 2), div(mul(bc, sub(bc, C(1))), C(2))),
    _f("ds_quarter_load", "foundry", "load t = fb fc; a quarter of t times fd, whole units", G4, R4,
       lambda a, b, c, d: F((b * c * d) // 4), div(mul(bc, fd), FOUR)),
    _f("ds_steps_sum", "apiary", "cells t = fb + fc; 1 + 2 + .. + t = t (t + 1) / 2", G3, R3,
       lambda a, b, c: F((b + c) * (b + c + 1) // 2), div(mul(add(fb, fc), add(add(fb, fc), C(1))), C(2))),
    # comparisons / remainders whose branch the evidence may never exercise (traps)
    _f("ds_overflow", "orchard", "harvest t = fb fc; overflow above fa = max(t - fa, 0)", G3, R3,
       lambda a, b, c: F(max(b * c - a, 0)), mx(sub(bc, fa), C(0))),
    _f("ds_cap_load", "foundry", "t = fb fc capped at fa, times fd", G4, R4,
       lambda a, b, c, d: F(min(b * c, a) * d), mul(mn(bc, fa), fd)),
    _f("ds_spill_mod", "apiary", "t = fa fd; spill t mod fc, plus fb", G4, R4,
       lambda a, b, c, d: F((a * d) % c + b), add(mod(ad, fc), fb)),
    # controls: one step (no intermediate reused)
    _f("ds_ctl_one_step", "orchard", "control: fb fc + fa", G3, R3,
       lambda a, b, c: F(b * c + a), add(bc, fa)),
    _f("ds_ctl_one_step2", "apiary", "control: fa + fb fc - fc", G3, R3,
       lambda a, b, c: F(a + b * c - c), sub(add(fa, bc), fc)),
)
