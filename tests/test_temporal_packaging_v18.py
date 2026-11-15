"""Temporal helpers are packaged without replacing earlier immutable seals."""
import ast
from pathlib import Path
import tempfile
import unittest
from scripts import release_files_v18 as release

ROOT=Path(__file__).resolve().parents[1]
HELPERS={'experiment_temporal_v18.py','audit_temporal_metrics_v18.py',
    'verify_temporal_replay_v18.py','summarize_temporal_v18.py','diagnose_temporal_v18.py',
    'account_temporal_cost_v18.py','study_retention_temporal_v18.py',
    'prepare_temporal_self_revision_v18.py','refresh_temporal_prerequisites_v18.py',
    'experiment_repository_temporal_v18.py'}


class TemporalPackagingTests(unittest.TestCase):
    def test_runtime_keeps_helpers_native_test_dependencies_and_old_seal(self):
        self.assertEqual(release.MANIFEST,'results/RELEASE_MANIFEST_TEMPORAL_V018.json')
        self.assertEqual(release.GATES,'results/GATES_TEMPORAL_V018.json')
        self.assertLessEqual(HELPERS,release.RUNTIME_SCRIPTS)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            names={*(f'scripts/{name}' for name in HELPERS),*release.RUNTIME_TESTS,
                release.MANIFEST,release.GATES,'results/RELEASE_MANIFEST_ADAPTIVE_V018.json',
                'tests/not_a_runtime_dependency.py','scripts/not_a_runtime_helper.py'}
            for name in names:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
            selected={name for name,_ in release.files(root,'runtime')}
            self.assertLessEqual({f'scripts/{name}' for name in HELPERS}|release.RUNTIME_TESTS,selected)
            self.assertIn('results/RELEASE_MANIFEST_ADAPTIVE_V018.json',selected)
            self.assertIn(release.GATES,selected);self.assertNotIn(release.MANIFEST,selected)
            self.assertNotIn('scripts/not_a_runtime_helper.py',selected)
            self.assertNotIn('tests/not_a_runtime_dependency.py',selected)

    def test_runtime_script_import_dependencies_are_included(self):
        for name in release.RUNTIME_SCRIPTS:
            path=ROOT/'scripts'/name
            self.assertTrue(path.is_file(),name)
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                if isinstance(node,ast.ImportFrom) and (node.module or '').split('.')[0]=='scripts':
                    modules=[node.module.partition('.')[2]] if node.module!='scripts' else [a.name for a in node.names]
                    for module in modules:self.assertIn(module.split('.')[0]+'.py',release.RUNTIME_SCRIPTS,name)
                if isinstance(node,ast.ImportFrom) and (node.module or '').split('.')[0]=='tests':
                    modules=[node.module.partition('.')[2]] if node.module!='tests' else [a.name for a in node.names]
                    for module in modules:self.assertIn('tests/'+module.split('.')[0]+'.py',release.RUNTIME_TESTS,name)


if __name__=='__main__':unittest.main()
