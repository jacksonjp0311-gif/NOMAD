"""Original evidence checks; no regeneration of historic studies."""
from pathlib import Path
import io
import stat
import tempfile
import unittest
import zipfile
from scripts.verify_lineage_v18 import ROOT, members, verify


class LineageTests(unittest.TestCase):
    def test_available_originals_verify_and_missing_full_archive_holds(self):
        result = verify()
        self.assertEqual(result['compact_v17']['status'], 'PASS')
        self.assertEqual(result['historical_evidence']['status'], 'PASS')
        self.assertEqual(result['engineering_5851566_evidence']['status'], 'PASS')
        self.assertFalse(result['historical_results_regenerated'])
        if not (ROOT / 'baseline/NOMAD-v0.16.0.zip').exists():
            self.assertEqual(result['gate_D'], 'HOLD')
            self.assertEqual(result['missing'][0]['path'], 'baseline/NOMAD-v0.16.0.zip')

    def test_substitute_archive_cannot_satisfy_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'fake.zip'
            fake.write_bytes(b'newly generated substitute')
            with self.assertRaisesRegex(ValueError, 'original compact'):
                verify(compact=fake)
            with self.assertRaisesRegex(ValueError, 'predecessor digest'):
                verify(predecessor=fake)

    def test_manifest_member_bytes_do_not_excuse_unsafe_archive_entries(self):
        cases = [('../../outside/', stat.S_IFDIR),
                 ('NOMAD-v0.17.0/source.py', stat.S_IFLNK),
                 ('NOMAD-v0.17.0/../outside/', stat.S_IFDIR),
                 ('NOMAD-v0.17.0/CON.txt', stat.S_IFREG),
                 ('NOMAD-v0.17.0/dir\\file.py', stat.S_IFREG)]
        for name, mode in cases:
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w') as archive:
                info = zipfile.ZipInfo(name)
                # ZipInfo's Windows constructor normalizes backslashes; the
                # fixture must model raw hostile ZIP member bytes explicitly.
                info.filename = name
                info.external_attr = (mode | 0o644) << 16
                archive.writestr(info, b'')
            data.seek(0)
            with self.subTest(name=name), zipfile.ZipFile(data) as archive:
                with self.assertRaises(ValueError):
                    members(archive, 'NOMAD-v0.17.0/')


if __name__ == '__main__':
    unittest.main()
