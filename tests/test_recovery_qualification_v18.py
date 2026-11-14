"""Recovery qualifier failure contracts, with explicit doubles and no Docker.

These tests never qualify native containment, recovery, or repository repair.
"""
from contextlib import ExitStack, redirect_stderr
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from nomad.isolation import SandboxPolicy
from nomad.mission_runtime import MissionHold
from scripts import qualify_recovery_v18 as qualifier
from scripts import qualify_isolation_v18 as isolation_qualifier
from scripts.qualify_isolation_v18 import qualification_source_identity

IMAGE = 'nomad/contract-double@sha256:' + 'd' * 64


def receipt_double():
    """Metadata fixture only; never admitted to an actual Docker execution."""
    policy = asdict(SandboxPolicy(image=IMAGE, **qualifier.POLICY))
    source = qualification_source_identity()
    record = {'schema': 'nomad.native-isolation-qualification.v18',
              'backend': 'docker', 'status': 'PASS', 'native_containment_gate': 'PASS',
              'image': IMAGE, 'policy': policy,
              'policy_sha256': qualifier.canonical_digest(policy),
              'host_identity_sha256': qualifier.canonical_digest(qualifier.qualification_host_identity()),
              'source_stable': True, 'source_sha256_before': source,
              'source_sha256_after': source, 'protected_host_sentinel_unchanged': True,
              'cases': [{'case': name, 'status': 'PASS'} for name in
                        (*qualifier.CONTROLLED_CASES, 'supervisor_hard_death_cleanup')]}
    record['cases'][-1].update(observed_live_container_before_owner_death=True,
                               cleanup_confirmed_after_owner_death=True)
    return record


