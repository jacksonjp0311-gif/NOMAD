"""TRANSCEND: typed adapters, native effect witnesses and scoped transfer."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from nomad.genesis import synthesize
from nomad.simulation_v10 import make_tasks
from nomad.simulation_v13 import TRAIN_FAMILIES, HOLDOUT_FAMILIES
from nomad.transcend import (MAX_INTEGER, TransferMemory, canonical, digest,
                             native_available, reference_values, render,
                             run_native, shifted_context, witnessed)


class TranscendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task=make_tasks(401,('square_plus',),n_per_family=1)[0]
        cls.solution=synthesize(cls.task).candidate
        assert cls.solution

    def test_render_language_specific_source(self):
        text='(x*x)+y'
        self.assertIn('def solve',render('python',text))
        self.assertIn('function solve',render('javascript',text))
        self.assertIn('fn solve',render('rust',text))
        self.assertEqual(canonical(text),'((x * x) + y)')

    def test_language_independent_bitwork_context(self):
        from nomad.genesis import _signature
        self.assertEqual(_signature(self.task),synthesize(self.task).source_context)

    def test_native_python_and_js(self):
        for language in ('python','javascript'):
            if not native_available(language):self.skipTest(f'{language} unavailable')
            with self.subTest(language=language):
                output=run_native(language,self.solution,self.task.public)
                self.assertEqual(output.status,'passed')
                self.assertEqual(output.values,tuple(x.expected for x in self.task.public))

    def test_rust_emitter_and_native_gate(self):
        program=render('rust','x+(y*2)')
        self.assertIn('i64',program)
        if native_available('rust'):
            result=run_native('rust',self.solution,self.task.public)
            self.assertEqual(result.status,'passed')
        else:
            result=run_native('rust',self.solution,self.task.public)
            self.assertEqual(result.status,'unavailable')
            self.assertFalse(result.values)

    def test_expression_syntax_is_restricted(self):
        for code in ('__import__("os").system("echo bad")', 'x/y',
                     '[x for x in range(2)]', 'x**2', 'x + 100', 'x;pass',
                     'x[0]', 'x.__class__'):
            with self.subTest(code=code),self.assertRaises((ValueError,SyntaxError)):
                render('javascript',code)

    def test_numeric_portability_refuses_overflow(self):
        from nomad.genesis import IOExample
        rows=(IOExample(MAX_INTEGER,3,0),)
        self.assertEqual(run_native('javascript','x*y',rows).status,'invalid')
        # Even Python must respect the common numeric contract.
        self.assertEqual(run_native('python','x*y',rows).status,'invalid')

    def test_witness_accepts_actual_native_evidence(self):
        receipt, info=witnessed('python',self.task,self.solution)
        self.assertIsNotNone(receipt)
        self.assertTrue(receipt.supported)
        self.assertTrue(receipt.verify_checksum())
        self.assertEqual(receipt.transmission_id,info['program_sha256'])

    def test_witness_rejects_public_only_overfit(self):
        # Make a task whose public examples are all x+y, whose challenge is x*x+y.
        from dataclasses import replace
        from nomad.genesis import IOExample
        task=replace(self.task,public=tuple(IOExample(x.x,x.y,x.x+x.y) for x in self.task.public))
        receipt,_=witnessed('python',task,'x+y')
        self.assertIsNotNone(receipt)
        self.assertFalse(receipt.supported)
        self.assertFalse(receipt.challenge_match)

    def test_persist_and_reconstruct_prior_without_language_in_key(self):
        receipt,_=witnessed('python',self.task,self.solution)
        memory=TransferMemory()
        memory.add('python',self.task,self.solution,receipt)
        with self.assertRaises(ValueError):
            memory.add('python',self.task,self.solution,receipt)
        memory.freeze()
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'memory.json'
            memory.save(file)
            reloaded=TransferMemory.load(file)
        self.assertEqual(memory.head,reloaded.head)
        self.assertEqual(memory.source_languages(),('python',))
        self.assertEqual(memory.prior(contextual=True).snapshot(),reloaded.prior(contextual=True).snapshot())
        self.assertNotIn('source_language',reloaded.snapshot()['transfer_key'])
        self.assertEqual(reloaded.prior(contextual=True).witnessed,1)

    def test_corruption_rejected_and_replay_cannot_rewrite(self):
        receipt,_=witnessed('python',self.task,self.solution)
        memory=TransferMemory();memory.add('python',self.task,self.solution,receipt);memory.freeze()
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'memory.json';memory.save(f)
            doc=json.loads(f.read_text())
            doc['payload']['events'][0]['event']['context_bits']+=1
            f.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):TransferMemory.load(f)
            doc['payload_sha256']=digest(doc['payload'])
            f.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):TransferMemory.load(f)
        with self.assertRaises(ValueError):memory.add('python',self.task,self.solution,receipt)

    def test_false_receipt_cannot_train(self):
        receipt,_=witnessed('python',self.task,'x+y')
        self.assertFalse(receipt.supported)
        with self.assertRaises(ValueError):TransferMemory().add('python',self.task,'x+y',receipt)
        receipt2,_=witnessed('javascript',self.task,self.solution)
        with self.assertRaises(ValueError):TransferMemory().add('python',self.task,self.solution,receipt2)

    def test_shuffled_context_keeps_global_counts(self):
        from nomad.genesis import train_prior
        tasks=[]
        for seed in (221,241):tasks.extend(make_tasks(seed,TRAIN_FAMILIES,n_per_family=1))
        prior,_=train_prior(tasks)
        shifted=shifted_context(prior)
        self.assertEqual(prior.operator.global_counts,shifted.operator.global_counts)
        self.assertEqual(set(prior.operator.context_counts.keys()),set(shifted.operator.context_counts.keys()))

    def test_language_and_family_disjointness(self):
        self.assertFalse(set(TRAIN_FAMILIES)&set(HOLDOUT_FAMILIES))
        self.assertEqual(len(TRAIN_FAMILIES),4)
        self.assertEqual(len(HOLDOUT_FAMILIES),4)

    def test_no_native_rust_claim_without_compiler(self):
        status=run_native('rust',self.solution,self.task.public)
        self.assertEqual(status.status,'passed' if native_available('rust') else 'unavailable')


if __name__=='__main__':unittest.main()
