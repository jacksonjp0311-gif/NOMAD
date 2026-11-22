"""NOVEL: a never-trained catalogue for a pure generalization measurement (docs/NOVEL.md).

Three task families that NOMAD's existing ``int`` opset (add, sub, mul, div, mod, min, max, ite;
constants 0-3) can express, but that no training curriculum, dev suite or sealed suite in this
repository contains (checked by grepping every task catalogue; see docs/NOVEL.md):

- ``coord``  lattice coordinate geometry on two points P = (px, py), Q = (qx, qy): taxicab and
             Chebyshev distance, squared Euclidean distance, dot and cross products, bounding boxes.
- ``digits`` decimal place value on one number nn with the base stated as a constant column tn = 10:
             digit sums, digit reversal, rounding, dropping a digit.
- ``order``  order statistics of three or four plain numbers (oa, ob, oc, od): median, clamp, range,
             sum of the largest two, counting how many exceed a threshold.

Built exactly like ``nomad.transfer2`` / ``nomad.science``: named int inputs, a stated constant as a
constant input column, Fraction (or plain integer) ground truth written independently of the
reference tree, rows kept only when the answer is an integer the reference tree reproduces,
5 public / 3 challenge / 3 final rows (the final split is never read by search or WITNESS).

Input names (px py qx qy, nn tn, oa ob oc od) are disjoint from every training signature and every
earlier catalogue. Measurement only: this module lives in scripts/ and changes nothing in nomad/.
Fixed before any field arm is measured on it.
"""
from __future__ import annotations

import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nomad.science import C, Formula, V, draw_rows, exact_answer, to_task  # noqa: E402,F401  (re-exported)

DOMAINS = ("coord", "digits", "order")

PTS = ("px", "py", "qx", "qy")
NUM = ("nn", "tn")
ORD3 = ("oa", "ob", "oc")
ORD4 = ("oa", "ob", "oc", "od")

R_PTS = {"px": (-12, 12), "py": (-12, 12), "qx": (-12, 12), "qy": (-12, 12)}
R_NUM3 = {"nn": (100, 999), "tn": ("const", 10)}
R_NUM2 = {"nn": (10, 99), "tn": ("const", 10)}
R_ORD3 = {"oa": (0, 40), "ob": (0, 40), "oc": (0, 40)}
R_ORD4 = {"oa": (0, 40), "ob": (0, 40), "oc": (0, 40), "od": (0, 40)}
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


def absd(a, b):
    return sub(mx(a, b), mn(a, b))


PX, PY, QX, QY = V("px"), V("py"), V("qx"), V("qy")
NN, TN = V("nn"), V("tn")
OA, OB, OC, OD = V("oa"), V("ob"), V("oc"), V("od")


