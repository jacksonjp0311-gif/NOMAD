"""CEIL sealed catalogue (docs/CEIL.md): ceiling divisions ("rounded up") by a constant.

Written before any field arm is measured on it. Three domains no earlier catalogue uses
(museum, marina, brewery), input names ``la..li`` disjoint from every catalogue, Fraction
ground truth written independently of the reference tree (``-(-n // k)``), 5 public /
3 challenge / 3 final rows (``nomad.science.draw_rows``, as TRANSFER-4 / SELFEDIT).

Mix, chosen by the shape of the claim and not by outcome: ceilings by constants the
trained field has learned or derives (2, 3, 4, 6, 9), ceilings by constants it does not
have (5, 7, 8, 10, 12; out of reach for the fit, in reach for the rewired control), and
three composites where the ceiling is only a part (``lc ceil(la / 4)``, ``ceil(ld / 2) + le``,
``lg ceil(lh / 6)``), which the top-level fit cannot produce.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, to_task  # noqa: F401  (re-exported)
from .selfedit_tasks import _add, _ceil_tree, _k, _mul

DOMAINS = ("museum", "marina", "brewery")

HALL = ("la", "lb", "lc")      # visitor groups, visitors per group, days
R_HALL = {"la": (1, 30), "lb": (1, 12), "lc": (1, 9)}
PORT = ("ld", "le", "lf")      # boats, crew per boat, trips
R_PORT = {"ld": (1, 20), "le": (1, 10), "lf": (1, 8)}
BREW = ("lg", "lh", "li")      # batches, bottles per batch (dozens), days
R_BREW = {"lg": (1, 25), "lh": (1, 12), "li": (1, 10)}


def _f(family, domain, kind, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:{kind}", text, inputs, ranges, truth, tree)


def _c(n: int, k: int) -> F:
    return F(-(-n // k))


def _kk(n: int) -> list:
    """Constants beyond selfedit_tasks._k (as trees of the leaves 2 and 3)."""
    return {5: _add(C(2), C(3)), 7: _add(_add(C(2), C(2)), C(3)), 10: _mul(C(2), _add(C(2), C(3)))}[n] \
        if n in (5, 7, 10) else _k(n)


CATALOGUE: tuple[Formula, ...] = (
    # museum
    _f("cl_m_guides", "museum", "packing", "guides, one per 9 visitors = ceil(la lb / 9)", HALL, R_HALL,
       lambda la, lb, lc: _c(la * lb, 9), _ceil_tree(_mul(V("la"), V("lb")), _kk(9))),
    _f("cl_m_benches", "museum", "packing", "benches seating 2, for la groups of lb = ceil(la lb / 2)", HALL, R_HALL,
       lambda la, lb, lc: _c(la * lb, 2), _ceil_tree(_mul(V("la"), V("lb")), C(2))),
    _f("cl_m_booklets", "museum", "packing", "booklets, one per 4 visitors = ceil(la lb / 4)", HALL, R_HALL,
       lambda la, lb, lc: _c(la * lb, 4), _ceil_tree(_mul(V("la"), V("lb")), _kk(4))),
    _f("cl_m_lockers", "museum", "packing", "locker rows of 3 for la groups and lb staff = ceil((la + lb) / 3)", HALL, R_HALL,
       lambda la, lb, lc: _c(la + lb, 3), _ceil_tree(_add(V("la"), V("lb")), C(3))),
    _f("cl_m_shifts", "museum", "time", "6-hour shifts covering la hours on lc days = ceil(la lc / 6)", HALL, R_HALL,
       lambda la, lb, lc: _c(la * lc, 6), _ceil_tree(_mul(V("la"), V("lc")), _kk(6))),
    _f("cl_m_audio", "museum", "packing", "audio-guide boxes of 12 = ceil(la lb lc / 12)", HALL, R_HALL,
       lambda la, lb, lc: _c(la * lb * lc, 12), _ceil_tree(_mul(_mul(V("la"), V("lb")), V("lc")), _kk(12))),
    _f("cl_m_badges", "museum", "packing", "badge sheets of 4 per day for la groups = lc ceil(la / 4)", HALL, R_HALL,
       lambda la, lb, lc: lc * _c(la, 4), _mul(V("lc"), _ceil_tree(V("la"), _kk(4)))),
    _f("cl_m_weeks", "museum", "time", "weeks started over la lc visit-days = ceil(la lc / 7)", HALL, R_HALL,
       lambda la, lb, lc: _c(la * lc, 7), _ceil_tree(_mul(V("la"), V("lc")), _kk(7))),
    # marina
    _f("cl_h_rafts", "marina", "packing", "life rafts for 6, ld boats of le crew = ceil(ld le / 6)", PORT, R_PORT,
       lambda ld, le, lf: _c(ld * le, 6), _ceil_tree(_mul(V("ld"), V("le")), _kk(6))),
    _f("cl_h_moorings", "marina", "packing", "mooring slots of 3 trips = ceil(ld lf / 3)", PORT, R_PORT,
       lambda ld, le, lf: _c(ld * lf, 3), _ceil_tree(_mul(V("ld"), V("lf")), C(3))),
    _f("cl_h_lifeboats", "marina", "packing", "lifeboats for 4 = ceil(ld le / 4)", PORT, R_PORT,
       lambda ld, le, lf: _c(ld * le, 4), _ceil_tree(_mul(V("ld"), V("le")), _kk(4))),
    _f("cl_h_fuel", "marina", "packing", "fuel drums, one per 9 crew-trips = ceil(ld le lf / 9)", PORT, R_PORT,
       lambda ld, le, lf: _c(ld * le * lf, 9), _ceil_tree(_mul(_mul(V("ld"), V("le")), V("lf")), _kk(9))),
    _f("cl_h_ropes", "marina", "packing", "rope pairs for ld boats and le spares = ceil((ld + le) / 2)", PORT, R_PORT,
       lambda ld, le, lf: _c(ld + le, 2), _ceil_tree(_add(V("ld"), V("le")), C(2))),
    _f("cl_h_tides", "marina", "time", "tide windows of 5 boat-trips = ceil(ld lf / 5)", PORT, R_PORT,
       lambda ld, le, lf: _c(ld * lf, 5), _ceil_tree(_mul(V("ld"), V("lf")), _kk(5))),
    _f("cl_h_crates", "marina", "packing", "crates of 8 crew-trip rations = ceil(ld le lf / 8)", PORT, R_PORT,
       lambda ld, le, lf: _c(ld * le * lf, 8), _ceil_tree(_mul(_mul(V("ld"), V("le")), V("lf")), _kk(8))),
    _f("cl_h_docks", "marina", "packing", "docks, one per 2 boats, plus le pilots = ceil(ld / 2) + le", PORT, R_PORT,
       lambda ld, le, lf: _c(ld, 2) + le, _add(_ceil_tree(V("ld"), C(2)), V("le"))),
    # brewery
    _f("cl_b_cases", "brewery", "packing", "cases of 6 for lg batches of lh = ceil(lg lh / 6)", BREW, R_BREW,
       lambda lg, lh, li: _c(lg * lh, 6), _ceil_tree(_mul(V("lg"), V("lh")), _kk(6))),
    _f("cl_b_kegs", "brewery", "packing", "kegs of 3 = ceil(lg lh / 3)", BREW, R_BREW,
       lambda lg, lh, li: _c(lg * lh, 3), _ceil_tree(_mul(V("lg"), V("lh")), C(3))),
    _f("cl_b_pallets", "brewery", "packing", "pallets of 4 over li days = ceil(lg lh li / 4)", BREW, R_BREW,
       lambda lg, lh, li: _c(lg * lh * li, 4), _ceil_tree(_mul(_mul(V("lg"), V("lh")), V("li")), _kk(4))),
    _f("cl_b_tanks", "brewery", "packing", "tanks of 4 for lg batches and li spare days = ceil((lg + li) / 4)", BREW, R_BREW,
       lambda lg, lh, li: _c(lg + li, 4), _ceil_tree(_add(V("lg"), V("li")), _kk(4))),
    _f("cl_b_crews", "brewery", "packing", "crews of 2 for lg batch-days li = ceil(lg li / 2)", BREW, R_BREW,
       lambda lg, lh, li: _c(lg * li, 2), _ceil_tree(_mul(V("lg"), V("li")), C(2))),
    _f("cl_b_sixpacks", "brewery", "packing", "six-pack carriers per batch for lg batches = lg ceil(lh / 6)", BREW, R_BREW,
       lambda lg, lh, li: lg * _c(lh, 6), _mul(V("lg"), _ceil_tree(V("lh"), _kk(6)))),
    _f("cl_b_labels", "brewery", "packing", "label rolls of 10 = ceil(lg lh / 10)", BREW, R_BREW,
       lambda lg, lh, li: _c(lg * lh, 10), _ceil_tree(_mul(V("lg"), V("lh")), _kk(10))),
    _f("cl_b_squares", "brewery", "packing", "3x3 racks for a lg x lg grid of bottles = ceil(lg lg / 9)", BREW, R_BREW,
       lambda lg, lh, li: _c(lg * lg, 9), _ceil_tree(_mul(V("lg"), V("lg")), _kk(9))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
