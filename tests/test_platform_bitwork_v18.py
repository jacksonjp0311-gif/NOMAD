"""Native execution, independence, stale memory and permanent negative cases."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nomad.platform_bitwork import NativeDecisionRanker, PublicObservation, digest
from nomad.native_bitwork import load_native, verified_runtime_identity
from nomad.mnemonic import EvidenceMemory
from nomad.causal_atlas import make_atlas_tasks, observe_intervention, SymbolGraph
from nomad.simulation_v12 import ACTION
from nomad.frontier import clone_frozen, run_external_contract

ROOT = Path(__file__).resolve().parents[1]


def sha(text): return hashlib.sha256(text.encode()).hexdigest()


def observation(i=0, **changes):
    return replace(PublicObservation('task'+str(i), sha('source'+str(i)), sha('candidate'+str(i)),
                       sha('receipt'+str(i)), '==→!=', True, 0), **changes)


class PlatformBitworkTests(unittest.TestCase):
    def test_original_vendor_archive_matches_frozen_v17_identity(self):
        # Independent of the intentionally omitted NOMAD predecessor archive.
        archive = ROOT/'vendor/BGR-v1.4.0-runtime.zip'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                         '93177c5cc628ac0c6426d8c612c0d769b86ed53cbd7b2a3f872d2706c601a8c2')

    def test_native_manifest_and_real_predict_observe(self):
        identity = verified_runtime_identity()
        self.assertGreater(identity['verified_files'], 1)
        model = load_native()()
        initial = model.predict(0)
        model.observe(0, 1)
        for _ in range(3):
            model.predict(0); model.observe(0, 1)
        self.assertNotEqual(model.predict(0), initial)
        self.assertEqual(model.snapshot()['version'], '1.4.0')

    def test_outside_runtime_import_is_refused(self):
        with patch.dict('sys.modules', {'bgr140': SimpleNamespace(__file__=__file__)}):
            with self.assertRaises(RuntimeError): load_native()

    def test_native_reorders_actual_candidate_list_without_authority(self):
        ranker = NativeDecisionRanker()
        for i in range(4):
            ranker.observe(observation(i), independently_observed=True)
        candidates = [SimpleNamespace(family='Add', source='x+y'), SimpleNamespace(family='==→!=', source='x!=y')]
        self.assertIs(ranker.rank(candidates)[0], candidates[1])
        self.assertEqual(ranker.summary()['authority'], 'ranking_only')
        self.assertEqual(ranker.summary()['external_repair_advantage'], 'NOT_ESTABLISHED')

    def test_arithmetic_route_scope_is_distinct_from_relational_history(self):
        ranker = NativeDecisionRanker(action_schema='genesis-vs-ast')
        with self.assertRaises(ValueError):
            ranker.observe(observation(), independently_observed=True)
        for i in range(4):
            ranker.observe(observation(i, family='GENESIS'), independently_observed=True)
        candidates = [SimpleNamespace(family='binary_operator'), SimpleNamespace(family='GENESIS')]
        self.assertIs(ranker.rank(candidates)[0], candidates[1])
        self.assertEqual(NativeDecisionRanker.load(ranker.snapshot()).summary()['action_schema'], 'genesis-vs-ast')

    def test_unobserved_replayed_and_renamed_evidence_cannot_inflate_support(self):
        ranker = NativeDecisionRanker()
        self.assertFalse(ranker.observe(observation()))
        self.assertTrue(ranker.observe(observation(), independently_observed=True))
        self.assertFalse(ranker.observe(observation(task_id='renamed', receipt_sha256=sha('changed'), capture_epoch=3), independently_observed=True))
        self.assertFalse(ranker.observe(observation(1, receipt_sha256=observation().receipt_sha256), independently_observed=True))
        self.assertEqual(ranker.summary()['independent_tasks'], 1)
        self.assertEqual(ranker.probabilities(), (0.5, 0.5))

    def test_stale_future_and_contradictory_observations_abstain(self):
        ranker = NativeDecisionRanker(ttl_epochs=1)
        for i in range(2): ranker.observe(observation(i), independently_observed=True)
        self.assertEqual(ranker.summary(now_epoch=2)['status'], 'cold')
        ranker.observe(observation(0, outcome=False, receipt_sha256=sha('counterexample')), independently_observed=True)
        self.assertEqual(ranker.summary()['contested_observations'], 1)
        self.assertEqual(ranker.summary()['status'], 'cold')
        future = NativeDecisionRanker()
        for i in range(2): future.observe(observation(i, capture_epoch=5), independently_observed=True)
        self.assertEqual(future.summary()['eligible_observations'], 0)

    def test_saved_memory_tampering_and_duplicate_observation_rejected(self):
        ranker = NativeDecisionRanker()
        for i in range(2): ranker.observe(observation(i), independently_observed=True)
        restored = NativeDecisionRanker.load(ranker.snapshot())
        self.assertEqual(restored.summary(), ranker.summary())
        document = ranker.snapshot(); document['payload']['events'][0]['outcome'] = False
        with self.assertRaises(ValueError): NativeDecisionRanker.load(document)
        document = ranker.snapshot(); document['payload']['events'].append(document['payload']['events'][0])
        document['sha256'] = digest(document['payload'])
        with self.assertRaises(ValueError): NativeDecisionRanker.load(document)

    def test_mnemonic_cannot_refresh_receipt_epoch_or_count_copied_sources(self):
        task = make_atlas_tasks(27019)[0]
        memory = EvidenceMemory(min_tasks=3)
        receipt = observe_intervention(task, ACTION)[0]
        memory.record(task=task, contract=task.contracts[0].key, action_source=ACTION, receipt=receipt, capture_epoch=0)
        with self.assertRaises(ValueError):
            memory.record(task=task, contract=task.contracts[0].key, action_source=ACTION, receipt=receipt, capture_epoch=1)
        for i in range(2):
            alias = replace(task, task_id='relabelled'+str(i))
            copied = observe_intervention(alias, ACTION)[0]
            with self.assertRaises(ValueError):
                memory.record(task=alias, contract=alias.contracts[0].key, action_source=ACTION, receipt=copied, capture_epoch=i+1)
        features = SymbolGraph(task.files).features(task.contracts[0], task.changed_file)
        self.assertEqual(memory.recall(action_source=ACTION, features=features, now_epoch=0).support_tasks, 1)

    def test_mnemonic_keeps_contradiction_instead_of_discarding_as_duplicate(self):
        from nomad.causal_atlas import digest as receipt_digest
        task = make_atlas_tasks(27019)[0]
        memory = EvidenceMemory(min_tasks=2)
        receipt = observe_intervention(task, ACTION)[0]
        self.assertTrue(receipt.changed)
        memory.record(task=task, contract=task.contracts[0].key, action_source=ACTION,
                      receipt=receipt, capture_epoch=0)
        contradicted = replace(receipt, after=receipt.before, receipt_digest='')
        contradicted = replace(contradicted, receipt_digest=receipt_digest(contradicted.payload()))
        memory.record(task=task, contract=task.contracts[0].key, action_source=ACTION,
                      receipt=contradicted, capture_epoch=0)
        features = SymbolGraph(task.files).features(task.contracts[0], task.changed_file)
        result = memory.recall(action_source=ACTION, features=features, now_epoch=1)
        self.assertEqual(result.status, 'contested')
        self.assertEqual(result.support_tasks, 1)

    def test_catalogue_false_positive_is_permanently_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = clone_frozen(ROOT/'external_sources', 'catalogue', Path(temporary)/'repo')
            source = repo/'catalogue/__init__.py'
            original = source.read_text(encoding='utf-8')
            bad = original.replace('len(self.namespace) == len(keys) - 1 and all(',
                                   'len(self.namespace) != len(keys) - 1 or all(', 1)
            self.assertNotEqual(original, bad)
            source.write_text(bad, encoding='utf-8')
            self.assertFalse(run_external_contract(repo, 'catalogue')['supported'])


if __name__ == '__main__': unittest.main()
