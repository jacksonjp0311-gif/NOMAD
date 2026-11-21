"""SELFEDIT task catalogues (docs/SELFEDIT.md).

``DEV_CATALOGUE`` is what the self-edit sandbox benchmarks a candidate genome
on (it is committed because the live body runs the sandbox on GitHub
runners; it is never a sealed suite and no proof is measured on it). The
sealed proof catalogue ``CATALOGUE`` is committed, with the pre-registered
criteria, before any field arm is measured on it.

Theme: everyday unit / packing formulas whose answer is a product or a
learned-block value rescaled by a constant the DSL does not have as a leaf
(4, 6, 8, 12, 16, 24, 36, ...). WORLD leaves are the constants 0..3, so such
a constant is either built from small constants inside the search or comes
from the field's learned / derived constants (docs/INVENT.md). Same
construction as ``nomad.transfer4``: named int inputs (disjoint from every
earlier catalogue), Fraction ground truth written independently of the
reference tree, 5 public / 3 challenge / 3 final rows.
"""
from __future__ import annotations

from fractions import Fraction as F

from .science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: F401  (re-exported)

DEV_DOMAINS = ("warehouse", "calendar")

CRATE = ("qa", "qb", "qc")     # crates: rows, columns, layers
DAYS = ("qd", "qe")            # days, shifts per day
EGGS = ("qf", "qg")            # cartons, hens
R_CRATE = {"qa": (1, 12), "qb": (1, 12), "qc": (1, 10)}
R_DAYS = {"qd": (1, 60), "qe": (1, 6)}
R_EGGS = {"qf": (1, 50), "qg": (1, 30)}


