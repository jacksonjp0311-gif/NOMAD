"""CLAUSE sealed composites (docs/CLAUSE.md): eight two-concept word problems, each ``B[slot := A]`` of two
MEANING concepts (none a MEANING concept, none one of COMBINE's), told as stories whose clauses carry one
idea each, with independent Python truths. Sixteen families in domains no other suite uses (greenhouse,
ferry, cannery, quarry, planetarium, clock shop, tannery, orchard); one or two distractor quantities each.
The field never trains on a composite or a two-concept story. Written before any field arm was measured
on them; tuning used only the uncommitted dev catalogue.
"""
from __future__ import annotations

from .meaning_tasks import COMPOSITES, Concept, K, V, _f, _gen, _r, op


def _reg(*cs: Concept) -> None:
    for c in cs:
        COMPOSITES[c.name] = c


def _net_gen(rng):
    a, b = rng.randint(3, 9), rng.randint(3, 9)
    return {"a": a, "b": b, "c": rng.randint(1, min(5, a * b // 3)), "d": rng.randint(1, min(5, a * b // 3))}


def _bundle_change_gen(rng):
    a, b, c, d = rng.randint(1, 5), rng.randint(1, 5), rng.randint(2, 4), rng.randint(2, 4)
    return {"a": a, "b": b, "c": c, "d": d, "e": (a + b) * c * d + rng.randint(0, 20)}


def _frame_boxes_gen(rng):
    c, d = rng.randint(1, 4), rng.randint(1, 4)
    return {"a": rng.randint(c + 2, 9), "b": rng.randint(d + 2, 9), "c": c, "d": d, "e": rng.randint(2, 9)}


_reg(
    Concept("cq_boxes_volume", ("a", "b", "c", "d"),
            op("div", op("add", op("mul", op("mul", V("a"), V("b")), V("c")), op("sub", V("d"), K(1))), V("d")),
            lambda a, b, c, d: (a * b * c + d - 1) // d, _gen(a=_r(2, 6), b=_r(2, 6), c=_r(2, 6), d=_r(2, 9))),
    Concept("cq_left_two", ("a", "b", "c", "d", "e"),
            op("mod", op("add", op("mul", V("a"), V("b")), op("mul", V("c"), V("d"))), V("e")),
            lambda a, b, c, d, e: (a * b + c * d) % e, _gen(a=_r(2, 9), b=_r(2, 9), c=_r(2, 9), d=_r(2, 9), e=_r(3, 9))),
    Concept("cq_mean_product", ("a", "b", "c"), op("div", op("add", op("mul", V("a"), V("b")), V("c")), K(2)),
            lambda a, b, c: (a * b + c) // 2, _gen(a=_r(2, 9), b=_r(2, 9), c=_r(1, 40))),
    Concept("cq_net_area", ("a", "b", "c", "d"), op("sub", op("sub", op("mul", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: a * b - c - d, _net_gen),
    Concept("cq_change_bundle", ("a", "b", "c", "d", "e"),
            op("sub", V("e"), op("mul", op("mul", op("add", V("a"), V("b")), V("c")), V("d"))),
            lambda a, b, c, d, e: e - (a + b) * c * d, _bundle_change_gen),
    Concept("cq_left_groups", ("a", "b", "c", "d"), op("mod", op("add", op("mul", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: (a * b + c) % d, _gen(a=_r(2, 9), b=_r(2, 9), c=_r(1, 15), d=_r(3, 9))),
    Concept("cq_boxes_frame", ("a", "b", "c", "d", "e"),
            op("div", op("add", op("sub", op("mul", V("a"), V("b")), op("mul", V("c"), V("d"))), op("sub", V("e"), K(1))), V("e")),
            lambda a, b, c, d, e: (a * b - c * d + e - 1) // e, _frame_boxes_gen),
    Concept("cq_trip_mean", ("a", "b", "c"), op("mul", op("mul", op("div", op("add", V("a"), V("b")), K(2)), V("c")), K(2)),
            lambda a, b, c: ((a + b) // 2) * c * 2, _gen(a=_r(1, 30), b=_r(1, 30), c=_r(2, 7))),
)

SEALED = (
    _f("cl_greenhouse_crates", "cq_boxes_volume", "greenhouse", "A greenhouse has {a} shelves, each shelf has {b} trays and each tray holds {c} pots. The pots are packed into crates that hold {d} each. The greenhouse is {x} years old. How many crates are needed to hold all the pots?", ("x",)),
    _f("cl_ferry_pallets", "cq_boxes_volume", "ferry", "A ferry deck has {a} lanes with {b} cars on each lane and {c} boxes in each car. The boxes go onto pallets that hold {d} each, on a route of {x} miles. How many pallets are needed for all the boxes?", ("x",)),
    _f("cl_cannery_left", "cq_left_two", "cannery", "One shelf has {a} rows of {b} cans and another shelf has {c} rows of {d} cans. The cans are packed into cases of {e}. The cannery has {x} workers. How many cans are left over that do not fill a case?", ("x",)),
    _f("cl_quarry_left", "cq_left_two", "quarry", "One wall of the quarry is {a} by {b} blocks and a second wall is {c} by {d} blocks. The blocks are loaded onto trucks of {e}, and the quarry is {x} meters deep. How many blocks are left over without a full truck?", ("x",)),
    _f("cl_dome_mean", "cq_mean_product", "planetarium", "One hall has {a} rows of {b} seats and a small hall has {c} seats, and the planetarium has {x} lamps. What is the average of the two halls?", ("x",)),
    _f("cl_orchard_mean", "cq_mean_product", "orchard", "One field has {a} rows of {b} trees and a small plot has {c} trees, with {x} pickers on the farm. What is the average of the field and the plot?", ("x",)),
    _f("cl_clock_left", "cq_net_area", "clock shop", "A display wall is laid in {a} rows with {b} clocks in each row. {c} clocks are sold on Monday and {d} clocks on Tuesday, and the shop has {x} lamps. How many clocks are left?", ("x",)),
    _f("cl_hide_left", "cq_net_area", "tannery", "A drying rack has {a} rows with {b} hides in each row; {c} hides are sold in spring and {d} hides in summer. The tannery has {x} workers. How many hides remain?", ("x",)),
    _f("cl_flower_change", "cq_change_bundle", "greenhouse", "Each bag holds {a} tulips and {b} roses, and a buyer takes {c} bags. Every flower costs {d} dollars, and the buyer pays with {e} dollars, in a greenhouse of {x} rooms. How much change comes back?", ("x",)),
    _f("cl_ferry_change", "cq_change_bundle", "ferry", "A tour boat takes {c} groups of {a} adults and {b} children. Each ticket costs {d} dollars and the host pays with {e} dollars, with {x} lifebelts on board. How much change comes back?", ("x",)),
    _f("cl_cannery_loose", "cq_left_groups", "cannery", "There are {a} cartons with {b} cans in each carton, plus {c} loose cans. The cans go into cases of {d}, and the cannery has {x} workers. How many cans are left over without a full case?", ("x",)),
    _f("cl_quarry_loose", "cq_left_groups", "quarry", "A yard has {a} stacks with {b} stones in each stack, plus {c} more stones. The stones are loaded in trucks of {d}, and the quarry is {x} meters deep. How many stones are left over that do not fill a truck?", ("x",)),
    _f("cl_dome_crates", "cq_boxes_frame", "planetarium", "A glass ceiling is {a} by {b} panels with a hole of {c} by {d} panels cut out of it. The panels are packed into crates that hold {e} each, and there are {x} domes. How many crates are needed for the panels that remain?", ("x",)),
    _f("cl_clock_boxes", "cq_boxes_frame", "clock shop", "A wall is {a} by {b} with a window of {c} by {d}, and the wall is {x} floors up. The tiles are packed into boxes that hold {e} each. How many boxes are needed for the wall that is left?", ("x",)),
    _f("cl_orchard_trip", "cq_trip_mean", "orchard", "The first tree is {a} meters away and the second tree is {b} meters away. What is the average of the two distances? A picker walks that distance there and back {c} times, with {x} baskets. How many meters are walked?", ("x",)),
    _f("cl_ferry_trip", "cq_trip_mean", "ferry", "Two docks are {a} and {b} kilometers away. What is the average of the two? A ferry sails that far there and back {c} times a day, with {x} ferries in service. How many kilometers are sailed?", ("x",)),
)
SEALED_NAMES = ("qa", "qb", "qc", "qd", "qe", "qf", "qg")
