"""MEMIDX: a second never-trained catalogue for the memory-content question (docs/MEMIDX.md).

Four new task domains on the existing ``int`` opset (add, sub, mul, div, mod, min, max, ite; constants
0-3), none in any training curriculum, dev suite or sealed suite of this repository, and none a duplicate
of NOVEL's coord / digits / order families (some, like NOVEL's coord, need |a - b|):

- ``sport``   two matches, goals gw : gx (match 1) and gy : gz (match 2): margins, aggregates, points.
- ``weather`` two days' high / low temperatures wh, wl (day 1) and vh, vl (day 2): swings and changes.
- ``pitch``   two notes za, zb as semitone numbers, the octave size stated as a constant column zo = 12:
              intervals, octaves, pitch classes.
- ``stock``   stock on hand sk, sl at two depots, orders rk, rl: shortfalls, fills, leftovers.

Built like ``scripts/novel_catalogue.py``: Fraction (or plain integer) ground truth written independently
of the reference tree, rows kept only when the answer is an integer the reference tree reproduces,
5 public / 3 challenge / 3 final rows (the final split is never read by search or WITNESS). Input names
(gw gx gy gz, wh wl vh vl, za zb zo, sk sl rk rl) appear in no other catalogue, test or script.
Measurement only; written and committed before any field arm is measured on the suite.
"""
from __future__ import annotations

import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nomad.science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: E402,F401  (re-exported)

DOMAINS = ("sport", "weather", "pitch", "stock")

SPT = ("gw", "gx", "gy", "gz")
WTH = ("wh", "wl", "vh", "vl")
PIT = ("za", "zb", "zo")
STK = ("sk", "sl", "rk", "rl")

R_SPT = {"gw": (0, 9), "gx": (0, 9), "gy": (0, 9), "gz": (0, 9)}
R_WTH = {"wh": (-5, 38), "wl": (-15, 30), "vh": (-5, 38), "vl": (-15, 30)}
R_PIT = {"za": (36, 96), "zb": (36, 96), "zo": ("const", 12)}
R_STK = {"sk": (0, 40), "sl": (0, 40), "rk": (0, 40), "rl": (0, 40)}
BAD = F(1, 3)   # a non-integer truth: the row is redrawn


def _f(family, domain, kind, text, inputs, ranges, truth, tree):
    return Formula(family, f"{domain}:{kind}", text, inputs, ranges, truth, tree)


def add(a, b):
    return ["add", a, b]


def sub(a, b):
    return ["sub", a, b]


def mul(a, b):
    return ["mul", a, b]


def div(a, b):
    return ["div", a, b]


def mod(a, b):
    return ["mod", a, b]


def mn(a, b):
    return ["min", a, b]


def mx(a, b):
    return ["max", a, b]


def ite(c, a, b):
    return ["ite", c, a, b]


def absd(a, b):
    return sub(mx(a, b), mn(a, b))


def pos(a, b):          # max(0, a - b)
    return mx(C(0), sub(a, b))


GW, GX, GY, GZ = V("gw"), V("gx"), V("gy"), V("gz")
WH, WL, VH, VL = V("wh"), V("wl"), V("vh"), V("vl")
ZA, ZB, ZO = V("za"), V("zb"), V("zo")
SK, SL, RK, RL = V("sk"), V("sl"), V("rk"), V("rl")


def _wx(fn):
    """Weather truth: a day's high is never below its low (else the row is redrawn)."""
    return lambda wh, wl, vh, vl: fn(wh, wl, vh, vl) if wh >= wl and vh >= vl else BAD


