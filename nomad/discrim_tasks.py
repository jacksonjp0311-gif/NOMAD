"""DISCRIM sealed catalogue (docs/DISCRIM.md): ambiguous two-stage word problems, new names, new inputs.

Written, and committed with the pre-registered criteria, before any arm is measured on it (only the
cold control is run by the generator). Domains no other catalogue uses (lighthouse, glacier, pottery);
named int inputs ``dj dk dl dm`` (disjoint from every catalogue); family prefix ``dx_``. Same
construction as ``nomad.let2_tasks``: Fraction ground truth written independently of the reference tree
(a row whose answer is not a valid integer is skipped), 5 public / 3 challenge / 3 final rows.

Ambiguity by construction (the LET2 losses: a let fit that only differs from the truth where one input
exceeds another): the input ranges overlap only partly (``dj`` 1-30 wide, ``dm`` 1-9 narrow, ``dk`` and
``dl`` 1-12), so an order between two inputs often holds on the 8 evidence rows by chance and a wrong
``max`` / ``min`` / ``abs`` explanation can fit all of them. Half of the formulas are plain two-stage
computations (an intermediate used twice), half contain a comparison or a remainder whose branch the
evidence may never exercise. Two one-step controls. None chosen by outcome.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("lighthouse", "glacier", "pottery")

D3 = ("dj", "dk", "dl")
D4 = ("dj", "dk", "dl", "dm")
R3 = {"dj": (1, 30), "dk": (1, 12), "dl": (1, 12)}
R4 = {"dj": (1, 30), "dk": (1, 12), "dl": (1, 12), "dm": (1, 9)}
NO = F(1, 2)     # not an integer: the row is skipped


def _f(family, domain, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:discrim", text, inputs, ranges, truth, tree)


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


dj, dk, dl, dm = V("dj"), V("dk"), V("dl"), V("dm")
kl = mul(dk, dl)
jm = mul(dj, dm)
FOUR = add(C(2), C(2))

CATALOGUE: tuple[Formula, ...] = (
    # plain two-stage (an intermediate t used twice)
    _f("dx_lamp_hours_spare", "lighthouse", "lamp hours t = dk nights x dl hours; t plus a quarter spare", D3, R3,
       lambda a, b, c: F(b * c + (b * c) // 4), add(kl, div(kl, FOUR))),
    _f("dx_crew_pairs", "lighthouse", "crew t = dk + dl; watch pairs t (t - 1) // 2", D3, R3,
       lambda a, b, c: F((b + c) * (b + c - 1) // 2), div(mul(add(dk, dl), sub(add(dk, dl), C(1))), C(2))),
    _f("dx_core_sq_less", "glacier", "core t = dj + dk; t squared minus dl", D3, R3,
       lambda a, b, c: F((a + b) ** 2 - c), sub(mul(add(dj, dk), add(dj, dk)), dl)),
    _f("dx_layers_and_third", "glacier", "layers t = dk dl + dj; 2 t plus a third of t", D3, R3,
       lambda a, b, c: F(2 * (b * c + a) + (b * c + a) // 3), add(mul(add(kl, dj), C(2)), div(add(kl, dj), C(3)))),
    _f("dx_kiln_two_rates", "pottery", "firings t = dk + dl; cost t dj + t dm", D4, R4,
       lambda a, b, c, d: F((b + c) * a + (b + c) * d), add(mul(add(dk, dl), dj), mul(add(dk, dl), dm))),
    _f("dx_bowls_sets_loose", "pottery", "bowls t = dk dl + dj; sets of 4 plus loose = t // 4 + t mod 4", D3, R3,
       lambda a, b, c: F((b * c + a) // 4 + (b * c + a) % 4), add(div(add(kl, dj), FOUR), mod(add(kl, dj), FOUR))),
    _f("dx_beam_sq_minus", "lighthouse", "t = dk dl; t squared minus t dm", D4, R4,
       lambda a, b, c, d: F((b * c) ** 2 - b * c * d), sub(mul(kl, kl), mul(kl, dm))),
    _f("dx_melt_stack", "glacier", "t = dk + dm; 1 + 2 + ... + t = t (t + 1) // 2", D4, R4,
       lambda a, b, c, d: F((b + d) * (b + d + 1) // 2), div(mul(add(dk, dm), add(add(dk, dm), C(1))), C(2))),
    _f("dx_glaze_half_more", "pottery", "t = dj dm; t + t // 2", D4, R4,
       lambda a, b, c, d: F(a * d + (a * d) // 2), add(jm, div(jm, C(2)))),
    _f("dx_shelf_cube", "pottery", "t = dk + dl; t t dm", D4, R4,
       lambda a, b, c, d: F((b + c) ** 2 * d), mul(mul(add(dk, dl), add(dk, dl)), dm)),
    _f("dx_trips_boat", "lighthouse", "t = dk dl; boat trips of dm needed = ceil(t / dm)", D4, R4,
       lambda a, b, c, d: F(-(-(b * c) // d)), div(add(kl, sub(dm, C(1))), dm)),
    _f("dx_ice_mean", "glacier", "t = dj dk; mean of t and dl dk = (t + dl dk) // 2", D3, R3,
       lambda a, b, c: F((a * b + c * b) // 2), div(add(mul(dj, dk), mul(dl, dk)), C(2))),
    # comparisons / remainders whose branch the evidence may never exercise (ambiguity traps)
    _f("dx_fuel_shortfall", "lighthouse", "need t = dk dm; shortfall below stock dj = max(t - dj, 0)", D4, R4,
       lambda a, b, c, d: F(max(b * d - a, 0)), mx(sub(mul(dk, dm), dj), C(0))),
    _f("dx_tide_gap", "lighthouse", "t = dk dl; gap to height dj = |t - dj|", D3, R3,
       lambda a, b, c: F(abs(b * c - a)), sub(mx(kl, dj), mn(kl, dj))),
    _f("dx_crevasse_cap", "glacier", "t = dj + dk; capped at 3 dl = min(t, 3 dl), doubled", D3, R3,
       lambda a, b, c: F(2 * min(a + b, 3 * c)), mul(mn(add(dj, dk), mul(C(3), dl)), C(2))),
    _f("dx_floe_area_half", "glacier", "floe t = dj dl; half of t (diagonals)", D3, R3,
       lambda a, b, c: F(a * c, 2) if (a * c) % 2 == 0 else NO, div(mul(dj, dl), C(2))),
    _f("dx_clay_left", "pottery", "t = dk dl; clay left after pots of dm = t mod dm, plus pots t // dm", D4, R4,
       lambda a, b, c, d: F((b * c) % d + (b * c) // d), add(mod(kl, dm), div(kl, dm))),
    _f("dx_wick_spare", "pottery", "t = dj - dm (when positive); t t // dk", D4, R4,
       lambda a, b, c, d: F((a - d) * (a - d) // b) if a >= d else NO, div(mul(sub(dj, dm), sub(dj, dm)), dk)),
    _f("dx_beacon_least", "lighthouse", "t = dk dl; min(t, dj dm) + t", D4, R4,
       lambda a, b, c, d: F(min(b * c, a * d) + b * c), add(mn(kl, jm), kl)),
    _f("dx_snow_over", "glacier", "t = dj dm; over the line dk dl = max(t, dk dl) - dk dl", D4, R4,
       lambda a, b, c, d: F(max(a * d, b * c) - b * c), sub(mx(jm, kl), kl)),
    _f("dx_kiln_change", "pottery", "change t = dj dm - dk dl (when not negative); bags of dk = t // dk", D4, R4,
       lambda a, b, c, d: F((a * d - b * c) // b) if a * d >= b * c else NO, div(sub(jm, kl), dk)),
    _f("dx_rope_left", "lighthouse", "t = dj + dk; rope left when dl dm is cut t at a time = (dl dm) mod t", D4, R4,
       lambda a, b, c, d: F((c * d) % (a + b)), mod(mul(dl, dm), add(dj, dk))),
    # controls: one step (no intermediate reused)
    _f("dx_ctl_one_step", "lighthouse", "control: dk dl + dj", D3, R3,
       lambda a, b, c: F(b * c + a), add(kl, dj)),
    _f("dx_ctl_one_step2", "glacier", "control: dj + dk dl - dl", D3, R3,
       lambda a, b, c: F(a + b * c - c), sub(add(dj, kl), dl)),
)
