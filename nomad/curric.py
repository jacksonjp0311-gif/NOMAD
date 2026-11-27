"""CURRIC (docs/CURRIC.md): a multi-family concept curriculum, and concepts promoted only after the field
certified them in several families.

Switch ``NOMAD_CURRIC`` (default on since its sealed PASS, docs/CURRIC.md; ``off`` restores the old
behavior exactly). Two parts, both inert when the switch is off:

1. **Curriculum generator** (``tasks``). Each *concept* is a small reference function of two integers
   (``CONCEPTS``). Each *context* (``CONTEXTS``) is a different task family that presents its two
   arguments differently: a plain pair, a pick of two out of three inputs (one distractor), and a pair given
   in swapped order under other input names. Every concept is asked in every context, as a separate
   family, with rows drawn from a seeded generator (``random.Random(f"curric:{seed}:...")``). The
   reference functions are written once here and never shown to search; search sees only rows, like every
   other WORLD family. The curriculum is a training set: no held-out family, judge suite or sealed suite
   is generated from it.

2. **Cross-family concepts** (``study`` / ``record`` / ``index``). ``study`` searches every curriculum
   family with the field (read-only) and, for each WITNESS-certified program, ``record`` logs the program
   and each composite subtree of it (sizes ``MIN_SIZE`` .. ``MAX_SIZE``) whose variables are all ints and
   number at most ``ARITY``, renamed to parameters, with the family it was certified in
   (``prior.curric_log``, the field's *concept memory*). Nothing else in the field changes: the library,
   programs, operator counts and variation state are untouched (dev: letting the curriculum into the
   main memory cost a task the switch-off field solved). ``index`` groups the logged trees by *behavior*
   (fingerprint on fixed synthetic probe rows, never a task's rows; two-parameter trees are one concept
   up to argument order) and promotes a behavior class to a concept only when it was certified in at
   least ``FAMILIES`` distinct families. Any tree shape counts (an ``ite`` form and a ``min`` / ``max``
   form of ``|a - b|`` are one concept), and nothing is closed by a rule: the only source of a concept is
   repeated certification.

The concept index is used by MEMIDX's existing search stage (``world.memidx_stage``): funded only by
MERGE's unspent skips, every fit WITNESS-gated, the gate's rejection record restored on a miss. With
``NOMAD_MEMIDX`` off (its default) the index holds the cross-family concepts and nothing else.

Controls (judge only): ``NOMAD_CURRIC_CONTROL=rewired:<seed>`` permutes the family labels over the logged
entries before counting, so recurrence is counted against the wrong families. ``NOMAD_CURRIC_CONTROL=gate1``
(ablation) promotes every logged behavior seen in a single family, i.e. no multi-family requirement. The content control
(shuffled memory) rewires every logged tree's operators like every other memory slot
(``scripts/novel_judge.shuffled``).
"""
from __future__ import annotations

import json
import os
import random

ARITY = 2          # most parameters of a concept
MIN_SIZE = 5       # a concept is a composite: at least two operators
MAX_SIZE = 11      # largest logged tree (whole programs up to the training search's reach)
FAMILIES = 3       # distinct certified families a behavior must recur in (dev-chosen)
WEIGHT = 1.0       # retrieval weight per supporting family
LOG_CAP = 4096     # most logged entries kept (oldest dropped)

# Concepts: reference functions of two ints (training material only).
CONCEPTS: dict[str, object] = {
    "absdiff": lambda a, b: abs(a - b),
    "posdiff": lambda a, b: max(a - b, 0),
    "sqdiff": lambda a, b: (a - b) * (a - b),
    "mid": lambda a, b: (a + b) // 2,
    "dbldiff": lambda a, b: 2 * abs(a - b),
}

# Contexts: (input signature, which inputs are the concept's (a, b)).
CONTEXTS: dict[str, tuple[dict[str, str], tuple[str, str]]] = {
    "pair": ({"x": "int", "y": "int"}, ("x", "y")),
    "pick": ({"p": "int", "q": "int", "r": "int"}, ("p", "r")),
    "swap": ({"m": "int", "n": "int"}, ("n", "m")),
}

SEED = 1           # the committed curriculum's row seed
ROWS = (6, 4, 4)   # public, challenge, final rows per family
LO, HI = 0, 20     # input range
LEVEL = 3


def enabled() -> bool:
    return os.environ.get("NOMAD_CURRIC", "on").strip().lower() not in ("off", "0", "false", "no")


def control() -> int | None:
    v = os.environ.get("NOMAD_CURRIC_CONTROL", "").strip().lower()
    if v.startswith("rewired:"):
        return int(v.split(":", 1)[1])
    return None


def families_needed() -> int:
    """FAMILIES, or 1 under the gate1 ablation."""
    return 1 if os.environ.get("NOMAD_CURRIC_CONTROL", "").strip().lower() == "gate1" else FAMILIES


def family(concept: str, context: str) -> str:
    return f"cu_{concept}_{context}"


