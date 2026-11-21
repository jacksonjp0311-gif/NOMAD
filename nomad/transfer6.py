"""TRANSFER-6: a sixth never-trained catalogue, the sealed proof suite for
GRAPH (co-occurrence graph + spreading activation proposing two-block anchor
pairs; docs/GRAPH.md).

GRAPH was tuned on uncommitted dev suites of the TRANSFER-1/2/3/4
catalogues, so it is judged on this **new** catalogue: three domains no
field arm trains on and no earlier catalogue covers (music / concerts, farm /
livestock, warehouse / office), new formulas, new input names (disjoint from
every earlier catalogue, the science, text and bridge catalogues and all
training tasks), a new seed. Written down, and committed, with the GRAPH
design frozen, before any field arm is measured on it.

Every formula is a textbook / everyday counting, costing or measuring
formula, none chosen by outcome; composite totals (sums of two or three
products) sit next to products, packing and floor/ceiling formulas, as in
earlier catalogues. Built exactly like ``nomad.transfer5``: named int
inputs, Fraction (or exact integer floor) ground truth written independently
of the reference tree, rows kept only when the answer is an integer the
reference tree reproduces, 5 public / 3 challenge / 3 final rows (the final
split is never read by search or WITNESS).
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("music", "farm", "warehouse")

SET = ("sng", "mnu")              # songs in a set, minutes per song
GIG = ("sng", "mnu", "brk")       # songs, minutes per song, minutes per break
BAND = ("plr", "ins")             # players, instruments per player
CHOIR = ("vrow", "vps")           # choir rows, voices in the front row
TOUR = ("shw", "tkt", "vnu")      # shows, tickets per show, venue fee units
FARM = ("cow", "hen")             # cows, hens
PEN = ("pnw", "pnl", "pns")       # pen width, pen length, posts spacing / pens
FEED = ("hd", "kgh", "dys")       # head of stock, kg per head per day, days
EGGS = ("egg", "epc", "cpt")      # eggs, eggs per carton, cartons per tray
SHELF = ("shf", "bxs", "lyr")     # shelves, boxes per shelf, layers
PALLET = ("itm", "ipb", "bpp")    # items, items per box, boxes per pallet
DESK = ("dsk", "chr")             # desks, chairs per desk
FLOOR = ("flw", "fll")            # office floor width, length

R_SET = {"sng": (1, 30), "mnu": (2, 9)}
R_GIG = {"sng": (2, 30), "mnu": (2, 9), "brk": (1, 20)}
R_BAND = {"plr": (2, 40), "ins": (1, 4)}
R_CHOIR = {"vrow": (1, 20), "vps": (4, 30)}
R_TOUR = {"shw": (1, 30), "tkt": (10, 500), "vnu": (1, 50)}
R_FARM = {"cow": (0, 60), "hen": (0, 200)}
R_PEN = {"pnw": (3, 40), "pnl": (3, 60), "pns": (1, 6)}
R_FEED = {"hd": (1, 80), "kgh": (1, 12), "dys": (1, 30)}
R_EGGS = {"egg": (1, 3000), "epc": (6, 30), "cpt": (2, 12)}
R_SHELF = {"shf": (1, 30), "bxs": (2, 20), "lyr": (1, 6)}
R_PALLET = {"itm": (1, 5000), "ipb": (4, 48), "bpp": (2, 40)}
R_DESK = {"dsk": (1, 80), "chr": (1, 4)}
R_FLOOR = {"flw": (4, 60), "fll": (4, 80)}


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


def _sq(x):
    return _mul(x, x)


FOUR = _add(C(2), C(2))
SIX = _mul(C(2), C(3))

CATALOGUE: tuple[Formula, ...] = (
    # music: sets on sng, mnu
    _f("m6_set_minutes", "music", "time", "minutes of music plus a 2-minute gap between songs = sng mnu + 2(sng - 1)", SET, R_SET,
       lambda sng, mnu: F(sng) * mnu + 2 * (sng - 1), _add(_mul(V("sng"), V("mnu")), _add(_sub(V("sng"), C(1)), _sub(V("sng"), C(1))))),
    _f("m6_setlist_orders", "music", "counting", "opener-closer choices from sng songs, mnu nights = mnu sng (sng - 1)", SET, R_SET,
       lambda sng, mnu: F(mnu) * sng * (sng - 1), _mul(_mul(V("mnu"), V("sng")), _sub(V("sng"), C(1)))),
    _f("m6_medley_pairs", "music", "counting", "two-song medleys from sng songs, mnu shows = mnu sng (sng - 1)/2", SET, R_SET,
       lambda sng, mnu: F(mnu) * sng * (sng - 1) / 2, _div(_mul(_mul(V("mnu"), V("sng")), _sub(V("sng"), C(1))), C(2))),
    # music: gig on sng, mnu, brk
    _f("m6_gig_length", "music", "time", "two sets of sng songs and one break = 2 sng mnu + brk", GIG, R_GIG,
       lambda sng, mnu, brk: 2 * F(sng) * mnu + brk, _add(_mul(_add(V("sng"), V("sng")), V("mnu")), V("brk"))),
    _f("m6_gig_breaks", "music", "time", "a break after every song but the last = sng mnu + (sng - 1) brk", GIG, R_GIG,
       lambda sng, mnu, brk: F(sng) * mnu + (sng - 1) * brk, _add(_mul(V("sng"), V("mnu")), _mul(_sub(V("sng"), C(1)), V("brk")))),
    _f("m6_hour_blocks", "music", "packing", "hour-long slots the gig needs = ceil((sng mnu + brk) / 60)", GIG, R_GIG,
       lambda sng, mnu, brk: _ceil(F(sng) * mnu + brk, 60),
       _cdiv(_add(_mul(V("sng"), V("mnu")), V("brk")), _mul(_mul(C(3), FOUR), _add(C(2), C(3))))),
    # music: band on plr, ins
    _f("m6_cables", "music", "counting", "cables: one per instrument plus one per player = plr ins + plr", BAND, R_BAND,
       lambda plr, ins: F(plr) * ins + plr, _add(_mul(V("plr"), V("ins")), V("plr"))),
    _f("m6_duets", "music", "counting", "duets between players of different instruments, ins each = ins^2 plr(plr-1)/2", BAND, R_BAND,
       lambda plr, ins: F(ins) ** 2 * plr * (plr - 1) / 2, _div(_mul(_mul(_sq(V("ins")), V("plr")), _sub(V("plr"), C(1))), C(2))),
    _f("m6_stands", "music", "counting", "music stands, one per two players rounded up, per instrument = ins ceil(plr / 2)", BAND, R_BAND,
       lambda plr, ins: F(ins) * _ceil(plr, 2), _mul(V("ins"), _cdiv(V("plr"), C(2)))),
    # music: choir on vrow, vps
    _f("m6_choir_size", "music", "counting", "vrow rows, vps in front, 2 more each row = vrow vps + vrow(vrow-1)", CHOIR, R_CHOIR,
       lambda vrow, vps: F(vrow) * vps + F(vrow) * (vrow - 1), _add(_mul(V("vrow"), V("vps")), _mul(V("vrow"), _sub(V("vrow"), C(1))))),
    _f("m6_choir_risers", "music", "counting", "riser steps: row k needs k steps = vps vrow(vrow+1)/2", CHOIR, R_CHOIR,
       lambda vrow, vps: F(vps) * vrow * (vrow + 1) / 2, _div(_mul(_mul(V("vps"), V("vrow")), _add(V("vrow"), C(1))), C(2))),
    _f("m6_choir_ends", "music", "counting", "singers at the row ends plus the front row = 2 vrow + vps - 2", CHOIR, R_CHOIR,
       lambda vrow, vps: 2 * F(vrow) + vps - 2, _sub(_add(_add(V("vrow"), V("vrow")), V("vps")), C(2))),
    # music: tour on shw, tkt, vnu
    _f("m6_tour_seats", "music", "counting", "seats sold with 2 guest seats a show = shw (tkt + 2)", TOUR, R_TOUR,
       lambda shw, tkt, vnu: F(shw) * (tkt + 2), _mul(V("shw"), _add(V("tkt"), C(2)))),
    _f("m6_tour_net", "music", "money", "ticket units minus venue fees = shw tkt - shw vnu", TOUR, R_TOUR,
       lambda shw, tkt, vnu: F(shw) * tkt - F(shw) * vnu, _sub(_mul(V("shw"), V("tkt")), _mul(V("shw"), V("vnu")))),
    _f("m6_tour_split", "music", "money", "net per show split 3 ways = (tkt - vnu) // 3, over shw shows", TOUR,
       {"shw": (1, 30), "tkt": (60, 500), "vnu": (1, 50)}, lambda shw, tkt, vnu: F(shw) * ((tkt - vnu) // 3),
       _mul(V("shw"), _div(_sub(V("tkt"), V("vnu")), C(3)))),
    # farm: animals on cow, hen
    _f("f6_legs", "farm", "counting", "legs = 4 cow + 2 hen", FARM, R_FARM,
       lambda cow, hen: 4 * F(cow) + 2 * hen, _add(_mul(FOUR, V("cow")), _add(V("hen"), V("hen")))),
    _f("f6_heads_legs", "farm", "counting", "heads plus legs = 5 cow + 3 hen", FARM, R_FARM,
       lambda cow, hen: 5 * F(cow) + 3 * hen, _add(_mul(_add(C(2), C(3)), V("cow")), _mul(C(3), V("hen")))),
    _f("f6_feed_buckets", "farm", "counting", "buckets: 3 per cow, 1 per 10 hens rounded up = 3 cow + ceil(hen / 10)", FARM, R_FARM,
       lambda cow, hen: 3 * F(cow) + _ceil(hen, 10), _add(_mul(C(3), V("cow")), _cdiv(V("hen"), _mul(C(2), _add(C(2), C(3)))))),
    _f("f6_pairs", "farm", "counting", "cow-hen pairs plus cow pairs = cow hen + cow(cow-1)/2", FARM, R_FARM,
       lambda cow, hen: F(cow) * hen + F(cow) * (cow - 1) / 2, _add(_mul(V("cow"), V("hen")), _div(_mul(V("cow"), _sub(V("cow"), C(1))), C(2)))),
    # farm: pens on pnw, pnl, pns
    _f("f6_pen_posts", "farm", "counting", "fence posts every pns round the pen = 2 (pnw // pns + pnl // pns)", PEN, R_PEN,
       lambda pnw, pnl, pns: 2 * F(pnw // pns + pnl // pns), _mul(C(2), _add(_div(V("pnw"), V("pns")), _div(V("pnl"), V("pns"))))),
    _f("f6_pen_split", "farm", "length", "fence for a pen split into pns strips = 2 pnl + (pns + 1) pnw", PEN, R_PEN,
       lambda pnw, pnl, pns: 2 * F(pnl) + (pns + 1) * pnw, _add(_add(V("pnl"), V("pnl")), _mul(_add(V("pns"), C(1)), V("pnw")))),
    _f("f6_pen_grass", "farm", "area", "grass left inside a path of width pns = (pnw - 2pns)(pnl - 2pns)", PEN, R_PEN,
       lambda pnw, pnl, pns: (F(pnw) - 2 * pns) * (pnl - 2 * pns) if pnw > 2 * pns and pnl > 2 * pns else _bad(),
       _mul(_sub(V("pnw"), _add(V("pns"), V("pns"))), _sub(V("pnl"), _add(V("pns"), V("pns"))))),
    _f("f6_pen_rows", "farm", "area", "pns pens in a row sharing walls, area plus wall length = pns pnw pnl + (pns + 1) pnl", PEN, R_PEN,
       lambda pnw, pnl, pns: F(pns) * pnw * pnl + (pns + 1) * pnl,
       _add(_mul(_mul(V("pns"), V("pnw")), V("pnl")), _mul(_add(V("pns"), C(1)), V("pnl")))),
    # farm: feed on hd, kgh, dys
    _f("f6_feed_total", "farm", "mass", "feed with a 2-day reserve = hd kgh (dys + 2)", FEED, R_FEED,
       lambda hd, kgh, dys: F(hd) * kgh * (dys + 2), _mul(_mul(V("hd"), V("kgh")), _add(V("dys"), C(2)))),
    _f("f6_feed_sacks", "farm", "packing", "25-kg sacks for the period = ceil(hd kgh dys / 25)", FEED, R_FEED,
       lambda hd, kgh, dys: _ceil(F(hd) * kgh * dys, 25),
       _cdiv(_mul(_mul(V("hd"), V("kgh")), V("dys")), _mul(_add(C(2), C(3)), _add(C(2), C(3))))),
    _f("f6_feed_growth", "farm", "mass", "herd grows by one head a day: kgh (hd dys + dys(dys-1)/2)", FEED, R_FEED,
       lambda hd, kgh, dys: F(kgh) * (F(hd) * dys + F(dys) * (dys - 1) / 2),
       _mul(V("kgh"), _add(_mul(V("hd"), V("dys")), _div(_mul(V("dys"), _sub(V("dys"), C(1))), C(2))))),
    # farm: eggs on egg, epc, cpt
    _f("f6_cartons", "farm", "packing", "cartons for every egg = ceil(egg / epc)", EGGS, R_EGGS,
       lambda egg, epc, cpt: _ceil(egg, epc), _cdiv(V("egg"), V("epc"))),
    _f("f6_trays", "farm", "packing", "trays for those cartons = ceil(ceil(egg / epc) / cpt)", EGGS, R_EGGS,
       lambda egg, epc, cpt: _ceil(_ceil(egg, epc), cpt), _cdiv(_cdiv(V("egg"), V("epc")), V("cpt"))),
    _f("f6_full_trays", "farm", "packing", "trays filled by full cartons = (egg // epc) // cpt", EGGS, R_EGGS,
       lambda egg, epc, cpt: F((egg // epc) // cpt), _div(_div(V("egg"), V("epc")), V("cpt"))),
    _f("f6_loose_cartons", "farm", "packing", "full cartons outside full trays = (egg // epc) mod cpt", EGGS, R_EGGS,
       lambda egg, epc, cpt: F((egg // epc) % cpt), _mod(_div(V("egg"), V("epc")), V("cpt"))),
    _f("f6_loose_eggs", "farm", "packing", "eggs left after full trays = egg - epc cpt ((egg // epc) // cpt)", EGGS, R_EGGS,
       lambda egg, epc, cpt: F(egg) - epc * cpt * ((egg // epc) // cpt),
       _sub(V("egg"), _mul(_mul(V("epc"), V("cpt")), _div(_div(V("egg"), V("epc")), V("cpt"))))),
    # warehouse: shelves on shf, bxs, lyr
    _f("w6_boxes", "warehouse", "counting", "boxes plus one spare per shelf = shf (bxs lyr + 1)", SHELF, R_SHELF,
       lambda shf, bxs, lyr: F(shf) * (bxs * lyr + 1), _mul(V("shf"), _add(_mul(V("bxs"), V("lyr")), C(1)))),
    _f("w6_top_and_rest", "warehouse", "counting", "boxes when the top layer holds 2 fewer = shf (bxs lyr - 2)", SHELF,
       {"shf": (1, 30), "bxs": (3, 20), "lyr": (1, 6)}, lambda shf, bxs, lyr: F(shf) * (bxs * lyr - 2),
       _mul(V("shf"), _sub(_mul(V("bxs"), V("lyr")), C(2)))),
    _f("w6_labels", "warehouse", "counting", "labels: one per box, one per shelf, one per layer = shf bxs lyr + shf + shf lyr", SHELF, R_SHELF,
       lambda shf, bxs, lyr: F(shf) * bxs * lyr + shf + F(shf) * lyr,
       _add(_add(_mul(_mul(V("shf"), V("bxs")), V("lyr")), V("shf")), _mul(V("shf"), V("lyr")))),
    _f("w6_brackets", "warehouse", "counting", "brackets: 4 per layer and 2 per shelf = 4 shf lyr + 2 shf", SHELF, R_SHELF,
       lambda shf, bxs, lyr: 4 * F(shf) * lyr + 2 * F(shf), _add(_mul(_mul(FOUR, V("shf")), V("lyr")), _add(V("shf"), V("shf")))),
    # warehouse: pallets on itm, ipb, bpp
    _f("w6_boxes_needed", "warehouse", "packing", "boxes for every item = ceil(itm / ipb)", PALLET, R_PALLET,
       lambda itm, ipb, bpp: _ceil(itm, ipb), _cdiv(V("itm"), V("ipb"))),
    _f("w6_pallets", "warehouse", "packing", "pallets for every box = ceil(ceil(itm / ipb) / bpp)", PALLET, R_PALLET,
       lambda itm, ipb, bpp: _ceil(_ceil(itm, ipb), bpp), _cdiv(_cdiv(V("itm"), V("ipb")), V("bpp"))),
    _f("w6_full_pallets", "warehouse", "packing", "pallets of full boxes = (itm // ipb) // bpp", PALLET, R_PALLET,
       lambda itm, ipb, bpp: F((itm // ipb) // bpp), _div(_div(V("itm"), V("ipb")), V("bpp"))),
    _f("w6_box_gap", "warehouse", "packing", "items to add to fill the last box = ipb ceil(itm / ipb) - itm", PALLET, R_PALLET,
       lambda itm, ipb, bpp: F(ipb) * _ceil(itm, ipb) - itm, _sub(_mul(V("ipb"), _cdiv(V("itm"), V("ipb"))), V("itm"))),
    # warehouse / office: desks on dsk, chr
    _f("w6_seats", "warehouse", "counting", "seats: chr per desk plus 2 per 4 desks rounded up = dsk chr + 2 ceil(dsk / 4)", DESK, R_DESK,
       lambda dsk, chr: F(dsk) * chr + 2 * _ceil(dsk, 4), _add(_mul(V("dsk"), V("chr")), _mul(C(2), _cdiv(V("dsk"), FOUR)))),
    _f("w6_sockets", "warehouse", "counting", "sockets: 2 per desk and 1 per chair = 2 dsk + dsk chr", DESK, R_DESK,
       lambda dsk, chr: 2 * F(dsk) + F(dsk) * chr, _add(_add(V("dsk"), V("dsk")), _mul(V("dsk"), V("chr")))),
    _f("w6_meetings", "warehouse", "counting", "one-to-ones among everyone seated = dsk chr (dsk chr - 1)/2", DESK, R_DESK,
       lambda dsk, chr: F(dsk) * chr * (dsk * chr - 1) / 2,
       _div(_mul(_mul(V("dsk"), V("chr")), _sub(_mul(V("dsk"), V("chr")), C(1))), C(2))),
    # warehouse / office: floor on flw, fll
    _f("w6_floor_border", "warehouse", "area", "1-unit walkway round the floor = flw fll - (flw - 2)(fll - 2)", FLOOR, R_FLOOR,
       lambda flw, fll: F(flw) * fll - (F(flw) - 2) * (fll - 2),
       _sub(_mul(V("flw"), V("fll")), _mul(_sub(V("flw"), C(2)), _sub(V("fll"), C(2))))),
    _f("w6_floor_tiles", "warehouse", "counting", "2x2 tiles over the floor, rounded up = ceil(flw / 2) ceil(fll / 2)", FLOOR, R_FLOOR,
       lambda flw, fll: _ceil(flw, 2) * _ceil(fll, 2), _mul(_cdiv(V("flw"), C(2)), _cdiv(V("fll"), C(2)))),
    _f("w6_floor_and_walls", "warehouse", "area", "floor plus walls 3 high = flw fll + 6 (flw + fll)", FLOOR, R_FLOOR,
       lambda flw, fll: F(flw) * fll + 6 * (F(flw) + fll), _add(_mul(V("flw"), V("fll")), _mul(SIX, _add(V("flw"), V("fll"))))),
    _f("w6_grid_points", "warehouse", "counting", "column grid points every unit = (flw + 1)(fll + 1)", FLOOR, R_FLOOR,
       lambda flw, fll: (F(flw) + 1) * (fll + 1), _mul(_add(V("flw"), C(1)), _add(V("fll"), C(1)))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
