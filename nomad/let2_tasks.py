"""LET2 sealed catalogue (docs/LET2.md): two-stage everyday word problems, new names, new inputs.

Written, and committed with the pre-registered criteria, before any arm is measured on it (only the
cold control is run by the generator). Every formula first computes an intermediate ``t`` and uses it
again (inside a second step, or as the input of a second calculation). Same construction as
``nomad.let_tasks``: named int inputs ``hu hv hw hx`` (disjoint from every catalogue), Fraction
ground truth written independently of the reference tree (a row whose answer is not a valid integer
is skipped), 5 public / 3 challenge / 3 final rows. Two one-step controls. None chosen by outcome.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("garden", "workshop", "market")

H3 = ("hu", "hv", "hw")
H4 = ("hu", "hv", "hw", "hx")
R3 = {"hu": (1, 12), "hv": (1, 12), "hw": (1, 30)}
R4 = {"hu": (1, 12), "hv": (1, 12), "hw": (1, 30), "hx": (1, 9)}
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


hu, hv, hw, hx = V("hu"), V("hv"), V("hw"), V("hx")
FIVE = add(C(2), C(3))
uv = mul(hu, hv)
upv = add(hu, hv)

CATALOGUE: tuple[Formula, ...] = (
    _f("k2_seedlings_spare", "garden", "seedlings t = hu trays x hv; plant t plus a fifth spare = t + t // 5", H3, R3,
       lambda a, b, c: F(a * b + (a * b) // 5), add(uv, div(uv, FIVE))),
    _f("k2_handshakes_crew", "workshop", "crew t = hu + hv; handshakes t (t - 1) // 2", H3, R3,
       lambda a, b, c: F((a + b) * (a + b - 1) // 2), div(mul(upv, sub(upv, C(1))), C(2))),
    _f("k2_off_target", "market", "sales t = hu x hv; distance from target hw = |t - hw|", H3, R3,
       lambda a, b, c: F(abs(a * b - c)), sub(mx(uv, hw), mn(uv, hw))),
    _f("k2_change_then_bags", "market", "change t = hw hx - hu hv; bags at price hu = t // hu", H4, R4,
       lambda a, b, c, d: F((c * d - a * b) // a) if c * d >= a * b else NO, div(sub(mul(hw, hx), uv), hu)),
    _f("k2_plot_sq_less", "garden", "side t = hu + hw; plot t squared minus hv paved", H3, R3,
       lambda a, b, c: F((a + c) ** 2 - b), sub(mul(add(hu, hw), add(hu, hw)), hv)),
    _f("k2_triple_and_third", "workshop", "bolts t = hu hv + hw; three t plus a third of t", H3, R3,
       lambda a, b, c: F(3 * (a * b + c) + (a * b + c) // 3),
       add(mul(add(uv, hw), C(3)), div(add(uv, hw), C(3)))),
    _f("k2_packs_and_loose", "market", "apples t = hu hv + hw; packs of 5 plus loose = t // 5 + t mod 5", H3, R3,
       lambda a, b, c: F((a * b + c) // 5 + (a * b + c) % 5), add(div(add(uv, hw), FIVE), mod(add(uv, hw), FIVE))),
    _f("k2_two_rates", "workshop", "hours t = hu + hv; pay t hw + t hx", H4, R4,
       lambda a, b, c, d: F((a + b) * c + (a + b) * d), add(mul(upv, hw), mul(upv, hx))),
    _f("k2_area_minus_strip", "garden", "t = hu hv; t squared minus t hw", H3, R3,
       lambda a, b, c: F((a * b) ** 2 - a * b * c), sub(mul(uv, uv), mul(uv, hw))),
    _f("k2_least_plus_t", "market", "stock t = hv hw; min(t, hu hx) + t", H4, R4,
       lambda a, b, c, d: F(min(b * c, a * d) + b * c), add(mn(mul(hv, hw), mul(hu, hx)), mul(hv, hw))),
    _f("k2_quarters_and_rest", "workshop", "t = hu + hv + hw; t // 4 + t mod 4", H3, R3,
       lambda a, b, c: F((a + b + c) // 4 + (a + b + c) % 4),
       add(div(add(upv, hw), add(C(2), C(2))), mod(add(upv, hw), add(C(2), C(2))))),
    _f("k2_margin_sq_minus", "market", "margin t = hw - hu; t t - t", H3, R3,
       lambda a, b, c: F((c - a) ** 2 - (c - a)), sub(mul(sub(hw, hu), sub(hw, hu)), sub(hw, hu))),
    _f("k2_spill_and_third", "garden", "t = hu hv; spill over hw plus a third of t", H3, R3,
       lambda a, b, c: F(max(a * b - c, 0) + (a * b) // 3), add(mx(sub(uv, hw), C(0)), div(uv, C(3)))),
    _f("k2_fence_posts", "garden", "half perimeter t = hu + hw; posts 2 t + 2", H3, R3,
       lambda a, b, c: F(2 * (a + c) + 2), add(mul(add(hu, hw), C(2)), C(2))),
    _f("k2_cube_side_area", "workshop", "t = hv + hw; t t hu", H3, R3,
       lambda a, b, c: F((b + c) ** 2 * a), mul(mul(add(hv, hw), add(hv, hw)), hu)),
    _f("k2_boxes_of_hx", "market", "t = hu hv hw; full boxes of hx plus the rest = t // hx + t mod hx", H4, R4,
       lambda a, b, c, d: F((a * b * c) // d + (a * b * c) % d),
       add(div(mul(uv, hw), hx), mod(mul(uv, hw), hx))),
    _f("k2_avg_wage", "workshop", "t = hu hw; mean of t and hv hw = (t + hv hw) // 2", H3, R3,
       lambda a, b, c: F((a * c + b * c) // 2), div(add(mul(hu, hw), mul(hv, hw)), C(2))),
    _f("k2_shortfall", "garden", "t = hv hx; max(t, hu hw) - t", H4, R4,
       lambda a, b, c, d: F(max(b * d, a * c) - b * d), sub(mx(mul(hv, hx), mul(hu, hw)), mul(hv, hx))),
    _f("k2_stack_total", "market", "t = hu + hw; 1 + 2 + ... + t = t (t + 1) // 2", H3, R3,
       lambda a, b, c: F((a + c) * (a + c + 1) // 2), div(mul(add(hu, hw), add(add(hu, hw), C(1))), C(2))),
    _f("k2_trips_needed", "workshop", "t = hv hw; trips of hx needed = ceil(t / hx)", H4, R4,
       lambda a, b, c, d: F(-(-(b * c) // d)), div(add(mul(hv, hw), sub(hx, C(1))), hx)),
    _f("k2_left_after_rounds", "market", "t = hu hv; coins left when hw hx are paid t at a time = (hw hx) mod t", H4, R4,
       lambda a, b, c, d: F((c * d) % (a * b)), mod(mul(hw, hx), uv)),
    _f("k2_t_plus_half", "garden", "t = hu hv + hw; t + t // 2", H3, R3,
       lambda a, b, c: F(a * b + c + (a * b + c) // 2), add(add(uv, hw), div(add(uv, hw), C(2)))),
    # controls: one step (no intermediate reused)
    _f("k2_ctl_one_step", "garden", "control: hu hv + hw", H3, R3,
       lambda a, b, c: F(a * b + c), add(uv, hw)),
    _f("k2_ctl_one_step2", "market", "control: hu + hv hw", H3, R3,
       lambda a, b, c: F(a + b * c), add(hu, mul(hv, hw))),
)
