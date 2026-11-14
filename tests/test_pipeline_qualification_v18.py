"""Real parser/learner integration and mocked Docker protocol tests.

These tests do not qualify native containment or isolated repair efficacy.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad.isolation import SandboxPolicy
from nomad.mission_runtime import InjectedInterruption, MissionHold, canonical, digest
from nomad.platform_bitwork import NativeDecisionRanker
from nomad.platform_mission import (initialize, inspect, recover, resolved_goal, run,
                                    read_memory_ranker, _execution_identity, _expression,
                                    _memory_models, _rows, _values)

IMAGE = 'nomad/test-contract@sha256:' + 'b' * 64
PUBLIC = [{'x': 4, 'y': 2, 'expected': 2}, {'x': 7, 'y': 3, 'expected': 4}]
CHALLENGE = [{'x': 81, 'y': 13, 'expected': 68}, {'x': -27, 'y': 14, 'expected': -41}]
FINAL = [{'x': 97, 'y': 31, 'expected': 66}, {'x': -53, 'y': 17, 'expected': -70}]


def create(base: Path, *, expression='x+y', epoch=0, memory=None, adaptive=True,
           mode='native', budget=4, final=None):
    base.mkdir(parents=True, exist_ok=True)
    source = base / 'source'
    source.mkdir()
    (source / 'arithmetic.py').write_bytes(f'def solve(x, y):\n    return {expression}\n'.encode())
    (source / 'facade.py').write_bytes(b'from arithmetic import solve\n')
    (source / 'irrelevant.py').write_bytes(b'def solve(x, y):\n    return x*y+9\n')
    (source / 'never_import.py').write_bytes(b'raise RuntimeError("UNTRUSTED_MODULE_MUST_NOT_EXECUTE_ON_HOST")\n')
    (source / 'tests').mkdir()
    (source / 'tests' / 'test_public.py').write_bytes(
        b'import unittest\nfrom facade import solve\nclass Tests(unittest.TestCase):\n'
        b'    def test_contract(self): self.assertEqual(solve(4,2),2)\n')
    root = base / 'mission'
    goal = initialize(root, source, goal_text='Restore public subtraction API', public=PUBLIC,
        challenge=CHALLENGE, final=final or FINAL, policy=SandboxPolicy(IMAGE), memory_root=memory,
        capture_epoch=epoch, adaptive_enabled=adaptive,
        ranker=NativeDecisionRanker(mode, action_schema='genesis-vs-ast'), max_executions=budget)
    return root, source, goal


def modeled_docker(source, *, command, policy, container_name):
    """A receipt double with actual parser-derived outcomes, never real Docker."""
    goal = resolved_goal(source.parent)
    current = (source / goal['target']).read_bytes()
    baseline = digest(current) == goal['baseline'][goal['target']]
    passed = _values(_expression(current.decode()), _rows(goal['public'])) == tuple(float(r['expected']) for r in goal['public'])
    assert not (source / 'sealed.json').exists()
    assert not (source / 'planning_memory.json').exists()
    assert not (source / 'events.jsonl').exists()
    return {**_execution_identity(goal, container_name, baseline=baseline),
        'schema': 'nomad.isolated-test.v1', 'tests_passed': passed, 'returncode': 0 if passed else 1,
        'timed_out': False, 'container_cleanup_confirmed': True,
        'output_sha256': digest(canonical({'passed': passed, 'source': digest(current)}))}


class PipelineQualificationTests(unittest.TestCase):
    def test_real_components_are_used_without_host_repository_execution(self):
        with tempfile.TemporaryDirectory() as td, ExitStack() as guards:
            for name in ('nomad.resonance.execute_python', 'nomad.repo_world.run_repo',
                         'nomad.inquiry.run_probe', 'nomad.causal_atlas.run_contract'):
                guards.enter_context(patch(name, side_effect=AssertionError('host repository execution forbidden')))
            root, source, goal = create(Path(td))
            self.assertEqual(goal['target'], 'arithmetic.py')
            self.assertEqual(goal['analysis']['entry_module'], 'facade')
            self.assertEqual(goal['analysis']['graph']['facade.py'], ['arithmetic.py'])
            self.assertIsNone(goal['candidate'])
            self.assertNotIn('GENESIS.synthesize', goal['analysis']['component_calls'])
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                outcome = run(root)
            self.assertEqual(outcome['status'], 'completed')
            self.assertEqual(outcome['baseline_probes_recorded'], 1)
            self.assertEqual(outcome['public_executions_recorded'], 1)
            self.assertEqual(outcome['pipeline']['GENESIS.synthesize'], 1)
            self.assertGreater(outcome['pipeline']['resonance.encode_resonance'], 0)
            events = [json.loads(line) for line in (root / 'events.jsonl').read_bytes().splitlines()]
            kinds = [row['kind'] for row in events]
            self.assertLess(kinds.index('PROBE_RESULT'), kinds.index('PROPOSAL_SELECTED'))
            self.assertEqual((source / 'arithmetic.py').read_bytes(), b'def solve(x, y):\n    return x+y\n')

    def test_distinct_verified_tasks_train_existing_memory_and_next_decision(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            memory = base / 'shared-memory'
            for i, expression in enumerate(('x+y', 'x*y', 'x+y+1'), 1):
                root, _, _ = create(base / str(i), expression=expression, epoch=i, memory=memory)
                with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                    self.assertEqual(run(root)['status'], 'completed')
            root, _, goal = create(base / 'next', expression='x+y+2', epoch=4, memory=memory)
            self.assertEqual(goal['analysis']['world_observations'], 3)
            self.assertEqual(goal['analysis']['eligible_memory_tasks'], 3)
            self.assertEqual(goal['analysis']['inquiry']['model']['training_tasks'], 3)
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                run(root)
            planning = resolved_goal(root)['planning']
            self.assertEqual(planning['ranking']['independent_tasks'], 3)
            self.assertTrue(any(p['outcome'] == 'impact' and p['support_tasks'] == 3
                                for p in planning['mnemonic_recall'].values()))
            records = _memory_models(memory, now_epoch=4)['records']
            self.assertEqual(len(records), 4)
            self.assertEqual(len(read_memory_ranker(memory, now_epoch=4).events), 4)

    def test_replayed_task_does_not_refresh_ttl_or_increase_independence(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            memory = base / 'memory'
            root, _, _ = create(base / 'first', memory=memory, epoch=1)
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                run(root)
            old = (memory / 'events.jsonl').read_bytes()
            replay, _, _ = create(base / 'copy', memory=memory, epoch=2)
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                run(replay)
            self.assertEqual((memory / 'events.jsonl').read_bytes(), old)
            self.assertEqual(len(_memory_models(memory, now_epoch=2)['records']), 1)
            self.assertEqual(_memory_models(memory, now_epoch=8)['eligible_tasks'], 0)
            self.assertEqual(read_memory_ranker(memory, now_epoch=8).summary(now_epoch=8)['eligible_observations'], 0)

    def test_discretionary_probe_can_abstain_without_fabricating_information(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, goal = create(Path(td))
            self.assertIsNone(goal['analysis']['inquiry']['decision'])
            self.assertIn('no informative', goal['analysis']['inquiry']['reason'])
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                run(root, interrupt_at=None)
            probe = next(json.loads(line) for line in (root / 'events.jsonl').read_bytes().splitlines()
                         if json.loads(line)['kind'] == 'PROBE_RESULT')
            self.assertEqual(probe['data']['posterior'], goal['analysis']['world_prior'])

    def test_new_interruption_boundaries_resume_without_duplicate_learning(self):
        for stop in ('after_probe', 'after_proposal', 'before_memory', 'after_memory', 'after_learning'):
            with self.subTest(stop=stop), tempfile.TemporaryDirectory() as td:
                root, _, _ = create(Path(td))
                with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker) as execute:
                    with self.assertRaises(InjectedInterruption):
                        run(root, interrupt_at=stop)
                    self.assertEqual(run(root)['status'], 'completed')
                    self.assertEqual(execute.call_count, 2)
                self.assertEqual(len(_memory_models(root / 'mnemonic', now_epoch=0)['records']), 1)

    def test_baseline_unknown_dispatch_recovers_only_after_authoritative_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create(Path(td))
            with self.assertRaises(InjectedInterruption):
                run(root, interrupt_at='after_probe_dispatch')
            with self.assertRaises(MissionHold):
                run(root)
            with patch('nomad.isolation.cleanup_isolated', return_value=True):
                recover(root)
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker) as execute:
                result = run(root)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['dispatches'], 3)
                self.assertEqual(execute.call_count, 2)

    def test_recovery_cannot_exceed_persisted_execution_budget(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create(Path(td), budget=2)
            for _ in range(2):
                with self.assertRaises(InjectedInterruption):
                    run(root, interrupt_at='after_probe_dispatch')
                with patch('nomad.isolation.cleanup_isolated', return_value=True):
                    recover(root)
            with patch('nomad.platform_mission.run_isolated') as execute:
                with self.assertRaises(MissionHold):
                    run(root)
                execute.assert_not_called()

    def test_frozen_private_rows_are_not_in_shared_memory(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create(Path(td))
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                run(root)
            def visit(value):
                if isinstance(value, dict):
                    if 'x' in value:
                        self.assertNotIn(value['x'], {r['x'] for r in CHALLENGE + FINAL})
                    for child in value.values(): visit(child)
                elif isinstance(value, list):
                    for child in value: visit(child)
            for line in (root / 'mnemonic' / 'events.jsonl').read_bytes().splitlines():
                visit(json.loads(line))

    def test_incomplete_public_success_with_private_failure_never_admits_memory(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            memory = base / 'shared'
            root, _, _ = create(base / 'case', memory=memory,
                                 final=[{'x': 97, 'y': 31, 'expected': 999}])
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                self.assertEqual(run(root)['status'], 'rejected')
            self.assertFalse(memory.exists())

    def test_deleted_pinned_history_cannot_be_silently_recreated(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            memory = base / 'shared'
            first, _, _ = create(base / 'one', memory=memory, epoch=1)
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                run(first)
            second, _, _ = create(base / 'two', memory=memory, epoch=2, expression='x*y')
            (memory / 'events.jsonl').unlink()
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                with self.assertRaises(MissionHold):
                    run(second)
            self.assertFalse((memory / 'events.jsonl').exists())

    def test_lost_memory_after_learning_write_prevents_false_completed_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create(Path(td))
            with patch('nomad.platform_mission.run_isolated', side_effect=modeled_docker):
                with self.assertRaises(InjectedInterruption):
                    run(root, interrupt_at='after_learning')
            (root / 'mnemonic' / 'events.jsonl').unlink()
            with self.assertRaises(MissionHold):
                run(root)
            self.assertNotIn(b'"kind":"LEARNED"', (root / 'events.jsonl').read_bytes())

    def test_public_probe_receipt_cannot_be_swapped_between_missions(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create(Path(td))
            def foreign(*args, **kwargs):
                return {**modeled_docker(*args, **kwargs), 'snapshot_sha256': 'f' * 64}
            with patch('nomad.platform_mission.run_isolated', side_effect=foreign):
                with self.assertRaises(MissionHold):
                    run(root)
            self.assertIsNone(resolved_goal(root)['candidate'])
            self.assertNotIn(b'PROPOSAL_SELECTED', (root / 'events.jsonl').read_bytes())


if __name__ == '__main__':
    unittest.main()
