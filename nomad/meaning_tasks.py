"""MEANING word-problem catalogue (docs/MEANING.md): integer tasks that carry a text description.

Each *concept* is an integer program over role variables ``a b c d`` with an
independent Python truth. A *family* is one concept told in one domain's
words: a description template whose ``{a}``.. ``{d}`` stand for the roles and
``{x}`` ``{y}`` for distractor quantities the story mentions but the answer
does not use. Numbers never appear in a description (only ``{placeholders}``),
so the words carry the structure and the public rows carry the data.

- ``TRAIN``: training families (kitchen, garden, school, workshop words). Their
  inputs are exactly the concept's roles; they are the only word tasks the
  field ever learns from.
- Held-out families (dev: uncommitted, under the dev directory; sealed:
  ``SEALED`` below, written before any field arm is measured on them) share
  concepts with training but use other domains, other nouns, other input
  names, and add distractor inputs, with the input order shuffled.

Ground truth is the Python function; a row is kept only when the reference
tree reproduces it exactly. Rows: 5 public / 3 challenge / 3 final, distinct,
public outputs not constant.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from .world import Invalid, WorldTask, make_task, run

N_PUBLIC, N_CHALLENGE, N_FINAL = 5, 3, 3
ROLES = ("a", "b", "c", "d")


def V(n):
    return ["var", n]


def K(k):
    return ["const", k]


def op(name, *xs):
    return [name, *xs]


@dataclass(frozen=True)
class Concept:
    name: str
    roles: tuple[str, ...]
    tree: list
    truth: Callable
    gen: Callable          # rng -> {role: value}


def _r(lo, hi):
    return lambda rng: rng.randint(lo, hi)


def _gen(**ranges):
    def g(rng):
        return {k: f(rng) for k, f in ranges.items()}
    return g


def _change_gen(rng):
    a, b = rng.randint(2, 9), rng.randint(2, 9)
    return {"a": a, "b": b, "c": a * b + rng.randint(0, 30)}


def _frame_gen(rng):
    c, d = rng.randint(1, 6), rng.randint(1, 6)
    return {"a": c + rng.randint(1, 8), "b": d + rng.randint(1, 8), "c": c, "d": d}


def _net_gen(rng):
    b, c = rng.randint(1, 20), rng.randint(1, 20)
    return {"a": b + c + rng.randint(0, 40), "b": b, "c": c}


def _loss_gen_d(rng):
    b = rng.randint(1, 9)
    return {"a": b + rng.randint(1, 12), "b": b, "c": rng.randint(2, 9), "d": rng.randint(1, 30)}


def _paint_gen(rng):
    a, b = rng.randint(2, 9), rng.randint(2, 9)
    return {"a": a, "b": b, "c": rng.randint(1, a * b - 1), "d": rng.randint(2, 5)}


def _loss_gen(rng):
    b = rng.randint(1, 9)
    return {"a": b + rng.randint(1, 12), "b": b, "c": rng.randint(2, 9)}


CONCEPTS: dict[str, Concept] = {c.name: c for c in (
    Concept("product", ("a", "b"), op("mul", V("a"), V("b")), lambda a, b: a * b,
            _gen(a=_r(2, 15), b=_r(2, 15))),
    Concept("volume", ("a", "b", "c"), op("mul", op("mul", V("a"), V("b")), V("c")),
            lambda a, b, c: a * b * c, _gen(a=_r(2, 9), b=_r(2, 9), c=_r(2, 9))),
    Concept("perimeter", ("a", "b"), op("mul", op("add", V("a"), V("b")), K(2)),
            lambda a, b: 2 * (a + b), _gen(a=_r(1, 30), b=_r(1, 30))),
    Concept("groups_plus", ("a", "b", "c"), op("add", op("mul", V("a"), V("b")), V("c")),
            lambda a, b, c: a * b + c, _gen(a=_r(2, 12), b=_r(2, 12), c=_r(1, 15))),
    Concept("change", ("a", "b", "c"), op("sub", V("c"), op("mul", V("a"), V("b"))),
            lambda a, b, c: c - a * b, _change_gen),
    Concept("loss_each", ("a", "b", "c"), op("mul", op("sub", V("a"), V("b")), V("c")),
            lambda a, b, c: (a - b) * c, _loss_gen),
    Concept("two_areas", ("a", "b", "c", "d"), op("add", op("mul", V("a"), V("b")), op("mul", V("c"), V("d"))),
            lambda a, b, c, d: a * b + c * d, _gen(a=_r(2, 9), b=_r(2, 9), c=_r(2, 9), d=_r(2, 9))),
    Concept("frame", ("a", "b", "c", "d"), op("sub", op("mul", V("a"), V("b")), op("mul", V("c"), V("d"))),
            lambda a, b, c, d: a * b - c * d, _frame_gen),
    Concept("share", ("a", "b", "c"), op("div", op("mul", V("a"), V("b")), V("c")),
            lambda a, b, c: (a * b) // c, _gen(a=_r(2, 12), b=_r(2, 12), c=_r(2, 6))),
    Concept("mean2", ("a", "b"), op("div", op("add", V("a"), V("b")), K(2)),
            lambda a, b: (a + b) // 2, _gen(a=_r(1, 40), b=_r(1, 40))),
    Concept("pool_share", ("a", "b", "c"), op("div", op("add", V("a"), V("b")), V("c")),
            lambda a, b, c: (a + b) // c, _gen(a=_r(1, 30), b=_r(1, 30), c=_r(2, 6))),
    Concept("leftover", ("a", "b"), op("mod", V("a"), V("b")),
            lambda a, b: a % b, _gen(a=_r(5, 60), b=_r(2, 9))),
    Concept("boxes_needed", ("a", "b"), op("div", op("add", V("a"), op("sub", V("b"), K(1))), V("b")),
            lambda a, b: (a + b - 1) // b, _gen(a=_r(1, 60), b=_r(2, 9))),
    Concept("bundle", ("a", "b", "c"), op("mul", op("add", V("a"), V("b")), V("c")),
            lambda a, b, c: (a + b) * c, _gen(a=_r(1, 9), b=_r(1, 9), c=_r(2, 9))),
    Concept("round_trip", ("a", "b"), op("mul", op("mul", V("a"), V("b")), K(2)),
            lambda a, b: a * b * 2, _gen(a=_r(1, 20), b=_r(1, 9))),
    Concept("sum_times", ("a", "b", "c", "d"), op("mul", op("add", op("add", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: (a + b + c) * d, _gen(a=_r(1, 9), b=_r(1, 9), c=_r(1, 9), d=_r(2, 6))),
    Concept("net", ("a", "b", "c"), op("sub", op("sub", V("a"), V("b")), V("c")),
            lambda a, b, c: a - b - c, _net_gen),
    Concept("triple_sum", ("a", "b", "c"), op("add", op("add", V("a"), V("b")), V("c")),
            lambda a, b, c: a + b + c, _gen(a=_r(1, 40), b=_r(1, 40), c=_r(1, 40))),
    # size 7: beyond the cold search at 10,000 once a story adds distractor quantities
    Concept("avg3", ("a", "b", "c"), op("div", op("add", op("add", V("a"), V("b")), V("c")), K(3)),
            lambda a, b, c: (a + b + c) // 3, _gen(a=_r(1, 40), b=_r(1, 40), c=_r(1, 40))),
    Concept("split_bill", ("a", "b", "c", "d"), op("div", op("add", op("mul", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: (a * b + c) // d, _gen(a=_r(2, 9), b=_r(2, 12), c=_r(1, 20), d=_r(2, 6))),
    Concept("save_days", ("a", "b", "c", "d"), op("add", op("mul", op("sub", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: (a - b) * c + d, _loss_gen_d),
    Concept("weeks_pay", ("a", "b", "c", "d"), op("mul", op("add", op("mul", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: (a * b + c) * d, _gen(a=_r(2, 9), b=_r(2, 9), c=_r(1, 15), d=_r(2, 6))),
    Concept("trips_total", ("a", "b", "c"), op("mul", op("mul", op("add", V("a"), V("b")), K(2)), V("c")),
            lambda a, b, c: (a + b) * 2 * c, _gen(a=_r(1, 15), b=_r(1, 15), c=_r(2, 7))),
    Concept("paint_rest", ("a", "b", "c", "d"), op("mul", op("sub", op("mul", V("a"), V("b")), V("c")), V("d")),
            lambda a, b, c, d: (a * b - c) * d, _paint_gen),
)}


@dataclass(frozen=True)
class WordFamily:
    family: str
    concept: str
    domain: str
    text: str                      # description with {a}.. role and {x} {y} distractor placeholders
    distractors: tuple[str, ...] = ()


def _f(family, concept, domain, text, distractors=()):
    return WordFamily(family, concept, domain, text, tuple(distractors))


# ---------------------------------------------------------------- training families (the only ones learned from)
TRAIN: tuple[WordFamily, ...] = (
    _f("wt_tile_floor", "product", "kitchen", "The kitchen floor is laid in {a} rows with {b} tiles in each row. How many tiles cover the floor?"),
    _f("wt_seed_rows", "product", "garden", "A gardener plants {a} rows of carrots with {b} seeds in every row. How many seeds are planted in total?"),
    _f("wt_desk_grid", "product", "school", "The classroom has {a} rows of desks and each row has {b} desks. How many desks are in the classroom?"),
    _f("wt_crate_jars", "volume", "kitchen", "A pantry holds {a} shelves, each shelf has {b} crates and each crate holds {c} jars. How many jars are in the pantry?"),
    _f("wt_planter_box", "volume", "garden", "A raised bed is {a} long, {b} wide and {c} deep. How much soil fills the bed (its volume)?"),
    _f("wt_book_carts", "volume", "school", "There are {a} carts with {b} boxes on each cart and {c} books in each box. How many books are there altogether?"),
    _f("wt_fence_bed", "perimeter", "garden", "A rectangular flower bed is {a} long and {b} wide. How much fence goes all the way around its edge?"),
    _f("wt_ribbon_tray", "perimeter", "kitchen", "A baking tray is {a} long and {b} wide. How much ribbon goes around the border of the tray?"),
    _f("wt_tape_board", "perimeter", "school", "A notice board is {a} wide and {b} tall. How much tape is needed to go around its whole edge?"),
    _f("wt_eggs_loose", "groups_plus", "kitchen", "There are {a} cartons with {b} eggs in each carton, plus {c} loose eggs. How many eggs are there in total?"),
    _f("wt_bulb_packs", "groups_plus", "garden", "A gardener buys {a} packs of {b} bulbs each and {c} extra single bulbs. How many bulbs altogether?"),
    _f("wt_pencil_boxes", "groups_plus", "school", "A teacher has {a} boxes holding {b} pencils each and {c} more pencils on the desk. How many pencils in total?"),
    _f("wt_flour_change", "change", "kitchen", "A cook pays with {c} coins for {a} bags of flour costing {b} coins each. How much change comes back?"),
    _f("wt_seed_budget", "change", "garden", "With {c} dollars a gardener buys {a} trays at {b} dollars each. How much money is left?"),
    _f("wt_lunch_money", "change", "school", "A student has {c} dollars and buys {a} snacks at {b} dollars each. How many dollars remain?"),
    _f("wt_melt_trays", "loss_each", "kitchen", "Each of {c} trays starts with {a} ice cubes and {b} cubes melt from every tray. How many cubes are left on all the trays?"),
    _f("wt_wilt_pots", "loss_each", "garden", "There are {c} pots with {a} flowers each, and {b} flowers wilt in each pot. How many flowers survive in all?"),
    _f("wt_absent_class", "loss_each", "school", "Each of {c} classes has {a} pupils and {b} pupils from each class are absent. How many pupils are present altogether?"),
    _f("wt_two_counters", "two_areas", "kitchen", "One counter is {a} by {b} tiles and a second counter is {c} by {d} tiles. How many tiles cover both counters?"),
    _f("wt_two_beds", "two_areas", "garden", "One bed has {a} rows of {b} plants and another bed has {c} rows of {d} plants. How many plants grow in both beds altogether?"),
    _f("wt_two_rooms", "two_areas", "school", "The library room is {a} by {b} carpet squares and the music room is {c} by {d} squares. How many squares for both rooms?"),
    _f("wt_mat_hole", "frame", "kitchen", "A mat is {a} by {b} squares with a hole of {c} by {d} squares cut out of it. How many squares of mat remain?"),
    _f("wt_lawn_pond", "frame", "garden", "A lawn is {a} by {b} with a pond {c} by {d} in the middle. How much lawn is left around the pond?"),
    _f("wt_wall_window", "frame", "school", "A wall is {a} by {b} with a window of {c} by {d}. How much wall area is left to paint?"),
    _f("wt_cookies_share", "share", "kitchen", "There are {a} plates with {b} cookies on each, shared equally among {c} children. How many cookies does each child get?"),
    _f("wt_seed_split", "share", "garden", "{a} packets of {b} seeds are split equally between {c} gardeners. How many seeds does each gardener get?"),
    _f("wt_sticker_share", "share", "school", "{a} sheets with {b} stickers each are divided equally among {c} pupils. How many stickers per pupil?"),
    _f("wt_avg_temps", "mean2", "kitchen", "The oven reads {a} degrees in the morning and {b} degrees at night. What is the average of the two readings?"),
    _f("wt_avg_heights", "mean2", "garden", "Two sunflowers are {a} and {b} tall. What is their average height?"),
    _f("wt_avg_scores", "mean2", "school", "A pupil scores {a} on the first test and {b} on the second test. What is the average score?"),
    _f("wt_soup_bowls", "pool_share", "kitchen", "{a} cups of soup and {b} more cups are poured together and shared equally among {c} bowls. How much per bowl?"),
    _f("wt_berries_pool", "pool_share", "garden", "Two pickers gather {a} and {b} berries, put them together and divide them equally into {c} baskets. How many per basket?"),
    _f("wt_crayons_pool", "pool_share", "school", "Two boxes of {a} and {b} crayons are combined and shared equally among {c} tables. How many crayons per table?"),
    _f("wt_eggs_left", "leftover", "kitchen", "{a} eggs are packed into cartons of {b}. How many eggs are left over that do not fill a carton?"),
    _f("wt_bulbs_left", "leftover", "garden", "{a} bulbs are planted in rows of {b}. How many bulbs are left over after the full rows?"),
    _f("wt_pupils_left", "leftover", "school", "{a} pupils form teams of {b}. How many pupils are left over without a full team?"),
    _f("wt_jars_needed", "boxes_needed", "kitchen", "{a} cookies are packed into jars that hold {b} each. How many jars are needed to hold all the cookies?"),
    _f("wt_pots_needed", "boxes_needed", "garden", "{a} seedlings go into trays that hold {b} each. How many trays are needed for all of them?"),
    _f("wt_buses_needed", "boxes_needed", "school", "{a} pupils ride in vans that seat {b} each. How many vans are needed to carry everyone?"),
    _f("wt_fruit_bags", "bundle", "kitchen", "Each bag holds {a} apples and {b} pears, and there are {c} bags. How many pieces of fruit in all the bags?"),
    _f("wt_flower_bunch", "bundle", "garden", "Each bunch has {a} roses and {b} tulips, and a gardener makes {c} bunches. How many flowers in total?"),
    _f("wt_kit_items", "bundle", "school", "Each kit has {a} pens and {b} rulers, and the class gets {c} kits. How many items altogether?"),
    _f("wt_walk_pantry", "round_trip", "kitchen", "The pantry is {a} steps away and a cook walks there and back {b} times. How many steps in total?"),
    _f("wt_walk_well", "round_trip", "garden", "The well is {a} meters away and a gardener goes there and back {b} times a day. How far does the gardener walk?"),
    _f("wt_walk_school", "round_trip", "school", "School is {a} blocks from home and a pupil makes the trip there and back {b} days. How many blocks are walked?"),
    _f("wt_shift_pay", "sum_times", "kitchen", "A cook works {a}, {b} and {c} hours on three days and earns {d} coins per hour. How many coins in total?"),
    _f("wt_water_beds", "sum_times", "garden", "Three beds need {a}, {b} and {c} cans of water each day, for {d} days. How many cans in total?"),
    _f("wt_lap_points", "sum_times", "school", "A team scores {a}, {b} and {c} goals in three games and each goal is worth {d} points. How many points altogether?"),
    _f("wt_flour_used", "net", "kitchen", "A sack has {a} cups of flour; {b} cups are used for bread and {c} cups for cake. How many cups are left?"),
    _f("wt_seeds_used", "net", "garden", "A gardener has {a} seeds, plants {b} on Monday and {c} on Tuesday. How many seeds remain?"),
    _f("wt_pages_read", "net", "school", "A book has {a} pages; a pupil reads {b} pages one day and {c} pages the next. How many pages are left to read?"),
    _f("wt_three_trays", "triple_sum", "kitchen", "Three trays hold {a}, {b} and {c} muffins. How many muffins altogether?"),
    _f("wt_three_rows", "triple_sum", "garden", "Three rows hold {a}, {b} and {c} tomato plants. How many plants in total?"),
    _f("wt_three_classes", "triple_sum", "school", "Three classes have {a}, {b} and {c} pupils. How many pupils are there altogether?"),
    _f("wt_avg_loaves", "avg3", "kitchen", "A baker makes {a}, {b} and {c} loaves on three days. What is the average number of loaves per day?"),
    _f("wt_avg_tomatoes", "avg3", "garden", "Three plants give {a}, {b} and {c} tomatoes. What is the average yield of the three plants?"),
    _f("wt_avg_marks", "avg3", "school", "A pupil scores {a}, {b} and {c} on three tests. What is the average of the three scores?"),
    _f("wt_pizza_split", "split_bill", "kitchen", "{a} pizzas cost {b} coins each plus a delivery fee of {c} coins, and the bill is split equally among {d} friends. How much does each friend pay?"),
    _f("wt_tool_split", "split_bill", "garden", "{a} shovels at {b} dollars each and a {c} dollar delivery fee are split equally among {d} neighbours. How much does each neighbour pay?"),
    _f("wt_trip_split", "split_bill", "school", "{a} museum tickets at {b} dollars each plus a {c} dollar bus fee are shared equally by {d} parents. How much does each parent pay?"),
    _f("wt_jar_savings", "save_days", "kitchen", "A cook earns {a} coins a day and spends {b} coins a day for {c} days, starting with {d} coins saved. How many coins are saved at the end?"),
    _f("wt_seed_savings", "save_days", "garden", "A gardener collects {a} seeds a day and uses {b} seeds a day for {c} days, after starting with {d} seeds. How many seeds are saved at the end?"),
    _f("wt_pocket_savings", "save_days", "school", "A pupil gets {a} dollars a day and spends {b} dollars a day for {c} days, starting with {d} dollars saved. How much is saved at the end?"),
    _f("wt_cook_weeks", "weeks_pay", "kitchen", "A cook works {a} shifts a week at {b} coins per shift and gets a {c} coin bonus each week, for {d} weeks. How many coins are earned in total?"),
    _f("wt_mow_weeks", "weeks_pay", "garden", "A gardener mows {a} lawns a week at {b} dollars per lawn plus a {c} dollar tip each week, for {d} weeks. How much is earned in total?"),
    _f("wt_tutor_weeks", "weeks_pay", "school", "A tutor teaches {a} lessons a week at {b} dollars per lesson plus a {c} dollar bonus each week, for {d} weeks. How much is earned in total?"),
    _f("wt_shop_trips", "trips_total", "kitchen", "The market is {a} blocks to the bakery and {b} more blocks to the store; a cook walks there and back {c} times. How many blocks in total?"),
    _f("wt_hose_trips", "trips_total", "garden", "The tap is {a} steps to the gate and {b} more steps to the bed; a gardener goes there and back {c} times. How many steps in total?"),
    _f("wt_bus_trips", "trips_total", "school", "Home is {a} miles to the station and {b} more miles to school; a pupil makes the trip there and back {c} days. How many miles in total?"),
    _f("wt_paint_cupboards", "paint_rest", "kitchen", "Each cupboard door is {a} by {b} squares with {c} squares of glass, and there are {d} doors. How many squares of wood are painted on all the doors?"),
    _f("wt_paint_sheds", "paint_rest", "garden", "Each shed wall is {a} by {b} panels with {c} panels taken by a door, and there are {d} walls. How many panels are painted on all the walls?"),
    _f("wt_paint_boards", "paint_rest", "school", "Each board is {a} by {b} squares with {c} squares covered by a poster, and there are {d} boards. How many squares are painted on all the boards?"),
)

# ---------------------------------------------------------------- sealed held-out families
# Written before any field arm was measured on them (docs/MEANING.md). Domains, nouns and input
# names never used in training or dev (stadium, hospital, orchestra, airport, zoo, theater);
# every story adds one or two distractor quantities; input order is shuffled per task.
SEALED: tuple[WordFamily, ...] = (
    _f("ms_stand_seats", "product", "stadium", "A stand has {a} rows with {b} seats in each row, and tickets cost {x} dollars. How many seats are in the stand?", ("x",)),
    _f("ms_pill_boxes", "volume", "hospital", "A ward cabinet has {a} drawers, each drawer holds {b} boxes and each box holds {c} pills; the ward has {x} beds. How many pills are in the cabinet?", ("x",)),
    _f("ms_stage_tape", "perimeter", "theater", "A rectangular stage is {a} long and {b} wide, and the show runs {x} nights. How much tape goes all the way around the edge of the stage?", ("x",)),
    _f("ms_reed_packs", "groups_plus", "orchestra", "A clarinet player buys {a} packs of {b} reeds each and {c} single reeds, before a concert of {x} minutes. How many reeds in total?", ("x",)),
    _f("ms_cafe_change", "change", "airport", "A traveller pays {c} dollars for {a} coffees at {b} dollars each at gate {x}. How much change comes back?", ("x",)),
    _f("ms_feed_left", "loss_each", "zoo", "Each of {c} pens gets {a} carrots and the goats eat {b} carrots from every pen; the zoo has {x} keepers. How many carrots are left in all the pens?", ("x",)),
    _f("ms_two_terminals", "two_areas", "airport", "Terminal one has {a} rows of {b} chairs and terminal two has {c} rows of {d} chairs; {x} flights leave today. How many chairs are in both terminals altogether?", ("x",)),
    _f("ms_two_wards", "two_areas", "hospital", "The north ward is {a} by {b} floor tiles and the south ward is {c} by {d} tiles, and {x} nurses work there with {y} doctors. How many tiles cover both wards?", ("x", "y")),
    _f("ms_pitch_goal", "frame", "stadium", "A pitch is {a} by {b} squares of grass with a stage of {c} by {d} squares on it for a concert by {x} singers. How much grass is left uncovered around the stage?", ("x",)),
    _f("ms_curtain_hole", "frame", "theater", "A curtain is {a} by {b} panels with a window of {c} by {d} panels cut out of it, in a hall of {x} seats. How many panels of curtain remain?", ("x",)),
    _f("ms_fish_share", "share", "zoo", "{a} buckets with {b} fish each are shared equally among {c} seals, fed {x} times a week. How many fish does each seal get?", ("x",)),
    _f("ms_avg_pulse", "mean2", "hospital", "A patient's pulse is {a} before lunch and {b} after lunch, in room {x}. What is the average of the two readings?", ("x",)),
    _f("ms_bags_pool", "pool_share", "airport", "Two flights bring {a} and {b} bags, which are put together and divided equally onto {c} belts staffed by {x} workers. How many bags per belt?", ("x",)),
    _f("ms_strings_left", "leftover", "orchestra", "{a} violin strings are packed into sets of {b}, for {x} violinists. How many strings are left over without a full set?", ("x",)),
    _f("ms_shuttles_needed", "boxes_needed", "airport", "{a} passengers ride shuttles that seat {b} each, to a hotel {x} miles away. How many shuttles are needed to carry everyone?", ("x",)),
    _f("ms_ambulances_needed", "boxes_needed", "hospital", "{a} patients are moved in ambulances that hold {b} each, with {x} drivers on call and {y} beds free. How many ambulances are needed for all of them?", ("x", "y")),
    _f("ms_snack_trays", "bundle", "theater", "Each tray has {a} sandwiches and {b} cakes, and the theater sets out {c} trays for {x} guests. How many snacks on all the trays?", ("x",)),
    _f("ms_keeper_walk", "round_trip", "zoo", "The lion house is {a} meters from the gate and a keeper walks there and back {b} times a day, carrying {x} kilograms. How far does the keeper walk?", ("x",)),
    _f("ms_rehearsal_pay", "sum_times", "orchestra", "A drummer rehearses {a}, {b} and {c} hours on three days and is paid {d} dollars per hour; the hall has {x} seats. How many dollars in total?", ("x",)),
    _f("ms_gate_shifts", "sum_times", "airport", "A guard works {a}, {b} and {c} hours on three days and earns {d} dollars per hour at a terminal with {x} gates and {y} shops. How many dollars are earned in total?", ("x", "y")),
    _f("ms_budget_used", "net", "stadium", "A club has {a} dollars; {b} dollars go on kits and {c} dollars on travel for {x} players. How many dollars are left?", ("x",)),
    _f("ms_three_enclosures", "triple_sum", "zoo", "Three enclosures hold {a}, {b} and {c} penguins, and the zoo opened {x} years ago. How many penguins altogether?", ("x",)),
    _f("ms_avg_crowd", "avg3", "stadium", "Three matches draw crowds of {a}, {b} and {c} people, with {x} stewards on duty. What is the average crowd of the three matches?", ("x",)),
    _f("ms_avg_patients", "avg3", "hospital", "A clinic sees {a}, {b} and {c} patients on three days, with {x} doctors and {y} nurses. What is the average number of patients per day?", ("x", "y")),
    _f("ms_taxi_split", "split_bill", "airport", "{a} taxis cost {b} dollars each plus a {c} dollar toll, and the bill is split equally among {d} colleagues flying to city {x}. How much does each colleague pay?", ("x",)),
    _f("ms_cake_split2", "split_bill", "orchestra", "{a} cakes at {b} dollars each and a {c} dollar delivery fee are shared equally by {d} musicians after a concert of {x} songs. How much does each musician pay?", ("x",)),
    _f("ms_hay_store", "save_days", "zoo", "A keeper brings in {a} bales a day and the elephants use {b} bales a day for {c} days, starting with {d} bales in the barn and {x} elephants. How many bales are in the barn at the end?", ("x",)),
    _f("ms_ticket_savings", "save_days", "theater", "An usher earns {a} dollars a day and spends {b} dollars a day for {c} days, starting with {d} dollars saved, in a theater of {x} rows. How much is saved at the end?", ("x",)),
    _f("ms_nurse_weeks", "weeks_pay", "hospital", "A nurse works {a} night shifts a week at {b} dollars per shift plus a {c} dollar bonus each week, for {d} weeks, on a floor of {x} rooms. How much is earned in total?", ("x",)),
    _f("ms_usher_weeks", "weeks_pay", "stadium", "A vendor sells {a} crates a week at {b} dollars per crate plus a {c} dollar tip each week, for {d} weeks, at a ground with {x} gates and {y} flags. How much is earned in total?", ("x", "y")),
    _f("ms_cart_trips", "trips_total", "airport", "The gate is {a} meters to the lounge and {b} more meters to the plane; a cart goes there and back {c} times carrying {x} bags. How many meters in total?", ("x",)),
    _f("ms_porter_trips", "trips_total", "hospital", "The lift is {a} steps to the lab and {b} more steps to the ward; a porter makes the trip there and back {c} times with {x} trolleys. How many steps in total?", ("x",)),
    _f("ms_paint_scenery", "paint_rest", "theater", "Each scenery flat is {a} by {b} squares with {c} squares covered by a door, and there are {d} flats for a play with {x} actors. How many squares are painted on all the flats?", ("x",)),
    _f("ms_paint_cages", "paint_rest", "zoo", "Each cage wall is {a} by {b} panels with {c} panels taken by a gate, and there are {d} walls around {x} monkeys. How many panels are painted on all the walls?", ("x",)),
)
SEALED_NAMES = ("sa", "sb", "sc", "sd", "se", "sf")

TRAIN_NAMES = ("tp", "tq", "tr", "tu")
DISTRACT = {"x": (1, 25), "y": (1, 25)}


def draw_rows(fam: WordFamily, rng: random.Random, names: dict[str, str]) -> list[tuple[dict, int]]:
    """Rows over the family's input names (roles + distractors), exact by the reference tree."""
    c = CONCEPTS[fam.concept]
    n = N_PUBLIC + N_CHALLENGE + N_FINAL
    tree = rename_tree(c.tree, names)
    for _ in range(50):
        rows, seen = [], set()
        for _ in range(5000):
            if len(rows) == n:
                break
            roles = c.gen(rng)
            r = {names[k]: v for k, v in roles.items()}
            for d in fam.distractors:
                lo, hi = DISTRACT.get(d, (1, 25))
                r[names[d]] = rng.randint(lo, hi)
            key = tuple(sorted(r.items()))
            if key in seen:
                continue
            want = c.truth(*(roles[k] for k in c.roles))
            try:
                got = run(tree, r)
            except Invalid:
                continue
            if got != want:
                continue
            seen.add(key)
            rows.append((r, want))
        if len(rows) == n and len({a for _, a in rows[:N_PUBLIC]}) > 1:
            return rows
    raise RuntimeError(f"could not draw rows for {fam.family}")