CATALOGUE: tuple[Formula, ...] = (
    # coord: two lattice points P = (px, py), Q = (qx, qy)
    _f("nv_c_taxicab", "coord", "distance", "taxicab distance |px-qx| + |py-qy|", PTS, R_PTS,
       lambda px, py, qx, qy: F(abs(px - qx) + abs(py - qy)), add(absd(PX, QX), absd(PY, QY))),
    _f("nv_c_chebyshev", "coord", "distance", "king-move distance max(|px-qx|, |py-qy|)", PTS, R_PTS,
       lambda px, py, qx, qy: F(max(abs(px - qx), abs(py - qy))), mx(absd(PX, QX), absd(PY, QY))),
    _f("nv_c_dist_sq", "coord", "distance", "squared distance (px-qx)^2 + (py-qy)^2", PTS, R_PTS,
       lambda px, py, qx, qy: F(px - qx) ** 2 + F(py - qy) ** 2,
       add(mul(sub(PX, QX), sub(PX, QX)), mul(sub(PY, QY), sub(PY, QY)))),
    _f("nv_c_dot", "coord", "vector", "dot product px qx + py qy", PTS, R_PTS,
       lambda px, py, qx, qy: F(px) * qx + F(py) * qy, add(mul(PX, QX), mul(PY, QY))),
    _f("nv_c_cross", "coord", "vector", "cross product px qy - py qx", PTS, R_PTS,
       lambda px, py, qx, qy: F(px) * qy - F(py) * qx, sub(mul(PX, QY), mul(PY, QX))),
    _f("nv_c_box_area", "coord", "box", "area of the bounding box of P and Q = |px-qx| |py-qy|", PTS, R_PTS,
       lambda px, py, qx, qy: F(abs(px - qx) * abs(py - qy)), mul(absd(PX, QX), absd(PY, QY))),
    _f("nv_c_box_perim", "coord", "box", "perimeter of the bounding box = 2(|px-qx| + |py-qy|)", PTS, R_PTS,
       lambda px, py, qx, qy: F(2 * (abs(px - qx) + abs(py - qy))), mul(C(2), add(absd(PX, QX), absd(PY, QY)))),
    _f("nv_c_tri_area2", "coord", "box", "twice the area of triangle O P Q = |px qy - py qx|", PTS, R_PTS,
       lambda px, py, qx, qy: F(abs(px * qy - py * qx)), absd(mul(PX, QY), mul(PY, QX))),
    _f("nv_c_mid_sum", "coord", "vector", "x + y of the lattice midpoint of P and Q = (px+qx)/2 + (py+qy)/2", PTS, R_PTS,
       lambda px, py, qx, qy: (F(px + qx) / 2 + F(py + qy) / 2) if (px + qx) % 2 == 0 and (py + qy) % 2 == 0 else BAD,
       add(div(add(PX, QX), C(2)), div(add(PY, QY), C(2)))),
    _f("nv_c_overlap", "coord", "box", "overlap of the x-shadows [px, qx] and [py, qy] (px < qx, py < qy) = max(0, min(qx,qy) - max(px,py))",
       PTS, R_PTS,
       lambda px, py, qx, qy: F(max(0, min(qx, qy) - max(px, py))) if px < qx and py < qy else BAD,
       mx(C(0), sub(mn(QX, QY), mx(PX, PY)))),
    # digits: decimal place value, base stated as tn = 10
    _f("nv_d_digit_sum3", "digits", "digit", "sum of the three digits of nn", NUM, R_NUM3,
       lambda nn, tn: F(sum(int(c) for c in str(nn))),
       add(add(mod(NN, TN), mod(div(NN, TN), TN)), div(NN, mul(TN, TN)))),
    _f("nv_d_tens", "digits", "digit", "tens digit of nn", NUM, R_NUM3,
       lambda nn, tn: F(int(str(nn)[-2])), mod(div(NN, TN), TN)),
    _f("nv_d_reverse2", "digits", "rearrange", "two-digit nn with its digits swapped", NUM, R_NUM2,
       lambda nn, tn: F(int(str(nn)[::-1])), add(mul(mod(NN, TN), TN), div(NN, TN))),
    _f("nv_d_swap_change", "digits", "rearrange", "digits-swapped two-digit nn minus nn", NUM, R_NUM2,
       lambda nn, tn: F(int(str(nn)[::-1]) - nn), sub(add(mul(mod(NN, TN), TN), div(NN, TN)), NN)),
    _f("nv_d_round10", "digits", "round", "nn rounded to the nearest ten (halves up)", NUM, R_NUM3,
       lambda nn, tn: F(int((F(nn) / 10 + F(1, 2)) // 1) * 10), mul(div(add(NN, div(TN, C(2))), TN), TN)),
    _f("nv_d_ends_sum", "digits", "digit", "first digit plus last digit of three-digit nn", NUM, R_NUM3,
       lambda nn, tn: F(int(str(nn)[0]) + int(str(nn)[-1])), add(div(NN, mul(TN, TN)), mod(NN, TN))),
    _f("nv_d_drop_middle", "digits", "rearrange", "three-digit nn with its middle digit removed", NUM, R_NUM3,
       lambda nn, tn: F(int(str(nn)[0] + str(nn)[2])), add(mul(div(NN, mul(TN, TN)), TN), mod(NN, TN))),
    _f("nv_d_digit_prod2", "digits", "digit", "product of the two digits of nn", NUM, R_NUM2,
       lambda nn, tn: F(int(str(nn)[0]) * int(str(nn)[1])), mul(div(NN, TN), mod(NN, TN))),
    _f("nv_d_nines", "digits", "digit", "remainder of nn's digit sum after casting out nines", NUM, R_NUM3,
       lambda nn, tn: F(sum(int(c) for c in str(nn)) % 9), mod(NN, sub(TN, C(1)))),
    _f("nv_d_alternating", "digits", "digit", "alternating digit sum: hundreds - tens + units", NUM, R_NUM3,
       lambda nn, tn: F(int(str(nn)[0]) - int(str(nn)[1]) + int(str(nn)[2])),
       add(sub(div(NN, mul(TN, TN)), mod(div(NN, TN), TN)), mod(NN, TN))),
    # order: order statistics of plain numbers
    _f("nv_o_median3", "order", "statistic", "median of oa, ob, oc", ORD3, R_ORD3,
       lambda a, b, c: F(sorted((a, b, c))[1]), mx(mn(OA, OB), mn(mx(OA, OB), OC))),
    _f("nv_o_clamp", "order", "clamp", "oa clamped to the window [ob, ob + oc]", ORD3, R_ORD3,
       lambda a, b, c: F(min(max(a, b), b + c)), mn(mx(OA, OB), add(OB, OC))),
    _f("nv_o_top_two", "order", "statistic", "sum of the two largest of oa, ob, oc", ORD3, R_ORD3,
       lambda a, b, c: F(sum(sorted((a, b, c))[1:])), sub(add(add(OA, OB), OC), mn(mn(OA, OB), OC))),
    _f("nv_o_range3", "order", "statistic", "largest minus smallest of oa, ob, oc", ORD3, R_ORD3,
       lambda a, b, c: F(max(a, b, c) - min(a, b, c)), sub(mx(mx(OA, OB), OC), mn(mn(OA, OB), OC))),
    _f("nv_o_gap_top", "order", "statistic", "how far oa is below the largest of oa, ob, oc", ORD3, R_ORD3,
       lambda a, b, c: F(max(a, b, c) - a), sub(mx(mx(OA, OB), OC), OA)),
    _f("nv_o_count_above", "order", "count", "how many of oa, ob exceed oc", ORD3, R_ORD3,
       lambda a, b, c: F(int(a > c) + int(b > c)), add(["ite", sub(OA, OC), C(1), C(0)], ["ite", sub(OB, OC), C(1), C(0)])),
    _f("nv_o_max_pair_sum", "order", "statistic", "the larger of the pair sums oa + ob and oc + od", ORD4, R_ORD4,
       lambda a, b, c, d: F(max(a + b, c + d)), mx(add(OA, OB), add(OC, OD))),
    _f("nv_o_minmax4", "order", "statistic", "the smaller of max(oa, ob) and max(oc, od)", ORD4, R_ORD4,
       lambda a, b, c, d: F(min(max(a, b), max(c, d))), mn(mx(OA, OB), mx(OC, OD))),
    _f("nv_o_middle_two4", "order", "statistic", "sum of the middle two of oa, ob, oc, od", ORD4, R_ORD4,
       lambda a, b, c, d: F(sum(sorted((a, b, c, d))[1:3])),
       sub(sub(add(add(OA, OB), add(OC, OD)), mx(mx(OA, OB), mx(OC, OD))), mn(mn(OA, OB), mn(OC, OD)))),
    _f("nv_o_second4", "order", "statistic", "second largest of oa, ob, oc, od", ORD4, R_ORD4,
       lambda a, b, c, d: F(sorted((a, b, c, d))[2]),
       mx(mn(mx(OA, OB), mx(OC, OD)), mx(mn(OA, OB), mn(OC, OD)))),
)

BY_FAMILY = {f.family: f for f in CATALOGUE}
