"""Mission control tests; mocked Docker results never qualify native isolation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from nomad.isolation import IsolationUnavailable, SandboxPolicy
from nomad.mission_runtime import InjectedInterruption, MissionHold
from nomad.platform_mission import initialize, inspect, run, recover

IMAGE = 'nomad/reviewed@sha256:' + 'a' * 64
SOURCE = 'def solve(x, y):\n    return x + y\n'
PUBLIC = [{'x': 4, 'y': 2, 'expected': 2}, {'x': 7, 'y': 3, 'expected': 4}]
CHALLENGE = [{'x': 8, 'y': 3, 'expected': 5}, {'x': 2, 'y': 5, 'expected': -3}]
FINAL = [{'x': -5, 'y': 3, 'expected': -8}, {'x': 9, 'y': -1, 'expected': 10}]


def fixture(base, *, source=SOURCE, public=None, challenge=None, final=None, ranker=None):
    base = Path(base)
    repo = base / 'repo'
    repo.mkdir()
    (repo / 'solution.py').write_bytes(source.encode())
    (repo / 'tests').mkdir()
    (repo / 'tests' / 'test_public.py').write_bytes(
        b'import unittest\nfrom solution import solve\nclass TestRepair(unittest.TestCase):\n'
        b'    def test_subtract(self): self.assertEqual(solve(4, 2), 2)\n')
    root = base / 'mission'
    initialize(root, repo, goal_text='Correct subtraction behavior',
               public=public or PUBLIC, challenge=challenge or CHALLENGE,
               final=final or FINAL, policy=SandboxPolicy(IMAGE), ranker=ranker)
    return root, repo


def passing_execution(source, *, command, policy, container_name):
    # This fake checks the payload boundary only. It does not execute repo code.
    assert (source / 'solution.py').is_file()
    assert not (source / 'sealed.json').exists()
    assert not (source / 'effects').exists()
    assert container_name.startswith('nomad-')
    from nomad.platform_mission import _execution_identity
    goal = json.loads((source.parent / 'goal.json').read_bytes())
    return {**_execution_identity(goal, container_name),
            'schema': 'nomad.isolated-test.v1', 'tests_passed': True,
            'container_cleanup_confirmed': True, 'returncode': 0, 'timed_out': False,
            'output_sha256': '0' * 64}


class PlatformMissionTests(unittest.TestCase):
    def test_genesis_proposal_and_scoped_learning_preserve_original(self):
        with tempfile.TemporaryDirectory() as td:
            root, repo = fixture(td)
            goal = json.loads((root / 'goal.json').read_bytes())
            self.assertGreater(goal['planning']['genesis']['candidates_evaluated'], 0)
            self.assertNotIn('challenge', goal)
            self.assertNotIn('final', goal)
            with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution) as call:
                result = run(root)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(call.call_count, 1)
                before = (root / 'events.jsonl').read_bytes()
                self.assertEqual(run(root)['status'], 'completed')
                self.assertEqual(call.call_count, 1)
                self.assertEqual(before, (root / 'events.jsonl').read_bytes())
            self.assertEqual((repo / 'solution.py').read_bytes(), SOURCE.encode())
            learning = json.loads((root / 'learning.json').read_bytes())
            self.assertEqual(learning['independent_task_count'], 1)
            self.assertIn('no skill promotion', learning['authority'])

    def test_restarts_at_durable_boundaries_do_not_duplicate_observations(self):
        checkpoints = ('after_plan', 'after_patch_write', 'after_patch_record',
                       'after_public', 'after_witness', 'after_final', 'after_commit', 'after_learning')
        for checkpoint in checkpoints:
            with self.subTest(checkpoint=checkpoint), tempfile.TemporaryDirectory() as td:
                root, _ = fixture(td)
                with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution) as call:
                    with self.assertRaises(InjectedInterruption):
                        run(root, interrupt_at=checkpoint)
                    result = run(root)
                    self.assertEqual(result['status'], 'completed')
                    self.assertEqual(result['public_executions_recorded'], 1)
                    self.assertEqual(result['witness_observations'], 1)
                    self.assertEqual(result['final_observations'], 1)
                    self.assertEqual(call.call_count, 1)

    def test_unknown_dispatch_holds_until_cleanup_then_fresh_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root, _ = fixture(td)
            with self.assertRaises(InjectedInterruption):
                run(root, interrupt_at='after_dispatch')
            with patch('nomad.platform_mission.run_isolated') as execute:
                with self.assertRaises(MissionHold):
                    run(root)
                execute.assert_not_called()
            with patch('nomad.isolation.cleanup_isolated', return_value=False):
                with self.assertRaises(MissionHold):
                    recover(root)
            with patch('nomad.isolation.cleanup_isolated', return_value=True):
                self.assertEqual(recover(root)['status'], 'in_progress')
            with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution):
                result = run(root)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['dispatches'], 2)
                self.assertEqual(result['public_executions_recorded'], 1)

    def test_identical_missions_never_share_container_cleanup_identity(self):
        with tempfile.TemporaryDirectory() as td:
            names = []
            identities = []
            for label in ('first', 'second'):
                base = Path(td) / label
                base.mkdir()
                root, _ = fixture(base)
                identities.append(json.loads((root / 'goal.json').read_bytes())['mission_id'])
                with self.assertRaises(InjectedInterruption):
                    run(root, interrupt_at='after_dispatch')
                last = json.loads((root / 'events.jsonl').read_bytes().splitlines()[-1])
                names.append(last['data']['container_name'])
            self.assertEqual(identities[0], identities[1])
            self.assertNotEqual(names[0], names[1])

    def test_unavailable_isolation_has_no_host_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root, _ = fixture(td)
            with patch('nomad.platform_mission.run_isolated', side_effect=IsolationUnavailable('Docker unavailable')):
                with self.assertRaises(IsolationUnavailable):
                    run(root)
            self.assertEqual(inspect(root)['status'], 'hold_uncertain_execution')
            self.assertFalse((root / 'learning.json').exists())

    def test_public_test_success_cannot_override_private_contradiction(self):
        for label, replacement in [('challenge', [{'x': 99, 'y': 2, 'expected': 198}]),
                                   ('final', [{'x': 99, 'y': 2, 'expected': 198}])]:
            with self.subTest(partition=label), tempfile.TemporaryDirectory() as td:
                root, repo = fixture(td, **{label: replacement})
                with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution):
                    result = run(root)
                self.assertEqual(result['status'], 'rejected')
                self.assertEqual((root / 'workspace' / 'solution.py').read_bytes(), SOURCE.encode())
                self.assertEqual((repo / 'solution.py').read_bytes(), SOURCE.encode())
                self.assertFalse((root / 'learning.json').exists())

    def test_rollback_can_resume_after_write_or_record(self):
        for stop in ('after_rollback_write', 'after_rollback_record'):
            with self.subTest(stop=stop), tempfile.TemporaryDirectory() as td:
                root, _ = fixture(td, challenge=[{'x': 99, 'y': 2, 'expected': 198}])
                with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution) as call:
                    with self.assertRaises(InjectedInterruption):
                        run(root, interrupt_at=stop)
                    self.assertEqual(run(root)['status'], 'rejected')
                    self.assertEqual(call.call_count, 1)

    def test_tampered_private_evidence_journal_or_source_holds(self):
        for relative in ('sealed.json', 'events.jsonl', 'workspace/solution.py', 'baseline/solution.py'):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as td:
                root, _ = fixture(td)
                path = root / relative
                path.chmod(0o600)
                path.write_bytes(path.read_bytes() + b'corruption')
                with patch('nomad.platform_mission.run_isolated') as execute:
                    with self.assertRaises(MissionHold):
                        run(root)
                    execute.assert_not_called()

    def test_hardlinked_snapshot_and_source_root_reparse_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root, _ = fixture(td)
            workspace_file = root / 'workspace' / 'solution.py'
            linked = Path(td) / 'outside-linked.py'
            os.link(workspace_file, linked)
            with self.assertRaises(MissionHold):
                inspect(root)
        with tempfile.TemporaryDirectory() as td:
            with patch('nomad.platform_mission._reparse', return_value=True):
                from nomad.isolation import UnsafeWorkspace
                with self.assertRaises(UnsafeWorkspace):
                    fixture(td)

    def test_mixed_case_snapshot_identity_matches_actual_admission(self):
        from nomad.isolation import snapshot_source
        from nomad.platform_mission import _execution_identity
        with tempfile.TemporaryDirectory() as td:
            root, repo = fixture(td)
            # Reinitialize with mixed-case file ordering, which differs between
            # WindowsPath ordering and portable case-sensitive path ordering.
            (repo / 'Zebra.txt').write_bytes(b'z')
            (repo / 'apple.txt').write_bytes(b'a')
            second = Path(td) / 'mission-second'
            goal = initialize(second, repo, goal_text='Subtract', public=PUBLIC,
                              challenge=CHALLENGE, final=FINAL, policy=SandboxPolicy(IMAGE))
            with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution):
                run(second)
            snapshot = snapshot_source(second / 'workspace', Path(td) / 'snapshot', SandboxPolicy(IMAGE))
            self.assertEqual(snapshot.digest, _execution_identity(goal, 'nomad-' + '0' * 24)['snapshot_sha256'])

    def test_repeated_or_overlapping_evidence_is_rejected(self):
        for rows in (PUBLIC + PUBLIC, CHALLENGE + PUBLIC[:1]):
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError):
                    fixture(td, challenge=rows)

    def test_effect_ambiguity_and_missing_ledger_block_execution(self):
        from nomad.effects import EffectLedger
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as td:
                root, _ = fixture(td)
                if missing:
                    (root / 'effects' / 'effects.jsonl').unlink()
                else:
                    ledger = EffectLedger(root / 'effects', create=False)
                    with ledger.ownership() as owner:
                        ledger.prepare(owner, 'remote-once', 'non_idempotent_external', 'a' * 64)
                        ledger.dispatch(owner, 'remote-once')
                with patch('nomad.platform_mission.run_isolated') as execute:
                    with self.assertRaises(MissionHold):
                        run(root)
                    execute.assert_not_called()

    def test_unsupported_source_never_executes_during_inspection(self):
        sources = ('import os\ndef solve(x,y): return x-y\n',
                   '@evil()\ndef solve(x,y): return x-y\n',
                   'def solve(x,y=evil()): return x-y\n',
                   'def solve(x,y): return __import__("os").getcwd()\n')
        for source in sources:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as td:
                with self.assertRaises(MissionHold):
                    fixture(td, source=source)
                self.assertFalse((Path(td) / 'mission').exists())

    def test_ranker_only_sees_candidates_and_public_planning(self):
        class Ranker:
            called = False
            def rank(self, candidates, *, now_epoch):
                self.called = True
                return list(candidates)
            def summary(self, *, now_epoch):
                return {'mode': 'test', 'authority': 'ranking_only'}
        ranker = Ranker()
        with tempfile.TemporaryDirectory() as td:
            root, _ = fixture(td, ranker=ranker)
            self.assertTrue(ranker.called)
            self.assertEqual(json.loads((root / 'goal.json').read_bytes())['planning']['ranking']['authority'], 'ranking_only')

    def test_stale_verifier_identity_holds_before_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root, _ = fixture(td)
            with patch('nomad.platform_mission._runtime_identity', return_value={'stale': '0' * 64}), \
                    patch('nomad.platform_mission.run_isolated') as execute:
                with self.assertRaises(MissionHold):
                    run(root)
                execute.assert_not_called()

    def test_foreign_or_inconsistent_execution_receipts_cannot_authorize_witness(self):
        mutations = ({'container_name': 'nomad-' + 'b' * 24},
                     {'snapshot_sha256': 'f' * 64}, {'image_digest': 'f' * 64},
                     {'command': ['python', '-c', 'exit(0)']},
                     {'returncode': 1}, {'tests_passed': 1}, {'timed_out': True})
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as td:
                root, _ = fixture(td)
                def forged(*args, **kwargs):
                    return {**passing_execution(*args, **kwargs), **mutation}
                with patch('nomad.platform_mission.run_isolated', side_effect=forged):
                    with self.assertRaises(MissionHold):
                        run(root)
                self.assertEqual(inspect(root)['witness_observations'], 0)

    def test_semantically_invalid_receipts_rejected_even_with_rechained_journal(self):
        from nomad.mission_runtime import canonical, digest
        for stop, kind in (('after_public', 'PUBLIC_RESULT'), ('after_final', 'FINAL_RESULT')):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                root, _ = fixture(td)
                with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution):
                    with self.assertRaises(InjectedInterruption):
                        run(root, interrupt_at=stop)
                path = root / 'events.jsonl'
                records = [json.loads(line) for line in path.read_bytes().splitlines()]
                self.assertEqual(records[-1]['kind'], kind)
                if kind == 'PUBLIC_RESULT':
                    records[-1]['data']['execution']['container_name'] = 'nomad-' + 'f' * 24
                else:
                    records[-1]['data']['observed_sha256'] = '0' * 64
                records[-1].pop('sha256')
                records[-1]['sha256'] = digest(canonical(records[-1]))
                path.write_bytes(b''.join(canonical(row) + b'\n' for row in records))
                with self.assertRaises(MissionHold):
                    inspect(root)

    def test_native_process_cannot_take_live_mission_ownership(self):
        from nomad.mission_runtime import exclusive_owner
        from nomad.supervised import minimal_env
        with tempfile.TemporaryDirectory() as td:
            root, _ = fixture(td)
            package_root = Path(__file__).resolve().parents[1]
            code = ('from pathlib import Path; import sys; '
                    'from nomad.mission_runtime import exclusive_owner\n'
                    'with exclusive_owner(Path(sys.argv[1])): pass\n')
            with exclusive_owner(root):
                child = subprocess.run([sys.executable, '-B', '-c', code, str(root)],
                    cwd=package_root, env=minimal_env({'PYTHONPATH': str(package_root)}),
                    capture_output=True, timeout=10)
            self.assertNotEqual(child.returncode, 0)
            self.assertIn(b'already owned', child.stderr)

    def test_completed_source_or_learning_drift_invalidates_status(self):
        for relative in ('workspace/solution.py', 'learning.json'):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as td:
                root, _ = fixture(td)
                with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution):
                    run(root)
                path = root / relative
                path.write_bytes(path.read_bytes() + b'\n')
                with self.assertRaises(MissionHold):
                    inspect(root)

    def test_windows_fixture_materialization_binds_exact_source_bytes(self):
        from nomad.codeworld import make_codeworld_tasks
        from nomad.mission_runtime import initialize as legacy_initialize
        with tempfile.TemporaryDirectory() as td:
            task = make_codeworld_tasks(9117, per_family=1)[0]
            root = Path(td) / 'legacy'
            goal = legacy_initialize(root, task)
            from hashlib import sha256
            source = (root / 'workspace' / 'solution.py').read_bytes()
            self.assertEqual(source, task.source.encode())
            self.assertEqual(sha256(source).hexdigest(), goal['original_sha256'])


if __name__ == '__main__':
    unittest.main()