CATALOGUE: tuple[Formula, ...] = (
    # sport: match 1 gw : gx, match 2 gy : gz
    _f("mx_s_margin1", "sport", "margin", "winning margin of match 1 |gw - gx|", SPT, R_SPT,
       lambda gw, gx, gy, gz: F(abs(gw - gx)), absd(GW, GX)),
    _f("mx_s_margin_sum", "sport", "margin", "sum of the two matches' margins", SPT, R_SPT,
       lambda gw, gx, gy, gz: F(abs(gw - gx) + abs(gy - gz)), add(absd(GW, GX), absd(GY, GZ))),
    _f("mx_s_margin_max", "sport", "margin", "the larger of the two margins", SPT, R_SPT,
       lambda gw, gx, gy, gz: F(max(abs(gw - gx), abs(gy - gz))), mx(absd(GW, GX), absd(GY, GZ))),
    _f("mx_s_margin_min", "sport", "margin", "the closer match's margin", SPT, R_SPT,
       lambda gw, gx, gy, gz: F(min(abs(gw - gx), abs(gy - gz))), mn(absd(GW, GX), absd(GY, GZ))),
    _f("mx_s_margin_gap", "sport", "margin", "match 1's margin minus match 2's", SPT, R_SPT,
       lambda gw, gx, gy, gz: F(abs(gw - gx) - abs(gy - gz)), sub(absd(GW, GX), absd(GY, GZ))),
    _f("mx_s_aggregate", "sport", "aggregate", "two-leg aggregate margin |(gw + gz) - (gx + gy)| (gw, gz: team A)",
       SPT, R_SPT, lambda gw, gx, gy, gz: F(abs(gw + gz - gx - gy)), absd(add(GW, GZ), add(GX, GY))),
    _f("mx_s_points", "sport", "points", "home points in match 1: 3 for a win, 1 for a draw, 0 for a loss",
       SPT, R_SPT, lambda gw, gx, gy, gz: F(3 if gw > gx else 1 if gw == gx else 0),
       ite(sub(GW, GX), C(3), ite(sub(GX, GW), C(0), C(1)))),
    _f("mx_s_winners_goals", "sport", "aggregate", "goals scored by the winner (or either side in a draw) of each match, summed",
       SPT, R_SPT, lambda gw, gx, gy, gz: F(max(gw, gx) + max(gy, gz)), add(mx(GW, GX), mx(GY, GZ))),
    # weather: day 1 high wh / low wl, day 2 high vh / low vl
    _f("mx_w_swing_sum", "weather", "swing", "the two days' high-low swings added", WTH, R_WTH,
       _wx(lambda wh, wl, vh, vl: F(wh - wl + vh - vl)), add(sub(WH, WL), sub(VH, VL))),
    _f("mx_w_high_change", "weather", "change", "how much the high changed |wh - vh|", WTH, R_WTH,
       _wx(lambda wh, wl, vh, vl: F(abs(wh - vh))), absd(WH, VH)),
    _f("mx_w_change_total", "weather", "change", "|wh - vh| + |wl - vl|", WTH, R_WTH,
       _wx(lambda wh, wl, vh, vl: F(abs(wh - vh) + abs(wl - vl))), add(absd(WH, VH), absd(WL, VL))),
    _f("mx_w_change_max", "weather", "change", "the larger of the high's and the low's change", WTH, R_WTH,
       _wx(lambda wh, wl, vh, vl: F(max(abs(wh - vh), abs(wl - vl)))), mx(absd(WH, VH), absd(WL, VL))),
    _f("mx_w_big_swing", "weather", "swing", "the bigger of the two days' swings", WTH, R_WTH,
       _wx(lambda wh, wl, vh, vl: F(max(wh - wl, vh - vl))), mx(sub(WH, WL), sub(VH, VL))),
    _f("mx_w_span", "weather", "swing", "two-day span: highest high minus lowest low", WTH, R_WTH,
       _wx(lambda wh, wl, vh, vl: F(max(wh, vh) - min(wl, vl))), sub(mx(WH, VH), mn(WL, VL))),
    _f("mx_w_mid1", "weather", "mean", "day 1's mid-range (wh + wl) / 2", WTH, R_WTH,
       _wx(lambda wh, wl, vh, vl: F(wh + wl, 2) if (wh + wl) % 2 == 0 else BAD), div(add(WH, WL), C(2))),
    _f("mx_w_swing_diff", "weather", "swing", "how different the two swings are |(wh - wl) - (vh - vl)|", WTH, R_WTH,
       _wx(lambda wh, wl, vh, vl: F(abs((wh - wl) - (vh - vl)))), absd(sub(WH, WL), sub(VH, VL))),
    # pitch: notes za, zb (semitones), octave zo = 12
    _f("mx_p_interval", "pitch", "interval", "interval in semitones |za - zb|", PIT, R_PIT,
       lambda za, zb, zo: F(abs(za - zb)), absd(ZA, ZB)),
    _f("mx_p_class_a", "pitch", "class", "pitch class of za (za mod 12)", PIT, R_PIT,
       lambda za, zb, zo: F(za % 12), mod(ZA, ZO)),
    _f("mx_p_octave_gap", "pitch", "octave", "how many octave numbers apart the notes are |za div 12 - zb div 12|",
       PIT, R_PIT, lambda za, zb, zo: F(abs(za // 12 - zb // 12)), absd(div(ZA, ZO), div(ZB, ZO))),
    _f("mx_p_simple", "pitch", "interval", "simple interval: |za - zb| mod 12", PIT, R_PIT,
       lambda za, zb, zo: F(abs(za - zb) % 12), mod(absd(ZA, ZB), ZO)),
    _f("mx_p_up_class", "pitch", "class", "ascending interval class from zb up to za: (za - zb) mod 12", PIT, R_PIT,
       lambda za, zb, zo: F((za - zb) % 12), mod(sub(ZA, ZB), ZO)),
    _f("mx_p_octaves", "pitch", "octave", "whole octaves in the interval |za - zb| div 12", PIT, R_PIT,
       lambda za, zb, zo: F(abs(za - zb) // 12), div(absd(ZA, ZB), ZO)),
    _f("mx_p_class_sum", "pitch", "class", "pitch class of za plus pitch class of zb", PIT, R_PIT,
       lambda za, zb, zo: F(za % 12 + zb % 12), add(mod(ZA, ZO), mod(ZB, ZO))),
    # stock: on hand sk, sl; orders rk, rl
    _f("mx_k_short1", "stock", "short", "shortfall at depot 1 max(0, rk - sk)", STK, R_STK,
       lambda sk, sl, rk, rl: F(max(0, rk - sk)), pos(RK, SK)),
    _f("mx_k_short_total", "stock", "short", "total shortfall over both depots", STK, R_STK,
       lambda sk, sl, rk, rl: F(max(0, rk - sk) + max(0, rl - sl)), add(pos(RK, SK), pos(RL, SL))),
    _f("mx_k_filled", "stock", "fill", "units shipped: min(sk, rk) + min(sl, rl)", STK, R_STK,
       lambda sk, sl, rk, rl: F(min(sk, rk) + min(sl, rl)), add(mn(SK, RK), mn(SL, RL))),
    _f("mx_k_left", "stock", "fill", "units left over at both depots", STK, R_STK,
       lambda sk, sl, rk, rl: F(max(0, sk - rk) + max(0, sl - rl)), add(pos(SK, RK), pos(SL, RL))),
    _f("mx_k_mismatch", "stock", "fill", "total mismatch |sk - rk| + |sl - rl|", STK, R_STK,
       lambda sk, sl, rk, rl: F(abs(sk - rk) + abs(sl - rl)), add(absd(SK, RK), absd(SL, RL))),
    _f("mx_k_worst", "stock", "short", "worst net need max(rk - sk, rl - sl)", STK, R_STK,
       lambda sk, sl, rk, rl: F(max(rk - sk, rl - sl)), mx(sub(RK, SK), sub(RL, SL))),
    _f("mx_k_pooled_short", "stock", "short", "shortfall if the depots pool stock max(0, rk + rl - sk - sl)", STK, R_STK,
       lambda sk, sl, rk, rl: F(max(0, rk + rl - sk - sl)), pos(add(RK, RL), add(SK, SL))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
