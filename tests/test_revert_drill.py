"""Self-revert drill as a test: guard -> git revert -> push, on a throwaway clone.

Runs scripts/revert_drill.py's two scenarios (regressed -> revert pushed,
healthy -> keep) against a temp clone whose origin is a temp bare repo. Live
main and the real remote are never touched.
"""
from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _drill():
    spec = importlib.util.spec_from_file_location("revert_drill", ROOT / "scripts" / "revert_drill.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(shutil.which("git") and (ROOT / ".git").exists(), "needs git and a checkout")
class RevertDrillTests(unittest.TestCase):
    def _run(self, regress: bool) -> dict:
        root = Path(tempfile.mkdtemp(prefix="nomad-revert-drill-test-"))
        try:
            return _drill().scenario(root, regress)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_regression_is_reverted_and_pushed(self) -> None:
        r = self._run(True)
        self.assertEqual(r["guard"].get("decision"), "revert", r)
        self.assertTrue(r["ok"], r["checks"])

    def test_healthy_change_is_kept(self) -> None:
        r = self._run(False)
        self.assertEqual(r["guard"].get("decision"), "keep", r)
        self.assertTrue(r["ok"], r["checks"])


if __name__ == "__main__":
    unittest.main()
