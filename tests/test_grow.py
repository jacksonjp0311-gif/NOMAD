"""GROW (docs/GROW.md): two-block anchors and learned scales inside PORT;
TRANSFER-2 catalogue and frozen suite. Off switches exact; an empty field and
the cold control are untouched."""
import json
import os
import random
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import grow_suite as GS  # noqa: E402
import transfer_suite as TS  # noqa: E402
from nomad import science as S  # noqa: E402
from nomad import transfer as T  # noqa: E402
from nomad import transfer2 as T2  # noqa: E402
from nomad.world import WorldPrior, bank_scales, certify, evaluate, run  # noqa: E402
from nomad.world_tasks import all_training  # noqa: E402

SHA2 = "d8de7508d8d500abef5233ed9f56abd3c1b50e2797fd3aee097d6bb3c4e1f19b"
VARS = ("NOMAD_ANCHOR2", "NOMAD_SCALE", "NOMAD_CONST", "NOMAD_PORT")


def _dev_task(family, seed=7):
    """A dev task (other row seed) of the first transfer catalogue; never the sealed rows."""
    f = T.BY_FAMILY[family]
    rows = T.draw_rows(f, random.Random(f"{seed}:{family}"))
    return T.to_task({"task_id": "dev", "family": family, "inputs": list(f.inputs), "rows": rows})


def _env(**kv):
    for k in VARS:
        os.environ.pop(k, None)
    os.environ.update(kv)


class Scales(unittest.TestCase):
    def test_scales_come_only_from_memory(self):
        self.assertEqual(bank_scales([]), [])
        bank = [("a", ["div", ["add", ["var", "x"], ["var", "y"]], ["const", 2]]),
                ("b", ["mul", ["var", "g"], ["mul", ["const", 3], ["const", 3]]]),
                ("c", ["mul", ["var", "x"], ["var", "y"]])]
        self.assertEqual([k for k, _ in bank_scales(bank)], [2, 3, 9])   # 3: the factor inside mul(3, 3)
        self.assertEqual(dict(bank_scales(bank))[9], ["mul", ["const", 3], ["const", 3]])


class Defaults(unittest.TestCase):
    def test_defaults_after_sealed_pass(self):
        from nomad.world import anchor2_enabled, const_enabled, scale_enabled
        _env()
        self.assertTrue(anchor2_enabled() and scale_enabled())   # docs/GROW.md: passed on TRANSFER-2
        self.assertFalse(const_enabled())                        # no dev gain: stays off
        _env(NOMAD_ANCHOR2="off", NOMAD_SCALE="off")
        self.assertFalse(anchor2_enabled() or scale_enabled())
        _env()


class GrowSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fields = TS.fields()

    def tearDown(self):
        for k in VARS:
            os.environ.pop(k, None)

    def _run(self, task, prior, vs=None, **env):
        _env(**env)
        if prior is None:
            return evaluate(task, prior=None, max_eval=10000)[0]
        return evaluate(task, prior=prior, variation=vs, casesplit=True, max_eval=10000)[0]

    def test_empty_field_and_cold_untouched(self):
        for fam in ("geo_diag3", "geo_diagonals", "geo_box_surface"):
            t = _dev_task(fam)
            for prior in (None, WorldPrior()):
                a = self._run(t, prior, NOMAD_ANCHOR2="off", NOMAD_SCALE="off")
                b = self._run(t, prior, NOMAD_ANCHOR2="on", NOMAD_SCALE="on", NOMAD_CONST="on")
                self.assertEqual((a.certified, a.evaluations, a.candidate), (b.certified, b.evaluations, b.candidate))

    def test_two_block_anchor_sum_of_three_products(self):
        p, vs = self.fields["math_sci"]
        t = _dev_task("geo_box_surface", 11)
        off = self._run(t, p, vs, NOMAD_ANCHOR2="off", NOMAD_SCALE="off")
        on = self._run(t, p, vs, NOMAD_ANCHOR2="on", NOMAD_SCALE="off")
        self.assertFalse(off.certified)
        self.assertTrue(on.certified)
        self.assertEqual(on.via, "port:anchor2")

    def test_learned_scale_halving(self):
        p, vs = self.fields["math_sci"]
        t = _dev_task("geo_diagonals", 7)
        off = self._run(t, p, vs, NOMAD_ANCHOR2="off", NOMAD_SCALE="off")
        on = self._run(t, p, vs, NOMAD_ANCHOR2="off", NOMAD_SCALE="on")
        self.assertFalse(off.certified)
        self.assertTrue(on.certified)
        self.assertTrue(on.via.startswith("port:scale:div2"))

    def test_math_only_field_has_no_scales(self):
        p, _ = self.fields["math"]
        bank = list(p.library.items()) + list(p.programs.items())
        self.assertEqual(bank_scales(bank), [])


class Transfer2Catalogue(unittest.TestCase):
    def test_well_formed_and_names_disjoint(self):
        fams = [f.family for f in T2.CATALOGUE]
        self.assertEqual(len(fams), len(set(fams)))
        train = {n for t in all_training() for n, _ in t.inputs} | {n for f in S.CATALOGUE for n in f.inputs}
        old = {n for f in T.CATALOGUE for n in f.inputs}
        mine = {n for f in T2.CATALOGUE for n in f.inputs}
        self.assertFalse(mine & train)
        self.assertFalse(mine & old)
        self.assertFalse(set(T2.BY_FAMILY) & (set(T.BY_FAMILY) | set(S.BY_FAMILY)))
        for f in T2.CATALOGUE:
            self.assertEqual(set(f.ranges), set(f.inputs))

    def test_rows_exact(self):
        for f in T2.CATALOGUE:
            a = T2.draw_rows(f, random.Random(f"7:{f.family}"))
            self.assertEqual(a, T2.draw_rows(f, random.Random(f"7:{f.family}")))
            for r, ans in a:
                q = Fraction(f.truth(*(r[n] for n in f.inputs)))
                self.assertEqual(q.denominator, 1)
                self.assertEqual(int(q), ans)
                self.assertEqual(run(f.tree, r), ans)


class FrozenTransfer2Suite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = json.loads(GS.OUT.read_text())

    def test_hash(self):
        self.assertEqual(GS.suite_hash(self.suite), SHA2)
        self.assertEqual(GS.HASH.read_text().split()[0], SHA2)

    def test_sections(self):
        s = self.suite
        self.assertEqual(len(s["hard"]), 35)
        self.assertEqual(len(s["easy"]) + len(s["hard"]) + len(s["stats"]["lookup_dropped"]), len(T2.CATALOGUE))
        self.assertTrue(all(not e["cold_certified"] for e in s["hard"]))

    def test_reference_certifies_and_wrong_rejected(self):
        _, _, hard = GS.load()
        for e, t in zip(self.suite["hard"], hard):
            r, pub, fin = certify(t, e["tree"])
            self.assertTrue(r.supported and pub and fin, e["family"])
            r2, _pub2, fin2 = certify(t, ["add", e["tree"], ["const", 1]])
            self.assertFalse(r2 is not None and r2.supported and fin2)


if __name__ == "__main__":
    unittest.main()
