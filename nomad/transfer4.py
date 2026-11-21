"""TRANSFER-4: a fourth never-trained catalogue, the sealed proof suite for
INVENT round 2 (budget-safe phase + iterated invention; docs/INVENT.md).

TRANSFER-3 and the science suite shaped the round-2 design, so round 2 is
judged on this **new** catalogue: three domains no field arm trains on and no
earlier catalogue covers (kitchen / baking, garden, workshop / crafts), new
formulas, new input names (disjoint from every earlier catalogue, the science
catalogue and all training tasks), a new seed. Written down, and committed,
with the INVENT design frozen, before any field arm is measured on it.

By the owner's brief the catalogue deliberately contains the round-2 target
shapes -- products of shifted terms ((n-2)^3, (a+1)(b+1), ...),
n(n+1)(n+2)-type products and nested (floor / ceiling) division -- next to
ordinary everyday formulas; every formula is a textbook / everyday counting
or measuring formula, none chosen by outcome. Built exactly like
``nomad.transfer3``: named int inputs, Fraction (or exact integer floor)
ground truth written independently of the reference tree, rows kept only when
the answer is an integer the reference tree reproduces, 5 public / 3
challenge / 3 final rows (the final split is never read by search or
WITNESS).
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("kitchen", "garden", "workshop")

TRAY = ("tw", "tl", "tk")         # tray: cookies across, cookies along, tiers
CAKE = ("ck",)                    # tiers / layers of a stacked treat
CAKE2 = ("ck", "tk")              # square cake side ck, height tk
DINNER = ("gs", "cr")             # guests, courses
COOKIE = ("cq", "cpb", "cbb")     # cookies, cookies per bag, bags per box
DOUGH = ("gs", "gpp", "bat")      # servings, grams per serving, batches
BED = ("bw", "bln", "bsp")        # bed width, bed length, spacing / border
POTS = ("tier", "nbx")            # pot-pyramid tiers, number of pyramids
SEEDS = ("sd", "spk", "pkc")      # seeds, seeds per packet, packets per crate
CUBE = ("cb",)                    # cube side (unit cubes)
WOOD = ("wa", "wb", "wc")         # board / box sides, wall or cut width
KNIT = ("kr", "kst", "kc")        # rows, stitches per row, colours

R_TRAY = {"tw": (1, 12), "tl": (1, 12), "tk": (1, 6)}
R_CAKE = {"ck": (2, 30)}
R_CAKE2 = {"ck": (2, 30), "tk": (1, 8)}
R_DINNER = {"gs": (1, 40), "cr": (1, 8)}
R_COOKIE = {"cq": (1, 900), "cpb": (2, 24), "cbb": (2, 12)}
R_DOUGH = {"gs": (1, 40), "gpp": ("step", 5, 200, 5), "bat": (1, 8)}
R_BED = {"bw": (2, 24), "bln": (2, 30), "bsp": (1, 5)}
R_POTS = {"tier": (2, 30), "nbx": (1, 8)}
R_SEEDS = {"sd": ("step", 10, 4000, 10), "spk": (2, 40), "pkc": (2, 12)}
R_CUBE = {"cb": (3, 20)}
R_WOOD = {"wa": (3, 24), "wb": (3, 24), "wc": (1, 8)}
R_SHELF = {"wa": (20, 400), "wb": (2, 12), "wc": (2, 6)}
R_KNIT = {"kr": (1, 60), "kst": (1, 80), "kc": (1, 6)}


def _f(family, domain, kind, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:{kind}", text, inputs, ranges, truth, tree)


def _sub(a, b):
    return ["sub", a, b]


def _add(a, b):
    return ["add", a, b]


def _mul(a, b):
    return ["mul", a, b]


def _div(a, b):
    return ["div", a, b]


def _mod(a, b):
    return ["mod", a, b]


def _ceil(n, k):
    return -(-F(n) // k)


def _cdiv(a, b):
    """ceiling division as a tree: (a + b - 1) // b."""
    return _div(_add(a, _sub(b, C(1))), b)


def _bad():
    return F(1, 3)   # not an integer: the row is redrawn


def _cube(x):
    return _mul(x, _mul(x, x))


