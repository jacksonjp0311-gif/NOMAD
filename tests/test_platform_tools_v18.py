"""Platform configuration and packaging security contracts."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nomad.platform import load_policy
from nomad.platform_cli import main
from scripts.build_release_v18 import build
from scripts.release_files_v18 import files, sha
from scripts.verify_package_v18 import verify


class PlatformToolsTests(unittest.TestCase):
    def test_missing_image_cannot_run_repository(self):
        with patch('nomad.isolation.run_isolated') as execute, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['isolated-demo', '--root', 'uncreated-demo']), 3)
        execute.assert_not_called()

    def test_config_denies_unknown_authority_and_unpinned_images(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            for data in (
                {'schema': 'nomad.platform.config.v1', 'image': 'python:latest'},
                {'schema': 'nomad.platform.config.v1', 'image': None, 'host_fallback': True},
                {'schema': 'nomad.platform.config.v1', 'image': None, 'timeout_s': 30},
            ):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    load_policy(path)

    def test_release_boundaries_exclude_local_state_but_keep_workflows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('.git/config', '.venv/token', 'runs/private', 'work/scratch',
                         'outputs/old.zip', 'nomad/code.py', '.github/workflows/ci.yml',
                         'platform.local.json', 'nomad/__pycache__/compiled.pyc'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            self.assertEqual([name for name, _ in files(root)],
                             ['.github/workflows/ci.yml', 'nomad/code.py'])

    def test_packages_reproduce_and_tampered_file_is_rejected(self):
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'input'
            root.mkdir()
            for name, content in [('nomad/code.py', 'x=1\n'),
                                  ('vendor/BGR-v1.4.0-runtime.zip', 'fixture'),
                                  ('results/GATES_V018.json', '{"publication":"HOLD"}')]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            first, second = Path(directory) / 'a.zip', Path(directory) / 'b.zip'
            with patch('scripts.build_release_v18.ROOT', root):
                build(first, 'source')
                build(second, 'source')
            self.assertEqual(sha(first), sha(second))
            with zipfile.ZipFile(first) as archive:
                archive.extractall(Path(directory) / 'unpack')
            extracted = Path(directory) / 'unpack/NOMAD-v0.18.0'
            with patch('scripts.verify_package_v18.BGR_SHA', sha(extracted / 'vendor/BGR-v1.4.0-runtime.zip')):
                self.assertEqual(verify(extracted)['source_integrity'], 'PASS')
                with self.assertRaisesRegex(ValueError, 'publication'):
                    verify(extracted, require_release=True)
                (extracted / 'nomad/code.py').write_text('changed')
                with self.assertRaisesRegex(ValueError, 'changed release bytes'):
                    verify(extracted)

    def test_packaging_refuses_secret_paths_and_included_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('synthetic secret')
            with self.assertRaisesRegex(ValueError, 'credential-like'):
                files(root)
            with patch('scripts.build_release_v18.ROOT', root):
                with self.assertRaisesRegex(ValueError, 'archive output'):
                    build(root / 'recursive.zip', 'source')


if __name__ == '__main__':
    unittest.main()
