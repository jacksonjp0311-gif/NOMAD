"""TRANSFER: a never-trained domain for the cross-domain transfer test.

Phase 2 toward general intelligence (docs/TRANSFER.md): does what the field
learned in mathematics (and science) help in a domain it has never trained
on? This module is the catalogue of that domain: integer **geometry**
(areas, perimeters, volumes, polygon counts) and **finance** (interest,
pricing, profit), built exactly like ``nomad.science``:

- named integer inputs; a stated constant (100 for percent, 180 degrees per
  triangle) is a constant input column, never a new DSL constant;
- ground truth with ``fractions.Fraction``, written independently of the
  reference tree; a row is kept only when the answer is an integer and the
  reference tree, run by the WORLD interpreter, reproduces it (WITNESS stays
  exact-match, no tolerance);
- 5 public / 3 challenge / 3 final rows (the final split is never read by
  search).

Input names are disjoint from every training signature (WORLD ``x, y``,
``s``, ``xs``; science ``u a t d v m I R h s k c gH gO kH kO kW``), so no
learned block applies under its own names: any reuse must come through
renaming or composition. No field arm is ever trained on these families.

Tasks carry no domain tag: the sensing step sees them as it would see any
unknown integer task (by features), the way a genuinely new domain arrives.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("geometry", "finance")
KINDS = {"geometry": ("area", "perimeter", "volume", "polygon"),
         "finance": ("interest", "pricing", "profit")}

BOX = ("L", "W", "H")                 # length, width, height
TRAP = ("B", "T", "Z")                # bottom base, top base, height
POLY = ("n", "q")                     # sides, q = 180 degrees
MONEY = ("P", "r", "Y", "C")          # principal, rate %, years, C = 100
SALE = ("S", "K", "N", "X")           # sell price, unit cost, units, fixed cost

R_BOX = {"L": (1, 20), "W": (1, 20), "H": (1, 12)}
R_TRAP = {"B": (1, 30), "T": (1, 30), "Z": (1, 20)}
R_POLY = {"n": (3, 30), "q": ("const", 180)}
R_MONEY = {"P": ("step", 100, 4000, 100), "r": (1, 20), "Y": (1, 10), "C": ("const", 100)}
R_SALE = {"S": (5, 60), "K": (1, 40), "N": (1, 50), "X": (0, 300)}


def _f(family, domain, kind, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:{kind}", text, inputs, ranges, truth, tree)


# Fixed before any arm is measured. Tiering (easy = cold certifies at 10k,
# hard = sealed) is decided only by the cold control (scripts/transfer_suite.py).
CATALOGUE: tuple[Formula, ...] = (
    # geometry, rectangles and boxes
    _f("geo_rect_area", "geometry", "area", "A = L*W", BOX, R_BOX,
       lambda L, W, H: F(L) * W, ["mul", V("L"), V("W")]),
    _f("geo_rect_perim", "geometry", "perimeter", "p = 2(L+W)", BOX, R_BOX,
       lambda L, W, H: 2 * (F(L) + W), ["mul", C(2), ["add", V("L"), V("W")]]),
    _f("geo_box_vol", "geometry", "volume", "V = L*W*H", BOX, R_BOX,
       lambda L, W, H: F(L) * W * H, ["mul", ["mul", V("L"), V("W")], V("H")]),
    _f("geo_box_lateral", "geometry", "area", "side area = 2H(L+W)", BOX, R_BOX,
       lambda L, W, H: 2 * F(H) * (F(L) + W), ["mul", ["mul", C(2), V("H")], ["add", V("L"), V("W")]]),
    _f("geo_box_surface", "geometry", "area", "surface = 2(LW+LH+WH)", BOX, R_BOX,
       lambda L, W, H: 2 * (F(L) * W + F(L) * H + F(W) * H),
       ["mul", C(2), ["add", ["mul", V("L"), V("W")], ["mul", V("H"), ["add", V("L"), V("W")]]]]),
    _f("geo_open_box", "geometry", "area", "open-top box = LW + 2H(L+W)", BOX, R_BOX,
       lambda L, W, H: F(L) * W + 2 * F(H) * (F(L) + W),
       ["add", ["mul", V("L"), V("W")], ["mul", ["mul", C(2), V("H")], ["add", V("L"), V("W")]]]),
    _f("geo_box_edges", "geometry", "perimeter", "edge length = 4(L+W+H)", BOX, R_BOX,
       lambda L, W, H: 4 * (F(L) + W + H), ["mul", ["add", C(2), C(2)], ["add", ["add", V("L"), V("W")], V("H")]]),
    _f("geo_diag2", "geometry", "area", "d^2 = L^2 + W^2", BOX, R_BOX,
       lambda L, W, H: F(L) * L + F(W) * W, ["add", ["mul", V("L"), V("L")], ["mul", V("W"), V("W")]]),
    _f("geo_diag3", "geometry", "volume", "d^2 = L^2 + W^2 + H^2", BOX, R_BOX,
       lambda L, W, H: F(L) * L + F(W) * W + F(H) * H,
       ["add", ["add", ["mul", V("L"), V("L")], ["mul", V("W"), V("W")]], ["mul", V("H"), V("H")]]),
    _f("geo_frame", "geometry", "area", "border of width H around L x W = (L+2H)(W+2H) - LW", BOX, R_BOX,
       lambda L, W, H: (F(L) + 2 * H) * (F(W) + 2 * H) - F(L) * W,
       ["mul", ["mul", C(2), V("H")], ["add", ["add", V("L"), V("W")], ["mul", C(2), V("H")]]]),
    _f("geo_square_pyramid", "geometry", "volume", "V = L^2 H / 3", BOX, R_BOX,
       lambda L, W, H: F(L) * L * H / 3, ["div", ["mul", ["mul", V("L"), V("L")], V("H")], C(3)]),
    # geometry, triangles and trapezoids
    _f("geo_tri_area", "geometry", "area", "A = B*Z/2", TRAP, R_TRAP,
       lambda B, T, Z: F(B) * Z / 2, ["div", ["mul", V("B"), V("Z")], C(2)]),
    _f("geo_trap_area", "geometry", "area", "A = (B+T)Z/2", TRAP, R_TRAP,
       lambda B, T, Z: (F(B) + T) * Z / 2, ["div", ["mul", ["add", V("B"), V("T")], V("Z")], C(2)]),
    _f("geo_trap_mid", "geometry", "perimeter", "midline = (B+T)/2", TRAP, R_TRAP,
       lambda B, T, Z: (F(B) + T) / 2, ["div", ["add", V("B"), V("T")], C(2)]),
    _f("geo_tri_prism", "geometry", "volume", "V = B*Z*T/2 (triangle B,Z; length T)", TRAP, R_TRAP,
       lambda B, T, Z: F(B) * Z * T / 2, ["div", ["mul", ["mul", V("B"), V("Z")], V("T")], C(2)]),
    _f("geo_trap_diff", "geometry", "area", "A(BZ) - A(TZ) = (B-T)Z/2 (B > T)", TRAP, R_TRAP,
       lambda B, T, Z: (F(B) - T) * Z / 2 if B > T else F(1, 3), ["div", ["mul", ["sub", V("B"), V("T")], V("Z")], C(2)]),
    # geometry, polygons
    _f("geo_angle_sum", "geometry", "polygon", "interior angle sum = (n-2)*180", POLY, R_POLY,
       lambda n, q: (F(n) - 2) * q, ["mul", ["sub", V("n"), C(2)], V("q")]),
    _f("geo_diagonals", "geometry", "polygon", "diagonals = n(n-3)/2", POLY, R_POLY,
       lambda n, q: F(n) * (n - 3) / 2, ["div", ["mul", V("n"), ["sub", V("n"), C(3)]], C(2)]),
    _f("geo_tri_count", "geometry", "polygon", "triangles from one vertex fan + diagonals = (n-2) + n(n-3)/2",
       POLY, R_POLY, lambda n, q: (F(n) - 2) + F(n) * (n - 3) / 2,
       ["add", ["sub", V("n"), C(2)], ["div", ["mul", V("n"), ["sub", V("n"), C(3)]], C(2)]]),
    _f("geo_ext_angle", "geometry", "polygon", "exterior angle = 360/n", POLY, R_POLY,
       lambda n, q: 2 * F(q) / n, ["div", ["mul", C(2), V("q")], V("n")]),
    _f("geo_int_angle", "geometry", "polygon", "interior angle = (n-2)*180/n", POLY, R_POLY,
       lambda n, q: (F(n) - 2) * q / n, ["div", ["mul", ["sub", V("n"), C(2)], V("q")], V("n")]),
    # finance, interest (C = 100)
    _f("fin_interest_1y", "finance", "interest", "one year's interest = P*r/100", MONEY, R_MONEY,
       lambda P, r, Y, C: F(P) * r / C, ["div", ["mul", V("P"), V("r")], V("C")]),
    _f("fin_simple_interest", "finance", "interest", "simple interest = P*r*Y/100", MONEY, R_MONEY,
       lambda P, r, Y, C: F(P) * r * Y / C, ["div", ["mul", ["mul", V("P"), V("r")], V("Y")], V("C")]),
    _f("fin_amount", "finance", "interest", "amount = P + P*r*Y/100", MONEY, R_MONEY,
       lambda P, r, Y, C: F(P) + F(P) * r * Y / C,
       ["add", V("P"), ["div", ["mul", ["mul", V("P"), V("r")], V("Y")], V("C")]]),
    _f("fin_discounted", "finance", "pricing", "price after r% off = P - P*r/100", MONEY, R_MONEY,
       lambda P, r, Y, C: F(P) - F(P) * r / C, ["sub", V("P"), ["div", ["mul", V("P"), V("r")], V("C")]]),
    _f("fin_taxed", "finance", "pricing", "price with r% tax = P + P*r/100", MONEY, R_MONEY,
       lambda P, r, Y, C: F(P) + F(P) * r / C, ["add", V("P"), ["div", ["mul", V("P"), V("r")], V("C")]]),
    _f("fin_per_year", "finance", "interest", "repay per year (interest-free) = P/Y", MONEY, R_MONEY,
       lambda P, r, Y, C: F(P) / Y, ["div", V("P"), V("Y")]),
    _f("fin_installment", "finance", "interest", "yearly payment = (P + P*r*Y/100)/Y", MONEY, R_MONEY,
       lambda P, r, Y, C: (F(P) + F(P) * r * Y / C) / Y,
       ["div", ["add", V("P"), ["div", ["mul", ["mul", V("P"), V("r")], V("Y")], V("C")]], V("Y")]),
    # finance, profit
    _f("fin_revenue", "finance", "profit", "revenue = S*N", SALE, R_SALE,
       lambda S, K, N, X: F(S) * N, ["mul", V("S"), V("N")]),
    _f("fin_gross_profit", "finance", "profit", "gross profit = (S-K)*N", SALE, R_SALE,
       lambda S, K, N, X: (F(S) - K) * N, ["mul", ["sub", V("S"), V("K")], V("N")]),
    _f("fin_net_profit", "finance", "profit", "net profit = (S-K)*N - X", SALE, R_SALE,
       lambda S, K, N, X: (F(S) - K) * N - X, ["sub", ["mul", ["sub", V("S"), V("K")], V("N")], V("X")]),
    _f("fin_total_cost", "finance", "profit", "total cost = K*N + X", SALE, R_SALE,
       lambda S, K, N, X: F(K) * N + X, ["add", ["mul", V("K"), V("N")], V("X")]),
    _f("fin_breakeven", "finance", "profit", "break-even units = X/(S-K) (S > K)", SALE, R_SALE,
       lambda S, K, N, X: F(X) / (F(S) - K) if S > K else F(1, 3), ["div", V("X"), ["sub", V("S"), V("K")]]),
    _f("fin_avg_cost", "finance", "profit", "average cost per unit = K + X/N", SALE, R_SALE,
       lambda S, K, N, X: F(K) + F(X) / N, ["add", V("K"), ["div", V("X"), V("N")]]),
)
BY_FAMILY = {f.family: f for f in CATALOGUE}


def domain_kind(family: str) -> tuple[str, str] | None:
    f = BY_FAMILY.get(family)
    return tuple(f.kind.split(":", 1)) if f else None


def is_transfer(family: str | None) -> bool:
    return bool(family) and family in BY_FAMILY
