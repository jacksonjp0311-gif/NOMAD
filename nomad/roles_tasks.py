"""ROLES sealed word-problem catalogue (docs/ROLES.md); written before any field arm is measured on it.

Stories in six domains no other suite uses (observatory, vineyard, circus, post office, ski resort,
mine), one family per MEANING concept, every story with two or three distractor quantities (numbers
the answer does not use, often next to the same relational words), inputs ``ha..hg`` shuffled. The
suite writes each story out with the numbers of the first public row (``meaning_tasks.story_entry``).
"""
from __future__ import annotations

from .meaning_tasks import _f

SEALED = (
    _f("rs_star_plates", "product", "observatory", "An archive {x} years old keeps {a} drawers of glass plates with {b} plates in each drawer, read by {y} astronomers. How many plates are in the archive?", ("x", "y")),
    _f("rs_barrel_cellar", "volume", "vineyard", "The cellar has {a} aisles, each aisle has {b} racks and each rack holds {c} barrels; the estate has {x} workers, {y} dogs and {z} tractors. How many barrels are in the cellar?", ("x", "y", "z")),
    _f("rs_ring_rope", "perimeter", "circus", "A rectangular ring is {a} long and {b} wide; {x} clowns and {y} horses perform in it. How much rope goes all the way around the ring?", ("x", "y")),
    _f("rs_parcel_sacks", "groups_plus", "post office", "On a day with {x} clerks, a sorter fills {a} sacks with {b} parcels each, plus {c} loose parcels, and {y} trucks wait outside. How many parcels in total?", ("x", "y")),
    _f("rs_lift_change", "change", "ski resort", "A skier with {x} friends pays with {c} dollars for {a} lift passes at {b} dollars each, on a slope of {y} meters and {z} turns. How much change comes back?", ("x", "y", "z")),
    _f("rs_lamp_broken", "loss_each", "mine", "Each of {c} tunnels has {a} lamps and {b} lamps in every tunnel are broken, in a mine {x} meters deep with {y} miners. How many lamps still work in all the tunnels?", ("x", "y")),
    _f("rs_two_domes", "two_areas", "observatory", "One dome floor is {a} by {b} tiles and the other dome floor is {c} by {d} tiles; there are {x} telescopes, {y} stairs and {z} guides. How many tiles cover both floors?", ("x", "y", "z")),
    _f("rs_tent_canvas", "frame", "circus", "A canvas is {a} by {b} squares with a door of {c} by {d} squares cut out of it, for a show with {x} acrobats and {y} seats. How many squares of canvas remain?", ("x", "y")),
    _f("rs_grape_share", "share", "vineyard", "{a} crates with {b} bunches of grapes each are shared equally among {c} buyers at a market {x} miles away with {y} stalls. How many bunches does each buyer get?", ("x", "y")),
    _f("rs_avg_snow", "mean2", "ski resort", "With {x} lifts open and {y} instructors on duty, the snow is {a} centimeters deep at the top and {b} centimeters at the bottom. What is the average of the two depths?", ("x", "y")),
    _f("rs_ore_pool", "pool_share", "mine", "Two carts of {a} and {b} kilograms of ore are tipped together and divided equally into {c} bins, by {x} miners after {y} hours, near tunnel {z}. How much ore per bin?", ("x", "y", "z")),
    _f("rs_stamp_left", "leftover", "post office", "{a} stamps are sorted into books of {b} by {x} clerks at counter {y}. How many stamps are left over without a full book?", ("x", "y")),
    _f("rs_sled_needed", "boxes_needed", "ski resort", "{a} skiers ride up in gondolas that seat {b} each, to a peak {x} meters high, while {y} skiers rest and {z} gondolas are idle. How many gondolas are needed to carry everyone?", ("x", "y", "z")),
    _f("rs_clown_kits", "bundle", "circus", "Each kit has {a} balls and {b} hoops, and the circus packs {c} kits for a tour of {x} towns with {y} trucks. How many props in all the kits?", ("x", "y")),
    _f("rs_walk_telescope", "round_trip", "observatory", "The telescope is {a} steps away and an astronomer goes there and back {b} times a night, carrying {x} charts, under {y} stars and {z} clouds. How many steps in total?", ("x", "y", "z")),
    _f("rs_picker_pay", "sum_times", "vineyard", "A picker works {a}, {b} and {c} hours on three days and earns {d} dollars per hour, on a vineyard of {x} rows with {y} sheds. How many dollars in total?", ("x", "y")),
    _f("rs_coal_used", "net", "mine", "A pile has {a} tons of coal; {b} tons are shipped in the morning and {c} tons in the afternoon, by {x} trains with {y} wagons and {z} drivers. How many tons are left?", ("x", "y", "z")),
    _f("rs_three_vans", "triple_sum", "post office", "Three vans carry {a}, {b} and {c} letters, and the postmaster has {x} stamps and {y} keys. How many letters altogether?", ("x", "y")),
    _f("rs_avg_jugglers", "avg3", "circus", "The circus sells {a}, {b} and {c} tickets on three nights, with {x} jugglers, {y} lions and {z} tents. What is the average number of tickets per night?", ("x", "y", "z")),
    _f("rs_lens_split", "split_bill", "observatory", "{a} lenses cost {b} dollars each plus a {c} dollar shipping fee, and the bill is split equally among {d} astronomers; the dome is {x} meters wide with {y} windows. How much does each astronomer pay?", ("x", "y")),
    _f("rs_wine_savings", "save_days", "vineyard", "A press makes {a} bottles a day and sells {b} bottles a day for {c} days, starting with {d} bottles in store, in a cellar of {x} rooms with {y} lamps and {z} doors. How many bottles are in store at the end?", ("x", "y", "z")),
    _f("rs_courier_weeks", "weeks_pay", "post office", "A courier delivers {a} routes a week at {b} dollars per route plus a {c} dollar bonus each week, for {d} weeks, with {x} bikes and {y} bags. How much is earned in total?", ("x", "y")),
    _f("rs_shaft_trips", "trips_total", "mine", "The lift is {a} meters to the first shaft and {b} more meters to the seam; a miner goes there and back {c} times carrying {x} tools for {y} hours with {z} lamps. How many meters in total?", ("x", "y", "z")),
    _f("rs_paint_lodges", "paint_rest", "ski resort", "Each lodge wall is {a} by {b} boards with {c} boards taken by a window, and there are {d} walls on a lodge {x} years old with {y} beds. How many boards are painted on all the walls?", ("x", "y")),
)
SEALED_NAMES = ("ha", "hb", "hc", "hd", "he", "hf", "hg")