def rename_tree(tree: list, names: dict[str, str]) -> list:
    if tree[0] == "var":
        return ["var", names[tree[1]]]
    if tree[0] == "const":
        return tree
    return [tree[0]] + [rename_tree(t, names) for t in tree[1:]]


def entry(fam: WordFamily, task_id: str, seed: int | str, name_pool: Sequence[str], shuffle: bool) -> dict:
    """A JSON-safe task entry: input names drawn from ``name_pool``, order shuffled when asked."""
    rng = random.Random(f"{seed}:{fam.family}")
    c = CONCEPTS[fam.concept]
    slots = list(c.roles) + list(fam.distractors)
    pool = list(name_pool)
    if shuffle:
        rng.shuffle(pool)
    names = dict(zip(slots, pool))
    order = [names[s] for s in slots]
    if shuffle:
        rng.shuffle(order)
    rows = draw_rows(fam, rng, names)
    return {"task_id": task_id, "family": fam.family, "concept": fam.concept, "domain": fam.domain,
            "words": fam.text, "inputs": order, "tree": rename_tree(c.tree, names),
            "rows": [[r, a] for r, a in rows]}


def to_task(e: dict) -> WorldTask:
    rows = [(dict(r), a) for r, a in e["rows"]]
    a, b = N_PUBLIC, N_PUBLIC + N_CHALLENGE
    return make_task(e["task_id"], e["family"], "int", {n: "int" for n in e["inputs"]}, "int",
                     rows[:a], rows[a:b], rows[b:], 9)


def train_entries() -> list[dict]:
    return [entry(f, f"mt-{i:02d}", "meaning-train", TRAIN_NAMES, shuffle=False) for i, f in enumerate(TRAIN)]


from typing import Sequence  # noqa: E402  (used in annotations above)
