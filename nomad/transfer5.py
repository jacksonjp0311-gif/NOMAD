"""TRANSFER-5: a fifth never-trained catalogue, the sealed proof suite for
ROUTE (learned routing table over the portable bank; docs/ROUTE.md).

ROUTE was tuned on uncommitted dev suites of the TRANSFER-1/2/3/4
catalogues, so it is judged on this **new** catalogue: three domains no
field arm trains on and no earlier catalogue covers (sport / tournaments,
transit / parking, venue / stage), new formulas, new input names (disjoint
from every earlier catalogue, the science and text catalogues, the bridge
catalogue and all training tasks), a new seed. Written down, and committed,
with the ROUTE design frozen, before any field arm is measured on it.

Every formula is a textbook / everyday counting, packing or measuring
formula, none chosen by outcome. Built exactly like ``nomad.transfer4``:
named int inputs, Fraction (or exact integer floor) ground truth written
independently of the reference tree, rows kept only when the answer is an
integer the reference tree reproduces, 5 public / 3 challenge / 3 final rows
(the final split is never read by search or WITNESS).
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DOMAINS = ("sport", "transit", "venue")

LEAGUE = ("tm", "rds")            # teams, round-robin cycles
SQUAD = ("tm", "sqd")             # teams, players per squad
COURT = ("cwd", "cln", "lnw")     # court width, length, line / margin width
MEET = ("ath", "lan", "evn")      # athletes, lanes, events
BUS = ("rid", "bcp", "dpt")       # riders, bus seats, buses per depot
TRAIN = ("ncar", "spr", "rpc")    # cars, seats per row, rows per car
LOT = ("lotw", "lotd", "stl")     # lot width, depth, stall / lamp spacing
STAIR = ("flr", "stp")            # floors, steps per flight
TIER = ("rws", "fst")             # rows of seats, seats in the front row
STAGE = ("stg",)                  # side of a square stage / light rig
TIX = ("tix", "grp", "blk")       # tickets, tickets per group, groups per block

R_LEAGUE = {"tm": (2, 30), "rds": (1, 4)}
R_SQUAD = {"tm": (2, 20), "sqd": (2, 25)}
R_COURT = {"cwd": (4, 40), "cln": (4, 60), "lnw": (1, 4)}
R_MEET = {"ath": (1, 200), "lan": (4, 10), "evn": (1, 12)}
R_BUS = {"rid": (1, 2000), "bcp": (8, 60), "dpt": (2, 10)}
R_TRAIN = {"ncar": (2, 14), "spr": (2, 6), "rpc": (5, 30)}
R_LOT = {"lotw": (5, 120), "lotd": (5, 90), "stl": (2, 9)}
R_STAIR = {"flr": (2, 40), "stp": (6, 24)}
R_TIER = {"rws": (1, 40), "fst": (4, 30)}
R_STAGE = {"stg": (3, 25)}
R_TIX = {"tix": (1, 5000), "grp": (2, 30), "blk": (2, 12)}


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


SIX = _mul(C(2), C(3))

CATALOGUE: tuple[Formula, ...] = (
    # sport: league on tm, rds
    _f("s5_round_robin", "sport", "counting", "games in rds round-robin cycles of tm teams = rds tm(tm-1)/2", LEAGUE, R_LEAGUE,
       lambda tm, rds: F(rds) * tm * (tm - 1) / 2, _div(_mul(_mul(V("rds"), V("tm")), _sub(V("tm"), C(1))), C(2))),
    _f("s5_max_points", "sport", "counting", "most points a team can take, 3 a win, rds cycles = 3 rds (tm - 1)", LEAGUE, R_LEAGUE,
       lambda tm, rds: 3 * F(rds) * (tm - 1), _mul(_mul(C(3), V("rds")), _sub(V("tm"), C(1)))),
    _f("s5_fixtures_home_away", "sport", "counting", "home and away fixtures, rds cycles = rds tm (tm - 1)", LEAGUE, R_LEAGUE,
       lambda tm, rds: F(rds) * tm * (tm - 1), _mul(_mul(V("rds"), V("tm")), _sub(V("tm"), C(1)))),
    _f("s5_matchdays", "sport", "counting", "matchdays of a double round robin with tm teams, rds cycles = 2 rds (tm - 1)", LEAGUE, R_LEAGUE,
       lambda tm, rds: 2 * F(rds) * (tm - 1), _mul(_add(V("rds"), V("rds")), _sub(V("tm"), C(1)))),
    _f("s5_triangles", "sport", "counting", "three-team mini leagues from tm teams, rds sets = rds tm(tm-1)(tm-2)/6", LEAGUE, R_LEAGUE,
       lambda tm, rds: F(rds) * tm * (tm - 1) * (tm - 2) / 6,
       _div(_mul(_mul(_mul(V("rds"), V("tm")), _sub(V("tm"), C(1))), _sub(V("tm"), C(2))), SIX)),
    # sport: squads on tm, sqd
    _f("s5_cross_handshakes", "sport", "counting", "handshakes between players of different teams = sqd^2 tm(tm-1)/2", SQUAD, R_SQUAD,
       lambda tm, sqd: F(sqd) ** 2 * tm * (tm - 1) / 2,
       _div(_mul(_mul(_sq(V("sqd")), V("tm")), _sub(V("tm"), C(1))), C(2))),
    _f("s5_all_handshakes", "sport", "counting", "handshakes among all tm sqd players = tm sqd (tm sqd - 1)/2", SQUAD, R_SQUAD,
       lambda tm, sqd: F(tm) * sqd * (tm * sqd - 1) / 2,
       _div(_mul(_mul(V("tm"), V("sqd")), _sub(_mul(V("tm"), V("sqd")), C(1))), C(2))),
    _f("s5_bench", "sport", "counting", "players on the bench, 11 on the field per team = tm (sqd - 11)", SQUAD,
       {"tm": (2, 20), "sqd": (12, 25)}, lambda tm, sqd: F(tm) * (sqd - 11),
       _mul(V("tm"), _sub(V("sqd"), _add(_mul(C(3), C(3)), C(2))))),
    _f("s5_captain_pairs", "sport", "counting", "captain + vice-captain choices over all teams = tm sqd (sqd - 1)", SQUAD, R_SQUAD,
       lambda tm, sqd: F(tm) * sqd * (sqd - 1), _mul(_mul(V("tm"), V("sqd")), _sub(V("sqd"), C(1)))),
    # sport: court on cwd, cln, lnw
    _f("s5_court_margin", "sport", "area", "margin of width lnw inside the court = cwd cln - (cwd - 2lnw)(cln - 2lnw)", COURT, R_COURT,
       lambda cwd, cln, lnw: F(cwd) * cln - (F(cwd) - 2 * lnw) * (cln - 2 * lnw) if cwd > 2 * lnw and cln > 2 * lnw else _bad(),
       _sub(_mul(V("cwd"), V("cln")), _mul(_sub(V("cwd"), _add(V("lnw"), V("lnw"))), _sub(V("cln"), _add(V("lnw"), V("lnw")))))),
    _f("s5_court_with_runoff", "sport", "area", "court plus a run-off of lnw all round = (cwd + 2lnw)(cln + 2lnw)", COURT, R_COURT,
       lambda cwd, cln, lnw: (F(cwd) + 2 * lnw) * (cln + 2 * lnw),
       _mul(_add(V("cwd"), _add(V("lnw"), V("lnw"))), _add(V("cln"), _add(V("lnw"), V("lnw"))))),
    _f("s5_court_tiles", "sport", "counting", "lnw-square tiles to cover the court = (cwd // lnw)(cln // lnw)", COURT, R_COURT,
       lambda cwd, cln, lnw: F(cwd // lnw) * (cln // lnw), _mul(_div(V("cwd"), V("lnw")), _div(V("cln"), V("lnw")))),
    _f("s5_net_posts", "sport", "length", "posts every lnw round the court = 2 (cwd // lnw + cln // lnw)", COURT, R_COURT,
       lambda cwd, cln, lnw: 2 * F(cwd // lnw + cln // lnw),
       _mul(C(2), _add(_div(V("cwd"), V("lnw")), _div(V("cln"), V("lnw"))))),
    _f("s5_center_cross", "sport", "area", "centre cross of width lnw = lnw (cwd + cln - lnw)", COURT, R_COURT,
       lambda cwd, cln, lnw: F(lnw) * (cwd + cln - lnw), _mul(V("lnw"), _sub(_add(V("cwd"), V("cln")), V("lnw")))),
    # sport: athletics meet on ath, lan, evn
    _f("s5_heats", "sport", "packing", "heats to run every athlete in lan lanes = ceil(ath / lan)", MEET, R_MEET,
       lambda ath, lan, evn: _ceil(ath, lan), _cdiv(V("ath"), V("lan"))),
    _f("s5_empty_lanes", "sport", "packing", "empty lanes over all heats = lan ceil(ath / lan) - ath", MEET, R_MEET,
       lambda ath, lan, evn: F(lan) * _ceil(ath, lan) - ath, _sub(_mul(V("lan"), _cdiv(V("ath"), V("lan"))), V("ath"))),
    _f("s5_all_heats", "sport", "packing", "heats over evn events = evn ceil(ath / lan)", MEET, R_MEET,
       lambda ath, lan, evn: F(evn) * _ceil(ath, lan), _mul(V("evn"), _cdiv(V("ath"), V("lan")))),
    _f("s5_podiums", "sport", "counting", "podium orders over evn events of lan finalists = evn lan(lan-1)(lan-2)", MEET, R_MEET,
       lambda ath, lan, evn: F(evn) * lan * (lan - 1) * (lan - 2),
       _mul(_mul(_mul(V("evn"), V("lan")), _sub(V("lan"), C(1))), _sub(V("lan"), C(2)))),
    # transit: buses on rid, bcp, dpt
    _f("t5_buses", "transit", "packing", "buses for every rider = ceil(rid / bcp)", BUS, R_BUS,
       lambda rid, bcp, dpt: _ceil(rid, bcp), _cdiv(V("rid"), V("bcp"))),
    _f("t5_depots", "transit", "packing", "depots for those buses = ceil(ceil(rid / bcp) / dpt)", BUS, R_BUS,
       lambda rid, bcp, dpt: _ceil(_ceil(rid, bcp), dpt), _cdiv(_cdiv(V("rid"), V("bcp")), V("dpt"))),
    _f("t5_full_depots", "transit", "packing", "depots filled by full buses = (rid // bcp) // dpt", BUS, R_BUS,
       lambda rid, bcp, dpt: F((rid // bcp) // dpt), _div(_div(V("rid"), V("bcp")), V("dpt"))),
    _f("t5_spare_buses", "transit", "packing", "full buses outside full depots = (rid // bcp) mod dpt", BUS, R_BUS,
       lambda rid, bcp, dpt: F((rid // bcp) % dpt), _mod(_div(V("rid"), V("bcp")), V("dpt"))),
    _f("t5_empty_seats", "transit", "packing", "empty seats on the last bus = bcp ceil(rid / bcp) - rid", BUS, R_BUS,
       lambda rid, bcp, dpt: F(bcp) * _ceil(rid, bcp) - rid, _sub(_mul(V("bcp"), _cdiv(V("rid"), V("bcp"))), V("rid"))),
    # transit: trains on ncar, spr, rpc
    _f("t5_train_seats", "transit", "counting", "seats when the first car is the engine = (ncar - 1) spr rpc", TRAIN, R_TRAIN,
       lambda ncar, spr, rpc: (F(ncar) - 1) * spr * rpc, _mul(_mul(_sub(V("ncar"), C(1)), V("spr")), V("rpc"))),
    _f("t5_window_seats", "transit", "counting", "window seats, two a row, engine excluded = 2 rpc (ncar - 1)", TRAIN, R_TRAIN,
       lambda ncar, spr, rpc: 2 * F(rpc) * (ncar - 1), _mul(_add(V("rpc"), V("rpc")), _sub(V("ncar"), C(1)))),
    _f("t5_middle_seats", "transit", "counting", "seats off the windows, engine excluded = (spr - 2) rpc (ncar - 1)", TRAIN,
       {"ncar": (2, 14), "spr": (3, 6), "rpc": (5, 30)}, lambda ncar, spr, rpc: (F(spr) - 2) * rpc * (ncar - 1),
       _mul(_mul(_sub(V("spr"), C(2)), V("rpc")), _sub(V("ncar"), C(1)))),
    _f("t5_couplings", "transit", "counting", "seat pairs facing across the car = spr rpc (rpc - 1) ncar / 2", TRAIN, R_TRAIN,
       lambda ncar, spr, rpc: F(spr) * rpc * (rpc - 1) * ncar / 2,
       _div(_mul(_mul(_mul(V("spr"), V("rpc")), _sub(V("rpc"), C(1))), V("ncar")), C(2))),
    # transit: parking lot on lotw, lotd, stl
    _f("t5_stalls", "transit", "counting", "stalls of side stl in the lot = (lotw // stl)(lotd // stl)", LOT, R_LOT,
       lambda lotw, lotd, stl: F(lotw // stl) * (lotd // stl), _mul(_div(V("lotw"), V("stl")), _div(V("lotd"), V("stl")))),
    _f("t5_lamps", "transit", "counting", "lamps on every stl grid point = (lotw // stl + 1)(lotd // stl + 1)", LOT, R_LOT,
       lambda lotw, lotd, stl: F(lotw // stl + 1) * (lotd // stl + 1),
       _mul(_add(_div(V("lotw"), V("stl")), C(1)), _add(_div(V("lotd"), V("stl")), C(1)))),
    _f("t5_paved_ring", "transit", "area", "ring road of width stl inside the lot = lotw lotd - (lotw - 2stl)(lotd - 2stl)", LOT, R_LOT,
       lambda lotw, lotd, stl: F(lotw) * lotd - (F(lotw) - 2 * stl) * (lotd - 2 * stl) if lotw > 2 * stl and lotd > 2 * stl else _bad(),
       _sub(_mul(V("lotw"), V("lotd")), _mul(_sub(V("lotw"), _add(V("stl"), V("stl"))), _sub(V("lotd"), _add(V("stl"), V("stl")))))),
    _f("t5_lot_minus_aisle", "transit", "area", "lot area less a centre aisle of width stl = lotd (lotw - stl)", LOT, R_LOT,
       lambda lotw, lotd, stl: F(lotd) * (lotw - stl), _mul(V("lotd"), _sub(V("lotw"), V("stl")))),
    # transit: stairs on flr, stp
    _f("t5_steps", "transit", "counting", "steps from the ground to floor flr = (flr - 1) stp", STAIR, R_STAIR,
       lambda flr, stp: (F(flr) - 1) * stp, _mul(_sub(V("flr"), C(1)), V("stp"))),
    _f("t5_visit_all", "transit", "counting", "steps climbed visiting every floor from the ground in turn = stp flr(flr-1)/2",
       STAIR, R_STAIR, lambda flr, stp: F(stp) * flr * (flr - 1) / 2,
       _div(_mul(_mul(V("stp"), V("flr")), _sub(V("flr"), C(1))), C(2))),
    _f("t5_round_trips", "transit", "counting", "steps up and down to each floor and back = stp flr(flr-1)", STAIR, R_STAIR,
       lambda flr, stp: F(stp) * flr * (flr - 1), _mul(_mul(V("stp"), V("flr")), _sub(V("flr"), C(1)))),
    # venue: tiered seats on rws, fst
    _f("v5_tier_seats", "venue", "counting", "rws rows, fst in front, 2 more each row = rws fst + rws(rws-1)", TIER, R_TIER,
       lambda rws, fst: F(rws) * fst + F(rws) * (rws - 1), _add(_mul(V("rws"), V("fst")), _mul(V("rws"), _sub(V("rws"), C(1))))),
    _f("v5_back_row", "venue", "counting", "seats in the back row = fst + 2(rws - 1)", TIER, R_TIER,
       lambda rws, fst: F(fst) + 2 * (rws - 1), _add(V("fst"), _add(_sub(V("rws"), C(1)), _sub(V("rws"), C(1))))),
    _f("v5_fan_seats", "venue", "counting", "rws rows, fst in front, 1 more each row = rws fst + rws(rws-1)/2", TIER, R_TIER,
       lambda rws, fst: F(rws) * fst + F(rws) * (rws - 1) / 2,
       _add(_mul(V("rws"), V("fst")), _div(_mul(V("rws"), _sub(V("rws"), C(1))), C(2)))),
    _f("v5_aisle_seats", "venue", "counting", "aisle seats, two a row, plus the front row = 2 rws + fst", TIER, R_TIER,
       lambda rws, fst: 2 * F(rws) + fst, _add(_add(V("rws"), V("rws")), V("fst"))),
    # venue: square stage / light rig on stg
    _f("v5_rim_panels", "venue", "counting", "rim panels of a stg x stg stage = 4 stg - 4", STAGE, R_STAGE,
       lambda stg: 4 * F(stg) - 4, _mul(_add(C(2), C(2)), _sub(V("stg"), C(1)))),
    _f("v5_inner_panels", "venue", "counting", "panels off the rim = (stg - 2)^2", STAGE, R_STAGE,
       lambda stg: (F(stg) - 2) ** 2, _sq(_sub(V("stg"), C(2)))),
    _f("v5_light_pyramid", "venue", "counting", "lights in a square pyramid rig of stg tiers = stg(stg+1)(2stg+1)/6", STAGE, R_STAGE,
       lambda stg: F(stg) * (stg + 1) * (2 * stg + 1) / 6,
       _div(_mul(_mul(V("stg"), _add(V("stg"), C(1))), _add(_add(V("stg"), V("stg")), C(1))), SIX)),
    _f("v5_truss_nodes", "venue", "counting", "truss nodes of a stg-cube rig = (stg + 1)^3", STAGE, R_STAGE,
       lambda stg: (F(stg) + 1) ** 3, _mul(_add(V("stg"), C(1)), _sq(_add(V("stg"), C(1))))),
    _f("v5_truss_bars", "venue", "counting", "unit bars of a stg x stg floor grid = 2 stg (stg + 1)", STAGE, R_STAGE,
       lambda stg: 2 * F(stg) * (stg + 1), _mul(_add(V("stg"), V("stg")), _add(V("stg"), C(1)))),
    _f("v5_speaker_stack", "venue", "counting", "speakers in a triangular stack of stg rows on a base of stg+1 = (stg+1)(stg+2)/2",
       STAGE, R_STAGE, lambda stg: (F(stg) + 1) * (stg + 2) / 2, _div(_mul(_add(V("stg"), C(1)), _add(V("stg"), C(2))), C(2))),
    # venue: tickets on tix, grp, blk
    _f("v5_groups", "venue", "packing", "groups to seat every ticket holder = ceil(tix / grp)", TIX, R_TIX,
       lambda tix, grp, blk: _ceil(tix, grp), _cdiv(V("tix"), V("grp"))),
    _f("v5_blocks", "venue", "packing", "seat blocks for every group = ceil(ceil(tix / grp) / blk)", TIX, R_TIX,
       lambda tix, grp, blk: _ceil(_ceil(tix, grp), blk), _cdiv(_cdiv(V("tix"), V("grp")), V("blk"))),
    _f("v5_full_blocks", "venue", "packing", "blocks filled by full groups = (tix // grp) // blk", TIX, R_TIX,
       lambda tix, grp, blk: F((tix // grp) // blk), _div(_div(V("tix"), V("grp")), V("blk"))),
    _f("v5_leftover_groups", "venue", "packing", "full groups outside full blocks = (tix // grp) mod blk", TIX, R_TIX,
       lambda tix, grp, blk: F((tix // grp) % blk), _mod(_div(V("tix"), V("grp")), V("blk"))),
    _f("v5_block_seats", "venue", "packing", "seats in the full blocks = ((tix // grp) // blk) blk grp", TIX, R_TIX,
       lambda tix, grp, blk: F((tix // grp) // blk) * blk * grp, _mul(_mul(_div(_div(V("tix"), V("grp")), V("blk")), V("blk")), V("grp"))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
