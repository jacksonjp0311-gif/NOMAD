"""AGREE: a budget-neutral LET2 with an agreement guard (docs/AGREE.md).

LET2 (docs/LET2.md) found real gains (its sealed suite 9 -> 13) but lost certifications elsewhere: a let fit
that reproduced every public and challenge row (so WITNESS accepted it) was wrong on the final rows and
returned before INVENT. DISCRIM (docs/DISCRIM.md) guarded it by looking for a *disagreeing* alternative; its
remaining certification loss (ceil ``cl_h_rafts``) was a fit with **no** surviving alternative at all, so the
experiment was empty and "confirmed" it vacuously.

AGREE turns the burden around (positive support): an accepted LET2 let fit may return early **only when an
independently derived alternative agrees with it**. Independent means assembled from something other than
the hit's own decomposition: another fit over the same intermediate (a different pair of one-step terms),
or a fit over a *different* intermediate (the next ``AGREE_T`` bound blocks of the same bounded let search).
Agreement is checked where the evidence is silent: on DISCRIM's deterministic distinguishing inputs (swaps /
recombinations / spread of the task's own evidence inputs; no expected outputs), the alternative and the hit
give the same value on every row where both are valid, and on at least ``AGREE_MIN_ROWS`` such rows. Any
alternative (independent, or one of the hit's evidence-preserving simplifications) that fits the evidence but
disagrees vetoes the early return. No support or a veto: the stage is a miss, and a LET2 miss is identical to
off (its evaluations come only from MERGE's unspent probe-equivalence skips, its WITNESS rejections are
forgotten, the unspent skips are charged afterwards).

No leakage: only ``task.inputs`` and the public + challenge rows (the WITNESS evidence) are read; search
receives a task view with ``final=()`` anyway (INTEGRITY defect 3). Pure functions, deterministic (no
hash-seed dependence), CPU only.
"""
from __future__ import annotations

import json
import os

from . import discrim as _D
from .world import size

AGREE_T = 8           # further bound intermediates the independent search may try after the hit's own
AGREE_ALT = 48        # most alternatives checked against the evidence per decision
AGREE_MIN_ROWS = 8    # distinguishing rows on which hit and supporter must both be valid (and equal)
AGREE_SCALES = (2, 3)  # scaled residual decompositions a op (b * k); divisors of the offset quotients
AGREE_DIVS = 6         # most divisors (2, 3, then the field's learned scales) for the offset quotients
COMMUTATIVE = ("add", "mul", "max", "min")


def enabled() -> bool:
    """NOMAD_AGREE (default off until its sealed judge passes)."""
    return os.environ.get("NOMAD_AGREE", "off").strip().lower() not in ("off", "0", "false", "no")


def control() -> str:
    """Judge-only controls: "" (none), "shuffled" (each alternative's outcomes compared on the wrong
    distinguishing rows, rotated by one) or "rewired" (each alternative's outcomes compared with the hit's
    outcomes on rows whose int inputs are rotated and incremented by one: agreement on the wrong question)."""
    return os.environ.get("NOMAD_AGREE_CONTROL", "").strip().lower()


def canon(tree) -> str:
    """A canonical text for syntactic identity: commutative operands in a fixed order."""
    def c(t):
        if t[0] in ("var", "const", "lib"):
            return t
        kids = [c(x) for x in t[1:]]
        if t[0] in COMMUTATIVE:
            kids.sort(key=lambda x: json.dumps(x))
        return [t[0]] + kids
    return json.dumps(c(tree))


def _rewire_rows(inputs, drows):
    """The wrong question: each int input's value taken from the next int input (cyclic) and incremented by
    one (so a function symmetric in its inputs is not immune to the rewiring)."""
    ints = [nm for nm, t in inputs if t == "int"]
    out = []
    for r in drows:
        s = dict(r)
        for i, nm in enumerate(ints):
            s[nm] = r[ints[(i + 1) % len(ints)]] + 1
        out.append(s)
    return out


def decide(hit, indep, simp, inputs, ev_rows) -> dict:
    """The agreement decision for one WITNESS-accepted let fit.

    ``indep``: independently derived alternatives; ``simp``: the hit's evidence-preserving simplifications
    (veto only, never support). Both already filtered to those that fit the evidence. Returns
    {"verdict": "supported" | "unsupported" | "vetoed", "support": n, "veto": n, "rival_class": n, "rows": n}.

    Supported: at least one independent alternative agrees with the hit (same value on every distinguishing
    row where both are valid, on at least AGREE_MIN_ROWS rows), and the hit's agreement class (the hit and
    its supporters) is strictly larger than the largest class of mutually agreeing rivals (alternatives
    that disagree with the hit). Unsupported: no agreeing independent alternative. Vetoed: otherwise."""
    drows = _D.rows(inputs, ev_rows)
    ctl = control()
    hs = _D.signature(hit, drows)
    arows = _rewire_rows(inputs, drows) if ctl == "rewired" else drows
    sig_ind = []
    for a in indep:
        sa = _D.signature(a, arows)
        if ctl == "shuffled" and sa:
            sa = sa[1:] + sa[:1]
        sig_ind.append(sa)
    sig_simp = []
    for a in simp:
        sa = _D.signature(a, arows)
        if ctl == "shuffled" and sa:
            sa = sa[1:] + sa[:1]
        sig_simp.append(sa)
    support = sum(1 for sa in sig_ind if not _D.disagree(hs, sa)
                  and sum(1 for x, y in zip(hs, sa) if x is not None and y is not None) >= AGREE_MIN_ROWS)
    rivals = [sa for sa in sig_ind + sig_simp if _D.disagree(hs, sa)]
    # the largest class of rivals that agree with each other (a rival explanation's own support)
    rival = max((sum(1 for y in rivals if not _D.disagree(x, y)) for x in rivals), default=0)
    if not support:
        verdict = "unsupported"
    elif 1 + support > rival:
        verdict = "supported"
    else:
        verdict = "vetoed"
    # Occam inside the agreement class: the smallest program that agrees with the hit everywhere it was
    # compared (the hit, its supporters, its agreeing simplifications); ties keep the earlier one (hit first)
    pick = hit
    if verdict == "supported":
        for a, sa in list(zip(indep, sig_ind)) + list(zip(simp, sig_simp)):
            if not _D.disagree(hs, sa) and sum(1 for x, y in zip(hs, sa) if x is not None and y is not None) >= AGREE_MIN_ROWS \
                    and size(a) < size(pick):
                pick = a
    return {"verdict": verdict, "support": support, "veto": len(rivals), "rival_class": rival, "rows": len(drows),
            "pick": pick}


BUDGET: list = [0]   # dev diagnostics only: the LET2 budget left when the guard started
TRACE: list = []   # filled only when NOMAD_AGREE_TRACE is set (dev diagnostics; never read by search)


def note(task, hit, indep, simp, d) -> None:
    if os.environ.get("NOMAD_AGREE_TRACE"):
        rec = {"task": task.task_id, "hit": hit, "indep": indep[:6], "simp": simp[:6], "budget": BUDGET[0], **d}
        TRACE.append(rec)
        print("AGREE", task.task_id, json.dumps(hit), d, "budget", BUDGET[0], [json.dumps(a) for a in indep][:4], flush=True)


__all__ = ["enabled", "control", "canon", "decide", "note", "AGREE_T", "AGREE_ALT", "AGREE_MIN_ROWS", "size"]
