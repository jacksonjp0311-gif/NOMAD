"""PRIMREC (docs/PRIMREC.md): primitives learned only by cross-family recurrence; switch default off.

A composite behavior certified in two different families becomes an indexed primitive; one family is not
enough; the rewired control counts recurrence against permuted family labels; a miss and an empty field are
identical to the switch-off search."""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad import memidx as M  # noqa: E402
from nomad import world as W  # noqa: E402

KEYS = ("NOMAD_MEMIDX", "NOMAD_PRIM", "NOMAD_PRIMREC", "NOMAD_MEMIDX_CONTROL")


class _Env:
    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.old = {k: os.environ.pop(k, None) for k in KEYS}
        os.environ.update(self.kv)

    def __exit__(self, *a):
        for k in KEYS:
            os.environ.pop(k, None)
        for k, v in self.old.items():
            if v is not None:
                os.environ[k] = v


def _v(n):
    return ["var", n]


def _absd(a, b):
    return ["max", ["sub", _v(a), _v(b)], ["sub", _v(b), _v(a)]]


def _field(fams=("geo/bounded", "price/bounded")) -> W.WorldPrior:
    """|a - b| certified inside larger programs, under different names, in the given families."""
    p = W.WorldPrior()
    progs = (["add", _absd("x", "y"), ["const", 1]], ["mul", ["sub", ["max", _v("u"), _v("v")], ["min", _v("u"), _v("v")]], ["const", 2]])
    sigs = ([["x", "int"], ["y", "int"]], [["u", "int"], ["v", "int"]])
    for i, (t, sig) in enumerate(zip(progs, sigs)):
        n = f"W{i:07d}"
        p.programs[n], p.programs_sig[n], p.programs_uses[n] = t, sig, 1.0
        p.programs_src[n] = fams[i % len(fams)]
    return p


def _absd_entries(idx):
    fp = M._fp(_absd("_v0", "_v1"), 2)
    return [e for e in idx if e["fp"] == fp and e.get("origin") == "recur"]


class PrimrecTests(unittest.TestCase):
    def test_default_off(self) -> None:
        with _Env():
            self.assertFalse(M.primrec_enabled())
        with _Env(NOMAD_MEMIDX="on"):
            self.assertFalse(_absd_entries(M.build(_field())))

    def test_two_families_derive_one_family_does_not(self) -> None:
        with _Env(NOMAD_MEMIDX="on", NOMAD_PRIMREC="on"):
            hit = _absd_entries(M.build(_field()))
            self.assertEqual(len(hit), 1)
            self.assertEqual(hit[0]["families"], ["geo/bounded", "price/bounded"])
            self.assertTrue(hit[0]["sym"])
            self.assertFalse(_absd_entries(M.build(_field(("geo/bounded",)))))

    def test_no_closure_rule(self) -> None:
        """A learned sub alone (the old PRIM source) yields no recurring |a - b|."""
        p = W.WorldPrior()
        for i, fam in enumerate(("a/x", "b/x")):
            n = f"L{i:07d}"
            p.library[n], p.library_sig[n], p.library_uses[n] = ["sub", _v("x"), _v("y")], [["x", "int"], ["y", "int"]], 1.0
            p.library_src[n] = fam
        with _Env(NOMAD_MEMIDX="on", NOMAD_PRIMREC="on"):
            self.assertFalse([e for e in M.build(p) if e.get("origin") == "recur"])

    def test_rewired_control_permutes_families(self) -> None:
        p = _field()
        for i, fam in enumerate(("geo/bounded",) * 6):
            n = f"Wz{i:06d}"
            p.programs[n], p.programs_sig[n], p.programs_uses[n] = ["add", _v("a"), _v("b")], [["a", "int"], ["b", "int"]], 1.0
            p.programs_src[n] = fam
        seen = set()
        for s in range(1, 6):
            with _Env(NOMAD_MEMIDX="on", NOMAD_PRIMREC="on", NOMAD_MEMIDX_CONTROL=f"rewired:{s}"):
                seen.add(len(_absd_entries(M.build(p))))
        self.assertIn(0, seen)

    def test_empty_field_and_miss_identical_to_off(self) -> None:
        rng = random.Random(7)
        rows = []
        while len(rows) < 11:
            r = {n: rng.randint(-12, 12) for n in ("px", "py")}
            rows.append((r, rng.randint(-50, 50)))
        t = W.make_task("t", "f", "int", {"px": "int", "py": "int"}, "int", rows[:5], rows[5:8], rows[8:])

        def run(prior, **env):
            with _Env(**env):
                ev = W.evaluate(t, prior=prior, max_eval=4000, max_size=7, casesplit=True)[0]
            return ev.certified, ev.evaluations, ev.candidate, ev.via
        self.assertEqual(run(W.WorldPrior(), NOMAD_MEMIDX="on"), run(W.WorldPrior(), NOMAD_MEMIDX="on", NOMAD_PRIMREC="on"))
        off = run(_field(), NOMAD_MEMIDX="off")
        self.assertFalse(off[0])
        self.assertEqual(run(_field(), NOMAD_MEMIDX="on"), run(_field(), NOMAD_MEMIDX="on", NOMAD_PRIMREC="on"))


if __name__ == "__main__":
    unittest.main()
