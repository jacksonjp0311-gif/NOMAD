"""INVENT (docs/INVENT.md): NOMAD invents its own building blocks from
certified memory. Abstractions by compression, learned constants, invented
primitives as single nodes in the field arm's probe. Off switch exact; an
empty field invents nothing; the cold control never sees an invention."""
import json
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import transfer_suite as TS  # noqa: E402
from nomad import invent as I  # noqa: E402
from nomad import transfer2 as T2  # noqa: E402
from nomad.world import WorldPrior, evaluate, port_bank, run, subtrees  # noqa: E402

SHA4 = "756c725c1c1957742974060635aec40cbf935ff2da00ccc63130a1de049b5078"
SHA3 = "5a8dab572468551d557558bea6ba2c004b90b254aa68c2878f3e91a9bb4f10e9"
V = lambda n: ["var", n]  # noqa: E731
H = lambda i: ["hole", i]  # noqa: E731


def _dev_task(family, seed=7):
    """A dev task (other row seed) of the TRANSFER-2 catalogue; never sealed rows."""
    f = T2.BY_FAMILY[family]
    rows = T2.draw_rows(f, random.Random(f"{seed}:{family}"))
    return T2.to_task({"task_id": "dev", "family": family, "inputs": list(f.inputs), "rows": rows})


def _env(v=None):
    os.environ.pop("NOMAD_INVENT", None)
    if v is not None:
        os.environ["NOMAD_INVENT"] = v


class Abstraction(unittest.TestCase):
    def test_lgg_and_match(self):
        a = ["add", ["mul", V("x"), V("x")], V("y")]
        b = ["add", ["mul", V("u"), V("u")], ["const", 1]]
        g = I.lgg(a, b)
        self.assertEqual(g, ["add", ["mul", H(0), H(0)], H(1)])   # same differing pair -> same hole
        self.assertTrue(I.match(g, a, {}))
        self.assertFalse(I.match(g, ["add", ["mul", V("x"), V("y")], V("y")], {}))   # repeated hole binds equal
        # commutative operators match in either order
        self.assertTrue(I.match(["add", H(0), ["mul", H(1), H(2)]], ["add", ["mul", V("a"), V("t")], V("u")], {}))

    def test_abstract_vars_and_instantiate(self):
        t = ["mul", V("I"), ["mul", V("I"), V("R")]]
        b = I.abstract_vars(t)
        self.assertEqual(b, ["mul", H(0), ["mul", H(0), H(1)]])
        self.assertEqual(I.instantiate(b, [V("G"), V("G")]), ["mul", V("G"), ["mul", V("G"), V("G")]])

    def test_compression_promotes_recurring_blocks(self):
        progs = [("p1", ["add", V("s"), ["mul", V("m"), V("k")]]),
                 ("p2", ["add", ["mul", V("a"), V("t")], V("u")]),
                 ("p3", ["add", ["mul", V("x"), V("x")], V("y")]),
                 ("p4", ["sub", ["mul", V("y"), V("y")], V("x")])]
        inv = I._invent(progs)
        forms = {x.infix(): x for x in inv}
        self.assertIn("λ a b c. a + b·c", forms)            # 3 uses: compresses the corpus
        self.assertIn("λ a. a·a", forms)                    # 2 uses, a repeated hole
        self.assertEqual(forms["λ a b c. a + b·c"].uses, 3)
        for x in inv:
            self.assertGreaterEqual(x.uses, I.MIN_USES)
            self.assertGreaterEqual(x.utility, 0)
            self.assertEqual(x.utility, x.uses * x.saving - (I._size(x.tree) - len(x.args)))
        # a block used once compresses nothing: not invented
        self.assertEqual(I._invent([("p1", ["add", V("s"), ["mul", V("m"), V("k")]])]), [])

    def test_symmetry_and_behaviour(self):
        self.assertEqual(I.symmetries(["mul", H(0), ["mul", H(1), H(2)]], ("int",) * 3), ((0, 1), (0, 2), (1, 2)))
        self.assertEqual(I.symmetries(["add", H(0), ["mul", H(1), H(2)]], ("int",) * 3), ((1, 2),))
        # behaviourally equal abstractions share one fingerprint (hole order ignored)
        self.assertEqual(I.behaviour(["add", H(0), ["mul", H(1), H(2)]], ("int",) * 3),
                         I.behaviour(["add", ["mul", H(0), H(1)], H(2)], ("int",) * 3))

    def test_composition_and_degenerate(self):
        sq = I.Invention("Isq", ("mul", H(0), H(0)), ("int",), "int", 3, 1, 0, "mul(y, y)")
        fadd = I.Invention("Fadd", ("add", H(0), H(1)), ("int", "int"), "int", 6, 0, 0, "add(a, b)", 0)
        fdiv = I.Invention("Fdiv", ("div", H(0), H(1)), ("int", "int"), "int", 6, 0, 0, "div(a, b)", 0)
        seen = {I.behaviour(x.tree, x.args) for x in (sq, fadd, fdiv)}
        out = I.compose([sq, fadd, fdiv], [sq, fadd, fdiv], [(2, ["const", 2])], seen, 2)
        forms = {x.infix(): x for x in out}
        self.assertIn("λ a b. (a + b)·(a + b)", forms)
        self.assertEqual(forms["λ a b. (a + b)·(a + b)"].parts, ("Isq", "Fadd"))
        self.assertTrue(all(x.round == 2 for x in out))
        # two different frames never compose on their own (only a frame with itself)
        self.assertNotIn("λ a b c. (a + b) // c", forms)
        self.assertTrue(I.degenerate(["div", ["div", ["mul", H(0), H(0)], H(0)], H(0)], ("int",)))   # = 1
        self.assertTrue(I.degenerate(["div", ["mul", H(0), H(1)], H(1)], ("int", "int")))             # = a
        self.assertFalse(I.degenerate(["div", ["div", H(0), H(1)], H(2)], ("int",) * 3))

    def test_constants_from_learned_scales_only(self):
        self.assertEqual(I.constants([]), [])
        two, three = ["const", 2], ["const", 3]
        got = I.constants([(2, two), (3, three)])
        self.assertEqual([k for k, _ in got], [4, 6][:I.MAX_CONSTANTS])
        self.assertEqual(run(got[0][1], {}), 4)


