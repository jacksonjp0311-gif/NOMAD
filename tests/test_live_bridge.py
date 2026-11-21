"""NOMAD_LIVE_BRIDGE: bridge training families in the live body curriculum (default off)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Env:
    def __init__(self, **kv):
        self.kv, self.old = kv, {}

    def __enter__(self):
        for k, v in self.kv.items():
            self.old[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _board(fams, treat=False, control=False, saved=0):
    return [{"task": f"world:{f}", "treatment": treat, "control": control, "evaluations_saved": saved} for f in fams]


class LiveBridgeTests(unittest.TestCase):
    def test_off_is_exactly_train(self) -> None:
        from nomad import world_tasks as W
        from nomad.curriculum import choose, open_levels, family_records
        with _Env(NOMAD_LIVE_BRIDGE=None):
            self.assertIs(W.curriculum_train(), W.TRAIN)
            self.assertFalse(W.live_bridge_enabled())
            fams = [t.family for t in W.all_training()]
            for rows in ([], _board(fams[:5]), _board(fams, treat=True, saved=3), _board(fams[:3] * 5)):
                t, plan = choose(rows)
                self.assertIn(t.family, fams)
                self.assertEqual(set(plan["open_levels"]), set(W.TRAIN))
                self.assertEqual(plan["candidates"], sum(len(ts) for L, ts in
                                                         ((L, ts) for d, lv in W.TRAIN.items() for L, ts in lv.items())
                                                         if L <= open_levels(family_records(rows))[W.domain_of(ts[0].family)]))
        with _Env(NOMAD_LIVE_BRIDGE="off"):
            self.assertIs(W.curriculum_train(), W.TRAIN)

    def test_on_adds_bridge_domain(self) -> None:
        from nomad import world_tasks as W
        from nomad.bridge import TRAIN_FAMILIES
        from nomad.curriculum import choose
        with _Env(NOMAD_LIVE_BRIDGE="on", NOMAD_BRIDGE=None):
            ct = W.curriculum_train()
            self.assertEqual(set(ct) - set(W.TRAIN), {"bridge"})
            self.assertEqual(sorted(t.family for ts in ct["bridge"].values() for t in ts), sorted(TRAIN_FAMILIES))
            t, plan = choose([])
            self.assertIn(t.family, TRAIN_FAMILIES)   # never attempted, highest level first
            # all bridge families beaten -> back to WORLD families
            t2, _ = choose(_board(TRAIN_FAMILIES, treat=True, control=False))
            self.assertNotIn(t2.family, TRAIN_FAMILIES)
            # all_training (evolve benchmark, feed, judges) never changes
            self.assertFalse(any(x.family in TRAIN_FAMILIES for x in W.all_training()))
        with _Env(NOMAD_LIVE_BRIDGE="on", NOMAD_BRIDGE="off"):   # the opset itself off -> no bridge domain
            self.assertIs(W.curriculum_train(), W.TRAIN)

    def test_lookup_resolves_bridge_families(self) -> None:
        from nomad import world_tasks as W
        with _Env(NOMAD_LIVE_BRIDGE=None):
            self.assertEqual(W.by_family("br_rotate").opset, "bridge")
            self.assertEqual(W.domain_of("br_rotate"), "bridge")
            self.assertIsNone(W.by_family("no_such_family"))

    def test_world_pair_on_bridge_task(self) -> None:
        from nomad.bridge import TRAIN_FAMILIES
        from nomad.consolidate import consolidate
        from nomad.world_loop import load_world_prior, world_pair
        with tempfile.TemporaryDirectory(prefix="nomad-lb-") as d:
            for sub in ("weights", "continuous", "society"):
                (Path(d) / sub).mkdir(parents=True)
            with _Env(NOMAD_DATA=d, NOMAD_LIVE_BRIDGE="on"):
                out = world_pair()
                self.assertIn(out["family"], TRAIN_FAMILIES)
                self.assertEqual(out["domain"], "bridge")
                consolidate()
                if out["treatment"]["certified"]:   # the learner re-attests and records the bridge family
                    self.assertIn(out["family"], load_world_prior().families)


if __name__ == "__main__":
    unittest.main()
