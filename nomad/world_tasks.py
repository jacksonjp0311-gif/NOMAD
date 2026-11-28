"""Frozen WORLD task families, curriculum levels, and held-out probes.

Inputs are fixed literals. Expected outputs come from a small reference
function per family, written here once and never shown to search. Public,
challenge, and final rows are disjoint. Held-out families are never used for
training, never enter the curriculum, and are only probed.
"""
from __future__ import annotations

from typing import Any, Callable

from .world import WorldTask, make_task

II = {"x": "int", "y": "int"}
SS = {"s": "str"}
LL = {"xs": "list"}

_INT_PUB = [(2, 5), (7, 3), (4, 4), (9, 2), (10, 1)]
_INT_CHA = [(11, 6), (3, 10), (8, 8)]
_INT_FIN = [(13, 4), (5, 12), (6, 1)]
_STR_PUB = ["abc", "hello", "Xy", "nomad"]
_STR_CHA = ["river", "Grok", "desert"]
_STR_FIN = ["camel", "wind", "Atlas"]
_LST_PUB = [[3, 1, 4], [9, 5, 2, 6], [1, 1], [2, 7, 8]]
_LST_CHA = [[10, 4, 7], [6, 6, 1, 3], [2, 9]]
_LST_FIN = [[8, 2, 5], [4, 4, 4, 9], [12, 3]]


def _int_task(tid, fam, fn, level, opset="int"):
    rows = lambda pts: [({"x": x, "y": y}, fn(x, y)) for x, y in pts]
    return make_task(tid, fam, opset, II, "int", rows(_INT_PUB), rows(_INT_CHA), rows(_INT_FIN), level)


def _str_task(tid, fam, fn, level, out="str"):
    rows = lambda pts: [({"s": s}, fn(s)) for s in pts]
    return make_task(tid, fam, "str", SS, out, rows(_STR_PUB), rows(_STR_CHA), rows(_STR_FIN), level)


def _lst_task(tid, fam, fn, level, out="int"):
    rows = lambda pts: [({"xs": xs}, fn(xs)) for xs in pts]
    return make_task(tid, fam, "list", LL, out, rows(_LST_PUB), rows(_LST_CHA), rows(_LST_FIN), level)


