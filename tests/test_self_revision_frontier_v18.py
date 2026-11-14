"""Proposal-audit contracts with explicit receipt doubles; no native self-repair claim."""
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from nomad.platform_mission import _manifest
from nomad.recursion import (SELF_REGRESSION_COMMAND, _revision_identity,
                            review_isolated_revision)
from nomad.isolation import SandboxPolicy
from dataclasses import asdict


class SelfRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.source, self.root = base/'source', base/'mission'
        (self.source/'nomad').mkdir(parents=True)
        (self.source/'tests').mkdir()
        (self.source/'nomad/proposal.py').write_bytes(b'def score(x,y): return x-y\n')
        (self.source/'tests/test_original.py').write_bytes(b'# unchanged regression fixture\n')
        self.root.mkdir()
        shutil.copytree(self.source, self.root/'baseline')
        shutil.copytree(self.source, self.root/'workspace')
        (self.root/'workspace/nomad/proposal.py').write_bytes(b'def score(x,y): return x+y\n')
        self.image = 'nomad/fixture@sha256:'+'1'*64
        self.goal = {'mission_id': 'test-only', 'baseline': _manifest(self.source),
                     'policy': asdict(SandboxPolicy(self.image))}
        self.summary = {'status': 'completed', 'witness_observations': 1,
                        'final_observations': 1, 'journal_head': 'e'*64}
        def receipt(root, name):
            return {**_revision_identity(root, _manifest(root)), 'schema': 'nomad.isolated-test.v1',
                'command': list(SELF_REGRESSION_COMMAND), 'image_digest': '1'*64,
                'returncode': 0, 'timed_out': False, 'tests_passed': True,
                'container_cleanup_confirmed': True, 'output_truncated': False,
                'output_sha256': 'a'*64, 'container_name': name, 'preflight': {'ready': True}}
        self.baseline_receipt = receipt(self.root/'baseline', 'nomad-'+'a'*24)
        self.candidate_receipt = receipt(self.root/'workspace', 'nomad-'+'b'*24)

    def review(self, **overrides):
        arguments = dict(allowed_paths=['nomad/proposal.py'], baseline_regression=self.baseline_receipt,
                         candidate_regression=self.candidate_receipt)
        arguments.update(overrides)
        with patch('nomad.platform_mission.resolved_goal', return_value=self.goal), \
             patch('nomad.platform_mission.inspect', return_value=self.summary):
            return review_isolated_revision(self.root, self.source, **arguments)

    def test_review_is_repeatable_and_never_replaces_authoritative_source(self):
        before = _manifest(self.source)
        first, second = self.review(), self.review()
        self.assertEqual(first, second)
        self.assertEqual(first['status'], 'ELIGIBLE_FOR_INDEPENDENT_REVIEW')
        self.assertEqual(first['production_promotion'], 'HOLD')
        self.assertFalse(first['authoritative_source_replaced'])
        self.assertEqual(_manifest(self.source), before)

    def test_missing_independent_final_cannot_review(self):
        self.summary['final_observations'] = 0
        with self.assertRaisesRegex(ValueError, 'completed mission'): self.review()

    def test_authoritative_drift_is_not_overwritten(self):
        path = self.source/'nomad/proposal.py'
        path.write_text('new owner change')
        with self.assertRaisesRegex(ValueError, 'authoritative source'): self.review()
        self.assertEqual(path.read_text(), 'new owner change')

    def test_candidate_cannot_rewrite_regression_tests(self):
        (self.root/'workspace/tests/test_original.py').write_text('remove assertions')
        with self.assertRaisesRegex(ValueError, 'protected'): self.review()

    def test_verifier_and_version_modules_are_not_allowed_revision_targets(self):
        for name in ('nomad/witness.py', 'nomad/isolation.py', 'nomad/recursion.py',
                     'nomad/__init__.py', 'tests/test_original.py'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'non-verifier'):
                self.review(allowed_paths=[name])

    def test_public_subset_or_stale_or_unclean_receipt_cannot_admit_revision(self):
        for key, value in [('command', ['python','public_only.py']), ('snapshot_sha256','b'*64),
                           ('container_cleanup_confirmed',False), ('tests_passed',False),
                           ('output_truncated',True), ('returncode',True), ('container_name','nomad-forged')]:
            receipt = {**self.candidate_receipt, key: value}
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, 'regression receipt'):
                self.review(candidate_regression=receipt)

    def test_baseline_receipt_cannot_be_relabelled_as_candidate(self):
        with self.assertRaisesRegex(ValueError, 'regression receipt'):
            self.review(candidate_regression=deepcopy(self.baseline_receipt))


if __name__ == '__main__': unittest.main()
