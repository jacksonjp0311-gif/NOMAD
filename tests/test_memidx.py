"""MEMIDX / PRIM (docs/MEMIDX.md): behavior-indexed function memory and derived primitives.

Off by default; the index is built from the field alone (never a task's rows); PRIM derives |a - b| from a
learned sub; a miss is identical to the switch-off search; an empty field and the cold control are
untouched; the rewired control changes the index order."""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from nomad import memidx as M  # noqa: E402
from nomad import world as W  # noqa: E402

KEYS = ("NOMAD_MEMIDX", "NOMAD_PRIM", "NOMAD_MEMIDX_CONTROL")


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


def _field() -> W.WorldPrior:
    """A small hand-made field: the same few blocks remembered under several input signatures."""
    p = W.WorldPrior()
    i = 0
    for a, b in (("x", "y"), ("u", "v"), ("tp", "tq"), ("m", "n")):
        sig = [[a, "int"], [b, "int"]]
        for t in (["sub", _v(a), _v(b)], ["add", _v(a), _v(b)], ["mul", _v(a), _v(b)],
                  ["max", _v(a), _v(b)], ["min", _v(a), _v(b)], ["mul", ["add", _v(a), _v(a)], _v(b)]):
            n = f"L{i:07d}"
            i += 1
            p.library[n], p.library_sig[n], p.library_uses[n] = t, sig, 1.0 + (i % 3)
            n = f"W{i:07d}"
            p.programs[n], p.programs_sig[n], p.programs_uses[n] = t, sig, 1.0
    return p


def _task(fn, inputs=("px", "py", "qx", "qy"), seed=0):
    rng = random.Random(seed)
    rows = []
    while len(rows) < 11:
        r = {n: rng.randint(-12, 12) for n in inputs}
        rows.append((r, fn(**r)))
    return W.make_task("t", "f", "int", {n: "int" for n in inputs}, "int", rows[:5], rows[5:8], rows[8:])


def _run(task, prior, **env):
    with _Env(**env):
        ev = W.evaluate(task, prior=prior, max_eval=6000, max_size=7, casesplit=True)[0]
    return ev.certified, ev.evaluations, ev.candidate, ev.via


class MemidxTests(unittest.TestCase):
    def test_default_off_and_on_switch(self) -> None:
        with _Env():
            self.assertFalse(M.enabled())
            self.assertFalse(M.prim_enabled())
            self.assertFalse(W._memidx_on())
        with _Env(NOMAD_MEMIDX="on", NOMAD_PRIM="on"):
            self.assertTrue(M.enabled() and M.prim_enabled() and W._memidx_on())

    def test_index_merges_renamings_and_marks_symmetry(self) -> None:
        with _Env(NOMAD_MEMIDX="on"):
            idx = M.build(_field())
        trees = [W.render(e["tree"]) for e in idx]
        self.assertEqual(len(trees), len(set(trees)))
        self.assertIn("sub(_v0, _v1)", trees)
        sym = {W.render(e["tree"]): e["sym"] for e in idx}
        self.assertFalse(sym["sub(_v0, _v1)"])
        self.assertTrue(sym["add(_v0, _v1)"])
        self.assertTrue(all(e["origin"] == "learned" for e in idx))

    def test_prim_derives_absdiff_from_learned_sub(self) -> None:
        with _Env(NOMAD_MEMIDX="on", NOMAD_PRIM="on"):
            idx = M.build(_field())
        absd = ["sub", ["max", _v("_v0"), _v("_v1")], ["min", _v("_v0"), _v("_v1")]]
        fp = M._fp(absd, 2)
        hit = [e for e in idx if e["fp"] == fp]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["origin"], "prim")
        # without a learned asymmetric two-argument function there is nothing to derive
        p = W.WorldPrior()
        p.library["La"], p.library_sig["La"], p.library_uses["La"] = ["add", _v("x"), _v("y")], [["x", "int"], ["y", "int"]], 1.0
        with _Env(NOMAD_MEMIDX="on", NOMAD_PRIM="on"):
            self.assertFalse([e for e in M.build(p) if e["origin"] == "prim"])

    def test_rewired_control_changes_the_order(self) -> None:
        with _Env(NOMAD_MEMIDX="on", NOMAD_PRIM="on"):
            a = [W.render(e["tree"]) for e in M.build(_field())]
        with _Env(NOMAD_MEMIDX="on", NOMAD_PRIM="on", NOMAD_MEMIDX_CONTROL="rewired:1"):
            b = [W.render(e["tree"]) for e in M.build(_field())]
        self.assertNotEqual(a, b)

    def test_a_miss_is_identical_to_off(self) -> None:
        rng = random.Random(5)
        noise = {}

        def fn(**r):
            k = tuple(sorted(r.items()))
            return noise.setdefault(k, rng.randint(-50, 50))
        t = _task(fn, seed=3)
        p = _field()
        off = _run(t, p, NOMAD_MEMIDX="off")
        on = _run(t, p, NOMAD_MEMIDX="on", NOMAD_PRIM="on")
        self.assertFalse(off[0])
        self.assertEqual(off, on)

    def test_empty_field_and_cold_untouched(self) -> None:
        t = _task(lambda px, py, qx, qy: abs(px - qx) + abs(py - qy), seed=1)
        self.assertEqual(_run(t, W.WorldPrior(), NOMAD_MEMIDX="off"),
                         _run(t, W.WorldPrior(), NOMAD_MEMIDX="on", NOMAD_PRIM="on"))
        self.assertEqual(_run(t, None, NOMAD_MEMIDX="off"), _run(t, None, NOMAD_MEMIDX="on", NOMAD_PRIM="on"))

    def test_instances_bind_by_type_any_names(self) -> None:
        with _Env(NOMAD_MEMIDX="on", NOMAD_PRIM="on"):
            idx = M.build(_field())
        inst = M.instances(idx, [("gw", "int"), ("gx", "int"), ("s", "str")])
        names = {n for t, _e in inst for n in W._var_names(t, [])}
        self.assertEqual(names, {"gw", "gx"})


if __name__ == "__main__":
    unittest.main()
