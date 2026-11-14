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
from scripts.release_files_v18 import GATES, files, sha
from scripts.verify_package_v18 import verify, verify_qualification_evidence


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
                                  (GATES, '{"publication":"HOLD"}')]:
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

    def test_windows_case_aliases_do_not_export_local_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('.GIT/config', 'Work/scratch', 'Runs/private',
                         'PLATFORM.LOCAL.JSON', 'nomad/__PYCACHE__/cache.PYC', 'nomad/code.py'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            self.assertEqual([name for name, _ in files(root)], ['nomad/code.py'])

    def test_packaging_refuses_secret_paths_and_included_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('synthetic secret')
            with self.assertRaisesRegex(ValueError, 'credential-like'):
                files(root)
            with patch('scripts.build_release_v18.ROOT', root):
                with self.assertRaisesRegex(ValueError, 'archive output'):
                    build(root / 'recursive.zip', 'source')

    def test_release_cannot_advance_with_any_platform_gate_unresolved(self):
        from scripts.release_files_v18 import MANIFEST
        from scripts.build_release_v18 import canonical, manifest
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'vendor').mkdir()
            (root / 'results').mkdir()
            archive = root / 'vendor/BGR-v1.4.0-runtime.zip'
            archive.write_bytes(b'fixture')
            for unresolved in ('gate_A', 'gate_B', 'gate_C', 'gate_D'):
                gates = {key: 'PASS' for key in ('publication', 'native_containment',
                         'isolated_mission_recovery', 'gate_A', 'gate_B', 'gate_C', 'gate_D')}
                gates[unresolved] = 'HOLD'
                (root / GATES).write_text(json.dumps(gates))
                with patch('scripts.build_release_v18.ROOT', root):
                    (root / MANIFEST).write_bytes(canonical(manifest('source')))
                with patch('scripts.verify_package_v18.BGR_SHA', sha(archive)), \
                     patch('scripts.verify_package_v18.verify_lineage', return_value={'gate_D': 'PASS'}):
                    with self.subTest(gate=unresolved), self.assertRaisesRegex(ValueError, 'publication gate HOLD'):
                        verify(root, require_release=True)

    def test_summary_pass_cannot_override_native_hold_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'results/native.json'
            path.parent.mkdir()
            path.write_text(json.dumps({'schema': 'nomad.native-isolation-qualification.v18',
                                        'native_containment_gate': 'HOLD', 'status': 'HOLD'}))
            name, checksum = 'results/native.json', sha(path)
            gates = {'gate_A': 'PASS', 'publication': 'PASS',
                     'qualification_evidence': {'gate_A': {'path': name, 'sha256': checksum}}}
            with self.assertRaisesRegex(ValueError, 'unresolved receipt for gate_A'):
                verify_qualification_evidence(root, gates, {name: checksum})
            path.write_text(json.dumps({'schema': 'nomad.native-isolation-qualification.v18',
                                        'native_containment_gate': 'PASS', 'status': 'PASS', 'cases': []}))
            checksum = sha(path)
            gates['qualification_evidence']['gate_A']['sha256'] = checksum
            with self.assertRaisesRegex(ValueError, 'native receipt is incomplete or stale'):
                verify_qualification_evidence(root, gates, {name: checksum})
            path.write_text('{}')
            with self.assertRaises(ValueError):
                verify_qualification_evidence(root, gates, {name: sha(path)})


if __name__ == '__main__':
    unittest.main()
