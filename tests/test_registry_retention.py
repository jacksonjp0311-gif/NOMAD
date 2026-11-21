import json
import os
import tempfile
import unittest
from unittest import mock


class RegistryRetentionTest(unittest.TestCase):
    def test_inbox_is_bounded_and_trim_caps_old_registries(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"NOMAD_DATA_ROOT": d}):
                from nomad import society, retention
                with mock.patch.object(society, "data_root", lambda: __import__("pathlib").Path(d)),                         mock.patch.object(retention, "data_root", lambda: __import__("pathlib").Path(d)):
                    for i in range(society.INBOX_KEEP + 25):
                        society.post("keeper", {"i": i})
                    reg = society.load_registry()
                    self.assertEqual(len(reg["keeper"].inbox), society.INBOX_KEEP)
                    self.assertEqual(reg["keeper"].inbox[-1]["message"]["i"], society.INBOX_KEEP + 24)
                    # an oversized legacy registry is capped by retention.trim()
                    reg["spark"].inbox = [{"m": j} for j in range(1000)]
                    society.save_registry(reg)
                    dropped = retention.trim()
                    self.assertEqual(dropped.get("society/registry.json:inbox"), 800)
                    self.assertEqual(len(society.load_registry()["spark"].inbox), society.INBOX_KEEP)
                    ledger = json.loads((__import__("pathlib").Path(d) / "retention.json").read_text())
                    self.assertEqual(ledger["society/registry.json:inbox"], 800)


if __name__ == "__main__":
    unittest.main()
