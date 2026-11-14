"""MNEMONIC: verification of persistence, scoped prediction, and counterexamples."""
from __future__ import annotations
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from nomad.mnemonic import EvidenceMemory, encode_features, action_digest
from nomad.causal_atlas import SymbolGraph, make_atlas_tasks, observe_intervention
from nomad.simulation_v12 import ACTION, _safe_shift, run_study


class MnemonicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = make_atlas_tasks(27019)
        cls.one = cls.tasks[0]
        cls.contract = cls.one.contracts[0]
        cls.receipt = observe_intervention(cls.one,ACTION)[0]
        cls.features = SymbolGraph(cls.one.files).features(cls.contract,cls.one.changed_file)

    def setup_memory(self):
        memory=EvidenceMemory(min_tasks=3)
        for seed in (27019,27037,27077):
            t=make_atlas_tasks(seed)[0]
            rec=observe_intervention(t,ACTION)[0]
            memory.record(task=t,contract=t.contracts[0].key,action_source=ACTION,receipt=rec,capture_epoch=0)
        return memory

    def test_binary_state_no_hash_randomness(self):
        v=encode_features(self.features)
        self.assertIsInstance(v,int)
        self.assertEqual(v.bit_count(),6)
        self.assertIsNone(encode_features(('unknown',)))
        self.assertIsNone(encode_features(tuple('something' for _ in range(6))))

    def test_action_ast_canonical(self):
        self.assertEqual(action_digest(ACTION),action_digest('def solve(x,y): return x*y+y\n'))
        self.assertNotEqual(action_digest(ACTION),action_digest('def solve(x,y): return x-y\n'))

    def test_minimum_independent_task_support(self):
        m=EvidenceMemory(min_tasks=3)
        m.record(task=self.one,contract=self.contract.key,action_source=ACTION,
                 receipt=self.receipt,capture_epoch=0)
        p=m.recall(action_source=ACTION,features=self.features,now_epoch=0)
        self.assertEqual((p.outcome,p.support_tasks),('abstain',1))

    def test_persistence_and_restart(self):
        m=self.setup_memory()
        before=m.recall(action_source=ACTION,features=self.features,now_epoch=0)
        self.assertEqual(before.status,'promoted')
        m.freeze()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'memory.json';m.save(path)
            restored=EvidenceMemory.load(path)
        self.assertTrue(restored.frozen)
        self.assertEqual(restored.recall(action_source=ACTION,features=self.features,now_epoch=0),before)
        self.assertEqual(restored.snapshot(),m.snapshot())
        with self.assertRaises(ValueError):
            restored.record(task=self.one,contract=self.contract.key,action_source=ACTION,
                            receipt=self.receipt,capture_epoch=1)

    def test_expiry_and_action_mismatch(self):
        m=self.setup_memory()
        self.assertEqual(m.recall(action_source=ACTION,features=self.features,now_epoch=6).status,'expired')
        self.assertEqual(m.recall(action_source='def solve(x,y): return x-y',features=self.features,now_epoch=0).outcome,'abstain')

    def test_cannot_transfer_authority(self):
        m=self.setup_memory()
        p=m.recall(action_source=ACTION,features=self.features,now_epoch=0)
        self.assertEqual(p.authority,'prediction_only')
        self.assertFalse(hasattr(p,'authorize'))

    def test_foreign_or_stale_receipt_rejected(self):
        m=EvidenceMemory()
        with self.assertRaises(ValueError):
            m.record(task=self.one,contract=self.contract.key,action_source=ACTION,
                     receipt=replace(self.receipt, task_id='foreign'),capture_epoch=0)
        altered=replace(self.one,files={**self.one.files,self.one.changed_file:'def solve(x,y): return x-y\n'})
        with self.assertRaises(ValueError):
            m.record(task=altered,contract=self.contract.key,action_source=ACTION,
                     receipt=self.receipt,capture_epoch=0)
        with self.assertRaises(ValueError):
            m.record(task=self.one,contract=self.contract.key,action_source=ACTION,
                     receipt=replace(self.receipt, receipt_digest='0'*64),capture_epoch=0)
        self.assertEqual(m.events,[])

    def test_duplicate_receipt_and_budget(self):
        m=EvidenceMemory(max_events=1)
        m.record(task=self.one,contract=self.contract.key,action_source=ACTION,receipt=self.receipt,capture_epoch=0)
        with self.assertRaises(ValueError):
            m.record(task=self.one,contract=self.contract.key,action_source=ACTION,receipt=self.receipt,capture_epoch=0)
        other=self.one.contracts[1]
        other_rec=observe_intervention(self.one,ACTION)[1]
        with self.assertRaises(ValueError):
            m.record(task=self.one,contract=other.key,action_source=ACTION,receipt=other_rec,capture_epoch=0)

    def test_sha_chain_detects_corruption(self):
        m=self.setup_memory()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'memory.json';m.save(p)
            data=json.loads(p.read_text())
            data['payload']['events'][0]['evidence']['changed']=False
            p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):EvidenceMemory.load(p)

    def test_chain_catches_recomputed_outer_hash(self):
        from nomad.mnemonic import digest
        m=self.setup_memory()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'memory.json';m.save(p)
            data=json.loads(p.read_text())
            data['payload']['events'][0]['evidence']['changed']=False
            data['payload_sha256']=digest(data['payload'])
            p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):EvidenceMemory.load(p)

    def test_real_counterexample_contests_prior(self):
        m=self.setup_memory()
        # Need stronger support on the conditional-specific cell.
        for seed in (28001,28011,28031):
            t=make_atlas_tasks(seed)[0]
            graph=SymbolGraph(t.files)
            rows=observe_intervention(t,ACTION)
            for c,r in zip(t.contracts,rows):
                if 'conditional' in graph.features(c,t.changed_file):
                    m.record(task=t,contract=c.key,action_source=ACTION,receipt=r,capture_epoch=0)
        shifted,key=_safe_shift(self.one)
        c=next(c for c in shifted.contracts if c.key==key)
        features=SymbolGraph(shifted.files).features(c,shifted.changed_file)
        self.assertEqual(m.recall(action_source=ACTION,features=features,now_epoch=0).outcome,'impact')
        receipt=next(r for c0,r in zip(shifted.contracts,observe_intervention(shifted,ACTION)) if c0.key==key)
        self.assertFalse(receipt.changed)
        successor=m.fork()
        successor.record(task=shifted,contract=key,action_source=ACTION,receipt=receipt,capture_epoch=1)
        self.assertEqual(successor.recall(action_source=ACTION,features=features,now_epoch=1).status,'contested')
        self.assertEqual(m.recall(action_source=ACTION,features=features,now_epoch=1).outcome,'impact')

    def test_generated_heldout_study(self):
        study=run_study(holdout_seeds=(19011,))
        self.assertEqual(study['scores']['warm']['false_classified'],0)
        self.assertGreater(study['scores']['warm']['correct_classified'],study['scores']['graph']['correct_classified'])
        self.assertEqual(study['drift']['after_witness']['status'],'contested')
        self.assertEqual(study['scores']['warm']['mean_top3_impacts'],3)

if __name__=='__main__':unittest.main()
