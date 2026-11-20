"""SCIENCE: the first science problem generator (integer physics and stoichiometry).

A science task is a WORLD int task whose rows are textbook "givens" and whose
answer is one exactly checkable number. Every family has

- named integer inputs (``u``, ``a``, ``t`` ...); a fixed physical or unit
  constant the problem states (60 s/min, 1000 m/km, 18 g/mol ...) is given as
  a constant input column (``k``, ``kW`` ...), exactly like a textbook problem
  lists the constants it uses. No interpreter, DSL or WITNESS change: the
  existing ``int`` opset (add, sub, mul, div, mod, min, max, ite) and the
  fixed constants 0-3 are all the search ever gets;
- a ground-truth function written with ``fractions.Fraction`` (independent
  of the program tree), and a reference program tree in the WORLD DSL. Rows
  are drawn by a seeded RNG and *kept only* when the exact rational answer is
  an integer and the reference tree, run by the WORLD interpreter, gives that
  same integer (so every division in the tree is exact on every row). WITNESS
  therefore stays exact-match: no tolerance, no floats;
- ``domain = "science"`` and a ``kind`` in ``KINDS`` so the sensing step can
  key on it (``science_tag(task)``, ``is_science(family)``).

Everything here is integer physics with chosen-to-be-exact inputs. It is a
checkable science *slice*, not open-ended scientific reasoning.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from fractions import Fraction as F
from typing import Callable

from .world import Invalid, WorldTask, make_task, run

DOMAIN = "science"
KINDS = ("kinematics", "mechanics", "physics_units", "stoich")
N_PUBLIC, N_CHALLENGE, N_FINAL = 5, 3, 3


def V(n: str) -> list:
    return ["var", n]


def C(k: int) -> list:
    return ["const", k]


@dataclass(frozen=True)
class Formula:
    family: str
    kind: str
    text: str
    inputs: tuple[str, ...]                        # all int; order is the task signature
    ranges: dict                                   # var -> (lo, hi) | ("const", k) | ("step", lo, hi, step)
    truth: Callable[..., F]                        # exact ground truth (Fraction)
    tree: list                                     # reference program (WORLD DSL)
    curriculum: tuple[str, ...] = field(default=())  # families that teach its blocks (documentation)


def _q(*a):
    return F(a[0]) if len(a) == 1 else a


# ------------------------------------------------------------------ catalogue
# Families are fixed here, before any field arm is measured. Which tier
# (easy curriculum vs sealed hard) a family lands in is decided only by the
# cold control at the deep-suite criterion (scripts/science_suite.py).
U = ("u", "a", "t")
UAD = ("u", "a", "d")
UVT = ("u", "v", "t")
MUV = ("m", "u", "v")
IRT = ("I", "R", "t")
HMS = ("h", "m", "s", "k")
VTK = ("v", "t", "k", "c")
STO = ("gH", "gO", "kH", "kO", "kW")

R_UAT = {"u": (0, 20), "a": (-3, 6), "t": (1, 12)}
R_UAD = {"u": (0, 20), "a": (1, 6), "d": (1, 40)}
R_UVT = {"u": (0, 20), "v": (0, 30), "t": (2, 12)}
R_MUV = {"m": (1, 20), "u": (0, 15), "v": (0, 20)}
R_IRT = {"I": (1, 12), "R": (1, 20), "t": (1, 30)}
R_HMS = {"h": (0, 9), "m": (0, 59), "s": (0, 59), "k": ("const", 60)}
R_VTK = {"v": (1, 120), "t": (1, 120), "k": ("const", 1000), "c": ("const", 3600)}
R_STO = {"gH": ("step", 2, 60, 2), "gO": ("step", 32, 640, 32),
         "kH": ("const", 2), "kO": ("const", 32), "kW": ("const", 18)}

CATALOGUE: tuple[Formula, ...] = (
    # kinematics, signature (u, a, t)
    Formula("sci_velocity", "kinematics", "v = u + a*t", U, R_UAT,
            lambda u, a, t: F(u) + F(a) * t, ["add", V("u"), ["mul", V("a"), V("t")]]),
    Formula("sci_dv", "kinematics", "dv = a*t", U, R_UAT,
            lambda u, a, t: F(a) * t, ["mul", V("a"), V("t")]),
    Formula("sci_d_rest", "kinematics", "d = a*t^2/2 (from rest)", U, R_UAT,
            lambda u, a, t: F(a) * t * t / 2, ["div", ["mul", V("a"), ["mul", V("t"), V("t")]], C(2)]),
    Formula("sci_displacement", "kinematics", "d = u*t + a*t^2/2", U, R_UAT,
            lambda u, a, t: F(u) * t + F(a) * t * t / 2,
            ["add", ["mul", V("u"), V("t")], ["div", ["mul", V("a"), ["mul", V("t"), V("t")]], C(2)]],
            ("sci_d_rest",)),
    Formula("sci_vmean_uat", "kinematics", "mean velocity = u + a*t/2", U, R_UAT,
            lambda u, a, t: F(u) + F(a) * t / 2, ["add", V("u"), ["div", ["mul", V("a"), V("t")], C(2)]],
            ("sci_dv",)),
    # kinematics, signature (u, a, d)
    Formula("sci_2ad", "kinematics", "2*a*d", UAD, R_UAD,
            lambda u, a, d: 2 * F(a) * d, ["mul", C(2), ["mul", V("a"), V("d")]]),
    Formula("sci_vsq", "kinematics", "v^2 = u^2 + 2*a*d", UAD, R_UAD,
            lambda u, a, d: F(u) * u + 2 * F(a) * d,
            ["add", ["mul", V("u"), V("u")], ["mul", C(2), ["mul", V("a"), V("d")]]], ("sci_2ad",)),
    # kinematics, signature (u, v, t)
    Formula("sci_accel", "kinematics", "a = (v - u)/t", UVT, R_UVT,
            lambda u, v, t: (F(v) - u) / t, ["div", ["sub", V("v"), V("u")], V("t")]),
    Formula("sci_vavg", "kinematics", "(u + v)/2", UVT, R_UVT,
            lambda u, v, t: (F(u) + v) / 2, ["div", ["add", V("u"), V("v")], C(2)]),
    Formula("sci_d_uvt", "kinematics", "d = (u + v)*t/2", UVT, R_UVT,
            lambda u, v, t: (F(u) + v) * t / 2, ["div", ["mul", ["add", V("u"), V("v")], V("t")], C(2)],
            ("sci_vavg",)),
    # mechanics, signature (m, u, v)
    Formula("sci_dp", "mechanics", "impulse = m*(v - u)", MUV, R_MUV,
            lambda m, u, v: F(m) * (v - u), ["mul", V("m"), ["sub", V("v"), V("u")]]),
    Formula("sci_ke_v", "mechanics", "KE = m*v^2/2", MUV, R_MUV,
            lambda m, u, v: F(m) * v * v / 2, ["div", ["mul", V("m"), ["mul", V("v"), V("v")]], C(2)]),
    Formula("sci_ke_u", "mechanics", "KE0 = m*u^2/2", MUV, R_MUV,
            lambda m, u, v: F(m) * u * u / 2, ["div", ["mul", V("m"), ["mul", V("u"), V("u")]], C(2)]),
    Formula("sci_dke", "mechanics", "work = m*(v^2 - u^2)/2", MUV, R_MUV,
            lambda m, u, v: F(m) * (F(v) * v - F(u) * u) / 2,
            ["div", ["sub", ["mul", V("m"), ["mul", V("v"), V("v")]], ["mul", V("m"), ["mul", V("u"), V("u")]]], C(2)],
            ("sci_ke_v", "sci_ke_u")),
    # mechanics (electrical energy), signature (I, R, t)
    Formula("sci_volt", "mechanics", "V = I*R", IRT, R_IRT,
            lambda I, R, t: F(I) * R, ["mul", V("I"), V("R")]),
    Formula("sci_power", "mechanics", "P = I^2*R", IRT, R_IRT,
            lambda I, R, t: F(I) * I * R, ["mul", ["mul", V("I"), V("I")], V("R")]),
    Formula("sci_energy", "mechanics", "E = I^2*R*t", IRT, R_IRT,
            lambda I, R, t: F(I) * I * R * t, ["mul", ["mul", ["mul", V("I"), V("I")], V("R")], V("t")],
            ("sci_power",)),
    # unit conversions, signature (h, m, s, k=60)
    Formula("sci_hm_to_min", "physics_units", "h:m -> minutes", HMS, R_HMS,
            lambda h, m, s, k: F(h) * k + m, ["add", ["mul", V("h"), V("k")], V("m")]),
    Formula("sci_ms_to_s", "physics_units", "m:s -> seconds", HMS, R_HMS,
            lambda h, m, s, k: F(m) * k + s, ["add", ["mul", V("m"), V("k")], V("s")]),
    Formula("sci_hm_to_s", "physics_units", "h:m -> seconds", HMS, R_HMS,
            lambda h, m, s, k: (F(h) * k + m) * k, ["mul", ["add", ["mul", V("h"), V("k")], V("m")], V("k")]),
    Formula("sci_hms_to_s", "physics_units", "h:m:s -> seconds", HMS, R_HMS,
            lambda h, m, s, k: (F(h) * k + m) * k + s,
            ["add", ["mul", ["add", ["mul", V("h"), V("k")], V("m")], V("k")], V("s")], ("sci_hm_to_s",)),
    # unit conversions, signature (v km/h, t s, k=1000 m/km, c=3600 s/h)
    Formula("sci_kmh_to_ms", "physics_units", "km/h -> m/s", VTK, R_VTK,
            lambda v, t, k, c: F(v) * k / c, ["div", ["mul", V("v"), V("k")], V("c")]),
    Formula("sci_dist_m", "physics_units", "metres covered at v km/h in t s", VTK, R_VTK,
            lambda v, t, k, c: F(v) * k * t / c, ["div", ["mul", ["mul", V("v"), V("k")], V("t")], V("c")],
            ("sci_kmh_to_ms",)),
    # stoichiometry: 2 H2 + O2 -> 2 H2O, grams in, molar masses as constants
    Formula("sci_mol_h2", "stoich", "mol H2 = g/2", STO, R_STO,
            lambda gH, gO, kH, kO, kW: F(gH) / kH, ["div", V("gH"), V("kH")]),
    Formula("sci_water_olim", "stoich", "mol H2O if O2 limits = 2*gO/32", STO, R_STO,
            lambda gH, gO, kH, kO, kW: 2 * F(gO) / kO, ["mul", C(2), ["div", V("gO"), V("kO")]]),
    Formula("sci_water_hlim_g", "stoich", "g H2O if H2 limits = 18*gH/2", STO, R_STO,
            lambda gH, gO, kH, kO, kW: F(kW) * gH / kH, ["mul", V("kW"), ["div", V("gH"), V("kH")]]),
    Formula("sci_water_mol", "stoich", "mol H2O = min(gH/2, 2*gO/32)", STO, R_STO,
            lambda gH, gO, kH, kO, kW: min(F(gH) / kH, 2 * F(gO) / kO),
            ["min", ["div", V("gH"), V("kH")], ["mul", C(2), ["div", V("gO"), V("kO")]]],
            ("sci_water_olim", "sci_water_hlim_g")),
    Formula("sci_water_g", "stoich", "g H2O = 18*min(gH/2, 2*gO/32)", STO, R_STO,
            lambda gH, gO, kH, kO, kW: F(kW) * min(F(gH) / kH, 2 * F(gO) / kO),
            ["mul", V("kW"), ["min", ["div", V("gH"), V("kH")], ["mul", C(2), ["div", V("gO"), V("kO")]]]],
            ("sci_water_olim", "sci_water_hlim_g")),
)
BY_FAMILY = {f.family: f for f in CATALOGUE}


def _draw(rng: random.Random, spec) -> int:
    if spec[0] == "const":
        return spec[1]
    if spec[0] == "step":
        _, lo, hi, st = spec
        return rng.randrange(lo, hi + 1, st)
    return rng.randint(spec[0], spec[1])


def exact_answer(f: Formula, row: dict) -> int | None:
    """The exact ground truth if it is an integer the reference tree reproduces."""
    try:
        q = F(f.truth(*(row[n] for n in f.inputs)))
    except ZeroDivisionError:
        return None
    if q.denominator != 1:
        return None
    try:
        got = run(f.tree, row)
    except Invalid:
        return None
    return int(q) if got == int(q) else None


def draw_rows(f: Formula, rng: random.Random, n: int = N_PUBLIC + N_CHALLENGE + N_FINAL,
              tries: int = 20000) -> list[tuple[dict, int]]:
    """n distinct rows with exact integer answers; public outputs not constant."""
    for _ in range(50):
        rows, seen = [], set()
        for _ in range(tries):
            if len(rows) == n:
                break
            r = {k: _draw(rng, f.ranges[k]) for k in f.inputs}
            key = tuple(r[k] for k in f.inputs)
            if key in seen:
                continue
            ans = exact_answer(f, r)
            if ans is None:
                continue
            seen.add(key)
            rows.append((r, ans))
        if len(rows) == n and len({a for _, a in rows[:N_PUBLIC]}) > 1:
            return rows
    raise RuntimeError(f"could not draw rows for {f.family}")


def to_task(entry: dict) -> WorldTask:
    """A suite entry (family, inputs, rows) as a WORLD task on the int opset."""
    rows = [(dict(r), e) for r, e in entry["rows"]]
    a, b = N_PUBLIC, N_PUBLIC + N_CHALLENGE
    return make_task(entry["task_id"], entry["family"], "int", {n: "int" for n in entry["inputs"]}, "int",
                     rows[:a], rows[a:b], rows[b:], entry.get("level", 9))


def is_science(family: str | None) -> bool:
    return bool(family) and family in BY_FAMILY


def science_tag(task_or_family) -> dict | None:
    """{"domain": "science", "kind": ...} for a science task/family, else None."""
    fam = getattr(task_or_family, "family", task_or_family)
    f = BY_FAMILY.get(fam)
    return {"domain": DOMAIN, "kind": f.kind} if f else None
