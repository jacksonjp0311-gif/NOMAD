"""NOMAD_LIVE_WORDS: MEANING word problems in the live body curriculum (default off); docs/LIVE_WORDS.md."""
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


class LiveWordsTests(unittest.TestCase):
    def test_off_is_unchanged(self) -> None:
        from nomad import world_tasks as W
        with _Env(NOMAD_LIVE_WORDS=None, NOMAD_LIVE_BRIDGE=None):
            self.assertFalse(W.live_words_enabled())
            self.assertIs(W.curriculum_train(), W.TRAIN)
        with _Env(NOMAD_LIVE_WORDS="on", NOMAD_MEANING="off", NOMAD_LIVE_BRIDGE=None):
            self.assertIs(W.curriculum_train(), W.TRAIN)   # MEANING off -> no word domain
        with _Env(NOMAD_LIVE_WORDS=None, NOMAD_LIVE_BRIDGE="on"):
            self.assertNotIn("words", W.curriculum_train())

    def test_on_adds_word_domain_at_level_one(self) -> None:
        from nomad import meaning_tasks as MT
        from nomad import world_tasks as W
        from nomad.curriculum import choose
        fams = [f.family for f in MT.TRAIN]
        with _Env(NOMAD_LIVE_WORDS="on", NOMAD_MEANING=None, NOMAD_LIVE_BRIDGE=None):
            ct = W.curriculum_train()
            self.assertEqual(set(ct) - set(W.TRAIN), {"words"})
            self.assertEqual(len(ct["words"][1]), W.WORDS_WINDOW)
            self.assertTrue(all(t.level == 1 for t in ct["words"][1]))
            seen = set()
            for v in range(0, 4 * W.WORDS_ROTATE, W.WORDS_ROTATE):   # the windows cover every family
                seen |= {t.family for t in W.words_window(v)}
            self.assertEqual(seen, set(fams))
            self.assertEqual(sorted(t.family for t in W.words_training()), sorted(fams))
            t, _ = choose(_board(fams, treat=True))   # all word families beaten -> back to WORLD
            self.assertNotIn(t.family, fams)
            self.assertFalse(any(x.family in fams for x in W.all_training()))
        self.assertEqual(W.domain_of("wt_tile_floor"), "words")
        self.assertIsNotNone(W.by_family("wt_tile_floor"))
        self.assertIn("rows", W.words_of("wt_tile_floor"))
        self.assertIsNone(W.words_of("br_rotate"))

    def test_body_learns_lexicon_from_live_word_receipts(self) -> None:
        from nomad.consolidate import consolidate
        from nomad.world_loop import load_world_prior, world_pair
        with tempfile.TemporaryDirectory(prefix="nomad-lw-") as d:
            for sub in ("weights", "continuous", "society"):
                (Path(d) / sub).mkdir(parents=True)
            with _Env(NOMAD_DATA=d, NOMAD_LIVE_WORDS="on", NOMAD_LIVE_BRIDGE="off", NOMAD_MEANING=None):
                certified = 0
                for _ in range(6):
                    out = world_pair(domain="words")
                    self.assertEqual(out["domain"], "words")
                    certified += bool(out["treatment"]["certified"])
                    consolidate()
                if certified:
                    self.assertTrue(load_world_prior().lexicon)


if __name__ == "__main__":
    unittest.main()