# ---------------------------------------------------------------- training families
# domain -> level -> [tasks]
TRAIN: dict[str, dict[int, list[WorldTask]]] = {
    "mathematics": {
        1: [
            _int_task("w-max", "max_pair", lambda x, y: max(x, y), 1),
            _int_task("w-min", "min_pair", lambda x, y: min(x, y), 1),
            _int_task("w-mod", "mod_pair", lambda x, y: x % y, 1),
            _int_task("w-div", "div_pair", lambda x, y: x // y, 1),
        ],
        2: [
            _int_task("w-relu", "relu_diff", lambda x, y: max(x - y, 0), 2),
            _int_task("w-pick", "pick_gt", lambda x, y: x if x - y > 0 else 0, 2),
            _int_task("w-sqp", "square_plus_y", lambda x, y: x * x + y, 2, opset="genesis"),
            _int_task("w-ysq", "ysquare_minus_x", lambda x, y: y * y - x, 2, opset="genesis"),
        ],
    },
    "language": {
        1: [
            _str_task("w-shout-rev", "rev_upper", lambda s: s[::-1].upper(), 1),
            _str_task("w-ends", "first_last", lambda s: s[:1] + s[-1:], 1),
        ],
        2: [
            _str_task("w-echo", "double_lower", lambda s: s.lower() + s.lower(), 2),
            _str_task("w-len2", "len_plus_len", lambda s: len(s) + len(s), 2, out="int"),
        ],
    },
    "coding": {
        1: [
            _lst_task("w-range", "range", lambda xs: max(xs) - min(xs), 1),
            _lst_task("w-sumtail", "sum_tail", lambda xs: sum(xs[1:]), 1),
        ],
        2: [
            _lst_task("w-second", "second_smallest", lambda xs: sorted(xs)[1], 2),
            _lst_task("w-sorted-rev", "sort_desc", lambda xs: tuple(sorted(xs)[::-1]), 2, out="list"),
        ],
    },
}

# ---------------------------------------------------------------- held-out probes
# Never trained. Honest note on budgets: the first draft used 5000 / 20000;
# after one measurement (both arms failed absdiff at 5000; the library field
# needed ~108k evaluations on quartic_sum) they were raised to the values
# below. Cold cannot reach quartic_sum at any budget (size 15 > max_size 7;
# cold exhausts the whole size-7 space). For absdiff the robust number is
# the evaluation ratio at an unlimited budget, reported by the probe.
HELDOUT: dict[str, dict[str, Any]] = {
    "absdiff": {   # new int family (phase 3): needs max and sub together
        "task": _int_task("h-absdiff", "absdiff", lambda x, y: abs(x - y), 9),
        "max_eval": 10000, "max_size": 7, "needs": "wider world",
    },
    "quartic_sum": {   # deeper family (phase 4): x^4 + y^4, size 15 without a library
        "task": _int_task("h-quartic", "quartic_sum", lambda x, y: x ** 4 + y ** 4, 9, opset="genesis"),
        "max_eval": 150000, "max_size": 7, "needs": "learned building blocks",
    },
    "last_first_upper": {   # language (phase 5)
        "task": _str_task("h-lfu", "last_first_upper", lambda s: (s[-1:] + s[:1]).upper(), 9),
        "max_eval": 5000, "max_size": 7, "needs": "string world",
    },
    "sum_minus_max": {   # coding (phase 5)
        "task": _lst_task("h-smm", "sum_minus_max", lambda xs: sum(xs) - max(xs), 9),
        "max_eval": 5000, "max_size": 7, "needs": "list world",
    },
    "ends_case": {   # nested ends: upper(last) + lower(first); cold fails within budget
        "task": _str_task("h-ecu", "ends_case", lambda s: s[-1:].upper() + s[:1].lower(), 9),
        "max_eval": 200, "max_size": 7, "needs": "nested string composition",
    },
}


def all_training() -> list[WorldTask]:
    return [t for levels in TRAIN.values() for ts in levels.values() for t in ts]


# ---------------------------------------------------------------- live bridge curriculum (docs/BRIDGE.md)
# NOMAD_LIVE_BRIDGE=on (default off; the body workflow passes the repo variable NOMAD_LIVE_BRIDGE) adds
# the 16 bridge training families (nomad.bridge.train_tasks: string x int tasks, opset "bridge") to the
# live curriculum as one more domain, so the running body practises number-text tasks. Off: the
# curriculum is exactly TRAIN. all_training() (evolve benchmark, feed, judges) never changes.
BRIDGE_DOMAIN = "bridge"
_BRIDGE_TASKS: list[WorldTask] = []


def live_bridge_enabled() -> bool:
    import os
    if os.environ.get("NOMAD_LIVE_BRIDGE", "off").strip().lower() not in ("on", "1", "true", "yes"):
        return False
    from .world import bridge_enabled
    return bridge_enabled()   # the bridge opset itself must be on


def bridge_training() -> list[WorldTask]:
    if not _BRIDGE_TASKS:
        from .bridge import train_tasks
        _BRIDGE_TASKS.extend(train_tasks())
    return _BRIDGE_TASKS


# ---------------------------------------------------------------- live word curriculum (docs/LIVE_WORDS.md)
# NOMAD_LIVE_WORDS=on (default off; the body workflow passes the repo variable NOMAD_LIVE_WORDS) adds
# the 72 MEANING training word problems (nomad.meaning_tasks.TRAIN, told as stories with numbers) as one
# more domain at level 1, so they compete by attempts instead of jumping the queue. The treatment arm
# passes the story as ``words`` (MEANING's stage reads it once a lexicon exists) and the packet carries
# it, so the sleep learner grows the lexicon from live receipts. The cold control never reads words.
# Off: the curriculum is exactly what it was. all_training() (evolve benchmark, feed, judges) never changes.
WORDS_DOMAIN = "words"
_WORDS: dict[str, tuple[WorldTask, str]] = {}


def live_words_enabled() -> bool:
    import os
    if os.environ.get("NOMAD_LIVE_WORDS", "off").strip().lower() not in ("on", "1", "true", "yes"):
        return False
    from .meaning import enabled
    return enabled()   # words are only read and learned while MEANING is on


def _words_table() -> dict[str, tuple[WorldTask, str]]:
    if not _WORDS:
        import dataclasses
        from .meaning_tasks import to_task, train_story_entries
        for e in train_story_entries():
            _WORDS[e["family"]] = (dataclasses.replace(to_task(e), level=1), e["story"])
    return _WORDS


def words_training() -> list[WorldTask]:
    return [t for t, _s in _words_table().values()]


def words_of(family: str) -> str | None:
    """The story of a live word family (resolved whatever the switch says now), else None."""
    if not family.startswith("wt_"):
        return None
    rec = _words_table().get(family)
    return rec[1] if rec else None


def curriculum_train() -> dict[str, dict[int, list[WorldTask]]]:
    """The live curriculum's domain -> level -> tasks: TRAIN itself when NOMAD_LIVE_BRIDGE and NOMAD_LIVE_WORDS are off."""
    bridge, words = live_bridge_enabled(), live_words_enabled()
    if not bridge and not words:
        return TRAIN
    out = dict(TRAIN)
    if bridge:
        ts = bridge_training()
        out[BRIDGE_DOMAIN] = {min(t.level for t in ts): list(ts)}
    if words:
        out[WORDS_DOMAIN] = {1: words_window()}
    return out


WORDS_WINDOW = 18          # word families offered at once: 6 concepts x their 3 domains
WORDS_ROTATE = 40          # field versions per window (the learner advances the version)


def words_window(version: int | None = None) -> list[WorldTask]:
    """The word families the live curriculum offers now: a contiguous window of ``WORDS_WINDOW``
    (catalogue order groups a concept's three domains), rotating every ``WORDS_ROTATE`` field
    versions, so word practice stays near a third of the cycles instead of swamping the 32 other
    families. Deterministic given the field version."""
    if version is None:
        from .field_queue import field_version
        version = field_version()
    ts = words_training()
    k = max(1, len(ts) // WORDS_WINDOW)
    i = (int(version) // WORDS_ROTATE) % k
    return ts[i * WORDS_WINDOW:(i + 1) * WORDS_WINDOW]


def by_family(family: str) -> WorldTask | None:
    for t in all_training():
        if t.family == family:
            return t
    # bridge training families (only ever recorded when NOMAD_LIVE_BRIDGE was on; resolved whatever
    # the switch says now, so packets queued under the switch are still re-attested by the learner)
    from .bridge import TRAIN_FAMILIES
    if family in TRAIN_FAMILIES:
        for t in bridge_training():
            if t.family == family:
                return t
    if family.startswith("wt_") and family in _words_table():   # live word families (LIVE_WORDS)
        return _words_table()[family][0]
    return None


def domain_of(family: str) -> str | None:
    for dom, levels in TRAIN.items():
        for ts in levels.values():
            if any(t.family == family for t in ts):
                return dom
    from .bridge import TRAIN_FAMILIES
    if family in TRAIN_FAMILIES:
        return BRIDGE_DOMAIN
    if family.startswith("wt_") and family in _words_table():
        return WORDS_DOMAIN
    # Science families (nomad/science.py) are not training families; they are
    # tagged so the sensing step can key on them. See docs/SCIENCE.md.
    from .science import DOMAIN, is_science
    return DOMAIN if is_science(family) else None
