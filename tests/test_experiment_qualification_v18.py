"""Protocol unit fixtures are synthetic metadata, never an efficacy corpus."""
from __future__ import annotations

import copy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import experiment_qualification_v18 as experiment


IMAGE = 'nomad/reviewed@sha256:'+'a'*64


def corpus():
    tasks = []
    for index in range(26):
        split = 'training' if index < 2 else 'evaluation'
        group = str(index if index < 2 else (index-2)//3)
        repo = ('train-' if index < 2 else 'eval-')+group
        tasks.append({'id': 'task-'+str(index), 'split': split,
            'repository': 'https://github.com/unit-fixture/'+repo,
            'author_group': repo, 'revision': 'b'*40,
            'issue_url': 'https://github.com/unit-fixture/'+repo+'/issues/'+str(index+1),
            'provenance_kind': 'authentic_upstream_issue',
            'source': 'sources/task-'+str(index), 'source_sha256': experiment.digest(['source', index]),
            'public_spec': 'public/task-'+str(index)+'.json', 'public_spec_sha256': experiment.digest(['public', index]),
            'private_contract': 'private/task-'+str(index)+'.json',
            'private_contract_sha256': experiment.digest(['private', index])})
    return {'schema': experiment.SCHEMA+'.corpus', 'curator': {'identity': 'UNIT_FIXTURE_NOT_A_REAL_CURATOR',
        'independently_authored_sources': True, 'evaluation_not_previously_seen_by_developer': True}, 'tasks': tasks}


def plan(corpus_data, qualification_sha='c'*64, recovery_sha='d'*64):
    value = {'schema': experiment.SCHEMA+'.plan', 'protocol': experiment.protocol(), 'corpus': corpus_data,
        'corpus_document_sha256': experiment.digest(corpus_data), 'independence_audit': {},
        'source_sha256': experiment.code_identity(), 'image': IMAGE,
        'qualification_sha256': qualification_sha, 'recovery_sha256': recovery_sha}
    return {'payload': value, 'sha256': experiment.digest(value)}


def mocked_native_receipt(kind):
    """Synthetic trusted-controller boundary fixture; never publish as evidence."""
    from scripts.qualify_isolation_v18 import CONTROLLED_CASES, qualification_host_identity
    from nomad.platform_mission import CHECKPOINTS
    sources = experiment.code_identity()
    policy = asdict(experiment.execution_policy(IMAGE))
    names = (set(CONTROLLED_CASES) | {'supervisor_hard_death_cleanup'} if kind == 'qualification' else
        set(CHECKPOINTS) | {'reference_and_terminal_replay', 'owner_hard_death_with_live_container',
            'tampered-sealed.json', 'tampered-planning_memory.json', 'tampered-events.jsonl',
            'tampered-baseline/arithmetic.py'})
    record = {'schema': ('nomad.native-isolation-qualification.v18' if kind == 'qualification'
                        else 'nomad.platform-recovery-qualification.v18'),
        'backend': 'docker', 'status': 'PASS', 'native_containment_gate': 'PASS',
        'isolated_mission_recovery': 'PASS', 'image': IMAGE, 'policy': policy,
        'policy_sha256': experiment.digest(policy), 'source_stable': True,
        'source_sha256_before': sources, 'source_sha256_after': sources,
        'host_identity_sha256': experiment.digest(qualification_host_identity()),
        'protected_host_sentinel_unchanged': True, 'original_source_unchanged': True,
        'cases': [{'case': name, 'status': 'PASS'} for name in sorted(names)]}
    for case in record['cases']:
        if case['case'] == 'supervisor_hard_death_cleanup':
            case.update({'observed_live_container_before_owner_death': True,
                         'cleanup_confirmed_after_owner_death': True})
        if case['case'] == 'owner_hard_death_with_live_container':
            case['death'] = {'observed_running_container': True, 'held_before_cleanup': True}
    record['receipt_sha256'] = experiment.digest(record)
    return record


class IntelligenceQualificationTests(unittest.TestCase):
    def test_missing_corpus_records_not_run_before_private_access_or_execution(self):
        with tempfile.TemporaryDirectory() as td, patch.object(experiment, '_private_contract') as hidden, \
                patch.object(experiment, '_trial') as trial:
            result = experiment.run(None, Path(td), None, None, Path(td)/'receipt.json')
            self.assertEqual(result['execution'], 'NOT_RUN')
            self.assertFalse(result['private_contracts_opened'])
            hidden.assert_not_called(); trial.assert_not_called()
            self.assertEqual(json.loads((Path(td)/'receipt.json').read_text())['trials'], [])

    def test_missing_qualification_never_reads_private_contracts(self):
        with tempfile.TemporaryDirectory() as td, patch.object(experiment, '_private_contract') as hidden, \
                patch.object(experiment, 'docker_preflight') as docker:
            result = experiment.run(plan(corpus()), Path(td), None, None, Path(td)/'receipt.json')
            self.assertEqual(result['execution'], 'NOT_RUN')
            hidden.assert_not_called(); docker.assert_not_called()

    def test_independence_metadata_is_audited_without_opening_outcomes(self):
        with tempfile.TemporaryDirectory() as td, patch.object(experiment, 'read_json') as read:
            result = experiment.audit_corpus(corpus(), Path(td), check_public_files=False)
            self.assertEqual(len(result['training_repositories']), 2)
            self.assertEqual(len(result['evaluation_repositories']), 8)
            self.assertFalse(result['private_contracts_opened']); read.assert_not_called()

    def test_repeated_task_source_and_issue_are_refused(self):
        for field in ('id', 'source_sha256', 'issue_url'):
            data = corpus(); data['tasks'][1][field] = data['tasks'][0][field]
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError):
                    experiment.audit_corpus(data, Path(td), check_public_files=False)

    def test_seen_repo_overlapping_authorship_and_mounted_private_data_are_refused(self):
        for change in ('seen', 'author', 'private'):
            data = corpus()
            if change == 'seen':
                data['tasks'][2]['repository'] = 'https://github.com/rasterio/affine'
                data['tasks'][2]['issue_url'] = 'https://github.com/rasterio/affine/issues/99999'
            elif change == 'author': data['tasks'][2]['author_group'] = data['tasks'][0]['author_group']
            else: data['tasks'][2]['private_contract'] = data['tasks'][0]['source']+'/secret.json'
            with self.subTest(change=change), tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError):
                    experiment.audit_corpus(data, Path(td), check_public_files=False)

    def test_changed_source_or_protocol_invalidates_frozen_plan(self):
        document = plan(corpus())
        document['payload']['protocol']['bounds']['max_eval'] = 1
        document['sha256'] = experiment.digest(document['payload'])
        with self.assertRaises(ValueError): experiment._validate_plan(document)
        document = plan(corpus()); document['payload']['source_sha256'] = {}
        document['sha256'] = experiment.digest(document['payload'])
        with self.assertRaises(ValueError): experiment._validate_plan(document)

    def test_all_arms_share_budget_and_only_c_enables_native(self):
        record = experiment.protocol()
        self.assertEqual(set(record['arms']), {'A', 'B', 'C', 'D'})
        self.assertEqual([arm for arm, settings in record['arms'].items() if settings['native_enabled']], ['C'])
        self.assertEqual(record['arms']['B']['adaptive_enabled'], record['arms']['C']['adaptive_enabled'])
        self.assertEqual(record['arms']['B']['ranker_mode'], 'frequency')
        self.assertFalse(record['evaluation_updates'])

    def test_unmatched_or_different_public_inputs_cannot_support_advantage(self):
        rows = []
        for arm in experiment.ARM_SPECS:
            rows.append({'seed': experiment.SEEDS[0], 'task_id': 'one', 'repository': 'fixture/repo',
                         'arm': arm, 'accepted': arm == 'C', 'source_sha256': 's', 'public_spec_sha256': 'p'})
        with self.assertRaises(ValueError): experiment.assess(rows[:-1])
        altered = copy.deepcopy(rows); altered[-1]['public_spec_sha256'] = 'leaked-more-information'
        with self.assertRaises(ValueError): experiment.assess(altered)
        with self.assertRaises(ValueError): experiment.assess(rows + rows[:1])

    def test_repeated_seed_trials_are_not_independent_repository_units(self):
        rows = []
        for seed in experiment.SEEDS:
            for arm in experiment.ARM_SPECS:
                rows.append({'seed': seed, 'task_id': 'one', 'repository': 'fixture/repo',
                    'arm': arm, 'accepted': arm == 'C', 'source_sha256': 's', 'public_spec_sha256': 'p'})
        result = experiment.assess(rows)
        self.assertEqual(result['contrasts']['C>B']['repository_wins'], 1)
        self.assertEqual(result['contrasts']['C>B']['p_one_sided'], 0.5)
        self.assertEqual(result['intelligence_advantage'], 'NOT_ESTABLISHED')

    def test_fake_pass_word_without_bound_native_receipt_is_refused(self):
        with self.assertRaises(ValueError):
            experiment._receipt_binding({'status': 'PASS', 'backend': 'docker'}, IMAGE, 'qualification')

    def test_bound_native_receipts_require_exact_schema_sources_host_policy_and_cases(self):
        for kind in ('qualification', 'recovery'):
            baseline = mocked_native_receipt(kind)
            experiment._receipt_binding(baseline, IMAGE, kind)
            for field, value in (('schema', 'other.test-only.v18'), ('backend', 'mock'),
                    ('host_identity_sha256', '0'*64), ('source_sha256_before', {}),
                    ('policy_sha256', '0'*64), ('cases', [])):
                record = copy.deepcopy(baseline)
                record[field] = value
                record['receipt_sha256'] = experiment.digest({k: v for k, v in record.items()
                                                             if k != 'receipt_sha256'})
                with self.subTest(kind=kind, changed=field), self.assertRaises(ValueError):
                    experiment._receipt_binding(record, IMAGE, kind)

    def test_recovery_must_bind_the_same_native_qualification_before_private_access(self):
        with tempfile.TemporaryDirectory() as td, patch.object(experiment, '_private_contract') as hidden, \
                patch.object(experiment, 'docker_preflight') as docker:
            root = Path(td); qualification = root/'qualification.json'; recovery = root/'recovery.json'
            experiment.write_new(qualification, mocked_native_receipt('qualification'))
            record = mocked_native_receipt('recovery')
            record['isolation_receipt_sha256'] = '0'*64
            record['receipt_sha256'] = experiment.digest({k: v for k, v in record.items()
                                                         if k != 'receipt_sha256'})
            experiment.write_new(recovery, record)
            document = plan(corpus(), experiment.file_hash(qualification), experiment.file_hash(recovery))
            result = experiment.run(document, root, qualification, recovery, root/'result.json')
            self.assertEqual(result['execution'], 'NOT_RUN')
            self.assertIn('same containment receipt', ' '.join(result['preflight']['reasons']))
            hidden.assert_not_called(); docker.assert_not_called()

    def test_preflight_accepts_bound_mock_contracts_and_rejects_changed_recovery_evidence(self):
        # Reachability of the prerequisite contract only; no native execution
        # or qualification is claimed by these deliberately mocked records.
        with tempfile.TemporaryDirectory() as td, patch.object(experiment, '_private_contract') as hidden, \
                patch.object(experiment, 'docker_preflight', return_value={'ready': True}) as docker:
            root = Path(td); qualification = root/'qualification.json'; recovery = root/'recovery.json'
            evidence = root/'native-evidence'; evidence.mkdir()
            retained = evidence/'unit-fixture.json'; retained.write_text('{"mock":true}')
            experiment.write_new(qualification, mocked_native_receipt('qualification'))
            record = mocked_native_receipt('recovery')
            record.update({'isolation_receipt_sha256': experiment.file_hash(qualification),
                'evidence_root': str(evidence),
                'evidence_files_sha256': {'unit-fixture.json': experiment.file_hash(retained)}})
            record['receipt_sha256'] = experiment.digest({k: v for k, v in record.items()
                                                         if k != 'receipt_sha256'})
            experiment.write_new(recovery, record)
            document = plan(corpus(), experiment.file_hash(qualification), experiment.file_hash(recovery))
            self.assertEqual(experiment.preflight(document, root, qualification, recovery)['status'], 'PASS')
            docker.reset_mock()
            (evidence/'extra.json').write_text('{}')
            result = experiment.preflight(document, root, qualification, recovery)
            self.assertEqual(result['execution'], 'NOT_RUN')
            self.assertIn('unbound extra files', ' '.join(result['reasons']))
            hidden.assert_not_called(); docker.assert_not_called()

    def test_false_public_success_has_explicit_public_pass_denominator(self):
        rows = []
        for index in range(3):
            for arm in experiment.ARM_SPECS:
                rows.append({'seed': experiment.SEEDS[0], 'task_id': str(index), 'repository': 'unit/repo',
                    'arm': arm, 'accepted': index == 0, 'status': 'completed' if index == 0 else 'rejected',
                    'source_sha256': str(index), 'public_spec_sha256': str(index),
                    'public_passed': index < 2, 'independent_contract_rejected': index == 1})
        summary = experiment.assess(rows)['outcomes_by_arm']['C']
        self.assertEqual(summary['trial_count'], 3)
        self.assertEqual(summary['public_passes'], 2)
        self.assertEqual(summary['public_success_rejected_independently'], 1)
        self.assertEqual(summary['false_success_rate'], 0.5)

    def test_immutable_result_and_path_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'result.json'
            experiment.write_new(path, {'historical': 'HOLD'})
            with self.assertRaises(FileExistsError): experiment.write_new(path, {'rewritten': 'PASS'})
            with self.assertRaises(ValueError): experiment._path(Path(td), '../secret.json')
            self.assertEqual(json.loads(path.read_text())['historical'], 'HOLD')
            with self.assertRaises(ValueError):
                experiment.read_json(path, expected_sha256='0'*64)
            with self.assertRaises(ValueError): experiment.read_json(path, limit=2)

    def test_protocol_only_freeze_cannot_be_mistaken_for_an_admitted_corpus_plan(self):
        with tempfile.TemporaryDirectory() as td:
            document = experiment.freeze_protocol(Path(td)/'design.json')
            self.assertEqual(document['payload']['tasks_registered'], 0)
            self.assertFalse(document['payload']['private_contracts_opened'])
            with self.assertRaises(ValueError): experiment._validate_plan(document)

    def test_mocked_schedule_clones_training_memory_without_evaluation_leakage(self):
        # This is protocol plumbing only. No repository or container executes,
        # and no mock receipt is published as a native or efficacy result.
        calls = []
        def fake_trial(task, corpus_root, destination, memory_root, settings, image):
            if task['split'] == 'training':
                memory_root.mkdir(exist_ok=True)
                (memory_root/'marker').write_text('training-only')
            else:
                self.assertEqual((memory_root/'marker').read_text(), 'training-only')
                (memory_root/'marker').write_text('evaluation-must-never-be-reused')
            calls.append((task['split'], dict(settings)))
            return {'task_id': task['id'], 'repository': experiment._repository(task['repository']),
                'status': 'rejected', 'accepted': False, 'candidate_attempts': 1, 'isolated_executions': 2,
                'source_sha256': task['source_sha256'], 'public_spec_sha256': task['public_spec_sha256'],
                'candidate_inventory_sha256': '1'*64}
        with tempfile.TemporaryDirectory() as td, \
                patch.object(experiment, 'preflight', return_value={'status': 'PASS', 'reasons': []}), \
                patch.object(experiment, 'audit_corpus', return_value={}), \
                patch.object(experiment, '_trial', side_effect=fake_trial):
            result = experiment.run(plan(corpus()), Path(td), None, None, Path(td)/'mock-only.json')
            self.assertEqual(result['execution'], 'COMPLETED')
            self.assertEqual(result['intelligence_advantage'], 'NOT_ESTABLISHED')
            self.assertEqual(len([x for x in calls if x[0] == 'evaluation']), 24*3*4)
            for arm, settings in experiment.ARM_SPECS.items():
                self.assertEqual(len([x for x in calls if x == ('evaluation', settings)]), 24*3)

    def test_trial_uses_real_controller_and_resolved_proposal_with_mocked_isolation(self):
        from tests.test_platform_mission_v18 import passing_execution, SOURCE, PUBLIC, CHALLENGE, FINAL
        from nomad.isolation import snapshot_source
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root/'sources'/'one'; source.mkdir(parents=True)
            (source/'solution.py').write_bytes(SOURCE.encode())
            (source/'tests').mkdir()
            (source/'tests'/'test_public.py').write_bytes(b'# controlled protocol fixture; not executed\n')
            public = root/'public.json'; private = root/'private.json'
            experiment.write_new(public, {'goal_text': 'subtraction', 'public': PUBLIC})
            experiment.write_new(private, {'challenge': CHALLENGE, 'final': FINAL})
            identity = snapshot_source(source, root/'identity', experiment.execution_policy(IMAGE))
            task = {'id': 'unit-fixture', 'source': 'sources/one',
                'source_sha256': identity.digest, 'repository': 'https://github.com/unit-fixture/one',
                'public_spec': 'public.json', 'public_spec_sha256': experiment.file_hash(public),
                'private_contract': 'private.json', 'private_contract_sha256': experiment.file_hash(private)}
            with patch('nomad.platform_mission.run_isolated', side_effect=passing_execution):
                result = experiment._trial(task, root, root/'mission', root/'memory', experiment.ARM_SPECS['C'], IMAGE)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['isolated_executions'], 2)
            self.assertEqual(result['candidate_attempts'], 1)
            self.assertIsInstance(result['genesis_candidates_evaluated'], int)
            self.assertEqual(result['planning']['ranking']['native_predictions_evaluated'], 2)
            # The source can change after corpus-wide audit. Each actual mission
            # must bind its admitted snapshot before any isolated dispatch.
            (source/'solution.py').write_bytes((SOURCE+'\n# changed after admission\n').encode())
            with patch('nomad.platform_mission.run_isolated') as worker:
                with self.assertRaisesRegex(ValueError, 'actual admitted mission snapshot'):
                    experiment._trial(task, root, root/'changed-mission', root/'changed-memory',
                                      experiment.ARM_SPECS['C'], IMAGE)
                worker.assert_not_called()


if __name__ == '__main__': unittest.main()