CATALOGUE: tuple[Formula, ...] = (
    # kitchen: trays on tw, tl, tk
    _f("k4_tray_total", "kitchen", "counting", "cookies on tk trays of tw x tl = tw tl tk", TRAY, R_TRAY,
       lambda tw, tl, tk: F(tw) * tl * tk, _mul(_mul(V("tw"), V("tl")), V("tk"))),
    _f("k4_tray_rim", "kitchen", "counting", "cookies on the rim of tk trays = (2tw + 2tl - 4) tk", TRAY, R_TRAY,
       lambda tw, tl, tk: (2 * F(tw) + 2 * tl - 4) * tk if tw > 1 and tl > 1 else _bad(),
       _mul(_sub(_add(_add(V("tw"), V("tw")), _add(V("tl"), V("tl"))), _add(C(2), C(2))), V("tk"))),
    _f("k4_tray_inner", "kitchen", "counting", "cookies off the rim of tk trays = (tw - 2)(tl - 2) tk", TRAY, R_TRAY,
       lambda tw, tl, tk: (F(tw) - 2) * (tl - 2) * tk if tw > 2 and tl > 2 else _bad(),
       _mul(_mul(_sub(V("tw"), C(2)), _sub(V("tl"), C(2))), V("tk"))),
    _f("k4_cut_pieces", "kitchen", "counting", "pieces after tw cuts across and tl along, tk layers = (tw+1)(tl+1)tk",
       TRAY, R_TRAY, lambda tw, tl, tk: (F(tw) + 1) * (tl + 1) * tk,
       _mul(_mul(_add(V("tw"), C(1)), _add(V("tl"), C(1))), V("tk"))),
    # kitchen: stacked treats on ck
    _f("k4_cake_layers_sq", "kitchen", "counting", "square tiers 1^2 + ... + ck^2 = ck(ck+1)(2ck+1)/6", CAKE, R_CAKE,
       lambda ck: F(ck) * (ck + 1) * (2 * ck + 1) / 6,
       _div(_mul(_mul(V("ck"), _add(V("ck"), C(1))), _add(_add(V("ck"), V("ck")), C(1))), _mul(C(2), C(3)))),
    _f("k4_candy_box", "kitchen", "volume", "candy box ck x (ck+1) x (ck+2) = ck(ck+1)(ck+2)", CAKE, R_CAKE,
       lambda ck: F(ck) * (ck + 1) * (ck + 2), _mul(_mul(V("ck"), _add(V("ck"), C(1))), _add(V("ck"), C(2)))),
    _f("k4_candy_pyramid_base", "kitchen", "counting", "triangular candy pyramid on a base of side ck+1 = (ck+1)(ck+2)(ck+3)/6",
       CAKE, R_CAKE, lambda ck: (F(ck) + 1) * (ck + 2) * (ck + 3) / 6,
       _div(_mul(_mul(_add(V("ck"), C(1)), _add(V("ck"), C(2))), _add(V("ck"), C(3))), _mul(C(2), C(3)))),
    _f("k4_sum_cubes", "kitchen", "counting", "cubes of sugar 1^3 + ... + ck^3 = (ck(ck+1)/2)^2", CAKE, R_CAKE,
       lambda ck: (F(ck) * (ck + 1) / 2) ** 2,
       _mul(_div(_mul(V("ck"), _add(V("ck"), C(1))), C(2)), _div(_mul(V("ck"), _add(V("ck"), C(1))), C(2)))),
    # kitchen: cakes on ck, tk
    _f("k4_frosting", "kitchen", "area", "frosting a square cake = ck^2 + 4 ck tk", CAKE2, R_CAKE2,
       lambda ck, tk: F(ck) ** 2 + 4 * F(ck) * tk,
       _add(_mul(V("ck"), V("ck")), _mul(_mul(_add(C(2), C(2)), V("ck")), V("tk")))),
    _f("k4_three_tiers", "kitchen", "volume", "three square tiers ck, ck-1, ck-2 of height tk = tk(ck^2 + (ck-1)^2 + (ck-2)^2)",
       CAKE2, R_CAKE2, lambda ck, tk: F(tk) * (F(ck) ** 2 + (F(ck) - 1) ** 2 + (F(ck) - 2) ** 2) if ck > 2 else _bad(),
       _mul(V("tk"), _add(_add(_mul(V("ck"), V("ck")), _mul(_sub(V("ck"), C(1)), _sub(V("ck"), C(1)))),
                         _mul(_sub(V("ck"), C(2)), _sub(V("ck"), C(2)))))),
    # kitchen: dinner on gs, cr
    _f("k4_plates", "kitchen", "counting", "plates for gs guests and 2 hosts over cr courses plus a bread plate = (gs + 2)(cr + 1)",
       DINNER, R_DINNER, lambda gs, cr: (F(gs) + 2) * (cr + 1), _mul(_add(V("gs"), C(2)), _add(V("cr"), C(1)))),
    _f("k4_toasts", "kitchen", "counting", "glass clinks among gs guests and 2 hosts, each course = cr (gs+2)(gs+1)/2",
       DINNER, R_DINNER, lambda gs, cr: F(cr) * (gs + 2) * (gs + 1) / 2,
       _div(_mul(_mul(V("cr"), _add(V("gs"), C(2))), _add(V("gs"), C(1))), C(2))),
    # kitchen: packing cookies on cq, cpb, cbb
    _f("k4_full_boxes", "kitchen", "packing", "full boxes = (cq // cpb) // cbb", COOKIE, R_COOKIE,
       lambda cq, cpb, cbb: F((cq // cpb) // cbb), _div(_div(V("cq"), V("cpb")), V("cbb"))),
    _f("k4_loose_bags", "kitchen", "packing", "full bags not in a full box = (cq // cpb) mod cbb", COOKIE, R_COOKIE,
       lambda cq, cpb, cbb: F((cq // cpb) % cbb), _mod(_div(V("cq"), V("cpb")), V("cbb"))),
    _f("k4_boxes_needed", "kitchen", "packing", "boxes to pack every cookie = ceil(ceil(cq / cpb) / cbb)", COOKIE, R_COOKIE,
       lambda cq, cpb, cbb: _ceil(_ceil(cq, cpb), cbb), _cdiv(_cdiv(V("cq"), V("cpb")), V("cbb"))),
    _f("k4_bag_shortfall", "kitchen", "packing", "cookies to bake to fill the last bag = cpb ceil(cq / cpb) - cq", COOKIE, R_COOKIE,
       lambda cq, cpb, cbb: F(cpb) * _ceil(cq, cpb) - cq, _sub(_mul(V("cpb"), _cdiv(V("cq"), V("cpb"))), V("cq"))),
    # kitchen: dough on gs, gpp, bat
    _f("k4_grams_per_batch", "kitchen", "mass", "grams per batch = gs gpp / bat", DOUGH, R_DOUGH,
       lambda gs, gpp, bat: F(gs) * gpp / bat, _div(_mul(V("gs"), V("gpp")), V("bat"))),
    _f("k4_dough_spare", "kitchen", "mass", "dough for gs + 2 servings per batch, bat batches = (gs + 2) gpp bat", DOUGH, R_DOUGH,
       lambda gs, gpp, bat: (F(gs) + 2) * gpp * bat, _mul(_mul(_add(V("gs"), C(2)), V("gpp")), V("bat"))),
    # garden: beds on bw, bln, bsp
    _f("g4_grid_plants", "garden", "counting", "plants every bsp along both sides = (bw // bsp + 1)(bln // bsp + 1)", BED, R_BED,
       lambda bw, bln, bsp: F(bw // bsp + 1) * (bln // bsp + 1),
       _mul(_add(_div(V("bw"), V("bsp")), C(1)), _add(_div(V("bln"), V("bsp")), C(1)))),
    _f("g4_inner_plants", "garden", "counting", "plants on the inner grid points, bsp beds = (bw - 1)(bln - 1) bsp", BED, R_BED,
       lambda bw, bln, bsp: (F(bw) - 1) * (bln - 1) * bsp, _mul(_mul(_sub(V("bw"), C(1)), _sub(V("bln"), C(1))), V("bsp"))),
    _f("g4_border_area", "garden", "area", "border of width bsp inside the bed = bw bln - (bw - 2bsp)(bln - 2bsp)", BED, R_BED,
       lambda bw, bln, bsp: F(bw) * bln - (F(bw) - 2 * bsp) * (bln - 2 * bsp) if bw > 2 * bsp and bln > 2 * bsp else _bad(),
       _sub(_mul(V("bw"), V("bln")), _mul(_sub(V("bw"), _add(V("bsp"), V("bsp"))), _sub(V("bln"), _add(V("bsp"), V("bsp")))))),
    _f("g4_inner_bed", "garden", "area", "bed left inside a border of width bsp = (bw - 2bsp)(bln - 2bsp)", BED, R_BED,
       lambda bw, bln, bsp: (F(bw) - 2 * bsp) * (bln - 2 * bsp) if bw > 2 * bsp and bln > 2 * bsp else _bad(),
       _mul(_sub(V("bw"), _add(V("bsp"), V("bsp"))), _sub(V("bln"), _add(V("bsp"), V("bsp"))))),
    _f("g4_fence_posts", "garden", "length", "posts every bsp round the bed = 2(bw // bsp + bln // bsp)", BED, R_BED,
       lambda bw, bln, bsp: 2 * F(bw // bsp + bln // bsp),
       _mul(C(2), _add(_div(V("bw"), V("bsp")), _div(V("bln"), V("bsp"))))),
    _f("g4_soil_half", "garden", "volume", "half-depth soil = bw bln bsp / 2", BED, R_BED,
       lambda bw, bln, bsp: F(bw) * bln * bsp / 2, _div(_mul(_mul(V("bw"), V("bln")), V("bsp")), C(2))),
    _f("g4_cross_path", "garden", "area", "cross-shaped path of width bsp = bsp(bw + bln - bsp)", BED, R_BED,
       lambda bw, bln, bsp: F(bsp) * (bw + bln - bsp), _mul(V("bsp"), _sub(_add(V("bw"), V("bln")), V("bsp")))),
    # garden: pot pyramids on tier, nbx
    _f("g4_pot_pyramids", "garden", "counting", "pots in nbx triangular pyramids = nbx tier(tier+1)(tier+2)/6", POTS, R_POTS,
       lambda tier, nbx: F(nbx) * tier * (tier + 1) * (tier + 2) / 6,
       _div(_mul(_mul(_mul(V("nbx"), V("tier")), _add(V("tier"), C(1))), _add(V("tier"), C(2))), _mul(C(2), C(3)))),
    _f("g4_square_pyramids", "garden", "counting", "pots in nbx square pyramids = nbx tier(tier+1)(2tier+1)/6", POTS, R_POTS,
       lambda tier, nbx: F(nbx) * tier * (tier + 1) * (2 * tier + 1) / 6,
       _div(_mul(_mul(_mul(V("nbx"), V("tier")), _add(V("tier"), C(1))), _add(_add(V("tier"), V("tier")), C(1))),
            _mul(C(2), C(3)))),
    _f("g4_triangle_beds", "garden", "counting", "plants in nbx triangular beds = nbx tier(tier+1)/2", POTS, R_POTS,
       lambda tier, nbx: F(nbx) * tier * (tier + 1) / 2, _div(_mul(_mul(V("nbx"), V("tier")), _add(V("tier"), C(1))), C(2))),
    _f("g4_pyramid_shell", "garden", "counting", "visible pots of a triangular pyramid = T(tier) - T(tier - 2), T(n) = n(n+1)(n+2)/6",
       POTS, R_POTS, lambda tier, nbx: (F(tier) * (tier + 1) * (tier + 2) - F(tier - 2) * (tier - 1) * tier) / 6 if tier > 2 else _bad(),
       _div(_sub(_mul(_mul(V("tier"), _add(V("tier"), C(1))), _add(V("tier"), C(2))),
                 _mul(_mul(_sub(V("tier"), C(2)), _sub(V("tier"), C(1))), V("tier"))), _mul(C(2), C(3)))),
    # garden: seeds on sd, spk, pkc
    _f("g4_packets", "garden", "packing", "packets to hold every seed = ceil(sd / spk)", SEEDS, R_SEEDS,
       lambda sd, spk, pkc: _ceil(sd, spk), _cdiv(V("sd"), V("spk"))),
    _f("g4_full_crates", "garden", "packing", "full crates = (sd // spk) // pkc", SEEDS, R_SEEDS,
       lambda sd, spk, pkc: F((sd // spk) // pkc), _div(_div(V("sd"), V("spk")), V("pkc"))),
    _f("g4_spare_packets", "garden", "packing", "full packets outside full crates = (sd // spk) mod pkc", SEEDS, R_SEEDS,
       lambda sd, spk, pkc: F((sd // spk) % pkc), _mod(_div(V("sd"), V("spk")), V("pkc"))),
    _f("g4_crates_needed", "garden", "packing", "crates for every seed = ceil(ceil(sd / spk) / pkc)", SEEDS, R_SEEDS,
       lambda sd, spk, pkc: _ceil(_ceil(sd, spk), pkc), _cdiv(_cdiv(V("sd"), V("spk")), V("pkc"))),
    # workshop: painted cubes on cb
    _f("w4_hidden_cubes", "workshop", "counting", "unpainted unit cubes of a painted cb-cube = (cb - 2)^3", CUBE, R_CUBE,
       lambda cb: (F(cb) - 2) ** 3, _cube(_sub(V("cb"), C(2)))),
    _f("w4_one_face", "workshop", "counting", "unit cubes with one painted face = 6 (cb - 2)^2", CUBE, R_CUBE,
       lambda cb: 6 * (F(cb) - 2) ** 2, _mul(_mul(C(2), C(3)), _mul(_sub(V("cb"), C(2)), _sub(V("cb"), C(2))))),
    _f("w4_painted_any", "workshop", "counting", "unit cubes with paint = cb^3 - (cb - 2)^3", CUBE, R_CUBE,
       lambda cb: F(cb) ** 3 - (F(cb) - 2) ** 3, _sub(_cube(V("cb")), _cube(_sub(V("cb"), C(2))))),
    _f("w4_lattice_nodes", "workshop", "counting", "joints of a cb-cube lattice = (cb + 1)^3", CUBE, R_CUBE,
       lambda cb: (F(cb) + 1) ** 3, _cube(_add(V("cb"), C(1)))),
    _f("w4_lattice_rods", "workshop", "counting", "unit rods of a cb-cube lattice = 3 cb (cb + 1)^2", CUBE, R_CUBE,
       lambda cb: 3 * F(cb) * (cb + 1) ** 2, _mul(_mul(C(3), V("cb")), _mul(_add(V("cb"), C(1)), _add(V("cb"), C(1))))),
    # workshop: boards and boxes on wa, wb, wc
    _f("w4_inner_box", "workshop", "volume", "inside of a box with walls 1 = (wa - 2)(wb - 2)(wc - 2)", WOOD, R_WOOD,
       lambda wa, wb, wc: (F(wa) - 2) * (wb - 2) * (wc - 2) if wc > 2 else _bad(),
       _mul(_mul(_sub(V("wa"), C(2)), _sub(V("wb"), C(2))), _sub(V("wc"), C(2)))),
    _f("w4_box_wood", "workshop", "volume", "wood in a closed box with walls 1 = wa wb wc - (wa - 2)(wb - 2)(wc - 2)", WOOD, R_WOOD,
       lambda wa, wb, wc: F(wa) * wb * wc - (F(wa) - 2) * (wb - 2) * (wc - 2) if wc > 2 else _bad(),
       _sub(_mul(_mul(V("wa"), V("wb")), V("wc")), _mul(_mul(_sub(V("wa"), C(2)), _sub(V("wb"), C(2))), _sub(V("wc"), C(2))))),
    _f("w4_pegboard", "workshop", "counting", "pegs on a wa x wb board, one per unit corner, wc boards = (wa + 1)(wb + 1) wc",
       WOOD, R_WOOD, lambda wa, wb, wc: (F(wa) + 1) * (wb + 1) * wc,
       _mul(_mul(_add(V("wa"), C(1)), _add(V("wb"), C(1))), V("wc"))),
    _f("w4_picture_frame", "workshop", "area", "frame of width wc round a wa x wb picture = (wa + 2wc)(wb + 2wc) - wa wb", WOOD, R_WOOD,
       lambda wa, wb, wc: (F(wa) + 2 * wc) * (wb + 2 * wc) - F(wa) * wb,
       _sub(_mul(_add(V("wa"), _add(V("wc"), V("wc"))), _add(V("wb"), _add(V("wc"), V("wc")))), _mul(V("wa"), V("wb")))),
    _f("w4_shelves", "workshop", "packing", "shelves from a wa-long board: pieces of wb, wc pieces a shelf = (wa // wb) // wc",
       WOOD, R_SHELF, lambda wa, wb, wc: F((wa // wb) // wc), _div(_div(V("wa"), V("wb")), V("wc"))),
    _f("w4_dowel_grid", "workshop", "counting", "dowels every wc on a wa x wb panel = (wa // wc + 1)(wb // wc + 1)", WOOD, R_WOOD,
       lambda wa, wb, wc: F(wa // wc + 1) * (wb // wc + 1),
       _mul(_add(_div(V("wa"), V("wc")), C(1)), _add(_div(V("wb"), V("wc")), C(1)))),
    # workshop: knitting on kr, kst, kc
    _f("w4_stripe_stitches", "workshop", "counting", "stitches in full kc-row stripes = (kr // kc) kc kst", KNIT, R_KNIT,
       lambda kr, kst, kc: F(kr // kc) * kc * kst, _mul(_mul(_div(V("kr"), V("kc")), V("kc")), V("kst"))),
    _f("w4_tri_shawl", "workshop", "counting", "triangular shawl of kr rows on a kst cast-on = kr kst + kr(kr - 1)/2", KNIT, R_KNIT,
       lambda kr, kst, kc: F(kr) * kst + F(kr) * (kr - 1) / 2,
       _add(_mul(V("kr"), V("kst")), _div(_mul(V("kr"), _sub(V("kr"), C(1))), C(2)))),
    _f("w4_colour_rows", "workshop", "counting", "rows of the last colour = kr - kc ((kr - 1) // kc)", KNIT, R_KNIT,
       lambda kr, kst, kc: F(kr) - kc * ((kr - 1) // kc), _sub(V("kr"), _mul(V("kc"), _div(_sub(V("kr"), C(1)), V("kc"))))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
