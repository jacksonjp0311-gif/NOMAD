"""CLAUSE2 sealed composites (docs/CLAUSE2.md): eight two-concept word problems, each ``B[slot := A]`` of two
MEANING concepts (none a MEANING concept, none one of COMBINE's or CLAUSE's, none a dev composite), told as
stories whose clauses carry one idea each, with independent Python truths. Five composites are told with the
"average" clause *before* its numbers (forward binding: "What is the average of the three ...? They are
...") and three with the numbers first (CLAUSE's backward binding). Sixteen families in domains no other
suite uses (shipyard, aquarium, bike shop, sawmill, ice rink, beehive, dairy, bookbindery); one distractor
quantity each. The field never trains on a composite or a two-concept story. Written before any field arm
was measured on them; tuning used only the uncommitted dev catalogues.
"""
from __future__ import annotations

from .meaning_tasks import COMPOSITES, Concept, K, V, _f, _gen, _r, op


def _reg(*cs: Concept) -> None:
    for c in cs:
        COMPOSITES[c.name] = c


def _avg_change_gen(rng):
    a, b, c, d = rng.randint(2, 30), rng.randint(2, 30), rng.randint(2, 30), rng.randint(2, 6)
    return {"a": a, "b": b, "c": c, "d": d, "e": ((a + b + c) // 3) * d + rng.randint(0, 40)}


_AVG3 = op("div", op("add", op("add", V("a"), V("b")), V("c")), K(3))
_MEAN2 = op("div", op("add", V("a"), V("b")), K(2))

_reg(
    Concept("cr_avg_left", ("a", "b", "c", "d"), op("mod", _AVG3, V("d")),
            lambda a, b, c, d: ((a + b + c) // 3) % d, _gen(a=_r(5, 90), b=_r(5, 90), c=_r(5, 90), d=_r(3, 9))),
    Concept("cr_avg_change", ("a", "b", "c", "d", "e"), op("sub", V("e"), op("mul", _AVG3, V("d"))),
            lambda a, b, c, d, e: e - ((a + b + c) // 3) * d, _avg_change_gen),
    Concept("cr_mean_round", ("a", "b", "c"), op("mul", op("mul", _MEAN2, V("c")), K(2)),
            lambda a, b, c: ((a + b) // 2) * c * 2, _gen(a=_r(2, 60), b=_r(2, 60), c=_r(2, 7))),
    Concept("cr_mean_boxes", ("a", "b", "c"), op("div", op("add", _MEAN2, op("sub", V("c"), K(1))), V("c")),
            lambda a, b, c: ((a + b) // 2 + c - 1) // c, _gen(a=_r(5, 90), b=_r(5, 90), c=_r(2, 9))),
    Concept("cr_avg_share", ("a", "b", "c", "d", "e"), op("div", op("mul", _AVG3, V("d")), V("e")),
            lambda a, b, c, d, e: (((a + b + c) // 3) * d) // e,
            _gen(a=_r(2, 40), b=_r(2, 40), c=_r(2, 40), d=_r(2, 9), e=_r(2, 7))),
    Concept("cr_area_round", ("a", "b", "c"), op("mul", op("mul", op("mul", V("a"), V("b")), V("c")), K(2)),
            lambda a, b, c: a * b * c * 2, _gen(a=_r(2, 12), b=_r(2, 30), c=_r(2, 7))),
    Concept("cr_bundle_left", ("a", "b", "c", "d"), op("mod", op("mul", op("add", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: ((a + b) * c) % d, _gen(a=_r(2, 12), b=_r(2, 12), c=_r(2, 9), d=_r(3, 9))),
    Concept("cr_sum_boxes", ("a", "b", "c", "d"),
            op("div", op("add", op("add", op("add", V("a"), V("b")), V("c")), op("sub", V("d"), K(1))), V("d")),
            lambda a, b, c, d: (a + b + c + d - 1) // d, _gen(a=_r(2, 60), b=_r(2, 60), c=_r(2, 60), d=_r(2, 9))),
)

SEALED = (
    # forward: the "average" clause comes before its numbers
    _f("cw_hive_left", "cr_avg_left", "beehive", "What is the average of the three hives? They give {a}, {b} and {c} jars of honey, and the keeper owns {x} hats. The jars are packed into crates of {d}. How many jars are left over that do not fill a crate?", ("x",)),
    _f("cw_mill_left", "cr_avg_left", "sawmill", "Find the average of the three loads: {a}, {b} and {c} planks. The planks are stacked into bundles of {d}, and the mill has {x} saws. How many planks are left over without a full bundle?", ("x",)),
    _f("cw_rink_change", "cr_avg_change", "ice rink", "What is the average of the three nights? The rink rented {a}, {b} and {c} pairs of skates. A club buys that many tickets at {d} dollars each and pays with {e} dollars, and the rink has {x} lights. How much change comes back?", ("x",)),
    _f("cw_bike_change", "cr_avg_change", "bike shop", "The shop takes the average of three weeks of repairs, {a}, {b} and {c}. A rider buys that many bells at {d} dollars each, the shop has {x} stands, and the rider pays with {e} dollars. How much change comes back?", ("x",)),
    _f("cw_tank_round", "cr_mean_round", "aquarium", "What is the average of the two tanks? They are {a} and {b} meters from the door, and the aquarium has {x} pumps. A keeper walks that distance there and back {c} times. How many meters are walked?", ("x",)),
    _f("cw_dock_round", "cr_mean_round", "shipyard", "Find the average of the two docks: {a} and {b} meters from the gate. A welder walks that far there and back {c} times a day, with {x} cranes in the yard. How far does the welder walk?", ("x",)),
    _f("cw_milk_boxes", "cr_mean_boxes", "dairy", "What is the average of the two milkings? The cows gave {a} and {b} liters, and the dairy has {x} barns. The milk goes into cans that hold {c} each. How many cans are needed for all the milk?", ("x",)),
    _f("cw_book_boxes", "cr_mean_boxes", "bookbindery", "Take the average of the two orders: {a} and {b} books. The books are packed into boxes that hold {c} each, and the bindery has {x} presses. How many boxes are needed to hold all the books?", ("x",)),
    _f("cw_hive_share", "cr_avg_share", "beehive", "What is the average of the three days? The bees fill {a}, {b} and {c} combs. There are {d} frames of that many combs, shared equally among {e} keepers, with {x} hives on the hill. How many combs does each keeper get?", ("x",)),
    _f("cw_dairy_share", "cr_avg_share", "dairy", "Find the average of the three churns: {a}, {b} and {c} pats of butter. {d} trays of that many pats are split equally between {e} shops, and the dairy has {x} cows. How many pats does each shop get?", ("x",)),
    # backward: the numbers come first (CLAUSE's binding)
    _f("cw_pier_round", "cr_area_round", "shipyard", "A pier is built of {a} sections with {b} meters in each section. A worker walks the pier there and back {c} times, and the yard has {x} boats. How many meters are walked?", ("x",)),
    _f("cw_glass_round", "cr_area_round", "aquarium", "A glass tunnel has {a} panels with {b} steps in each panel, and the aquarium has {x} sharks. A diver goes there and back through it {c} times. How many steps in total?", ("x",)),
    _f("cw_wheel_left", "cr_bundle_left", "bike shop", "Each box holds {a} front wheels and {b} back wheels, and there are {c} boxes. The wheels are packed into racks of {d}, and the shop is {x} years old. How many wheels are left over that do not fill a rack?", ("x",)),
    _f("cw_skate_left", "cr_bundle_left", "ice rink", "Each locker holds {a} skates and {b} helmets, and there are {c} lockers. The gear is packed into bags of {d}, with {x} coaches on the ice. How many pieces are left over that do not fill a bag?", ("x",)),
    _f("cw_log_boxes", "cr_sum_boxes", "sawmill", "Three trucks bring {a}, {b} and {c} logs, and the mill has {x} workers. The logs are loaded onto carts that hold {d} each. How many carts are needed for all the logs?", ("x",)),
    _f("cw_page_boxes", "cr_sum_boxes", "bookbindery", "Three presses print {a}, {b} and {c} pages. The pages are packed into folders that hold {d} each, and the bindery opened {x} years ago. How many folders are needed to hold all the pages?", ("x",)),
)
SEALED_NAMES = ("ya", "yb", "yc", "yd", "ye", "yf", "yg")
