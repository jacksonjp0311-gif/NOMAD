"""Optional output transport contracts; mocks do not qualify native Docker."""
from contextlib import ExitStack
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad.isolation import IsolationUnavailable, SandboxPolicy, run_isolated
from nomad.supervised import ProcessResult

IMAGE = 'nomad/contract-double@sha256:' + 'c' * 64


class IsolatedOutputContracts(unittest.TestCase):
    def execute(self, output=b'{"observed":2}\n', include_output=True, **changes):
        observed = ProcessResult(0, output, sha256(output).hexdigest(), False, False,
                                 len(output), 1, 'windows-job-empty-confirmed')
        observed = replace(observed, **changes)
        with tempfile.TemporaryDirectory() as directory, ExitStack() as guards:
            source = Path(directory) / 'source'
            source.mkdir()
            (source / 'solution.py').write_bytes(b'def solve(x,y): return x-y\n')
            guards.enter_context(patch('nomad.isolation.sandbox_available', return_value=True))
            guards.enter_context(patch('nomad.isolation.docker_preflight', return_value={'ready': True}))
            guards.enter_context(patch('nomad.isolation.run_supervised', return_value=observed))
            cleanup = guards.enter_context(patch('nomad.isolation._cleanup_container', return_value=True))
            try:
                return run_isolated(source, command=['python', '-I', '-B', '-c', 'print(2)'],
                                    policy=SandboxPolicy(IMAGE), include_output=include_output)
            finally:
                cleanup.assert_called_once()

    def test_complete_utf8_is_bound_to_original_bytes(self):
        data = '{"observed":"caf\u00e9"}\n'.encode('utf-8')
        result = self.execute(data)
        self.assertEqual(result['output_utf8'].encode('utf-8'), data)
        self.assertEqual(sha256(result['output_utf8'].encode('utf-8')).hexdigest(), result['output_sha256'])
        self.assertEqual(result['command'], ['python', '-I', '-B', '-c', 'print(2)'])
        self.assertIn('independent WITNESS', result['authority'])

    def test_default_does_not_disclose_captured_output(self):
        self.assertNotIn('output_utf8', self.execute(include_output=False))

    def test_incomplete_or_inconsistent_output_holds_after_cleanup(self):
        for changes in ({'truncated': True}, {'total_output_bytes': 999},
                        {'output_sha256': '0' * 64}, {'cleanup': 'windows-job-cleanup-unconfirmed'}):
            with self.subTest(changes=changes), self.assertRaises(IsolationUnavailable):
                self.execute(**changes)

    def test_invalid_encoding_and_oversize_output_hold(self):
        for data in (b'\xff', b'x' * 8193):
            with self.subTest(bytes=len(data)), self.assertRaises(IsolationUnavailable):
                self.execute(data)

    def test_option_types_are_rejected_before_any_dispatch(self):
        with patch('nomad.isolation.sandbox_available') as readiness:
            for bad in (1, None, 'true'):
                with self.subTest(value=bad), self.assertRaises(ValueError):
                    run_isolated(Path('unused'), command=['python'], policy=SandboxPolicy(IMAGE), include_output=bad)
            readiness.assert_not_called()


if __name__ == '__main__':
    unittest.main()