class Fields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fields = TS.fields()

    def tearDown(self):
        _env()

    def test_empty_field_invents_nothing(self):
        self.assertEqual(I.inventions(WorldPrior()), [])
        t = _dev_task("g2_box_minus_cube")
        self.assertIsNone(I.kit(WorldPrior(), t, port_bank(WorldPrior(), t)))

    def test_inventions_come_from_memory_and_are_deterministic(self):
        p, _ = self.fields["math_sci"]
        a = [x.infix() for x in I.inventions(p)]
        p2, _ = TS.fields()["math_sci"]
        self.assertEqual(a, [x.infix() for x in I.inventions(p2)])
        self.assertIn("λ a. a·a", a)
        self.assertIn("λ a b c. a·b·c", a)
        pm, _ = self.fields["math"]
        got = I.inventions(pm)
        self.assertEqual([x.infix() for x in got if x.round == 1], ["λ a. a·a"])
        sq = got[0].name
        # round 2: every composed primitive is built from a round-1 primitive
        r2 = [x for x in got if x.round == 2]
        self.assertTrue(r2)
        self.assertTrue(all(sq in x.parts for x in r2))
        self.assertIn("λ a. a·a·a·a", [x.infix() for x in r2])     # the square of the square

    def test_math_sci_nested_primitives(self):
        p, _ = self.fields["math_sci"]
        got = I.inventions(p)
        r1 = {x.name for x in got if x.round == 1}
        nested = [x for x in got if x.round == 2 and r1 & set(x.parts)]
        self.assertGreaterEqual(len(nested), 3)
        forms = [x.infix() for x in nested]
        self.assertIn("λ a b c. (a + b·c)·(a + b·c)", forms)       # primitive inside primitive
        self.assertIn("λ a b c. (a + b·c) // 2", forms)            # primitive under a learned constant
        for x in got:
            self.assertLessEqual(len(x.args), I.MAX_HOLES)

    def test_default_off_and_off_switch_exact(self):
        _env()
        self.assertFalse(I.enabled())   # docs/INVENT.md: sealed criterion 4 failed (science per-task loss)
        t = _dev_task("g2_box_minus_cube")
        p, vs = self.fields["math_sci"]
        a = evaluate(t, prior=p, variation=vs, casesplit=True, max_eval=10000)[0]
        _env("off")
        b = evaluate(t, prior=p, variation=vs, casesplit=True, max_eval=10000)[0]
        self.assertEqual((a.certified, a.evaluations, a.candidate), (b.certified, b.evaluations, b.candidate))

    def test_empty_and_cold_untouched(self):
        for fam in ("g2_box_minus_cube", "g2_square_pyr_number", "g2_hex_number"):
            t = _dev_task(fam)
            for prior in (None, WorldPrior()):
                kw = {} if prior is None else dict(casesplit=True)
                _env("off")
                a = evaluate(t, prior=prior, max_eval=10000, **kw)[0]
                _env("on")
                b = evaluate(t, prior=prior, max_eval=10000, **kw)[0]
                self.assertEqual((a.certified, a.evaluations, a.candidate), (b.certified, b.evaluations, b.candidate))

    def test_invented_cube_reaches_a_dev_task(self):
        t = _dev_task("g2_box_minus_cube")          # EFG - G^3, dev rows (seed 7)
        p, vs = self.fields["math_sci"]
        _env("off")
        off = evaluate(t, prior=p, variation=vs, casesplit=True, max_eval=10000)[0]
        _env("on")
        on = evaluate(t, prior=p, variation=vs, casesplit=True, max_eval=10000)[0]
        self.assertFalse(off.certified)
        self.assertTrue(on.certified)
        self.assertTrue(on.via.startswith("port:"))
        # the certified program is plain operators: no hole, no library call
        self.assertFalse(any(x[0] in ("hole", "lib") for x in subtrees(on.tree)))

    def test_derived_constant_reaches_a_dev_task(self):
        t = _dev_task("g2_square_pyr_number")       # n(n+1)(2n+1)/6, dev rows (seed 7)
        p, vs = self.fields["math_sci"]
        _env("off")
        off = evaluate(t, prior=p, variation=vs, casesplit=True, max_eval=10000)[0]
        _env("on")
        on = evaluate(t, prior=p, variation=vs, casesplit=True, max_eval=10000)[0]
        self.assertFalse(off.certified)
        self.assertTrue(on.certified)
        self.assertTrue(on.via.startswith("port:invent:"))

    def test_no_per_task_loss_on_dev(self):
        """Budget edge (docs/INVENT.md, round 2): main's path is unchanged up
        to the INVENT phase, which is deferred when a bank block already
        equals the goal on INVENT_EQ_GATE rows; no dev task off solves is lost."""
        p, vs = self.fields["math_sci"]
        lost = []
        for f in T2.CATALOGUE:
            t = _dev_task(f.family)
            _env("off")
            off = evaluate(t, prior=p, variation=vs, casesplit=True, max_eval=10000)[0]
            if not off.certified:
                continue
            _env("on")
            on = evaluate(t, prior=p, variation=vs, casesplit=True, max_eval=10000)[0]
            if not on.certified:
                lost.append(f.family)
            elif on.via in ("port:anchor", "port:block", "stage1"):
                self.assertEqual(on.evaluations, off.evaluations)   # solved before the phase: identical
        self.assertEqual(lost, [])

    def test_kit_ops_expand_to_plain_trees(self):
        p, _ = self.fields["math_sci"]
        t = _dev_task("g2_hex_number")
        k = I.kit(p, t, port_bank(p, t))
        self.assertTrue(k.ops and k.instances)
        for op in k.ops.values():
            tree = op.build([V("cnt")] * len(op.args))
            self.assertFalse(any(x[0] == "hole" for x in subtrees(tree)))
            self.assertEqual(op.fn(*([3] * len(op.args))), run(tree, {"cnt": 3}))
        self.assertLessEqual(len(k.instances), I.MAX_INSTANCES)
        json.dumps([x for _, x in k.instances])


