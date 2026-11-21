"""COMBINE two-concept word problems (docs/COMBINE.md).

Each *composite* is a program built from two MEANING concepts, the output of one filling a variable
of the other, with an independent Python truth. No composite is a MEANING concept, and the field
never trains on a composite or a two-concept story: the sealed families test whether NOMAD can
answer a story that chains two ideas it learned separately. Stories are written out with the
numbers of the first public row (``meaning_tasks.story_entry``), carry one or two distractor
quantities, and use domains no other suite uses.
"""
from __future__ import annotations

from .meaning_tasks import COMPOSITES, Concept, K, V, _f, _gen, _r, op


def _reg(*cs: Concept) -> None:
    for c in cs:
        COMPOSITES[c.name] = c


def _pos_net_gen(rng):
    b, c = rng.randint(1, 9), rng.randint(1, 9)
    return {"a": rng.randint(2, 6), "b": rng.randint(2, 6), "c": rng.randint(1, 9), "d": b, "e": c}


# sealed composites (disjoint from every dev composite)
_reg(
    Concept("cb_boxes_two_areas", ("a", "b", "c", "d", "e"),
            op("div", op("add", op("add", op("mul", V("a"), V("b")), op("mul", V("c"), V("d"))), op("sub", V("e"), K(1))), V("e")),
            lambda a, b, c, d, e: (a * b + c * d + e - 1) // e,
            _gen(a=_r(2, 9), b=_r(2, 9), c=_r(2, 9), d=_r(2, 9), e=_r(2, 9))),
    Concept("cb_left_volume", ("a", "b", "c", "d"), op("mod", op("mul", op("mul", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: (a * b * c) % d, _gen(a=_r(2, 9), b=_r(2, 9), c=_r(2, 9), d=_r(3, 9))),
    Concept("cb_mean2_times", ("a", "b", "c"), op("mul", op("div", op("add", V("a"), V("b")), K(2)), V("c")),
            lambda a, b, c: ((a + b) // 2) * c, _gen(a=_r(1, 30), b=_r(1, 30), c=_r(2, 9))),
    Concept("cb_change_sum", ("a", "b", "c", "d", "e"), op("sub", V("e"), op("mul", op("add", op("add", V("a"), V("b")), V("c")), V("d"))),
            lambda a, b, c, d, e: e - (a + b + c) * d,
            lambda rng: (lambda a, b, c, d: {"a": a, "b": b, "c": c, "d": d, "e": (a + b + c) * d + rng.randint(0, 25)})(
                rng.randint(1, 6), rng.randint(1, 6), rng.randint(1, 6), rng.randint(2, 5))),
    Concept("cb_trip_legs", ("a", "b", "c", "d"), op("mul", op("mul", op("add", op("add", V("a"), V("b")), V("c")), V("d")), K(2)),
            lambda a, b, c, d: (a + b + c) * d * 2, _gen(a=_r(1, 12), b=_r(1, 12), c=_r(1, 12), d=_r(2, 6))),
    Concept("cb_net_groups", ("a", "b", "c", "d", "e"),
            op("sub", op("sub", op("add", op("mul", V("a"), V("b")), V("c")), V("d")), V("e")),
            lambda a, b, c, d, e: a * b + c - d - e, _pos_net_gen),
    Concept("cb_avg3_product", ("a", "b", "c", "d"), op("div", op("add", op("add", op("mul", V("a"), V("b")), V("c")), V("d")), K(3)),
            lambda a, b, c, d: (a * b + c + d) // 3, _gen(a=_r(2, 9), b=_r(2, 9), c=_r(1, 40), d=_r(1, 40))),
    Concept("cb_change_weeks", ("a", "b", "c", "d"), op("mul", op("sub", V("c"), op("mul", V("a"), V("b"))), V("d")),
            lambda a, b, c, d: (c - a * b) * d, lambda rng: (lambda a, b: {"a": a, "b": b, "c": a * b + rng.randint(1, 20), "d": rng.randint(2, 7)})(rng.randint(2, 6), rng.randint(2, 6))),
)


# sealed two-concept stories (six domains no other suite uses); written before any field arm is measured
SEALED = (
    _f("cs_lamp_boxes", "cb_boxes_two_areas", "lighthouse", "The keeper's two rooms are {a} by {b} tiles and {c} by {d} tiles, and tiles are sold in boxes of {e}; the tower is {x} meters tall. How many boxes of tiles are needed for both rooms?", ("x",)),
    _f("cs_hive_boxes", "cb_boxes_two_areas", "apiary", "One field has {a} rows of {b} hives and another field has {c} rows of {d} hives, and a truck carries {e} hives at a time, over {x} miles with {y} beekeepers. How many truck loads move every hive?", ("x", "y")),
    _f("cs_jar_left", "cb_left_volume", "apiary", "A shed holds {a} shelves with {b} crates on each shelf and {c} jars in each crate, and the jars are packed into gift sets of {d}, for {x} shops. How many jars are left over without a full set?", ("x",)),
    _f("cs_cup_left", "cb_left_volume", "pottery studio", "A kiln has {a} racks, each rack has {b} trays and each tray holds {c} cups; the cups go into boxes of {d}, fired at {x} degrees for {y} hours. How many cups are left over without a full box?", ("x", "y")),
    _f("cs_avg_lanes", "cb_mean2_times", "bowling alley", "One lane scores {a} pins and another lane scores {b} pins in a frame, and the average of the two lanes is kept up for {c} frames, with {x} bowlers. How many pins is that in total?", ("x",)),
    _f("cs_avg_oxygen", "cb_mean2_times", "space station", "Two tanks give {a} and {b} liters of oxygen an hour, and the station uses the average of the two for {c} hours, while {x} astronauts sleep and {y} modules stay sealed. How many liters are used?", ("x", "y")),
    _f("cs_shoe_change", "cb_change_sum", "bowling alley", "A team rents {a}, {b} and {c} pairs of shoes in three games at {d} dollars a pair and pays with {e} dollars, on lane {x}. How much change comes back?", ("x",)),
    _f("cs_clay_change", "cb_change_sum", "pottery studio", "A potter buys {a}, {b} and {c} bags of clay on three days at {d} dollars a bag, starting with {e} dollars, in a studio of {x} wheels and {y} kilns. How many dollars are left?", ("x", "y")),
    _f("cs_stairs_legs", "cb_trip_legs", "lighthouse", "The path is {a} steps to the gate, {b} steps to the door and {c} steps up the stairs, and the keeper goes there and back {d} times a day with {x} lamps. How many steps a day?", ("x",)),
    _f("cs_hose_legs", "cb_trip_legs", "fire station", "The hose runs {a} meters to the truck, {b} meters to the hydrant and {c} meters to the house, and a firefighter walks it there and back {d} times, with {x} ladders and {y} helmets. How many meters are walked?", ("x", "y")),
    _f("cs_suits_used", "cb_net_groups", "space station", "A locker holds {a} racks of {b} suits plus {c} spare suits; {d} suits go out on the first walk and {e} on the second, at an orbit of {x} kilometers. How many suits are left in the locker?", ("x",)),
    _f("cs_hose_used", "cb_net_groups", "fire station", "The store has {a} reels of {b} hoses each plus {c} loose hoses; {d} hoses go to one fire and {e} to another, with {x} trucks and {y} sirens. How many hoses are left?", ("x", "y")),
    _f("cs_avg_honey", "cb_avg3_product", "apiary", "The first hive gives {a} frames of {b} grams of honey, the second gives {c} grams and the third {d} grams, with {x} bees on guard. What is the average yield of the three hives?", ("x",)),
    _f("cs_avg_pins", "cb_avg3_product", "bowling alley", "The first team knocks {a} frames of {b} pins, the second team knocks {c} pins and the third {d} pins, on a night with {x} lanes and {y} snacks. What is the average score of the three teams?", ("x", "y")),
    _f("cs_fuel_weeks", "cb_change_weeks", "space station", "Each week the station gets {c} liters of fuel and burns {a} engines at {b} liters each, for {d} weeks, with {x} panels. How many liters are saved over all the weeks?", ("x",)),
    _f("cs_glaze_weeks", "cb_change_weeks", "pottery studio", "Each week a potter is given {c} dollars and spends it on {a} pots of glaze at {b} dollars each, for {d} weeks, at a studio with {x} windows and {y} shelves. How many dollars are kept over all the weeks?", ("x", "y")),
)
SEALED_NAMES = ("ja", "jb", "jc", "jd", "je", "jf", "jg")
