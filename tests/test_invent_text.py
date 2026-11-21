"""INVENT_TEXT (docs/INVENT_TEXT.md): concat residual anchors on string goals. Off switch exact; an empty
field gains nothing; the sealed catalogue's ground truth matches its reference trees."""
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from nomad import bridge as XB  # noqa: E402
from nomad import text_invent_tasks as T  # noqa: E402
from nomad.world import WorldPrior, evaluate, run  # noqa: E402


def _dev(family, seed=7):
    f = next(x for x in XB.DEV_CATALOGUE if x.family == family)
    rows = XB.draw_rows(f, random.Random(f"{seed}:{family}"))
    return XB.to_task({"task_id": "dev", "family": family, "inputs": list(f.inputs), "out": f.out,
                       "rows": [[r, a] for r, a in rows]})


class _Env:
    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in self.kv}
        os.environ.update(self.kv)

    def __exit__(self, *exc):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class InventText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bridge_suite as BS
        cls.p, cls.vs = BS.fields()["trained"]

    def _run(self, t, flag, prior=None, vs=None):
        with _Env(NOMAD_BRIDGE="on", NOMAD_INVENT_TEXT=flag):
            return evaluate(t, prior=prior, variation=vs, max_eval=10000, max_size=7, casesplit=True)[0]

    def test_concat_anchor_certifies_dev_split(self):
        t = _dev("b_split_at")
        off = self._run(t, "off", self.p, self.vs)
        on = self._run(t, "on", self.p, self.vs)
        self.assertFalse(off.certified)
        self.assertTrue(on.certified)
        self.assertTrue(str(on.via).startswith("port:invent:text:"))

    def test_off_and_empty_unchanged(self):
        for fam in ("b_rot_upper", "b_split_at", "b_tail_echo"):
            t = _dev(fam)
            a, b = self._run(t, "off", WorldPrior()), self._run(t, "on", WorldPrior())
            self.assertEqual((a.certified, a.evaluations), (b.certified, b.evaluations))
        t = _dev("b_rot_upper")   # no prefix / suffix evidence: identical with the trained field too
        a, b = self._run(t, "off", self.p, self.vs), self._run(t, "on", self.p, self.vs)
        self.assertEqual((a.certified, a.evaluations, a.candidate), (b.certified, b.evaluations, b.candidate))

    def test_catalogue(self):
        names = {n for f in T.CATALOGUE for n in f.inputs}
        self.assertFalse(names & set(XB.GEN))
        for f in T.CATALOGUE:
            rows = T.draw_rows(f, random.Random(f"t:{f.family}"))
            self.assertEqual(len(rows), 11)
            for r, a in rows:
                self.assertEqual(run(f.tree, r), a)


if __name__ == "__main__":
    unittest.main()
