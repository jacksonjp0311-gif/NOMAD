"""TRANSFER-3: a third never-trained catalogue, the sealed proof suite for INVENT (docs/INVENT.md).

TRANSFER-2's remaining misses are known (cubes, divide-by-6, nested
division) and the INVENT design was tuned on uncommitted dev suites of the
first two catalogues. So INVENT is judged on this **new** catalogue: three
domains no field arm trains on and no earlier catalogue covers (building /
materials, games / tournaments, travel / logistics), new formulas, new input
names, a new seed. Written down, and committed, before any field arm is
measured on it; formulas were chosen as ordinary textbook / everyday
formulas, not by outcome. Built exactly like ``nomad.transfer2``: named int
inputs, stated constants as constant input columns, Fraction ground truth
written independently of the reference tree, rows kept only when the answer
is an integer the reference tree reproduces, 5 public / 3 challenge / 3
final rows (the final split is never read by search or WITNESS).
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("building", "games", "travel")

ROOM = ("wd", "ln", "ht")                  # room / box width, length, height
PLOT = ("pa", "pb", "pc")                  # plot sides pa x pb, path or border width pc
STACK = ("nl",)                            # layers / rows / side count
LEAGUE = ("nt", "rd")                      # teams, rounds (or players per team)
TABLE = ("wn", "dr", "ls", "hc")           # wins, draws, losses, hc = 100
FUEL = ("km", "lp", "pl", "hc")            # distance, litres per 100 km, price per litre, hc = 100
FARE = ("ad", "ch", "fr")                  # adults, children, full fare
CLOCK = ("hh", "mm", "sp", "sx")           # hours, minutes, speed per hour, sx = 60
LOAD = ("pax", "cap", "hire")            # passengers / items, capacity per vehicle / box, hire fee per vehicle

R_ROOM = {"wd": (1, 20), "ln": (1, 20), "ht": (1, 12)}
R_PLOT = {"pa": (1, 30), "pb": (1, 30), "pc": (1, 6)}
R_STACK = {"nl": (2, 40)}
R_LEAGUE = {"nt": (3, 24), "rd": (1, 6)}
R_TABLE = {"wn": (0, 30), "dr": (0, 20), "ls": (0, 30), "hc": ("const", 100)}
R_FUEL = {"km": ("step", 50, 2000, 50), "lp": (3, 15), "pl": (1, 4), "hc": ("const", 100)}
R_FARE = {"ad": (1, 9), "ch": (0, 9), "fr": ("step", 4, 120, 4)}
R_CLOCK = {"hh": (0, 12), "mm": (0, 59), "sp": ("step", 6, 120, 6), "sx": ("const", 60)}
R_LOAD = {"pax": (1, 400), "cap": (2, 60), "hire": (1, 90)}


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


def _ceil(n, k):
    return -(-F(n) // k)


CATALOGUE: tuple[Formula, ...] = (
    # building: rooms and boxes on wd, ln, ht
    _f("b3_walls", "building", "area", "four walls = 2 ht (wd + ln)", ROOM, R_ROOM,
       lambda wd, ln, ht: 2 * F(ht) * (wd + ln), _mul(_add(V("ht"), V("ht")), _add(V("wd"), V("ln")))),
    _f("b3_walls_ceiling", "building", "area", "walls + ceiling = 2 ht (wd + ln) + wd ln", ROOM, R_ROOM,
       lambda wd, ln, ht: 2 * F(ht) * (wd + ln) + F(wd) * ln,
       _add(_mul(_add(V("ht"), V("ht")), _add(V("wd"), V("ln"))), _mul(V("wd"), V("ln")))),
    _f("b3_box_surface_open", "building", "area", "open-top box = wd ln + 2 ht wd + 2 ht ln", ROOM, R_ROOM,
       lambda wd, ln, ht: F(wd) * ln + 2 * F(ht) * wd + 2 * F(ht) * ln,
       _add(_mul(V("wd"), V("ln")), _mul(_add(V("ht"), V("ht")), _add(V("wd"), V("ln"))))),
    _f("b3_diag_sq", "building", "length", "space diagonal squared = wd^2 + ln^2 + ht^2", ROOM, R_ROOM,
       lambda wd, ln, ht: F(wd) ** 2 + F(ln) ** 2 + F(ht) ** 2,
       _add(_add(_mul(V("wd"), V("wd")), _mul(V("ln"), V("ln"))), _mul(V("ht"), V("ht")))),
    _f("b3_two_cubes", "building", "volume", "two cube crates = wd^3 + ht^3", ROOM, R_ROOM,
       lambda wd, ln, ht: F(wd) ** 3 + F(ht) ** 3,
       _add(_mul(V("wd"), _mul(V("wd"), V("wd"))), _mul(V("ht"), _mul(V("ht"), V("ht"))))),
    _f("b3_room_minus_cube", "building", "volume", "room air minus a cube cabinet of side ht = wd ln ht - ht^3", ROOM, R_ROOM,
       lambda wd, ln, ht: F(wd) * ln * ht - F(ht) ** 3 if wd * ln > ht * ht else F(1, 3),
       _sub(_mul(_mul(V("wd"), V("ln")), V("ht")), _mul(V("ht"), _mul(V("ht"), V("ht"))))),
    _f("b3_sq_pyramid", "building", "volume", "square pyramid = wd^2 ht / 3", ROOM, R_ROOM,
       lambda wd, ln, ht: F(wd) ** 2 * ht / 3, _div(_mul(_mul(V("wd"), V("wd")), V("ht")), C(3))),
    _f("b3_wedge", "building", "volume", "wedge (half box) = wd ln ht / 2", ROOM, R_ROOM,
       lambda wd, ln, ht: F(wd) * ln * ht / 2, _div(_mul(_mul(V("wd"), V("ln")), V("ht")), C(2))),
    _f("b3_frame_edges", "building", "length", "box frame edges = 4 (wd + ln + ht)", ROOM, R_ROOM,
       lambda wd, ln, ht: 4 * (F(wd) + ln + ht),
       _mul(_add(C(2), C(2)), _add(_add(V("wd"), V("ln")), V("ht")))),
    _f("b3_square_room_tiles", "building", "area", "floor wd^2 plus a wd x ht strip, quartered = (wd^2 + wd ht) / 4", ROOM, R_ROOM,
       lambda wd, ln, ht: (F(wd) ** 2 + F(wd) * ht) / 4,
       _div(_mul(V("wd"), _add(V("wd"), V("ht"))), _mul(C(2), C(2)))),
    # building: plots with a border on pa, pb, pc
    _f("b3_path_around", "building", "area", "path of width pc around pa x pb = (pa + 2pc)(pb + 2pc) - pa pb", PLOT, R_PLOT,
       lambda pa, pb, pc: (F(pa) + 2 * pc) * (pb + 2 * pc) - F(pa) * pb,
       _sub(_mul(_add(V("pa"), _add(V("pc"), V("pc"))), _add(V("pb"), _add(V("pc"), V("pc")))), _mul(V("pa"), V("pb")))),
    _f("b3_fence_border", "building", "length", "fence around the path = 2(pa + pb) + 8 pc", PLOT, R_PLOT,
       lambda pa, pb, pc: 2 * (F(pa) + pb) + 8 * pc,
       _add(_mul(C(2), _add(V("pa"), V("pb"))), _mul(_add(C(2), C(2)), _add(V("pc"), V("pc"))))),
    _f("b3_slab", "building", "volume", "slab pa x pb, pc quarter-units thick = pa pb pc / 4", PLOT, R_PLOT,
       lambda pa, pb, pc: F(pa) * pb * pc / 4, _div(_mul(_mul(V("pa"), V("pb")), V("pc")), _mul(C(2), C(2)))),
    _f("b3_two_beds", "building", "area", "square bed pa^2 plus square bed pb^2 minus a pc^2 corner", PLOT, R_PLOT,
       lambda pa, pb, pc: F(pa) ** 2 + F(pb) ** 2 - F(pc) ** 2,
       _sub(_add(_mul(V("pa"), V("pa")), _mul(V("pb"), V("pb"))), _mul(V("pc"), V("pc")))),
    _f("b3_cube_shell", "building", "volume", "hollow cube side pa, wall 1 = pa^3 - (pa - 2)^3 (pa > 2)", PLOT, R_PLOT,
       lambda pa, pb, pc: F(pa) ** 3 - (F(pa) - 2) ** 3 if pa > 2 else F(1, 3),
       _sub(_mul(V("pa"), _mul(V("pa"), V("pa"))),
            _mul(_sub(V("pa"), C(2)), _mul(_sub(V("pa"), C(2)), _sub(V("pa"), C(2)))))),
    # games: stacks and counting on nl
    _f("g3_tetra_stack", "games", "counting", "cannonballs in a triangular pyramid = n(n+1)(n+2)/6", STACK, R_STACK,
       lambda n: F(n) * (n + 1) * (n + 2) / 6,
       _div(_mul(_mul(V("nl"), _add(V("nl"), C(1))), _add(V("nl"), C(2))), _mul(C(2), C(3)))),
    _f("g3_pentagonal", "games", "counting", "pentagonal number = n(3n - 1)/2", STACK, R_STACK,
       lambda n: F(n) * (3 * n - 1) / 2, _div(_mul(V("nl"), _sub(_mul(C(3), V("nl")), C(1))), C(2))),
    _f("g3_star_number", "games", "counting", "star number = 6n(n - 1) + 1", STACK, R_STACK,
       lambda n: 6 * F(n) * (n - 1) + 1,
       _add(_mul(_mul(_mul(C(2), C(3)), V("nl")), _sub(V("nl"), C(1))), C(1))),
    _f("g3_squares_on_board", "games", "counting", "squares of every size on an n x n board (= n(n+1)(2n+1)/6) minus the n^2 unit squares", STACK, R_STACK,
       lambda n: F(n) * (n + 1) * (2 * n + 1) / 6 - F(n) ** 2,
       _sub(_div(_mul(_mul(V("nl"), _add(V("nl"), C(1))), _add(_add(V("nl"), V("nl")), C(1))), _mul(C(2), C(3))),
            _mul(V("nl"), V("nl")))),
    _f("g3_cube_count", "games", "counting", "unit cubes in an n-cube with one face layer removed = n^3 - n^2", STACK, R_STACK,
       lambda n: F(n) ** 3 - F(n) ** 2, _mul(_mul(V("nl"), V("nl")), _sub(V("nl"), C(1)))),
    # games: tournaments on nt teams, rd rounds / players
    _f("g3_round_robin", "games", "tournament", "games in rd round-robins of nt teams = rd nt(nt-1)/2", LEAGUE, R_LEAGUE,
       lambda nt, rd: F(rd) * nt * (nt - 1) / 2, _div(_mul(_mul(V("rd"), V("nt")), _sub(V("nt"), C(1))), C(2))),
    _f("g3_cross_handshakes", "games", "tournament", "handshakes between players of different teams = rd^2 nt(nt-1)/2", LEAGUE, R_LEAGUE,
       lambda nt, rd: F(rd) ** 2 * nt * (nt - 1) / 2,
       _div(_mul(_mul(_mul(V("rd"), V("rd")), V("nt")), _sub(V("nt"), C(1))), C(2))),
    _f("g3_league_points_max", "games", "tournament", "points available, 3 per game, home and away = 3 nt(nt-1) rd", LEAGUE, R_LEAGUE,
       lambda nt, rd: 3 * F(nt) * (nt - 1) * rd, _mul(_mul(_mul(C(3), V("rd")), V("nt")), _sub(V("nt"), C(1)))),
    _f("g3_groups_then_final", "games", "tournament", "rd groups of nt teams round-robin, then a knockout of rd = rd nt(nt-1)/2 + rd - 1", LEAGUE, R_LEAGUE,
       lambda nt, rd: F(rd) * nt * (nt - 1) / 2 + rd - 1,
       _add(_div(_mul(_mul(V("rd"), V("nt")), _sub(V("nt"), C(1))), C(2)), _sub(V("rd"), C(1)))),
    # games: league table on wn, dr, ls, hc = 100
    _f("g3_points", "games", "table", "points = 3 wn + dr", TABLE, R_TABLE,
       lambda wn, dr, ls, hc: 3 * F(wn) + dr, _add(_mul(C(3), V("wn")), V("dr"))),
    _f("g3_points_pct", "games", "table", "percent of possible points = 100 (3wn + dr) / (3 (wn + dr + ls))", TABLE, R_TABLE,
       lambda wn, dr, ls, hc: F(hc) * (3 * wn + dr) / (3 * (wn + dr + ls)) if wn + dr + ls else F(1, 3),
       _div(_mul(V("hc"), _add(_mul(C(3), V("wn")), V("dr"))), _mul(C(3), _add(_add(V("wn"), V("dr")), V("ls"))))),
    _f("g3_win_pct", "games", "table", "win percent with draws as halves = 100 (2wn + dr) / (2 (wn + dr + ls))", TABLE, R_TABLE,
       lambda wn, dr, ls, hc: F(hc) * (2 * wn + dr) / (2 * (wn + dr + ls)) if wn + dr + ls else F(1, 3),
       _div(_mul(V("hc"), _add(_add(V("wn"), V("wn")), V("dr"))), _mul(C(2), _add(_add(V("wn"), V("dr")), V("ls"))))),
    _f("g3_points_behind", "games", "table", "points dropped = 3 (dr + ls) - dr = 2 dr + 3 ls", TABLE, R_TABLE,
       lambda wn, dr, ls, hc: 2 * F(dr) + 3 * F(ls), _add(_add(V("dr"), V("dr")), _mul(C(3), V("ls")))),
    # travel: fuel on km, lp (l / 100 km), pl (price per litre), hc = 100
    _f("t3_fuel_cost", "travel", "fuel", "fuel cost = km lp pl / 100", FUEL, R_FUEL,
       lambda km, lp, pl, hc: F(km) * lp * pl / hc, _div(_mul(_mul(V("km"), V("lp")), V("pl")), V("hc"))),
    _f("t3_fuel_return", "travel", "fuel", "return trip fuel cost = 2 km lp pl / 100", FUEL, R_FUEL,
       lambda km, lp, pl, hc: 2 * F(km) * lp * pl / hc,
       _div(_mul(_mul(_add(V("km"), V("km")), V("lp")), V("pl")), V("hc"))),
    _f("t3_fuel_saving", "travel", "fuel", "saving from using lp - 1 instead of lp l/100 km = km pl / 100", FUEL, R_FUEL,
       lambda km, lp, pl, hc: F(km) * lp * pl / hc - F(km) * (lp - 1) * pl / hc,
       _div(_mul(V("km"), V("pl")), V("hc"))),
    _f("t3_fuel_plus_toll", "travel", "fuel", "fuel cost plus a toll of lp per 100 km = km lp pl / 100 + km lp / 100", FUEL, R_FUEL,
       lambda km, lp, pl, hc: F(km) * lp * pl / hc + F(km) * lp / hc,
       _div(_mul(_mul(V("km"), V("lp")), _add(V("pl"), C(1))), V("hc"))),
    _f("t3_litres_two_legs", "travel", "fuel", "litres for km out at lp and back at lp + 2 = km lp / 100 + km (lp + 2) / 100", FUEL, R_FUEL,
       lambda km, lp, pl, hc: F(km) * lp / hc + F(km) * (lp + 2) / hc,
       _div(_mul(V("km"), _add(_add(V("lp"), V("lp")), C(2))), V("hc"))),
    # travel: fares on ad, ch, fr
    _f("t3_family_fare", "travel", "fare", "adults full fare, children half = ad fr + ch fr / 2", FARE, R_FARE,
       lambda ad, ch, fr: F(ad) * fr + F(ch) * fr / 2, _add(_mul(V("ad"), V("fr")), _div(_mul(V("ch"), V("fr")), C(2)))),
    _f("t3_group_discount", "travel", "fare", "a quarter off for everyone = 3 (ad + ch) fr / 4", FARE, R_FARE,
       lambda ad, ch, fr: 3 * (F(ad) + ch) * fr / 4,
       _div(_mul(_mul(C(3), _add(V("ad"), V("ch"))), V("fr")), _mul(C(2), C(2)))),
    _f("t3_return_family", "travel", "fare", "return trip, children half = fr (2 ad + ch)", FARE, R_FARE,
       lambda ad, ch, fr: F(fr) * (2 * ad + ch), _mul(V("fr"), _add(_add(V("ad"), V("ad")), V("ch")))),
    _f("t3_fare_third_off_kids", "travel", "fare", "children a third off = ad fr + 2 ch fr / 3", FARE, R_FARE,
       lambda ad, ch, fr: F(ad) * fr + 2 * F(ch) * fr / 3,
       _add(_mul(V("ad"), V("fr")), _div(_mul(_add(V("ch"), V("ch")), V("fr")), C(3)))),
    # travel: clock on hh, mm, sp (per hour), sx = 60
    _f("t3_distance", "travel", "time", "distance at sp per hour for hh:mm = sp (60 hh + mm) / 60", CLOCK, R_CLOCK,
       lambda hh, mm, sp, sx: F(sp) * (sx * hh + mm) / sx,
       _div(_mul(V("sp"), _add(_mul(V("sx"), V("hh")), V("mm"))), V("sx"))),
    _f("t3_round_trip_minutes", "travel", "time", "minutes for a round trip of hh:mm each way plus a 30 min stop = 2(60 hh + mm) + sx/2", CLOCK, R_CLOCK,
       lambda hh, mm, sp, sx: 2 * (F(sx) * hh + mm) + F(sx) / 2,
       _add(_mul(C(2), _add(_mul(V("sx"), V("hh")), V("mm"))), _div(V("sx"), C(2)))),
    _f("t3_arrival_minute", "travel", "time", "minute of the hour on arrival after hh:mm plus sp minutes = (mm + sp) mod 60", CLOCK, R_CLOCK,
       lambda hh, mm, sp, sx: (F(mm) + sp) % sx, ["mod", _add(V("mm"), V("sp")), V("sx")]),
    _f("t3_arrival_hour", "travel", "time", "hours elapsed when leaving at hh:mm and travelling sp minutes = hh + (mm + sp) div 60", CLOCK, R_CLOCK,
       lambda hh, mm, sp, sx: F(hh) + (F(mm) + sp) // sx, _add(V("hh"), _div(_add(V("mm"), V("sp")), V("sx")))),
    # travel: loads on pax, cap, hire
    _f("t3_vehicles", "travel", "load", "vehicles needed = ceil(pax / cap)", LOAD, R_LOAD,
       lambda pax, cap, hire: _ceil(pax, cap), _div(_sub(_add(V("pax"), V("cap")), C(1)), V("cap"))),
    _f("t3_empty_seats", "travel", "load", "empty seats = cap ceil(pax / cap) - pax", LOAD, R_LOAD,
       lambda pax, cap, hire: cap * _ceil(pax, cap) - pax,
       _sub(_mul(V("cap"), _div(_sub(_add(V("pax"), V("cap")), C(1)), V("cap"))), V("pax"))),
    _f("t3_hire_cost", "travel", "load", "hire cost = hire ceil(pax / cap)", LOAD, R_LOAD,
       lambda pax, cap, hire: hire * _ceil(pax, cap), _mul(V("hire"), _div(_sub(_add(V("pax"), V("cap")), C(1)), V("cap")))),
    _f("t3_last_vehicle", "travel", "load", "passengers in the last vehicle = (pax - 1) mod cap + 1", LOAD, R_LOAD,
       lambda pax, cap, hire: (F(pax) - 1) % cap + 1, _add(["mod", _sub(V("pax"), C(1)), V("cap")], C(1))),
    _f("t3_cost_per_head", "travel", "load", "hire cost per passenger, rounded down = hire ceil(pax / cap) div pax", LOAD, R_LOAD,
       lambda pax, cap, hire: (hire * _ceil(pax, cap)) // pax,
       _div(_mul(V("hire"), _div(_sub(_add(V("pax"), V("cap")), C(1)), V("cap"))), V("pax"))),
)
BY_FAMILY = {f.family: f for f in CATALOGUE}


def is_transfer3(family: str | None) -> bool:
    return bool(family) and family in BY_FAMILY
