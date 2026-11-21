"""PORT (docs/PORT.md): learned blocks and whole programs travel between input
signatures by renaming; used only inside the block probe; off switch exact;
an empty field has no bank; cheap tasks untouched; programs persist."""
import json
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad import world as W  # noqa: E402
from nomad.world import WorldPrior, evaluate, make_task, synthesize  # noqa: E402

PTS = [(2, 5), (7, 3), (4, 4), (9, 2), (10, 1), (11, 6), (3, 10), (8, 8), (13, 4), (5, 12), (6, 1)]


def _two_ab():
    rows = [({"a": a, "b": b}, 2 * a * b) for a, b in PTS]
    return make_task("t-2ab", "port_2ab", "int", {"a": "int", "b": "int"}, "int",
                     rows[:5], rows[5:8], rows[8:])


def _vsq():
    """u*u + 2*a*d over (u, a, d): cold misses at 10k; uses the learned 2ab."""
    rng = random.Random(5)

    def rows(n):
        out = []
        for _ in range(n):
            u, a, d = rng.randint(-9, 12), rng.randint(-5, 6), rng.randint(1, 12)
            out.append(({"u": u, "a": a, "d": d}, u * u + 2 * a * d))
        return out
    return make_task("t-vsq", "port_vsq", "int", {"u": "int", "a": "int", "d": "int"}, "int",
                     rows(5), rows(3), rows(3))


def _learned():
    src = _two_ab()
    p = WorldPrior()
    ev, r = evaluate(src, prior=p)
    assert ev.certified
    p.add_witnessed(ev.tree, r, family=src.family, opset=W.OPSETS["int"], inputs=src.inputs)
    return p


class Port(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("NOMAD_PORT", None)

    def test_whole_program_is_remembered_and_persisted(self):
        p = _learned()
        self.assertIn(["mul", ["add", ["var", "a"], ["var", "a"]], ["var", "b"]], list(p.programs.values()))
        back = WorldPrior.from_snapshot(json.loads(json.dumps(p.snapshot())))
        self.assertEqual(back.programs, p.programs)
        self.assertEqual(back.programs_sig, p.programs_sig)
        old = WorldPrior.from_snapshot({k: v for k, v in p.snapshot().items() if not k.startswith("programs")})
        self.assertEqual(old.programs, {})   # snapshots from before PORT still load
        p.decay(0.5)
        self.assertTrue(all(v <= 0.5 for v in p.programs_uses.values()))

    def test_programs_capped(self):
        p = WorldPrior()
        old = W.PROGRAMS_CAP
        W.PROGRAMS_CAP = 3
        try:
            for k in range(6):
                p._keep_program(["add", ["var", "x"], ["const", k % 4]] if k < 4 else
                                ["mul", ["var", "x"], ["const", k - 3]], [["x", "int"]])
            self.assertLessEqual(len(p.programs), 3)
        finally:
            W.PROGRAMS_CAP = old

    def test_bank_renames_by_type_and_empty_field_has_none(self):
        task = _vsq()
        self.assertEqual(W.port_bank(WorldPrior(), task), [])
        bank = [t for _n, t in W.port_bank(_learned(), task)]
        self.assertIn(["mul", ["add", ["var", "a"], ["var", "a"]], ["var", "d"]], bank)
        self.assertIn(["mul", ["add", ["var", "u"], ["var", "u"]], ["var", "a"]], bank)
        names = {n for n, _ in task.inputs}
        for t in bank:
            self.assertTrue(set(W._var_names(t, [])) <= names)
        # a str block never lands on int inputs
        p = WorldPrior()
        p._keep_program(["concat", ["var", "s"], ["var", "s"]], [["s", "str"]])
        self.assertEqual(W.port_bank(p, task), [])

    def test_learned_program_transfers_to_a_new_signature(self):
        task, p = _vsq(), _learned()
        cold, _ = evaluate(task, max_eval=10000)
        empty, _ = evaluate(task, prior=WorldPrior(), max_eval=10000)
        on, _ = evaluate(task, prior=p, max_eval=10000)
        os.environ["NOMAD_PORT"] = "off"
        off, _ = evaluate(task, prior=p, max_eval=10000)
        self.assertFalse(cold.certified)
        self.assertFalse(empty.certified)
        self.assertFalse(off.certified)
        self.assertTrue(on.certified)
        self.assertTrue(on.via.startswith("port:"))
        self.assertLessEqual(on.evaluations, 10000)

    def test_off_switch_is_exact(self):
        task, p = _vsq(), _learned()
        os.environ["NOMAD_PORT"] = "off"
        a = synthesize(task, prior=p, max_eval=10000)
        q = WorldPrior.from_snapshot(p.snapshot())
        q.programs, q.programs_sig, q.programs_uses = {}, {}, {}
        b = synthesize(task, prior=q, max_eval=10000)
        self.assertEqual((a.tree, a.evaluations, a.via), (b.tree, b.evaluations, b.via))

    def test_task_solved_before_trigger_is_untouched(self):
        from nomad.world_tasks import by_family
        t = by_family("pick_gt")
        p = _learned()
        on = synthesize(t, prior=p, max_eval=10000)
        os.environ["NOMAD_PORT"] = "off"
        off = synthesize(t, prior=p, max_eval=10000)
        self.assertEqual((on.evaluations, on.tree, on.via), (off.evaluations, off.tree, off.via))

    def test_residual(self):
        g = (10, 20, 30)
        self.assertEqual(W._residual("add", (1, 2, 3), g), (9, 18, 27))
        self.assertEqual(W._residual("sub", (11, 22, 33), g), (1, 2, 3))
        self.assertEqual(W._residual("rsub", (1, 2, 3), g), (11, 22, 33))
        self.assertEqual(W._residual("mul", (2, 4, 5), g), (5, 5, 6))
        self.assertIsNone(W._residual("mul", (3, 4, 5), g))
        self.assertIsNone(W._residual("mul", (0, 4, 5), g))


if __name__ == "__main__":
    unittest.main()
