"""TRANSFER-8: an eighth never-trained catalogue, the sealed proof suite for
MERGE (probe-equivalent portable-bank blocks are one idea; the evaluations
duplicates would cost buy distinct anchors; docs/MERGE.md).

MERGE was tuned on uncommitted dev suites of the TRANSFER-1/2/3/4 catalogues
(and guarded on dev seeds of the science, TRANSFER-5/6 and SELFEDIT
catalogues), so it is judged on this **new** catalogue: three domains no
field arm trains on and no earlier catalogue covers (brewery, railway,
laundry), new formulas, new input names (disjoint from every earlier
catalogue and training task; checked by grep over nomad/, scripts/,
data/deep/, tests/), a new seed. Written down, and committed, with the MERGE
design frozen, before any field arm is measured on it.

Every formula is a textbook / everyday counting, costing or measuring
formula, none chosen by outcome. Built exactly like ``nomad.transfer7``:
named int inputs, Fraction (or exact integer floor) ground truth written
independently of the reference tree, rows kept only when the answer is an
integer the reference tree reproduces, 5 public / 3 challenge / 3 final rows
(the final split is never read by search or WITNESS).
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("brewery", "railway", "laundry")

BATCH = ("bch", "lbt", "fmd")     # batches, litres per batch, fermentation days
KEG = ("lit", "lpk", "kpp")       # litres, litres per keg, kegs per pallet
TAP = ("tpx", "opn")              # taps, opening hours
TRAIN = ("trn", "cgt", "spc")     # trains, carriages per train, seats per carriage
TRACK = ("tkl", "tkw")            # corridor length, corridor width
FREIGHT = ("frt", "wpt", "wgc")   # freight tonnes, tonnes per wagon, wagons per train
TIMES = ("dph", "rnh")            # departures per hour, running hours
LOAD = ("kgl", "kpm", "mch")      # kg of laundry, kg per machine load, machines
LINEN = ("bdw", "bdl")            # bed width, bed length
WASH = ("wsh", "lpd", "dop")      # washers, loads per washer per day, days open

R_BATCH = {"bch": (1, 30), "lbt": (20, 500), "fmd": (3, 21)}
R_KEG = {"lit": (1, 6000), "lpk": (10, 60), "kpp": (2, 12)}
R_TAP = {"tpx": (1, 24), "opn": (1, 16)}
R_TRAIN = {"trn": (1, 20), "cgt": (2, 12), "spc": (20, 80)}
R_TRACK = {"tkl": (4, 300), "tkw": (4, 40)}
R_FREIGHT = {"frt": (1, 6000), "wpt": (20, 90), "wgc": (5, 40)}
R_TIMES = {"dph": (1, 12), "rnh": (1, 20)}
R_LOAD = {"kgl": (1, 3000), "kpm": (5, 25), "mch": (1, 12)}
R_LINEN = {"bdw": (3, 20), "bdl": (5, 25)}
R_WASH = {"wsh": (1, 12), "lpd": (2, 10), "dop": (1, 7)}


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


def _sq(x):
    return _mul(x, x)


FOUR = _add(C(2), C(2))
FIVE = _add(C(2), C(3))
SIX = _mul(C(2), C(3))
SEVEN = _add(FOUR, C(3))
TEN = _mul(C(2), FIVE)
TWELVE = _mul(FOUR, C(3))
TWENTY = _mul(FOUR, FIVE)

CATALOGUE: tuple[Formula, ...] = (
    # brewery: batches on bch, lbt, fmd
    _f("b8_litres_net", "brewery", "counting", "litres after a 10-litre sampling loss per batch = bch (lbt - 10)", BATCH, R_BATCH,
       lambda bch, lbt, fmd: F(bch) * (lbt - 10), _mul(V("bch"), _sub(V("lbt"), TEN))),
    _f("b8_tank_days", "brewery", "time", "tank-days with one cleaning day per batch = bch fmd + bch", BATCH, R_BATCH,
       lambda bch, lbt, fmd: F(bch) * fmd + bch, _add(_mul(V("bch"), V("fmd")), V("bch"))),
    _f("b8_samples", "brewery", "counting", "gravity samples: one a day plus 2 per batch = bch (fmd + 2)", BATCH, R_BATCH,
       lambda bch, lbt, fmd: F(bch) * (fmd + 2), _mul(V("bch"), _add(V("fmd"), C(2)))),
    _f("b8_weeks", "brewery", "time", "fermentation weeks started, all batches = bch ceil(fmd / 7)", BATCH, R_BATCH,
       lambda bch, lbt, fmd: F(bch) * _ceil(fmd, 7), _mul(V("bch"), _cdiv(V("fmd"), SEVEN))),
    _f("b8_blends", "brewery", "counting", "releases: every batch alone and every blend of two = bch (bch + 1) / 2", BATCH, R_BATCH,
       lambda bch, lbt, fmd: F(bch) * (bch + 1) / 2, _div(_mul(V("bch"), _add(V("bch"), C(1))), C(2))),
    _f("b8_tasting", "brewery", "counting", "tasting litres: 2 per batch-day = 2 bch fmd, plus one litre per batch", BATCH, R_BATCH,
       lambda bch, lbt, fmd: 2 * F(bch) * fmd + bch, _add(_mul(_add(V("bch"), V("bch")), V("fmd")), V("bch"))),
    # brewery: kegs on lit, lpk, kpp
    _f("b8_kegs", "brewery", "packing", "kegs for every litre = ceil(lit / lpk)", KEG, R_KEG,
       lambda lit, lpk, kpp: _ceil(lit, lpk), _cdiv(V("lit"), V("lpk"))),
    _f("b8_pallets", "brewery", "packing", "pallets for those kegs = ceil(ceil(lit / lpk) / kpp)", KEG, R_KEG,
       lambda lit, lpk, kpp: _ceil(_ceil(lit, lpk), kpp), _cdiv(_cdiv(V("lit"), V("lpk")), V("kpp"))),
    _f("b8_full_pallets", "brewery", "packing", "pallets of full kegs = (lit // lpk) // kpp", KEG, R_KEG,
       lambda lit, lpk, kpp: F((lit // lpk) // kpp), _div(_div(V("lit"), V("lpk")), V("kpp"))),
    _f("b8_dregs", "brewery", "packing", "litres left after the full kegs = lit mod lpk", KEG, R_KEG,
       lambda lit, lpk, kpp: F(lit % lpk), _mod(V("lit"), V("lpk"))),
    _f("b8_keg_room", "brewery", "packing", "empty litres in the last keg = lpk ceil(lit / lpk) - lit", KEG, R_KEG,
       lambda lit, lpk, kpp: F(lpk) * _ceil(lit, lpk) - lit, _sub(_mul(V("lpk"), _cdiv(V("lit"), V("lpk"))), V("lit"))),
    _f("b8_loose_kegs", "brewery", "packing", "full kegs left off the full pallets = (lit // lpk) mod kpp", KEG, R_KEG,
       lambda lit, lpk, kpp: F((lit // lpk) % kpp), _mod(_div(V("lit"), V("lpk")), V("kpp"))),
    # brewery: taps on tpx, opn
    _f("b8_pours", "brewery", "counting", "pints at 12 per tap-hour = 12 tpx opn", TAP, R_TAP,
       lambda tpx, opn: 12 * F(tpx) * opn, _mul(_mul(TWELVE, V("tpx")), V("opn"))),
    _f("b8_line_cleans", "brewery", "counting", "line cleans: every 4 hours plus once at close, per tap = tpx (opn // 4 + 1)", TAP, R_TAP,
       lambda tpx, opn: F(tpx) * (opn // 4 + 1), _mul(V("tpx"), _add(_div(V("opn"), FOUR), C(1)))),
    _f("b8_tap_pairs", "brewery", "counting", "ordered side-by-side comparisons of two taps = tpx (tpx - 1)", TAP, R_TAP,
       lambda tpx, opn: F(tpx) * (tpx - 1), _mul(V("tpx"), _sub(V("tpx"), C(1)))),
    _f("b8_staff", "brewery", "packing", "bar staff, one per 6 taps rounded up, each hour = opn ceil(tpx / 6)", TAP, R_TAP,
       lambda tpx, opn: F(opn) * _ceil(tpx, 6), _mul(V("opn"), _cdiv(V("tpx"), SIX))),
    _f("b8_glasses", "brewery", "counting", "glasses: 12 pints per tap-hour plus 20 spare = 12 tpx opn + 20", TAP, R_TAP,
       lambda tpx, opn: 12 * F(tpx) * opn + 20, _add(_mul(_mul(TWELVE, V("tpx")), V("opn")), TWENTY)),
    # railway: trains on trn, cgt, spc
    _f("r8_seats", "railway", "counting", "seats = trn cgt spc", TRAIN, R_TRAIN,
       lambda trn, cgt, spc: F(trn) * cgt * spc, _mul(_mul(V("trn"), V("cgt")), V("spc"))),
    _f("r8_first_class", "railway", "counting", "one carriage per train at half seating = trn ((cgt - 1) spc + spc // 2)", TRAIN, R_TRAIN,
       lambda trn, cgt, spc: F(trn) * ((cgt - 1) * spc + spc // 2),
       _mul(V("trn"), _add(_mul(_sub(V("cgt"), C(1)), V("spc")), _div(V("spc"), C(2))))),
    _f("r8_doors", "railway", "counting", "doors: 4 per carriage and 2 cab doors per train = 4 trn cgt + 2 trn", TRAIN, R_TRAIN,
       lambda trn, cgt, spc: 4 * F(trn) * cgt + 2 * F(trn), _add(_mul(_mul(FOUR, V("trn")), V("cgt")), _add(V("trn"), V("trn")))),
    _f("r8_couplings", "railway", "counting", "couplings between carriages = trn (cgt - 1)", TRAIN, R_TRAIN,
       lambda trn, cgt, spc: F(trn) * (cgt - 1), _mul(V("trn"), _sub(V("cgt"), C(1)))),
    _f("r8_capacity", "railway", "counting", "capacity with 20 standing per carriage = trn cgt (spc + 20)", TRAIN, R_TRAIN,
       lambda trn, cgt, spc: F(trn) * cgt * (spc + 20), _mul(_mul(V("trn"), V("cgt")), _add(V("spc"), TWENTY))),
    # railway: corridor on tkl, tkw
    _f("r8_corridor", "railway", "area", "corridor area with a 1-unit drain each side = tkl (tkw + 2)", TRACK, R_TRACK,
       lambda tkl, tkw: F(tkl) * (tkw + 2), _mul(V("tkl"), _add(V("tkw"), C(2)))),
    _f("r8_fence", "railway", "length", "fence round the corridor plus a 4-unit gate frame = 2 (tkl + tkw) + 4", TRACK, R_TRACK,
       lambda tkl, tkw: 2 * (F(tkl) + tkw) + 4, _add(_mul(C(2), _add(V("tkl"), V("tkw"))), FOUR)),
    _f("r8_inner", "railway", "area", "corridor less a 1-unit verge all round = (tkl - 2)(tkw - 2)", TRACK, R_TRACK,
       lambda tkl, tkw: (F(tkl) - 2) * (tkw - 2), _mul(_sub(V("tkl"), C(2)), _sub(V("tkw"), C(2)))),
    _f("r8_verge", "railway", "area", "the verge itself = tkl tkw - (tkl - 2)(tkw - 2)", TRACK, R_TRACK,
       lambda tkl, tkw: F(tkl) * tkw - (F(tkl) - 2) * (tkw - 2),
       _sub(_mul(V("tkl"), V("tkw")), _mul(_sub(V("tkl"), C(2)), _sub(V("tkw"), C(2))))),
    _f("r8_strips", "railway", "packing", "3-wide ballast strips along the length = tkl ceil(tkw / 3)", TRACK, R_TRACK,
       lambda tkl, tkw: F(tkl) * _ceil(tkw, 3), _mul(V("tkl"), _cdiv(V("tkw"), C(3)))),
    _f("r8_squares", "railway", "area", "sum of the squared sides = tkl^2 + tkw^2", TRACK, R_TRACK,
       lambda tkl, tkw: F(tkl) ** 2 + F(tkw) ** 2, _add(_sq(V("tkl")), _sq(V("tkw")))),
    # railway: freight on frt, wpt, wgc
    _f("r8_wagons", "railway", "packing", "wagons for every tonne = ceil(frt / wpt)", FREIGHT, R_FREIGHT,
       lambda frt, wpt, wgc: _ceil(frt, wpt), _cdiv(V("frt"), V("wpt"))),
    _f("r8_freight_trains", "railway", "packing", "trains for those wagons = ceil(ceil(frt / wpt) / wgc)", FREIGHT, R_FREIGHT,
       lambda frt, wpt, wgc: _ceil(_ceil(frt, wpt), wgc), _cdiv(_cdiv(V("frt"), V("wpt")), V("wgc"))),
    _f("r8_full_trains", "railway", "packing", "trains of full wagons = (frt // wpt) // wgc", FREIGHT, R_FREIGHT,
       lambda frt, wpt, wgc: F((frt // wpt) // wgc), _div(_div(V("frt"), V("wpt")), V("wgc"))),
    _f("r8_spare_wagons", "railway", "packing", "full wagons left off the full trains = (frt // wpt) mod wgc", FREIGHT, R_FREIGHT,
       lambda frt, wpt, wgc: F((frt // wpt) % wgc), _mod(_div(V("frt"), V("wpt")), V("wgc"))),
    _f("r8_tonne_room", "railway", "packing", "spare tonnes in the last wagon = wpt ceil(frt / wpt) - frt", FREIGHT, R_FREIGHT,
       lambda frt, wpt, wgc: F(wpt) * _ceil(frt, wpt) - frt, _sub(_mul(V("wpt"), _cdiv(V("frt"), V("wpt"))), V("frt"))),
    # railway: timetable on dph, rnh
    _f("r8_departures", "railway", "counting", "departures including the last train = dph rnh + 1", TIMES, R_TIMES,
       lambda dph, rnh: F(dph) * rnh + 1, _add(_mul(V("dph"), V("rnh")), C(1))),
    _f("r8_movements", "railway", "counting", "movements, both directions = 2 dph rnh", TIMES, R_TIMES,
       lambda dph, rnh: 2 * F(dph) * rnh, _mul(_add(V("dph"), V("dph")), V("rnh"))),
    _f("r8_crews", "railway", "packing", "crews, one per 4 departures rounded up, each hour = rnh ceil(dph / 4)", TIMES, R_TIMES,
       lambda dph, rnh: F(rnh) * _ceil(dph, 4), _mul(V("rnh"), _cdiv(V("dph"), FOUR))),
    _f("r8_meets", "railway", "counting", "pairs of departures that could meet = dph rnh (dph rnh - 1) / 2", TIMES, R_TIMES,
       lambda dph, rnh: F(dph * rnh) * (dph * rnh - 1) / 2,
       _div(_mul(_mul(V("dph"), V("rnh")), _sub(_mul(V("dph"), V("rnh")), C(1))), C(2))),
    # laundry: loads on kgl, kpm, mch
    _f("l8_loads", "laundry", "packing", "machine loads for every kg = ceil(kgl / kpm)", LOAD, R_LOAD,
       lambda kgl, kpm, mch: _ceil(kgl, kpm), _cdiv(V("kgl"), V("kpm"))),
    _f("l8_rounds", "laundry", "packing", "rounds of all machines = ceil(ceil(kgl / kpm) / mch)", LOAD, R_LOAD,
       lambda kgl, kpm, mch: _ceil(_ceil(kgl, kpm), mch), _cdiv(_cdiv(V("kgl"), V("kpm")), V("mch"))),
    _f("l8_full_loads", "laundry", "packing", "full loads = kgl // kpm", LOAD, R_LOAD,
       lambda kgl, kpm, mch: F(kgl // kpm), _div(V("kgl"), V("kpm"))),
    _f("l8_last_load", "laundry", "packing", "kg in the part load = kgl mod kpm", LOAD, R_LOAD,
       lambda kgl, kpm, mch: F(kgl % kpm), _mod(V("kgl"), V("kpm"))),
    _f("l8_idle_slots", "laundry", "packing", "machine slots unused in the last round = mch ceil(ceil(kgl/kpm)/mch) - ceil(kgl/kpm)", LOAD, R_LOAD,
       lambda kgl, kpm, mch: F(mch) * _ceil(_ceil(kgl, kpm), mch) - _ceil(kgl, kpm),
       _sub(_mul(V("mch"), _cdiv(_cdiv(V("kgl"), V("kpm")), V("mch"))), _cdiv(V("kgl"), V("kpm")))),
    # laundry: linen on bdw, bdl
    _f("l8_sheet", "laundry", "area", "flat sheet with a 2-unit tuck on every side = (bdw + 4)(bdl + 4)", LINEN, R_LINEN,
       lambda bdw, bdl: (F(bdw) + 4) * (bdl + 4), _mul(_add(V("bdw"), FOUR), _add(V("bdl"), FOUR))),
    _f("l8_hem", "laundry", "length", "hem round the bed outline plus 4 for the corners = 2 (bdw + bdl) + 4", LINEN, R_LINEN,
       lambda bdw, bdl: 2 * (F(bdw) + bdl) + 4, _add(_mul(C(2), _add(V("bdw"), V("bdl"))), FOUR)),
    _f("l8_quarter", "laundry", "area", "one quarter after folding in half both ways = (bdw // 2)(bdl // 2)", LINEN, R_LINEN,
       lambda bdw, bdl: F(bdw // 2) * (bdl // 2), _mul(_div(V("bdw"), C(2)), _div(V("bdl"), C(2)))),
    _f("l8_set", "laundry", "area", "flat and fitted sheet plus a pillow strip = 2 bdw bdl + 2 bdw", LINEN, R_LINEN,
       lambda bdw, bdl: 2 * F(bdw) * bdl + 2 * F(bdw), _add(_mul(_add(V("bdw"), V("bdw")), V("bdl")), _add(V("bdw"), V("bdw")))),
    _f("l8_squares", "laundry", "area", "sum of the squared sides = bdw^2 + bdl^2", LINEN, R_LINEN,
       lambda bdw, bdl: F(bdw) ** 2 + F(bdl) ** 2, _add(_sq(V("bdw")), _sq(V("bdl")))),
    # laundry: washers on wsh, lpd, dop
    _f("l8_week_loads", "laundry", "counting", "loads a week = wsh lpd dop", WASH, R_WASH,
       lambda wsh, lpd, dop: F(wsh) * lpd * dop, _mul(_mul(V("wsh"), V("lpd")), V("dop"))),
    _f("l8_service", "laundry", "counting", "loads with one service slot per washer-day = wsh dop (lpd - 1)", WASH, R_WASH,
       lambda wsh, lpd, dop: F(wsh) * dop * (lpd - 1), _mul(_mul(V("wsh"), V("dop")), _sub(V("lpd"), C(1)))),
    _f("l8_scoops", "laundry", "counting", "detergent scoops: 2 per load plus 1 per washer-day = wsh dop (2 lpd + 1)", WASH, R_WASH,
       lambda wsh, lpd, dop: F(wsh) * dop * (2 * lpd + 1), _mul(_mul(V("wsh"), V("dop")), _add(_add(V("lpd"), V("lpd")), C(1)))),
    _f("l8_pairs", "laundry", "counting", "washer pairs scheduled together, each day = dop wsh (wsh - 1) / 2", WASH, R_WASH,
       lambda wsh, lpd, dop: F(dop) * wsh * (wsh - 1) / 2, _div(_mul(_mul(V("dop"), V("wsh")), _sub(V("wsh"), C(1))), C(2))),
    _f("l8_tokens", "laundry", "counting", "tokens: one per load plus 3 per washer = wsh lpd dop + 3 wsh", WASH, R_WASH,
       lambda wsh, lpd, dop: F(wsh) * lpd * dop + 3 * F(wsh), _add(_mul(_mul(V("wsh"), V("lpd")), V("dop")), _mul(C(3), V("wsh")))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