class RecoveryQualificationContractTests(unittest.TestCase):
    def test_missing_prerequisites_hold_before_docker_or_mission_creation(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(qualifier, 'docker_preflight', side_effect=AssertionError('Docker forbidden')), \
             patch.object(qualifier, 'initialize', side_effect=AssertionError('mission forbidden')):
            evidence = Path(directory) / 'never-created'
            result = qualifier.qualify(evidence_root=evidence)
            self.assertEqual(result['status'], 'HOLD')
            self.assertEqual(result['cases'], [])
            self.assertFalse(evidence.exists())
            self.assertEqual(result['receipt_sha256'], qualifier.canonical_digest(
                {key: value for key, value in result.items() if key != 'receipt_sha256'}))

    def test_hold_receipt_never_reaches_live_preflight(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(qualifier, 'docker_preflight', side_effect=AssertionError('Docker forbidden')), \
             patch.object(qualifier, 'initialize', side_effect=AssertionError('mission forbidden')):
            path = Path(directory) / 'hold.json'
            record = receipt_double()
            record['status'] = record['native_containment_gate'] = 'HOLD'
            record['receipt_sha256'] = qualifier.canonical_digest(record)
            path.write_text(json.dumps(record), encoding='utf-8')
            result = qualifier.qualify(IMAGE, path, Path(directory) / 'evidence')
            self.assertEqual(result['status'], 'HOLD')
            self.assertEqual(result['cases'], [])

    def test_malformed_receipt_shapes_return_hold_before_live_preflight(self):
        for bad in ([], {'cases': [None]}, {'cases': 'not-a-list'},
                    {'source_sha256_before': [], 'source_sha256_after': []}):
            with self.subTest(shape=bad), tempfile.TemporaryDirectory() as directory, \
                 patch.object(qualifier, 'docker_preflight', side_effect=AssertionError('Docker forbidden')):
                record = [] if isinstance(bad, list) else {**receipt_double(), **bad}
                if isinstance(record, dict):
                    record['receipt_sha256'] = qualifier.canonical_digest(record)
                path = Path(directory) / 'malformed.json'
                path.write_text(json.dumps(record), encoding='utf-8')
                result = qualifier.qualify(IMAGE, path, Path(directory) / 'evidence')
                self.assertEqual(result['status'], 'HOLD')
                self.assertEqual(result['cases'], [])

    def test_owner_observation_failure_still_kills_owner_and_recovers_dispatch(self):
        owner = Mock()
        owner.poll.return_value = None
        owner.returncode = 1
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(qualifier.subprocess, 'Popen', return_value=owner), \
             patch.object(qualifier, '_rows', return_value=[{'kind': 'PROBE_DISPATCHED',
                 'data': {'container_name': 'nomad-' + 'b' * 24}}]), \
             patch.object(qualifier, '_docker_prefix', return_value=['docker']), \
             patch.object(qualifier, 'run_supervised', side_effect=OSError('controlled observation failure')), \
             patch.object(qualifier, 'recover') as cleanup:
            root = Path(directory) / 'mission'
            with self.assertRaisesRegex(OSError, 'controlled observation failure'):
                qualifier._hard_death(root, Path(directory))
            owner.kill.assert_called_once()
            owner.wait.assert_called_once_with(timeout=5)
            cleanup.assert_called_once_with(root)

    def test_native_prerequisite_rejects_unobserved_or_unclean_owner_death(self):
        for field in ('observed_live_container_before_owner_death', 'cleanup_confirmed_after_owner_death'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory, \
                 patch.object(qualifier, 'docker_preflight', side_effect=AssertionError('Docker forbidden')):
                record = receipt_double()
                record['cases'][-1][field] = False
                record['receipt_sha256'] = qualifier.canonical_digest(record)
                path = Path(directory) / 'contradictory.json'
                path.write_text(json.dumps(record), encoding='utf-8')
                result = qualifier.qualify(IMAGE, path, Path(directory) / 'evidence')
                self.assertEqual(result['status'], 'HOLD')
                self.assertEqual(result['cases'], [])

    def test_containment_observation_failure_still_cleans_named_container(self):
        owner = Mock()
        owner.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(isolation_qualifier.subprocess, 'Popen', return_value=owner) as launch, \
             patch.object(isolation_qualifier, '_docker_prefix', return_value=['docker']), \
             patch.object(isolation_qualifier, 'run_supervised', side_effect=OSError('controlled observation failure')), \
             patch.object(isolation_qualifier, 'cleanup_isolated', return_value=True) as cleanup:
            with self.assertRaisesRegex(OSError, 'controlled observation failure'):
                isolation_qualifier._crash_cleanup_probe(Path(directory), SandboxPolicy(IMAGE), Path(directory))
            owner.kill.assert_called_once()
            owner.wait.assert_called_once_with(timeout=5)
            cleanup.assert_called_once()
            self.assertRegex(cleanup.call_args.args[0], r'^nomad-[a-f0-9]{24}$')
            self.assertEqual(json.loads(launch.call_args.args[0][4]), asdict(SandboxPolicy(IMAGE)))

    def test_failed_emergency_cleanup_remains_explicitly_unconfirmed(self):
        with patch.object(qualifier, '_hard_death_once', side_effect=OSError('probe failed')), \
             patch.object(qualifier, 'recover', side_effect=MissionHold('daemon unavailable')):
            with self.assertRaisesRegex(MissionHold, 'cleanup is unconfirmed'):
                qualifier._hard_death(Path('unused-mission'), Path('unused-base'))

    def test_containment_sentinel_loss_produces_fail_receipt(self):
        def delete_sentinel(source, **kwargs):
            (source.parent / 'protected-host-sentinel').unlink()
            return {'tests_passed': True}
        with patch.object(isolation_qualifier, 'docker_preflight', return_value={'ready': True}), \
             patch.object(isolation_qualifier, 'CONTROLLED_CASES', ('nonroot',)), \
             patch.object(isolation_qualifier, 'run_isolated', side_effect=delete_sentinel), \
             patch.object(isolation_qualifier, '_crash_cleanup_probe',
                          return_value={'case': 'supervisor_hard_death_cleanup', 'status': 'HOLD'}):
            result = isolation_qualifier.qualify(IMAGE)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['native_containment_gate'], 'FAIL')
        self.assertFalse(result['protected_host_sentinel_unchanged'])

    def test_source_instability_never_downgrades_an_observed_fail(self):
        report = {'source_sha256_before': {'fixture': 'before'}, 'status': 'FAIL',
                  'isolated_mission_recovery': 'FAIL', 'reason': 'protected sentinel changed'}
        with patch.object(qualifier, 'source_identity', return_value={'fixture': 'after'}):
            result = qualifier._seal(report)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['isolated_mission_recovery'], 'FAIL')
        self.assertFalse(result['source_stable'])
        self.assertIn('protected sentinel changed', result['reason'])

    def test_missed_rollback_interruption_cannot_count_as_passing_case(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as guards:
            guards.enter_context(patch.object(qualifier, '_validate_isolation_receipt', return_value='e' * 64))
            guards.enter_context(patch.object(qualifier, 'docker_preflight', return_value={'ready': True}))
            guards.enter_context(patch.object(qualifier, 'CHECKPOINTS', ('after_rollback_write', 'after_rollback_record')))
            guards.enter_context(patch.object(qualifier, 'run', return_value={'status': 'rejected'}))
            guards.enter_context(patch.object(qualifier, '_control', return_value={'passed': True}))
            guards.enter_context(patch.object(qualifier, '_hard_death', return_value={'controlled_double': True}))
            result = qualifier.qualify(IMAGE, Path('unused-contract-double'), Path(directory) / 'evidence')
            self.assertEqual(result['status'], 'HOLD')
            failure = next(case for case in result['cases'] if case['case'] == 'qualification_execution')
            self.assertIn('rollback interruption boundary was not reached', failure['reason'])
            self.assertFalse(any(case['case'] == 'after_rollback_write' and case['status'] == 'PASS'
                                 for case in result['cases']))

    def test_deleted_protected_sentinel_produces_fail_receipt(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as guards:
            evidence = Path(directory) / 'evidence'
            def delete_sentinel(*args, **kwargs):
                (evidence / 'protected-host-sentinel').unlink()
                raise MissionHold('controlled stop after sentinel deletion')
            guards.enter_context(patch.object(qualifier, '_validate_isolation_receipt', return_value='e' * 64))
            guards.enter_context(patch.object(qualifier, 'docker_preflight', return_value={'ready': True}))
            guards.enter_context(patch.object(qualifier, 'run', side_effect=delete_sentinel))
            result = qualifier.qualify(IMAGE, Path('unused-contract-double'), evidence)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(result['isolated_mission_recovery'], 'FAIL')
            self.assertFalse(result['protected_host_sentinel_unchanged'])

    def test_existing_output_is_preserved_without_attempting_qualification(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(qualifier, 'qualify') as execute, redirect_stderr(io.StringIO()):
            path = Path(directory) / 'preserved.json'
            path.write_bytes(b'original receipt')
            with self.assertRaises(SystemExit) as error:
                qualifier.main(['--output', str(path)])
            self.assertEqual(error.exception.code, 2)
            execute.assert_not_called()
            self.assertEqual(path.read_bytes(), b'original receipt')


if __name__ == '__main__':
    unittest.main()