def _f(family, domain, kind, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:{kind}", text, inputs, ranges, truth, tree)


def _add(a, b):
    return ["add", a, b]


def _sub(a, b):
    return ["sub", a, b]


def _mul(a, b):
    return ["mul", a, b]


def _div(a, b):
    return ["div", a, b]


def _k(n: int) -> list:
    """The constant n as a small tree of the leaves 2 and 3."""
    trees = {4: _mul(C(2), C(2)), 6: _mul(C(2), C(3)), 8: _mul(C(2), _mul(C(2), C(2))),
             9: _mul(C(3), C(3)), 12: _mul(C(2), _mul(C(2), C(3))), 16: _mul(_mul(C(2), C(2)), _mul(C(2), C(2))),
             18: _mul(C(2), _mul(C(3), C(3))), 24: _mul(_mul(C(2), C(2)), _mul(C(2), C(3))),
             36: _mul(_mul(C(2), C(3)), _mul(C(2), C(3)))}
    return trees[n]


def _abc():
    return _mul(_mul(V("qa"), V("qb")), V("qc"))


DEV_CATALOGUE: tuple[Formula, ...] = (
    _f("sd_crate_dozens", "warehouse", "packing", "full dozens in qa x qb x qc = (qa qb qc) // 12", CRATE, R_CRATE,
       lambda qa, qb, qc: F((qa * qb * qc) // 12), _div(_abc(), _k(12))),
    _f("sd_crate_eighths", "warehouse", "packing", "full 8-packs in qa x qb x qc = (qa qb qc) // 8", CRATE, R_CRATE,
       lambda qa, qb, qc: F((qa * qb * qc) // 8), _div(_abc(), _k(8))),
    _f("sd_crate_quarters", "warehouse", "packing", "quarter pallets = (qa qb qc) // 4", CRATE, R_CRATE,
       lambda qa, qb, qc: F((qa * qb * qc) // 4), _div(_abc(), _k(4))),
    _f("sd_crate_six", "warehouse", "packing", "six-packs filled = (qa qb qc) // 6", CRATE, R_CRATE,
       lambda qa, qb, qc: F((qa * qb * qc) // 6), _div(_abc(), _k(6))),
    _f("sd_crate_twelve_x", "warehouse", "packing", "bottles in qa qb qc dozen-cases = 12 qa qb qc", CRATE, R_CRATE,
       lambda qa, qb, qc: F(12 * qa * qb * qc), _mul(_abc(), _k(12))),
    _f("sd_crate_eight_x", "warehouse", "packing", "cans in qa qb qc 8-packs = 8 qa qb qc", CRATE, R_CRATE,
       lambda qa, qb, qc: F(8 * qa * qb * qc), _mul(_abc(), _k(8))),
    _f("sd_crate_sq16", "warehouse", "packing", "16ths of a square floor qa^2 qc = (qa qa qc) // 16", CRATE, R_CRATE,
       lambda qa, qb, qc: F((qa * qa * qc) // 16), _div(_mul(_mul(V("qa"), V("qa")), V("qc")), _k(16))),
    _f("sd_crate_rim12", "warehouse", "packing", "dozens on a qa x qb rim, qc layers = ((qa+qb) qc) // 12", CRATE, R_CRATE,
       lambda qa, qb, qc: F(((qa + qb) * qc) // 12), _div(_mul(_add(V("qa"), V("qb")), V("qc")), _k(12))),
    _f("sd_days_hours", "calendar", "units", "hours in qd days of qe shifts = 24 qd qe", DAYS, R_DAYS,
       lambda qd, qe: F(24 * qd * qe), _mul(_mul(V("qd"), V("qe")), _k(24))),
    _f("sd_days_weeks6", "calendar", "units", "6-day weeks in qd days x qe shifts = (qd qe) // 6", DAYS, R_DAYS,
       lambda qd, qe: F((qd * qe) // 6), _div(_mul(V("qd"), V("qe")), _k(6))),
    _f("sd_days_tri24", "calendar", "units", "relay handovers among qd crews per day, in whole days = qd(qd+1)//24", DAYS, R_DAYS,
       lambda qd, qe: F((qd * (qd + 1)) // 24), _div(_mul(V("qd"), _add(V("qd"), C(1))), _k(24))),
    _f("sd_days_sq36", "calendar", "units", "36ths of qd^2 = (qd qd) // 36", DAYS, R_DAYS,
       lambda qd, qe: F((qd * qd) // 36), _div(_mul(V("qd"), V("qd")), _k(36))),
    _f("sd_eggs_dozen", "warehouse", "units", "eggs in qf cartons of a dozen from qg hens = 12 qf qg", EGGS, R_EGGS,
       lambda qf, qg: F(12 * qf * qg), _mul(_mul(V("qf"), V("qg")), _k(12))),
    _f("sd_eggs_plus18", "warehouse", "units", "eggs: qf flats of 18 plus qg loose = 18 qf + qg", EGGS, R_EGGS,
       lambda qf, qg: F(18 * qf + qg), _add(_mul(V("qf"), _k(18)), V("qg"))),
    _f("sd_eggs_tri8", "warehouse", "units", "8-egg boxes for qf(qf+1)/2 eggs = qf(qf+1) // 16", EGGS, R_EGGS,
       lambda qf, qg: F((qf * (qf + 1)) // 16), _div(_mul(V("qf"), _add(V("qf"), C(1))), _k(16))),
    _f("sd_eggs_mix9", "warehouse", "units", "9-egg trays from qf qg eggs = (qf qg) // 9", EGGS, R_EGGS,
       lambda qf, qg: F((qf * qg) // 9), _div(_mul(V("qf"), V("qg")), _k(9))),
)

# ---------------------------------------------------------------- the sealed catalogue
# Written before any field arm is measured on it (docs/SELFEDIT.md, "Sealed suite"). New domains
# (music, sport, travel), new input names (disjoint from every catalogue, DEV_CATALOGUE included),
# new formulas: everyday counting / unit formulas with a constant factor or divisor. Some constants are
# derivable from learned scales (4, 6, 8, 12, 16, 18, 24, 36), some are not (7, 60), some answers are
# ceilings (not a floor fit); every formula is an everyday formula, none chosen by outcome.

DOMAINS = ("music", "sport", "travel")

BARS = ("zp", "zq")            # bars, players
TEAM = ("zr", "zs", "zt")      # teams, rounds, players per team
TRIP = ("zu", "zv", "zw")      # days, travellers, bags per traveller
R_BARS = {"zp": (1, 64), "zq": (1, 12)}
R_TEAM = {"zr": (2, 20), "zs": (1, 10), "zt": (1, 15)}
R_TRIP = {"zu": (1, 30), "zv": (1, 9), "zw": (1, 8)}


def _ceil_tree(a, k):
    return _div(_add(a, _sub(k, C(1))), k)


CATALOGUE: tuple[Formula, ...] = (
    # music
    _f("se_m_beats44", "music", "counting", "beats in zp bars of 4/4 for zq players = 4 zp zq", BARS, R_BARS,
       lambda zp, zq: F(4 * zp * zq), _mul(_mul(V("zp"), V("zq")), _k(4))),
    _f("se_m_sixteenths", "music", "counting", "sixteenth notes in zp bars plus zq pickup notes = 16 zp + zq", BARS, R_BARS,
       lambda zp, zq: F(16 * zp + zq), _add(_mul(V("zp"), _k(16)), V("zq"))),
    _f("se_m_phrases8", "music", "counting", "full 8-bar phrases over zq parts of zp bars = (zp zq) // 8", BARS, R_BARS,
       lambda zp, zq: F((zp * zq) // 8), _div(_mul(V("zp"), V("zq")), _k(8))),
    _f("se_m_sets12", "music", "counting", "practice sets of 12 bars from zp bars played zq times = (zp zq) // 12", BARS, R_BARS,
       lambda zp, zq: F((zp * zq) // 12), _div(_mul(V("zp"), V("zq")), _k(12))),
    _f("se_m_warmup8", "music", "counting", "warm-up with i notes in bar i, in groups of 8 = zp(zp+1) // 16", BARS, R_BARS,
       lambda zp, zq: F((zp * (zp + 1)) // 16), _div(_mul(V("zp"), _add(V("zp"), C(1))), _k(16))),
    _f("se_m_six8", "music", "counting", "eighth notes in zp bars of 6/8 plus zq = 6 zp + zq", BARS, R_BARS,
       lambda zp, zq: F(6 * zp + zq), _add(_mul(V("zp"), _k(6)), V("zq"))),
    _f("se_m_stands", "music", "packing", "music stands, one per 2 players, for zq players in zp sections = ceil(zp zq / 2)",
       BARS, R_BARS, lambda zp, zq: F(-(-(zp * zq) // 2)), _ceil_tree(_mul(V("zp"), V("zq")), C(2))),
    # sport
    _f("se_s_relay4", "sport", "packing", "full 4-person relay teams from zr teams of zt = (zr zt) // 4", TEAM, R_TEAM,
       lambda zr, zs, zt: F((zr * zt) // 4), _div(_mul(V("zr"), V("zt")), _k(4))),
    _f("se_s_six_aside", "sport", "packing", "full six-a-side squads from zr zt players = (zr zt) // 6", TEAM, R_TEAM,
       lambda zr, zs, zt: F((zr * zt) // 6), _div(_mul(V("zr"), V("zt")), _k(6))),
    _f("se_s_golf_extra", "sport", "counting", "holes: zr rounds of 18 plus zs extra holes = 18 zr + zs", TEAM, R_TEAM,
       lambda zr, zs, zt: F(18 * zr + zs), _add(_mul(V("zr"), _k(18)), V("zs"))),
    _f("se_s_golf_total", "sport", "counting", "holes played by zr groups over zs rounds = 18 zr zs", TEAM, R_TEAM,
       lambda zr, zs, zt: F(18 * zr * zs), _mul(_mul(V("zr"), V("zs")), _k(18))),
    _f("se_s_race24", "sport", "units", "team-hours in zs 24-hour races of zt drivers = 24 zs zt", TEAM, R_TEAM,
       lambda zr, zs, zt: F(24 * zs * zt), _mul(_mul(V("zs"), V("zt")), _k(24))),
    _f("se_s_bracket16", "sport", "packing", "full 16-player brackets from zr teams of zt = (zr zt) // 16", TEAM, R_TEAM,
       lambda zr, zs, zt: F((zr * zt) // 16), _div(_mul(V("zr"), V("zt")), _k(16))),
    _f("se_s_jersey_boxes", "sport", "packing", "boxes of 12 jerseys for zr teams of zt = ceil(zr zt / 12)", TEAM, R_TEAM,
       lambda zr, zs, zt: F(-(-(zr * zt) // 12)), _ceil_tree(_mul(V("zr"), V("zt")), _k(12))),
    _f("se_s_league_games", "sport", "counting", "league games: zr teams, everyone twice, zs seasons = zs zr (zr - 1)", TEAM, R_TEAM,
       lambda zr, zs, zt: F(zs * zr * (zr - 1)), _mul(V("zs"), _mul(V("zr"), _sub(V("zr"), C(1))))),
    _f("se_s_balls_dozen", "sport", "packing", "full dozens of balls, zt per player, zr zs players = (zr zs zt) // 12",
       TEAM, R_TEAM, lambda zr, zs, zt: F((zr * zs * zt) // 12),
       _div(_mul(_mul(V("zr"), V("zs")), V("zt")), _k(12))),
    # travel
    _f("se_t_hours", "travel", "units", "traveller-hours in zu days for zv travellers = 24 zu zv", TRIP, R_TRIP,
       lambda zu, zv, zw: F(24 * zu * zv), _mul(_mul(V("zu"), V("zv")), _k(24))),
    _f("se_t_weeks", "travel", "units", "full weeks of zu days for zv travellers = (zu zv) // 7", TRIP, R_TRIP,
       lambda zu, zv, zw: F((zu * zv) // 7), _div(_mul(V("zu"), V("zv")), _add(_add(C(2), C(2)), C(3)))),
    _f("se_t_straps12", "travel", "packing", "12-packs of straps for zu zv zw bags = (zu zv zw) // 12", TRIP, R_TRIP,
       lambda zu, zv, zw: F((zu * zv * zw) // 12), _div(_mul(_mul(V("zu"), V("zv")), V("zw")), _k(12))),
    _f("se_t_slots8", "travel", "packing", "full 8-slot racks for zu zv zw items = (zu zv zw) // 8", TRIP, R_TRIP,
       lambda zu, zv, zw: F((zu * zv * zw) // 8), _div(_mul(_mul(V("zu"), V("zv")), V("zw")), _k(8))),
    _f("se_t_rows6", "travel", "packing", "full rows of 6 seats for zu zv passengers and zw crew = (zu zv + zw) // 6", TRIP, R_TRIP,
       lambda zu, zv, zw: F((zu * zv + zw) // 6), _div(_add(_mul(V("zu"), V("zv")), V("zw")), _k(6))),
    _f("se_t_legs18", "travel", "units", "18-km legs in 1 + 2 + ... + zu km = zu(zu+1) // 36", TRIP, R_TRIP,
       lambda zu, zv, zw: F((zu * (zu + 1)) // 36), _div(_mul(V("zu"), _add(V("zu"), C(1))), _k(36))),
    _f("se_t_rooms4", "travel", "packing", "rooms of 4 for zv zw guests = ceil(zv zw / 4)", TRIP, R_TRIP,
       lambda zu, zv, zw: F(-(-(zv * zw) // 4)), _ceil_tree(_mul(V("zv"), V("zw")), _k(4))),
    _f("se_t_minutes", "travel", "units", "minutes in zu hours plus zv = 60 zu + zv", TRIP, R_TRIP,
       lambda zu, zv, zw: F(60 * zu + zv), _add(_mul(V("zu"), _mul(_k(6), _add(_add(C(3), C(3)), _add(C(2), C(2))))), V("zv"))),
)

# ---------------------------------------------------------------- the round-2 sealed catalogue
# Written before any field arm is measured on it (docs/SELFEDIT.md, "Round 2"). New domains (garden,
# school, factory), new input names (yp..yw, disjoint from every catalogue), new formulas of the same
# kind: everyday counting / unit formulas with a constant factor or divisor; some constants derivable from
# learned scales, some not (5, 7, 10, 30), some ceilings; none chosen by outcome.

DOMAINS2 = ("garden", "school", "factory")

BEDS = ("yp", "yq")            # beds, plants per bed
CLASS = ("yr", "ys", "yt")     # classes, students per class, weeks
LINE = ("yu", "yv", "yw")      # machines, hours, parts per hour
R_BEDS = {"yp": (1, 40), "yq": (1, 16)}
R_CLASS = {"yr": (1, 12), "ys": (5, 35), "yt": (1, 14)}
R_LINE = {"yu": (1, 9), "yv": (1, 24), "yw": (1, 12)}

CATALOGUE2: tuple[Formula, ...] = (
    # garden
    _f("se2_g_trays6", "garden", "packing", "full 6-cell seed trays for yp beds of yq plants = (yp yq) // 6", BEDS, R_BEDS,
       lambda yp, yq: F((yp * yq) // 6), _div(_mul(V("yp"), V("yq")), _k(6))),
    _f("se2_g_flats12", "garden", "packing", "full 12-pot flats for yp yq plants = (yp yq) // 12", BEDS, R_BEDS,
       lambda yp, yq: F((yp * yq) // 12), _div(_mul(V("yp"), V("yq")), _k(12))),
    _f("se2_g_bulbs8", "garden", "counting", "bulbs: 8 per plant spot, yp beds of yq spots = 8 yp yq", BEDS, R_BEDS,
       lambda yp, yq: F(8 * yp * yq), _mul(_mul(V("yp"), V("yq")), _k(8))),
    _f("se2_g_border4", "garden", "counting", "edging stakes: 4 per bed plus yq spares = 4 yp + yq", BEDS, R_BEDS,
       lambda yp, yq: F(4 * yp + yq), _add(_mul(V("yp"), _k(4)), V("yq"))),
    _f("se2_g_bags16", "garden", "packing", "full 16-litre bags from a triangle of yp rows = yp(yp+1) // 32", BEDS, R_BEDS,
       lambda yp, yq: F((yp * (yp + 1)) // 32), _div(_mul(V("yp"), _add(V("yp"), C(1))), _mul(C(2), _k(16)))),
    _f("se2_g_square9", "garden", "packing", "full 9-plant squares in a yp x yp plot = (yp yp) // 9", BEDS, R_BEDS,
       lambda yp, yq: F((yp * yp) // 9), _div(_mul(V("yp"), V("yp")), _k(9))),
    _f("se2_g_hoses5", "garden", "packing", "hoses, one per 5 beds = ceil(yp / 5)", BEDS, R_BEDS,
       lambda yp, yq: F(-(-yp // 5)), _ceil_tree(V("yp"), _add(C(2), C(3)))),
    _f("se2_g_rows24", "garden", "packing", "full 24-plant rows from yp beds of yq = (yp yq) // 24", BEDS, R_BEDS,
       lambda yp, yq: F((yp * yq) // 24), _div(_mul(V("yp"), V("yq")), _k(24))),
    # school
    _f("se2_s_lessons", "school", "counting", "lessons: 6 a day, 5 days, yt weeks, yr classes = 30 yr yt", CLASS, R_CLASS,
       lambda yr, ys, yt: F(30 * yr * yt), _mul(_mul(V("yr"), V("yt")), _mul(_k(6), _add(C(2), C(3))))),
    _f("se2_s_tables4", "school", "packing", "full 4-seat tables for yr classes of ys = (yr ys) // 4", CLASS, R_CLASS,
       lambda yr, ys, yt: F((yr * ys) // 4), _div(_mul(V("yr"), V("ys")), _k(4))),
    _f("se2_s_teams8", "school", "packing", "full 8-player teams from yr ys students = (yr ys) // 8", CLASS, R_CLASS,
       lambda yr, ys, yt: F((yr * ys) // 8), _div(_mul(V("yr"), V("ys")), _k(8))),
    _f("se2_s_pencils12", "school", "counting", "pencils: a dozen per student, yr classes of ys = 12 yr ys", CLASS, R_CLASS,
       lambda yr, ys, yt: F(12 * yr * ys), _mul(_mul(V("yr"), V("ys")), _k(12))),
    _f("se2_s_buses", "school", "packing", "36-seat buses for yr classes of ys = ceil(yr ys / 36)", CLASS, R_CLASS,
       lambda yr, ys, yt: F(-(-(yr * ys) // 36)), _ceil_tree(_mul(V("yr"), V("ys")), _k(36))),
    _f("se2_s_terms7", "school", "units", "full weeks in yt fortnights of yr days = (yr yt) // 7", CLASS, R_CLASS,
       lambda yr, ys, yt: F((yr * yt) // 7), _div(_mul(V("yr"), V("yt")), _add(_add(C(2), C(2)), C(3)))),
    _f("se2_s_books16", "school", "packing", "full 16-book boxes, yt books each for yr ys students = (yr ys yt) // 16",
       CLASS, R_CLASS, lambda yr, ys, yt: F((yr * ys * yt) // 16), _div(_mul(_mul(V("yr"), V("ys")), V("yt")), _k(16))),
    _f("se2_s_register", "school", "counting", "register marks: 2 a day over yt weeks of 5 days for ys = 10 ys yt", CLASS, R_CLASS,
       lambda yr, ys, yt: F(10 * ys * yt), _mul(_mul(V("ys"), V("yt")), _mul(C(2), _add(C(2), C(3))))),
    # factory
    _f("se2_f_parts", "factory", "counting", "parts from yu machines over yv hours at yw per hour = yu yv yw", LINE, R_LINE,
       lambda yu, yv, yw: F(yu * yv * yw), _mul(_mul(V("yu"), V("yv")), V("yw"))),
    _f("se2_f_boxes12", "factory", "packing", "full 12-part boxes = (yu yv yw) // 12", LINE, R_LINE,
       lambda yu, yv, yw: F((yu * yv * yw) // 12), _div(_mul(_mul(V("yu"), V("yv")), V("yw")), _k(12))),
    _f("se2_f_days24", "factory", "units", "full days of machine time in yu yv hours = (yu yv) // 24", LINE, R_LINE,
       lambda yu, yv, yw: F((yu * yv) // 24), _div(_mul(V("yu"), V("yv")), _k(24))),
    _f("se2_f_shifts8", "factory", "units", "full 8-hour shifts in yu yv machine-hours = (yu yv) // 8", LINE, R_LINE,
       lambda yu, yv, yw: F((yu * yv) // 8), _div(_mul(V("yu"), V("yv")), _k(8))),
    _f("se2_f_minutes", "factory", "units", "machine-minutes for yu machines over yv hours = 60 yu yv", LINE, R_LINE,
       lambda yu, yv, yw: F(60 * yu * yv), _mul(_mul(V("yu"), V("yv")), _mul(_k(6), _mul(C(2), _add(C(2), C(3)))))),
    _f("se2_f_pallets36", "factory", "packing", "full 36-part pallets plus yu loose crates = (yv yw) // 36 + yu", LINE, R_LINE,
       lambda yu, yv, yw: F((yv * yw) // 36 + yu), _add(_div(_mul(V("yv"), V("yw")), _k(36)), V("yu"))),
    _f("se2_f_bolts6", "factory", "counting", "bolts: 6 per part, yu machines x yw parts = 6 yu yw", LINE, R_LINE,
       lambda yu, yv, yw: F(6 * yu * yw), _mul(_mul(V("yu"), V("yw")), _k(6))),
    _f("se2_f_crates", "factory", "packing", "crates of 18 for yv yw parts = ceil(yv yw / 18)", LINE, R_LINE,
       lambda yu, yv, yw: F(-(-(yv * yw) // 18)), _ceil_tree(_mul(V("yv"), V("yw")), _k(18))),
)

BY_FAMILY = {f.family: f for f in DEV_CATALOGUE + CATALOGUE + CATALOGUE2}


class _Dev:
    """Module-like view used by scripts/transfer_suite.generate for dev suites."""
    CATALOGUE = DEV_CATALOGUE
    DOMAINS = DEV_DOMAINS
    draw_rows = staticmethod(draw_rows)
    to_task = staticmethod(to_task)


DEV = _Dev()


class _Round2:
    """Module-like view of the round-2 sealed catalogue (scripts/selfedit_suite.py --round 2)."""
    CATALOGUE = CATALOGUE2
    DOMAINS = DOMAINS2
    draw_rows = staticmethod(draw_rows)
    to_task = staticmethod(to_task)


ROUND2 = _Round2()
