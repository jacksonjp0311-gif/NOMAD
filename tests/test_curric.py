"""CURRIC (docs/CURRIC.md): multi-family concept curriculum; switch default on (sealed PASS).

The generator presents every concept in every context as its own family; a behavior certified in at least
FAMILIES families becomes a concept, fewer is not enough; study changes only the concept memory; the
switch off, an empty field and a concept-free field search exactly as before; the rewired and gate1
controls and the snapshot round trip behave as documented."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad import curric as CU  # noqa: E402
from nomad import world as W  # noqa: E402

KEYS = ("NOMAD_CURRIC", "NOMAD_CURRIC_CONTROL", "NOMAD_MEMIDX", "NOMAD_PRIM", "NOMAD_PRIMREC")


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


ABSD_ITE = ["ite", ["sub", _v("x"), _v("y")], ["sub", _v("x"), _v("y")], ["sub", _v("y"), _v("x")]]
ABSD_MM = ["sub", ["max", _v("p"), _v("r")], ["min", _v("r"), _v("p")]]
ABSD_SW = ["max", ["sub", _v("n"), _v("m")], ["sub", _v("m"), _v("n")]]


def _logged(fams):
    p = W.WorldPrior()
    trees = (ABSD_ITE, ABSD_MM, ABSD_SW)
    sigs = ([["x", "int"], ["y", "int"]], [["p", "int"], ["q", "int"], ["r", "int"]], [["m", "int"], ["n", "int"]])
    with _Env(NOMAD_CURRIC="on"):
        for t, s, f in zip(trees, sigs, fams):
            CU.record(p, t, f, s)
    return p


class CurricTests(unittest.TestCase):
    def test_default_on_and_off_is_inert(self):
        with _Env():
            self.assertTrue(CU.enabled())
            self.assertTrue(W._curric_on())
        with _Env(NOMAD_CURRIC="off"):
            self.assertFalse(CU.enabled())
            self.assertFalse(W._curric_on())
            p = W.WorldPrior()
            CU.record(p, ABSD_ITE, "f", [["x", "int"], ["y", "int"]])
            self.assertFalse(getattr(p, "curric_log", None))
            self.assertEqual(CU.study(p), {})

    def test_generator_families(self):
        ts = CU.tasks()
        self.assertEqual(len(ts), len(CU.CONCEPTS) * len(CU.CONTEXTS))
        self.assertEqual(len({t.family for t in ts}), len(ts))
        self.assertEqual([t.public for t in ts], [t.public for t in CU.tasks()])   # deterministic
        pick = [t for t in ts if t.family == "cu_absdiff_pick"][0]
        for r, e in pick.public + pick.challenge + pick.final:
            self.assertEqual(e, abs(r["p"] - r["r"]))
        sw = [t for t in ts if t.family == "cu_posdiff_swap"][0]
        for r, e in sw.public:
            self.assertEqual(e, max(r["n"] - r["m"], 0))

    def test_three_families_make_a_concept(self):
        p = _logged(("a", "b", "c"))
        with _Env(NOMAD_CURRIC="on"):
            idx = CU.index(p)
        self.assertEqual(len(idx), 1)
        self.assertEqual(idx[0]["families"], ["a", "b", "c"])
        self.assertEqual(W.run(idx[0]["tree"], {"_v0": 3, "_v1": 10}), 7)
        self.assertEqual(W.run(idx[0]["tree"], {"_v0": 10, "_v1": 3}), 7)

    def test_too_few_families(self):
        p = _logged(("a", "a", "b"))
        with _Env(NOMAD_CURRIC="on"):
            self.assertEqual(CU.index(p), [])
            self.assertFalse(W._curric_bank(p))
        with _Env(NOMAD_CURRIC="on", NOMAD_CURRIC_CONTROL="gate1"):
            self.assertEqual(len(CU.index(p)), 1)

    def test_rewired_permutes_labels(self):
        p = _logged(("a", "b", "c"))
        with _Env(NOMAD_CURRIC="on", NOMAD_CURRIC_CONTROL="rewired:1"):
            idx = CU.index(p)
        self.assertEqual(len(idx), 1)   # labels permuted among three distinct families: still three

    def test_snapshot_round_trip(self):
        p = _logged(("a", "b", "c"))
        q = W.WorldPrior.from_snapshot(json.loads(json.dumps(p.snapshot())))
        self.assertEqual(q.curric_log, p.curric_log)
        self.assertNotIn("curric_log", W.WorldPrior().snapshot())

    def test_study_changes_only_concept_memory(self):
        p = W.WorldPrior()
        before = json.dumps(p.snapshot(), sort_keys=True)
        ts = [t for t in CU.tasks() if t.family in ("cu_mid_pair", "cu_mid_pick", "cu_mid_swap")]
        with _Env(NOMAD_CURRIC="on"):
            res = CU.study(p, task_list=ts, max_eval=4000)
            idx = CU.index(p)
        self.assertTrue(all(res.values()), res)
        snap = p.snapshot()
        snap.pop("curric_log")
        self.assertEqual(json.dumps(snap, sort_keys=True), before)
        self.assertEqual(len(idx), 1)
        self.assertEqual(W.run(idx[0]["tree"], {"_v0": 4, "_v1": 9}), 6)

    def test_concept_helps_and_switch_off_is_unchanged(self):
        p = _logged(("a", "b", "c"))
        p.programs["Wq"] = ["add", ["mul", _v("u"), _v("v")], ["const", 3]]
        p.programs_sig["Wq"] = [["u", "int"], ["v", "int"]]
        p.programs_uses["Wq"] = 1.0
        rows = [({"g": g, "h": h}, abs(g - h) + 1) for g, h in ((3, 9), (12, 4), (7, 7), (0, 5), (20, 1), (6, 2),
                                                                 (2, 15), (9, 9), (11, 3), (5, 8), (14, 0))]
        t = W.make_task("t-cu", "cu_test", "int", {"g": "int", "h": "int"}, "int", rows[:5], rows[5:8], rows[8:])
        with _Env(NOMAD_CURRIC="off"):
            off = W.evaluate(t, prior=p, max_eval=3000)[0]
        with _Env(NOMAD_CURRIC="0"):
            off2 = W.evaluate(t, prior=p, max_eval=3000)[0]
        self.assertEqual((off.certified, off.evaluations, off.tree), (off2.certified, off2.evaluations, off2.tree))
        e = W.WorldPrior()
        with _Env(NOMAD_CURRIC="off"):
            e_off = W.evaluate(t, prior=e, max_eval=3000)[0]
        with _Env(NOMAD_CURRIC="on"):
            e_on = W.evaluate(t, prior=e, max_eval=3000)[0]
        self.assertEqual((e_off.certified, e_off.evaluations), (e_on.certified, e_on.evaluations))


if __name__ == "__main__":
    unittest.main()