def tasks(seed: int = SEED) -> list:
    """The curriculum: every concept in every context, one WORLD family each (deterministic)."""
    from .world import make_task
    out = []
    n = sum(ROWS)
    for c in sorted(CONCEPTS):
        g = CONCEPTS[c]
        for x in sorted(CONTEXTS):
            ins, (a, b) = CONTEXTS[x]
            rng = random.Random(f"curric:{seed}:{c}:{x}")
            rows = []
            for _ in range(n):
                r = {k: rng.randint(LO, HI) for k in ins}
                rows.append((r, g(r[a], r[b])))
            p, q = ROWS[0], ROWS[0] + ROWS[1]
            out.append(make_task(f"cu-{c}-{x}", family(c, x), "int", ins, "int",
                                 rows[:p], rows[p:q], rows[q:], LEVEL))
    return out


# ---------------------------------------------------------------- cross-family concepts
def _int_only(tree: list) -> bool:
    from .world import OPS, subtrees
    return all(x[0] in ("var", "const") or (x[0] in OPS and OPS[x[0]].out == "int") for x in subtrees(tree))


def record(prior, tree: list, family: str | None, inputs) -> None:
    """Log a certified program's int-only composites with the family they were certified in."""
    if not enabled() or not family:
        return
    from .world import _canon_vars, _var_names, size, subtrees
    types = {a: b for a, b in inputs}
    log = prior.__dict__.setdefault("curric_log", [])
    seen = set()
    for x in subtrees(tree):
        if x[0] in ("var", "const", "lib") or not (MIN_SIZE <= size(x) <= MAX_SIZE):
            continue
        if any(y[0] == "lib" for y in subtrees(x)) or not _int_only(x):
            continue
        vs = _var_names(x, [])
        if not vs or len(vs) > ARITY or any(types.get(v) != "int" for v in vs):
            continue
        c = _canon_vars(x)
        k = json.dumps(c)
        if k in seen:
            continue
        seen.add(k)
        log.append([family, c])
    if len(log) > LOG_CAP:
        del log[:len(log) - LOG_CAP]


_MEMO: dict = {}


def index(prior) -> list[dict]:
    """Concepts certified in at least FAMILIES distinct families, in MEMIDX's entry format (memoized on
    the log's content; callers get fresh copies)."""
    log = getattr(prior, "curric_log", None) or []
    if not log:
        return []
    key = (len(log), json.dumps(log), control(), families_needed(), ARITY)
    hit = _MEMO.get(id(prior))
    if hit is None or hit[0] != key:
        hit = (key, _index(log))
        _MEMO.clear()
        _MEMO[id(prior)] = hit
    return [dict(e) for e in hit[1]]


def _index(log: list) -> list[dict]:
    from .memidx import _fp, _swap, _trivial
    from .world import size, _var_names
    log = list(log)
    need = families_needed()
    ctl = control()
    if ctl is not None:
        labels = [f for f, _ in log]
        random.Random(f"curric-rewired-{ctl}").shuffle(labels)
        log = [[l, t] for l, (_, t) in zip(labels, log)]
    classes: dict[tuple, dict] = {}
    for fam, t in log:
        k = len(_var_names(t, []))
        if not 1 <= k <= ARITY:
            continue
        fp = _fp(t, k)
        if _trivial(fp, k):
            continue
        if k == 2:                        # one concept up to argument order
            sw = _swap(t)
            fs = _fp(sw, 2)
            if fs < fp:
                t, fp = sw, fs
        e = classes.setdefault((k, fp), {"tree": t, "k": k, "fp": fp, "fams": set()})
        e["fams"].add(fam)
        if (size(t), json.dumps(t)) < (size(e["tree"]), json.dumps(e["tree"])):
            e["tree"] = t
    out = []
    for e in classes.values():
        if len(e["fams"]) >= need:
            out.append({"tree": e["tree"], "k": e["k"], "fp": e["fp"], "origin": "concept",
                        "weight": WEIGHT * len(e["fams"]), "families": sorted(e["fams"])})
    out.sort(key=lambda e: (-e["weight"], size(e["tree"]), json.dumps(e["tree"])))
    return out


def study(prior, variation=None, task_list=None, rounds: int = 1, max_eval: int = 20000) -> dict:
    """Study the concept curriculum into concept memory only: each family is searched with the field
    (read-only; WITNESS certifies on public + challenge rows) and a certified program is logged with its
    family (``record``). The field's other memory (library, programs, operator counts, variation state)
    is not changed, so with the switch off the field searches exactly as before. Returns per-family
    outcomes. Deterministic."""
    from .world import evaluate
    out: dict[str, bool] = {}
    if not enabled():
        return out
    for _ in range(rounds):
        for t in (tasks() if task_list is None else task_list):
            ev, r = evaluate(t, prior=prior, variation=variation, max_eval=max_eval)
            ok = bool(ev.certified and r is not None and r.supported and r.verify_checksum())
            out[t.family] = out.get(t.family, False) or ok
            if ok:
                record(prior, ev.tree, t.family, [list(i) for i in t.inputs])
    return out
