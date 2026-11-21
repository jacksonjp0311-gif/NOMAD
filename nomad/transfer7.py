"""TRANSFER-7: a seventh never-trained catalogue, the sealed proof suite for
ROUTE_CUT (learned ROUTE relevance fills the tail of the PORT_SCAN cut when
memory is large; docs/ROUTE_CUT.md).

ROUTE_CUT was tuned on uncommitted dev suites of the TRANSFER-1/2/3/4
catalogues, so it is judged on this **new** catalogue: three domains no
field arm trains on and no earlier catalogue covers (clinic / pharmacy,
print shop / bindery, harbour / port), new formulas, new input names
(disjoint from every earlier catalogue, the science, text, bridge and
selfedit catalogues and all training tasks), a new seed. Written down, and
committed, with the ROUTE_CUT design frozen, before any field arm is
measured on it.

Every formula is a textbook / everyday counting, costing or measuring
formula, none chosen by outcome; composite totals (sums of two or three
products) sit next to products, packing and floor/ceiling formulas, as in
earlier catalogues. Built exactly like ``nomad.transfer6``: named int
inputs, Fraction (or exact integer floor) ground truth written independently
of the reference tree, rows kept only when the answer is an integer the
reference tree reproduces, 5 public / 3 challenge / 3 final rows (the final
split is never read by search or WITNESS).
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("clinic", "print", "harbour")

DOSE = ("pat", "dpd", "trd")      # patients, doses per day, treatment days
WARD = ("wrd", "bpw")             # wards, beds per ward
NURSE = ("nrs", "sft")            # nurses, shifts per nurse per week
PILL = ("pil", "ppb", "bpc")      # pills, pills per bottle, bottles per case
BOOK = ("pgs", "cps")             # pages per book, copies
SHEET = ("lfs", "ups", "rms")     # leaves, pages up per sheet, sheets per ream (/100)
POSTER = ("pstw", "psth")         # poster width, height
BIND = ("vol", "sgv", "pps")      # volumes, signatures per volume, pages per signature
SHIP = ("shp", "cbx")             # ships, containers per ship
CRANE = ("crn", "lph", "wkh")     # cranes, lifts per crane-hour, work hours
DOCK = ("dkw", "dkl")             # quay width, quay length
CARGO = ("crg", "upb", "bpk")     # cargo units, units per bin, bins per truck

R_DOSE = {"pat": (1, 40), "dpd": (1, 6), "trd": (1, 21)}
R_WARD = {"wrd": (1, 30), "bpw": (2, 40)}
R_NURSE = {"nrs": (1, 60), "sft": (1, 7)}
R_PILL = {"pil": (1, 5000), "ppb": (10, 120), "bpc": (2, 24)}
R_BOOK = {"pgs": (4, 400), "cps": (1, 50)}
R_SHEET = {"lfs": (1, 3000), "ups": (1, 8), "rms": (2, 10)}
R_POSTER = {"pstw": (2, 60), "psth": (2, 80)}
R_BIND = {"vol": (1, 20), "sgv": (1, 30), "pps": (4, 32)}
R_SHIP = {"shp": (1, 30), "cbx": (1, 400)}
R_CRANE = {"crn": (1, 12), "lph": (5, 40), "wkh": (1, 24)}
R_DOCK = {"dkw": (4, 50), "dkl": (5, 90)}
R_CARGO = {"crg": (1, 6000), "upb": (4, 60), "bpk": (2, 30)}


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
FIVE = _add(C(2), C(3))
SEVEN = _add(FOUR, C(3))
TEN = _mul(C(2), FIVE)

CATALOGUE: tuple[Formula, ...] = (
    # clinic: doses on pat, dpd, trd
    _f("c7_doses", "clinic", "counting", "doses with one spare per patient = pat (dpd trd + 1)", DOSE, R_DOSE,
       lambda pat, dpd, trd: F(pat) * (dpd * trd + 1), _mul(V("pat"), _add(_mul(V("dpd"), V("trd")), C(1)))),
    _f("c7_doses_loading", "clinic", "counting", "a double first-day dose = pat dpd (trd + 1)", DOSE, R_DOSE,
       lambda pat, dpd, trd: F(pat) * dpd * (trd + 1), _mul(_mul(V("pat"), V("dpd")), _add(V("trd"), C(1)))),
    _f("c7_doses_taper", "clinic", "counting", "last two days at one dose = pat (dpd (trd - 2) + 2)", DOSE,
       {"pat": (1, 40), "dpd": (1, 6), "trd": (3, 21)}, lambda pat, dpd, trd: F(pat) * (dpd * (trd - 2) + 2),
       _mul(V("pat"), _add(_mul(V("dpd"), _sub(V("trd"), C(2))), C(2)))),
    _f("c7_weeks", "clinic", "time", "treatment weeks started = ceil(trd / 7), for pat patients", DOSE, R_DOSE,
       lambda pat, dpd, trd: F(pat) * _ceil(trd, 7), _mul(V("pat"), _cdiv(V("trd"), SEVEN))),
    # clinic: wards on wrd, bpw
    _f("c7_beds", "clinic", "counting", "beds plus one isolation bed per ward = wrd bpw + wrd", WARD, R_WARD,
       lambda wrd, bpw: F(wrd) * bpw + wrd, _add(_mul(V("wrd"), V("bpw")), V("wrd"))),
    _f("c7_bed_pairs", "clinic", "counting", "neighbouring bed pairs, beds in a line per ward = wrd (bpw - 1)", WARD, R_WARD,
       lambda wrd, bpw: F(wrd) * (bpw - 1), _mul(V("wrd"), _sub(V("bpw"), C(1)))),
    _f("c7_rounds", "clinic", "counting", "doctor visits: every bed twice and every ward once = 2 wrd bpw + wrd", WARD, R_WARD,
       lambda wrd, bpw: 2 * F(wrd) * bpw + wrd, _add(_mul(_add(V("wrd"), V("wrd")), V("bpw")), V("wrd"))),
    _f("c7_ward_transfers", "clinic", "counting", "ordered moves between wards = bpw wrd (wrd - 1)", WARD, R_WARD,
       lambda wrd, bpw: F(bpw) * wrd * (wrd - 1), _mul(_mul(V("bpw"), V("wrd")), _sub(V("wrd"), C(1)))),
    # clinic: nurses on nrs, sft
    _f("c7_shifts", "clinic", "counting", "shifts worked plus 3 cover shifts a week = nrs sft + 3", NURSE, R_NURSE,
       lambda nrs, sft: F(nrs) * sft + 3, _add(_mul(V("nrs"), V("sft")), C(3))),
    _f("c7_handovers", "clinic", "counting", "handovers between nurses = nrs (nrs - 1) / 2, sft weeks", NURSE, R_NURSE,
       lambda nrs, sft: F(sft) * nrs * (nrs - 1) / 2, _div(_mul(_mul(V("sft"), V("nrs")), _sub(V("nrs"), C(1))), C(2))),
    _f("c7_hours", "clinic", "time", "hours: 8 per shift plus 1 handover hour per nurse = 8 nrs sft + nrs", NURSE, R_NURSE,
       lambda nrs, sft: 8 * F(nrs) * sft + nrs, _add(_mul(_mul(_mul(C(2), FOUR), V("nrs")), V("sft")), V("nrs"))),
    _f("c7_teams", "clinic", "packing", "teams of 4 nurses, rounded up, per shift = sft ceil(nrs / 4)", NURSE, R_NURSE,
       lambda nrs, sft: F(sft) * _ceil(nrs, 4), _mul(V("sft"), _cdiv(V("nrs"), FOUR))),
    # clinic: pharmacy on pil, ppb, bpc
    _f("c7_bottles", "clinic", "packing", "bottles for every pill = ceil(pil / ppb)", PILL, R_PILL,
       lambda pil, ppb, bpc: _ceil(pil, ppb), _cdiv(V("pil"), V("ppb"))),
    _f("c7_cases", "clinic", "packing", "cases for those bottles = ceil(ceil(pil / ppb) / bpc)", PILL, R_PILL,
       lambda pil, ppb, bpc: _ceil(_ceil(pil, ppb), bpc), _cdiv(_cdiv(V("pil"), V("ppb")), V("bpc"))),
    _f("c7_full_cases", "clinic", "packing", "cases of full bottles = (pil // ppb) // bpc", PILL, R_PILL,
       lambda pil, ppb, bpc: F((pil // ppb) // bpc), _div(_div(V("pil"), V("ppb")), V("bpc"))),
    _f("c7_loose_pills", "clinic", "packing", "pills left over after full bottles = pil mod ppb", PILL, R_PILL,
       lambda pil, ppb, bpc: F(pil % ppb), _mod(V("pil"), V("ppb"))),
    _f("c7_case_space", "clinic", "packing", "pills a case holds minus those packed in the last case = ppb bpc - pil mod (ppb bpc)", PILL, R_PILL,
       lambda pil, ppb, bpc: F(ppb * bpc - pil % (ppb * bpc)), _sub(_mul(V("ppb"), V("bpc")), _mod(V("pil"), _mul(V("ppb"), V("bpc"))))),
    # print: books on pgs, cps
    _f("p7_sheets", "print", "packing", "sheets, two pages a sheet, per copy = cps ceil(pgs / 2)", BOOK, R_BOOK,
       lambda pgs, cps: F(cps) * _ceil(pgs, 2), _mul(V("cps"), _cdiv(V("pgs"), C(2)))),
    _f("p7_pages_cover", "print", "counting", "printed pages with a 4-page cover = cps (pgs + 4)", BOOK, R_BOOK,
       lambda pgs, cps: F(cps) * (pgs + 4), _mul(V("cps"), _add(V("pgs"), FOUR))),
    _f("p7_proofs", "print", "counting", "proof pages: the whole book twice plus one page per copy = 2 pgs + cps", BOOK, R_BOOK,
       lambda pgs, cps: 2 * F(pgs) + cps, _add(_add(V("pgs"), V("pgs")), V("cps"))),
    _f("p7_spreads", "print", "counting", "facing-page spreads per book = pgs // 2 - 1, over cps copies", BOOK, R_BOOK,
       lambda pgs, cps: F(cps) * (pgs // 2 - 1), _mul(V("cps"), _sub(_div(V("pgs"), C(2)), C(1)))),
    _f("p7_signatures", "print", "packing", "16-page signatures per copy, rounded up = cps ceil(pgs / 16)", BOOK, R_BOOK,
       lambda pgs, cps: F(cps) * _ceil(pgs, 16), _mul(V("cps"), _cdiv(V("pgs"), _mul(FOUR, FOUR)))),
    # print: sheets on lfs, ups, rms
    _f("p7_press_sheets", "print", "packing", "press sheets for lfs leaves, ups up = ceil(lfs / ups)", SHEET, R_SHEET,
       lambda lfs, ups, rms: _ceil(lfs, ups), _cdiv(V("lfs"), V("ups"))),
    _f("p7_reams", "print", "packing", "reams of rms hundred sheets = ceil(ceil(lfs / ups) / (100 rms))", SHEET, R_SHEET,
       lambda lfs, ups, rms: _ceil(_ceil(lfs, ups), 100 * rms),
       _cdiv(_cdiv(V("lfs"), V("ups")), _mul(_mul(TEN, TEN), V("rms")))),
    _f("p7_waste", "print", "packing", "blank slots on the last sheet = ups ceil(lfs / ups) - lfs", SHEET, R_SHEET,
       lambda lfs, ups, rms: F(ups) * _ceil(lfs, ups) - lfs, _sub(_mul(V("ups"), _cdiv(V("lfs"), V("ups"))), V("lfs"))),
    _f("p7_makeready", "print", "counting", "sheets with 10 make-ready sheets per ream started = ceil(lfs/ups) + 10 rms", SHEET, R_SHEET,
       lambda lfs, ups, rms: _ceil(lfs, ups) + 10 * rms, _add(_cdiv(V("lfs"), V("ups")), _mul(TEN, V("rms")))),
    # print: posters on pstw, psth
    _f("p7_poster_trim", "print", "area", "a 1-unit trim margin all round = pstw psth - (pstw - 2)(psth - 2)", POSTER, R_POSTER,
       lambda pstw, psth: F(pstw) * psth - (F(pstw) - 2) * (psth - 2),
       _sub(_mul(V("pstw"), V("psth")), _mul(_sub(V("pstw"), C(2)), _sub(V("psth"), C(2))))),
    _f("p7_poster_frame", "print", "length", "frame round the poster plus a 2-unit hanger = 2 (pstw + psth) + 2", POSTER, R_POSTER,
       lambda pstw, psth: 2 * (F(pstw) + psth) + 2, _add(_mul(C(2), _add(V("pstw"), V("psth"))), C(2))),
    _f("p7_poster_tiles", "print", "packing", "A-size tiles 3 by 4 needed = ceil(pstw / 3) ceil(psth / 4)", POSTER, R_POSTER,
       lambda pstw, psth: _ceil(pstw, 3) * _ceil(psth, 4), _mul(_cdiv(V("pstw"), C(3)), _cdiv(V("psth"), FOUR))),
    _f("p7_poster_mount", "print", "area", "mount board with a 2-unit border = (pstw + 4)(psth + 4)", POSTER, R_POSTER,
       lambda pstw, psth: (F(pstw) + 4) * (psth + 4), _mul(_add(V("pstw"), FOUR), _add(V("psth"), FOUR))),
    _f("p7_poster_diag", "print", "area", "sum of the squared sides = pstw^2 + psth^2", POSTER, R_POSTER,
       lambda pstw, psth: F(pstw) ** 2 + F(psth) ** 2, _add(_sq(V("pstw")), _sq(V("psth")))),
    # print: binding on vol, sgv, pps
    _f("p7_set_pages", "print", "counting", "pages in the set plus 2 endpapers a volume = vol (sgv pps + 2)", BIND, R_BIND,
       lambda vol, sgv, pps: F(vol) * (sgv * pps + 2), _mul(V("vol"), _add(_mul(V("sgv"), V("pps")), C(2)))),
    _f("p7_stitches", "print", "counting", "stitches: 3 per signature and 2 per volume = 3 vol sgv + 2 vol", BIND, R_BIND,
       lambda vol, sgv, pps: 3 * F(vol) * sgv + 2 * F(vol), _add(_mul(_mul(C(3), V("vol")), V("sgv")), _add(V("vol"), V("vol")))),
    _f("p7_folds", "print", "counting", "folded quarter-sheets: vol sgv (pps // 4)", BIND, R_BIND,
       lambda vol, sgv, pps: F(vol) * sgv * (pps // 4), _mul(_mul(V("vol"), V("sgv")), _div(V("pps"), FOUR))),
    _f("p7_index", "print", "counting", "index entries: one per page and one per signature = vol sgv pps + vol sgv", BIND, R_BIND,
       lambda vol, sgv, pps: F(vol) * sgv * pps + F(vol) * sgv,
       _add(_mul(_mul(V("vol"), V("sgv")), V("pps")), _mul(V("vol"), V("sgv")))),
    # harbour: ships on shp, cbx
    _f("h7_moves", "harbour", "counting", "crane moves: unload and reload every box = 2 shp cbx", SHIP, R_SHIP,
       lambda shp, cbx: 2 * F(shp) * cbx, _mul(_add(V("shp"), V("shp")), V("cbx"))),
    _f("h7_lines", "harbour", "counting", "mooring lines: 6 per ship plus 1 per 50 boxes rounded up = 6 shp + ceil(cbx/50)", SHIP, R_SHIP,
       lambda shp, cbx: 6 * F(shp) + _ceil(cbx, 50), _add(_mul(_mul(C(2), C(3)), V("shp")), _cdiv(V("cbx"), _mul(TEN, FIVE)))),
    _f("h7_berth_pairs", "harbour", "counting", "ship pairs plus box total = shp(shp-1)/2 + shp cbx", SHIP, R_SHIP,
       lambda shp, cbx: F(shp) * (shp - 1) / 2 + F(shp) * cbx,
       _add(_div(_mul(V("shp"), _sub(V("shp"), C(1))), C(2)), _mul(V("shp"), V("cbx")))),
    _f("h7_stack", "harbour", "packing", "stacks 5 high per ship = shp ceil(cbx / 5)", SHIP, R_SHIP,
       lambda shp, cbx: F(shp) * _ceil(cbx, 5), _mul(V("shp"), _cdiv(V("cbx"), FIVE))),
    # harbour: cranes on crn, lph, wkh
    _f("h7_lifts", "harbour", "counting", "lifts with a 1-hour break per crane = crn lph (wkh - 1)", CRANE,
       {"crn": (1, 12), "lph": (5, 40), "wkh": (2, 24)}, lambda crn, lph, wkh: F(crn) * lph * (wkh - 1),
       _mul(_mul(V("crn"), V("lph")), _sub(V("wkh"), C(1)))),
    _f("h7_lifts_ramp", "harbour", "counting", "first hour at half rate: crn (lph wkh - lph // 2)", CRANE, R_CRANE,
       lambda crn, lph, wkh: F(crn) * (lph * wkh - lph // 2), _mul(V("crn"), _sub(_mul(V("lph"), V("wkh")), _div(V("lph"), C(2))))),
    _f("h7_crane_shifts", "harbour", "time", "8-hour shifts per crane, rounded up = crn ceil(wkh / 8)", CRANE, R_CRANE,
       lambda crn, lph, wkh: F(crn) * _ceil(wkh, 8), _mul(V("crn"), _cdiv(V("wkh"), _mul(C(2), FOUR)))),
    _f("h7_crane_total", "harbour", "counting", "lifts plus 2 safety checks per crane-hour = crn wkh (lph + 2)", CRANE, R_CRANE,
       lambda crn, lph, wkh: F(crn) * wkh * (lph + 2), _mul(_mul(V("crn"), V("wkh")), _add(V("lph"), C(2)))),
    # harbour: quay on dkw, dkl
    _f("h7_quay_edge", "harbour", "length", "fendered edge: two lengths and one width = 2 dkl + dkw", DOCK, R_DOCK,
       lambda dkw, dkl: 2 * F(dkl) + dkw, _add(_add(V("dkl"), V("dkl")), V("dkw"))),
    _f("h7_quay_lane", "harbour", "area", "quay less a 2-unit lane round it = (dkw - 4)(dkl - 4)", DOCK, R_DOCK,
       lambda dkw, dkl: (F(dkw) - 4) * (dkl - 4) if dkw > 4 and dkl > 4 else _bad(),
       _mul(_sub(V("dkw"), FOUR), _sub(V("dkl"), FOUR))),
    _f("h7_bollards", "harbour", "counting", "bollards every 5 units along both lengths, plus corners = 2 (dkl // 5) + 4", DOCK, R_DOCK,
       lambda dkw, dkl: 2 * F(dkl // 5) + 4, _add(_mul(C(2), _div(V("dkl"), FIVE)), FOUR)),
    _f("h7_quay_paint", "harbour", "area", "quay plus a 1-unit kerb strip on the length = dkw dkl + 2 dkl", DOCK, R_DOCK,
       lambda dkw, dkl: F(dkw) * dkl + 2 * F(dkl), _add(_mul(V("dkw"), V("dkl")), _add(V("dkl"), V("dkl")))),
    # harbour: cargo on crg, upb, bpk
    _f("h7_bins", "harbour", "packing", "bins for every cargo unit = ceil(crg / upb)", CARGO, R_CARGO,
       lambda crg, upb, bpk: _ceil(crg, upb), _cdiv(V("crg"), V("upb"))),
    _f("h7_trucks", "harbour", "packing", "trucks for those bins = ceil(ceil(crg / upb) / bpk)", CARGO, R_CARGO,
       lambda crg, upb, bpk: _ceil(_ceil(crg, upb), bpk), _cdiv(_cdiv(V("crg"), V("upb")), V("bpk"))),
    _f("h7_full_trucks", "harbour", "packing", "trucks of full bins = (crg // upb) // bpk", CARGO, R_CARGO,
       lambda crg, upb, bpk: F((crg // upb) // bpk), _div(_div(V("crg"), V("upb")), V("bpk"))),
    _f("h7_spare_bins", "harbour", "packing", "full bins left after full trucks = (crg // upb) mod bpk", CARGO, R_CARGO,
       lambda crg, upb, bpk: F((crg // upb) % bpk), _mod(_div(V("crg"), V("upb")), V("bpk"))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