class Transfer3Suite(unittest.TestCase):
    def test_frozen_suite_hash_and_shape(self):
        import invent_suite as IS
        suite, easy, hard = IS.load(IS.OUT, check=True)
        self.assertEqual(IS.suite_hash(suite), SHA3)
        self.assertEqual(suite["seed"], 20261125)
        self.assertEqual((len(easy), len(hard)), (6, 40))
        self.assertTrue(all(not e["cold_certified"] for e in suite["hard"]))
        for t in hard:
            self.assertEqual((len(t.public), len(t.challenge), len(t.final)), (5, 3, 3))

    def test_catalogue_is_new(self):
        from nomad import transfer as T1
        from nomad import transfer3 as T3
        from nomad.world_tasks import all_training
        names3 = {n for f in T3.CATALOGUE for n in f.inputs}
        old = {n for f in T1.CATALOGUE + T2.CATALOGUE for n in f.inputs}
        old |= {n for t in all_training() for n, _ in t.inputs}
        self.assertFalse(names3 & old)
        self.assertFalse({f.family for f in T3.CATALOGUE} & {f.family for f in T1.CATALOGUE + T2.CATALOGUE})


class Transfer4Catalogue(unittest.TestCase):
    def test_frozen_suite_hash_and_shape(self):
        import invent2_suite as IS2
        suite, easy, hard = IS2.load(IS2.OUT, check=True)
        self.assertEqual(IS2.suite_hash(suite), SHA4)
        self.assertEqual(suite["seed"], 20261126)
        self.assertEqual((len(easy), len(hard)), (12, 35))
        self.assertTrue(all(not e["cold_certified"] for e in suite["hard"]))
        for t in hard:
            self.assertEqual((len(t.public), len(t.challenge), len(t.final)), (5, 3, 3))

    def test_catalogue_is_new(self):
        from nomad import science as S
        from nomad import transfer as T1
        from nomad import transfer3 as T3
        from nomad import transfer4 as T4
        from nomad.world_tasks import all_training
        names4 = {n for f in T4.CATALOGUE for n in f.inputs}
        earlier = T1.CATALOGUE + T2.CATALOGUE + T3.CATALOGUE + S.CATALOGUE
        old = {n for f in earlier for n in f.inputs} | {n for t in all_training() for n, _ in t.inputs}
        self.assertFalse(names4 & old)
        self.assertFalse({f.family for f in T4.CATALOGUE} & {f.family for f in earlier})
        self.assertEqual(set(T4.DOMAINS), {f.kind.split(":")[0] for f in T4.CATALOGUE})

    def test_reference_trees_reproduce_truth(self):
        from nomad import transfer4 as T4
        for f in T4.CATALOGUE:
            rows = T4.draw_rows(f, random.Random(f"test:{f.family}"))
            self.assertGreater(len({a for _r, a in rows[:5]}), 1, f.family)
            for r, a in rows:
                self.assertEqual(run(f.tree, r), a)


if __name__ == "__main__":
    unittest.main()
