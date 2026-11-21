"""TRANSFER-2: a second never-trained geometry + finance catalogue (GROW, docs/GROW.md).

The first transfer suite (``nomad/transfer.py``, docs/TRANSFER.md) is known:
its 9 unsolved tasks shaped the GROW design (on uncommitted dev suites of
that catalogue). So GROW is judged on this **new** catalogue: new formulas
wherever possible, new input names, a new seed. Built exactly like
``nomad.transfer`` / ``nomad.science``: named int inputs, stated constants as
constant input columns, Fraction ground truth written independently of the
reference tree, rows kept only when the answer is an integer the reference
tree reproduces, 5 public / 3 challenge / 3 final rows.

Input names are disjoint from every training signature and from the first
transfer catalogue. No field arm is ever trained on these families. Fixed
before any field arm is measured on them.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("geometry", "finance")

CUBE = ("E", "F", "G")                    # three lengths
PRISM = ("A", "D", "J", "Lz")             # two bases, a height, a length
COUNT = ("cnt", "z")                      # a count, z = 180 degrees
CASH = ("M", "i", "yrs", "O")             # amount, rate %, years (or people), O = 100
SHOP = ("pr", "cs", "qty", "fee")         # price, unit cost, quantity, per-unit fee or fixed cost
WAGE = ("hr", "ot", "rate")               # hours, overtime hours, hourly rate

R_CUBE = {"E": (1, 20), "F": (1, 20), "G": (1, 12)}
R_PRISM = {"A": (1, 25), "D": (1, 25), "J": (1, 15), "Lz": (1, 12)}
R_COUNT = {"cnt": (3, 30), "z": ("const", 180)}
R_CASH = {"M": ("step", 100, 5000, 100), "i": (1, 25), "yrs": (1, 10), "O": ("const", 100)}
R_SHOP = {"pr": (5, 80), "cs": (1, 50), "qty": (1, 60), "fee": (0, 9)}
R_WAGE = {"hr": (1, 40), "ot": (0, 15), "rate": (8, 40)}


def _f(family, domain, kind, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:{kind}", text, inputs, ranges, truth, tree)


def _sub(a, b):
    return ["sub", a, b]


CATALOGUE: tuple[Formula, ...] = (
    # geometry: solids and plane figures on three lengths E, F, G
    _f("g2_cube_vol", "geometry", "volume", "V = E^3", CUBE, R_CUBE,
       lambda E, F_, G: F(E) ** 3, ["mul", V("E"), ["mul", V("E"), V("E")]]),
    _f("g2_cube_surface", "geometry", "area", "S = 6E^2", CUBE, R_CUBE,
       lambda E, F_, G: 6 * F(E) ** 2, ["mul", ["mul", C(2), C(3)], ["mul", V("E"), V("E")]]),
    _f("g2_three_faces", "geometry", "area", "three faces = EF + FG + EG", CUBE, R_CUBE,
       lambda E, F_, G: F(E) * F_ + F(F_) * G + F(E) * G,
       ["add", ["mul", V("E"), V("F")], ["mul", V("G"), ["add", V("E"), V("F")]]]),
    _f("g2_box_minus_cube", "geometry", "volume", "box EFG minus a cube of side G", CUBE, R_CUBE,
       lambda E, F_, G: F(E) * F_ * G - F(G) ** 3,
       _sub(["mul", ["mul", V("E"), V("F")], V("G")], ["mul", V("G"), ["mul", V("G"), V("G")]])),
    _f("g2_square_ring", "geometry", "area", "square ring = E^2 - F^2 (E > F)", CUBE, R_CUBE,
       lambda E, F_, G: F(E) ** 2 - F(F_) ** 2 if E > F_ else F(1, 3),
       _sub(["mul", V("E"), V("E")], ["mul", V("F"), V("F")])),
    _f("g2_corner_cut", "geometry", "area", "rectangle EF with a G x G corner cut (G < E, F)", CUBE, R_CUBE,
       lambda E, F_, G: F(E) * F_ - F(G) ** 2 if G < E and G < F_ else F(1, 3),
       _sub(["mul", V("E"), V("F")], ["mul", V("G"), V("G")])),
    _f("g2_path_around", "geometry", "area", "path of width 1 around E x F = (E+2)(F+2) - EF", CUBE, R_CUBE,
       lambda E, F_, G: (F(E) + 2) * (F_ + 2) - F(E) * F_,
       ["add", ["mul", C(2), ["add", V("E"), V("F")]], ["add", C(2), C(2)]]),
    _f("g2_ribbon", "geometry", "perimeter", "ribbon round a box twice = 2E + 2F + 4G", CUBE, R_CUBE,
       lambda E, F_, G: 2 * F(E) + 2 * F_ + 4 * F(G),
       ["mul", C(2), ["add", ["add", V("E"), V("F")], ["add", V("G"), V("G")]]]),
    _f("g2_cuboid_edges_diff", "geometry", "perimeter", "edges of box EFG minus edges of cube G = 4(E+F-2G)", CUBE, R_CUBE,
       lambda E, F_, G: 4 * (F(E) + F_ + G) - 12 * F(G),
       ["mul", ["add", C(2), C(2)], _sub(["add", V("E"), V("F")], ["add", V("G"), V("G")])]),
    _f("g2_rect_pyramid", "geometry", "volume", "V = EFG/3", CUBE, R_CUBE,
       lambda E, F_, G: F(E) * F_ * G / 3, ["div", ["mul", ["mul", V("E"), V("F")], V("G")], C(3)]),
    _f("g2_space_diag_sq", "geometry", "volume", "d^2 of a cube side E plus a square side F = 3E^2 + F^2", CUBE, R_CUBE,
       lambda E, F_, G: 3 * F(E) ** 2 + F(F_) ** 2,
       ["add", ["mul", C(3), ["mul", V("E"), V("E")]], ["mul", V("F"), V("F")]]),
    _f("g2_two_squares", "geometry", "area", "two squares = E^2 + F^2 + 2G (plus a 2 x G strip)", CUBE, R_CUBE,
       lambda E, F_, G: F(E) ** 2 + F(F_) ** 2 + 2 * F(G),
       ["add", ["add", ["mul", V("E"), V("E")], ["mul", V("F"), V("F")]], ["add", V("G"), V("G")]]),
    # geometry: prisms and trapezoids on A, D (bases), J (height), Lz (length)
    _f("g2_trap_prism", "geometry", "volume", "trapezoid prism = (A+D)J Lz / 2", PRISM, R_PRISM,
       lambda A, D, J, Lz: (F(A) + D) * J * Lz / 2,
       ["div", ["mul", ["mul", ["add", V("A"), V("D")], V("J")], V("Lz")], C(2)]),
    _f("g2_tri_prism_surface", "geometry", "area", "right prism, rectangle faces = (A+D+J) Lz", PRISM, R_PRISM,
       lambda A, D, J, Lz: (F(A) + D + J) * Lz,
       ["mul", ["add", ["add", V("A"), V("D")], V("J")], V("Lz")]),
    _f("g2_rect_prism_pair", "geometry", "volume", "two blocks = A J Lz + D J", PRISM, R_PRISM,
       lambda A, D, J, Lz: F(A) * J * Lz + F(D) * J,
       ["mul", V("J"), ["add", ["mul", V("A"), V("Lz")], V("D")]]),
    _f("g2_tri_area_diff", "geometry", "area", "triangle (A,J) minus triangle (D,J) halves: (A-D)J/2 (A > D)", PRISM, R_PRISM,
       lambda A, D, J, Lz: (F(A) - D) * J / 2 if A > D else F(1, 3),
       ["div", ["mul", _sub(V("A"), V("D")), V("J")], C(2)]),
    _f("g2_kite", "geometry", "area", "kite with diagonals A and D = AD/2", PRISM, R_PRISM,
       lambda A, D, J, Lz: F(A) * D / 2, ["div", ["mul", V("A"), V("D")], C(2)]),
    _f("g2_trap_plus_rect", "geometry", "area", "trapezoid (A,D,J) on a J x Lz rectangle = (A+D)J/2 + J Lz", PRISM, R_PRISM,
       lambda A, D, J, Lz: (F(A) + D) * J / 2 + F(J) * Lz,
       ["add", ["div", ["mul", ["add", V("A"), V("D")], V("J")], C(2)], ["mul", V("J"), V("Lz")]]),
    # geometry: counting on cnt (z = 180 degrees)
    _f("g2_handshakes", "geometry", "polygon", "segments between k points = k(k-1)/2", COUNT, R_COUNT,
       lambda k, z: F(k) * (k - 1) / 2, ["div", ["mul", V("cnt"), _sub(V("cnt"), C(1))], C(2)]),
    _f("g2_triangular", "geometry", "polygon", "triangular number = k(k+1)/2", COUNT, R_COUNT,
       lambda k, z: F(k) * (k + 1) / 2, ["div", ["mul", V("cnt"), ["add", V("cnt"), C(1)]], C(2)]),
    _f("g2_hex_number", "geometry", "polygon", "centred hexagonal number = 3k(k-1) + 1", COUNT, R_COUNT,
       lambda k, z: 3 * F(k) * (k - 1) + 1,
       ["add", ["mul", ["mul", C(3), V("cnt")], _sub(V("cnt"), C(1))], C(1)]),
    _f("g2_square_pyr_number", "geometry", "polygon", "square pyramidal number = k(k+1)(2k+1)/6", COUNT, R_COUNT,
       lambda k, z: F(k) * (k + 1) * (2 * k + 1) / 6,
       ["div", ["mul", ["mul", V("cnt"), ["add", V("cnt"), C(1)]], ["add", ["add", V("cnt"), V("cnt")], C(1)]],
        ["mul", C(2), C(3)]]),
    _f("g2_int_angle2", "geometry", "polygon", "interior angle = 180 - 360/k", COUNT, R_COUNT,
       lambda k, z: F(z) - 2 * F(z) / k, _sub(V("z"), ["div", ["add", V("z"), V("z")], V("cnt")])),
    _f("g2_angle_sum_rt", "geometry", "polygon", "angle sum in right angles = 2(k-2)", COUNT, R_COUNT,
       lambda k, z: 2 * (F(k) - 2), ["mul", C(2), _sub(V("cnt"), C(2))]),
    # finance: interest and pricing on M, i (%), y, O = 100
    _f("f2_extra_interest", "finance", "interest", "interest after the first year = M i (y-1)/100", CASH, R_CASH,
       lambda M, i, y, O: F(M) * i * (y - 1) / O,
       ["div", ["mul", ["mul", V("M"), V("i")], _sub(V("yrs"), C(1))], V("O")]),
    _f("f2_markup_markdown", "finance", "pricing", "price after +i% then -y% of M = M + M i/100 - M y/100", CASH, R_CASH,
       lambda M, i, y, O: F(M) + F(M) * i / O - F(M) * y / O,
       ["div", ["mul", V("M"), _sub(["add", V("O"), V("i")], V("yrs"))], V("O")]),
    _f("f2_split_bill", "finance", "pricing", "bill M plus i% tip split among y = (M + M i/100)/y", CASH, R_CASH,
       lambda M, i, y, O: (F(M) + F(M) * i / O) / y,
       ["div", ["div", ["mul", V("M"), ["add", V("O"), V("i")]], V("O")], V("yrs")]),
    _f("f2_savings", "finance", "interest", "save M a year for y years plus i% once = My + My i/100", CASH, R_CASH,
       lambda M, i, y, O: F(M) * y + F(M) * y * i / O,
       ["div", ["mul", ["mul", V("M"), V("yrs")], ["add", V("O"), V("i")]], V("O")]),
    _f("f2_double_rate", "finance", "interest", "interest at twice the rate = 2 M i y/100", CASH, R_CASH,
       lambda M, i, y, O: 2 * F(M) * i * y / O,
       ["div", ["mul", ["mul", ["add", V("M"), V("M")], V("i")], V("yrs")], V("O")]),
    _f("f2_rate_gap", "finance", "interest", "M i/100 - M y/100 (i > y)", CASH, R_CASH,
       lambda M, i, y, O: F(M) * (i - y) / O if i > y else F(1, 3),
       ["div", ["mul", V("M"), _sub(V("i"), V("yrs"))], V("O")]),
    # finance: shop on price, cost, quantity, fee
    _f("f2_two_lines", "finance", "profit", "invoice = pr qty + cs fee", SHOP, R_SHOP,
       lambda pr, cs, qty, fee: F(pr) * qty + F(cs) * fee,
       ["add", ["mul", V("pr"), V("qty")], ["mul", V("cs"), V("fee")]]),
    _f("f2_margin_after_fee", "finance", "profit", "profit = (pr - cs - fee) qty", SHOP, R_SHOP,
       lambda pr, cs, qty, fee: (F(pr) - cs - fee) * qty,
       ["mul", _sub(_sub(V("pr"), V("cs")), V("fee")), V("qty")]),
    _f("f2_restock", "finance", "profit", "sell qty at pr, buy qty + fee units at cs = pr qty - cs (qty + fee)", SHOP, R_SHOP,
       lambda pr, cs, qty, fee: F(pr) * qty - F(cs) * (qty + fee),
       _sub(["mul", V("pr"), V("qty")], ["mul", V("cs"), ["add", V("qty"), V("fee")]])),
    _f("f2_bulk_order", "finance", "profit", "cost of qty at cs plus fee per unit plus pr shipping = (cs+fee) qty + pr", SHOP, R_SHOP,
       lambda pr, cs, qty, fee: (F(cs) + fee) * qty + pr,
       ["add", ["mul", ["add", V("cs"), V("fee")], V("qty")], V("pr")]),
    _f("f2_profit_two_prices", "finance", "profit", "qty sold at pr, fee units given away: pr(qty-fee) - cs qty", SHOP, R_SHOP,
       lambda pr, cs, qty, fee: F(pr) * (qty - fee) - F(cs) * qty,
       _sub(["mul", V("pr"), _sub(V("qty"), V("fee"))], ["mul", V("cs"), V("qty")])),
    # finance: wages
    _f("f2_wage_ot", "finance", "profit", "pay = hr rate + ot rate 3/2", WAGE, R_WAGE,
       lambda hr, ot, rate: F(hr) * rate + F(ot) * rate * 3 / 2,
       ["div", ["mul", V("rate"), ["add", ["add", V("hr"), V("hr")], ["mul", C(3), V("ot")]]], C(2)]),
    _f("f2_wage_double", "finance", "profit", "pay = hr rate + 2 ot rate", WAGE, R_WAGE,
       lambda hr, ot, rate: F(hr) * rate + 2 * F(ot) * rate,
       ["mul", V("rate"), ["add", V("hr"), ["add", V("ot"), V("ot")]]]),
    _f("f2_wage_gap", "finance", "profit", "regular minus overtime pay at time-and-a-half = hr rate - 3 ot rate/2", WAGE, R_WAGE,
       lambda hr, ot, rate: F(hr) * rate - F(ot) * rate * 3 / 2,
       ["div", ["mul", V("rate"), _sub(["add", V("hr"), V("hr")], ["mul", C(3), V("ot")])], C(2)]),
)
BY_FAMILY = {f.family: f for f in CATALOGUE}


def is_transfer2(family: str | None) -> bool:
    return bool(family) and family in BY_FAMILY
