from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from nomad.genesis import (
    IOExample, SynthesisTask, GrammarPrior, synthesize, evaluate_task,
    fixed_v9_reachable, train_prior, _render, _extract_expression,
)
from nomad.simulation_v10 import make_tasks, run_suite


class GenesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training = make_tasks(131, ('square_plus','sum_times_y','times_shift','shift_times_y'), n_per_family=1)
        cls.test = make_tasks(911, ('difference_product','sum_times_x_shift','bilinear_plus','shifted_product'), n_per_family=1)

    def test_old_operator_vocabulary_cannot_solve_new_compositions(self):
        for task in self.test:
            with self.subTest(task=task.hidden_family):
                reach, count = fixed_v9_reachable(task, all_splits=True)
                self.assertFalse(reach)
                self.assertGreaterEqual(count, 2)

    def test_new_synthesizer_reaches_withheld_families(self):
        for task in self.test:
            with self.subTest(task=task.hidden_family):
                run, receipt = evaluate_task(task)
                self.assertTrue(run.synthesized)
                self.assertTrue(run.public_tests)
                self.assertTrue(run.witness_supported)
                self.assertTrue(run.final_correct)
                self.assertFalse(run.v9_reachable)
                self.assertTrue(receipt.verify_checksum())

    def test_actual_file_edit_and_python_unittest(self):
        task = self.test[0]
        result, receipt = evaluate_task(task, actual_tests=True)
        self.assertTrue(result.public_tests)
        self.assertTrue(result.witness_supported)
        self.assertTrue(result.final_correct)
        self.assertIsNotNone(receipt)

    def test_visible_counterexample_refines_search(self):
        source = 'def solve(x, y):\n    return x + y\n'
        pairs = [(0,2),(1,3),(1,5),(2,-2),(3,2),(-2,1),(5,0)]
        public = tuple(IOExample(x,y,x*x+y) for x,y in pairs)
        hold = tuple(IOExample(x,y,x*x+y) for x,y in ((4,2),(-4,-1),(6,3)))
        task = SynthesisTask('ce',source,public,hold,hold)
        run=synthesize(task)
        self.assertTrue(run.public_correct)
        self.assertGreater(run.counterexamples, 0)
        result,receipt=evaluate_task(task, actual_tests=True)
        self.assertTrue(result.witness_supported)

    def test_witness_rejects_visible_only_overfit(self):
        source='def solve(x, y):\n    return x + y\n'
        public=tuple(IOExample(x,y,x*x+y) for x,y in ((0,2),(1,3),(1,5),(0,1)))
        chall=tuple(IOExample(x,y,x*x+y) for x,y in ((2,3),(4,-1)))
        task=SynthesisTask('witness-reject',source,public,chall,chall)
        # The first minimum-description public solution is just x+y.
        result,receipt=evaluate_task(task)
        self.assertTrue(result.synthesized)
        self.assertFalse(result.witness_supported)
        self.assertFalse(result.final_correct)
        self.assertTrue(receipt.verify_checksum())
        self.assertFalse(receipt.supported)

    def test_withheld_data_never_guides_synthesis(self):
        task=self.test[1]
        a=synthesize(task)
        corrupt=dataclasses.replace(task,
            challenge=tuple(IOExample(e.x,e.y,e.expected+99) for e in task.challenge),
            final=tuple(IOExample(e.x,e.y,e.expected-18) for e in task.final),
            hidden_family='NO_SUCH_FAMILY')
        b=synthesize(corrupt)
        self.assertEqual((a.candidate,a.candidates_evaluated,a.source_context),
                         (b.candidate,b.candidates_evaluated,b.source_context))

    def test_bad_or_unsafe_input_is_refused(self):
        with self.assertRaises(ValueError):
            _extract_expression('def solve(x, y):\n    return __import__("os").system("echo BAD")\n')
        with self.assertRaises(ValueError):
            _render('__import__("os")')
        with self.assertRaises(ValueError):
            _render('x // y')

    def test_candidate_budget_is_binding(self):
        task=self.test[0]
        run=synthesize(task,max_eval=1)
        self.assertFalse(run.public_correct)
        self.assertIsNone(run.candidate)
        self.assertEqual(run.candidates_evaluated,1)

    def test_attested_only_training_and_tampered_receipt(self):
        task=self.training[0]
        result,receipt=evaluate_task(task)
        self.assertTrue(result.witness_supported)
        learner=GrammarPrior()
        learner.add_witnessed(result.learned_context, result.candidate, receipt)
        self.assertEqual(learner.witnessed,1)
        with self.assertRaises(ValueError):
            learner.add_witnessed(result.learned_context,result.candidate,
                                  dataclasses.replace(receipt,world_epoch=999))

    def test_training_uses_only_witness_supported_results(self):
        prior,stats=train_prior(self.training)
        self.assertEqual(stats['attempted'],len(self.training))
        self.assertGreater(prior.witnessed,0)
        self.assertEqual(prior.witnessed,stats['verified_skills'])

    def test_study_is_reproducible(self):
        kwargs={'n_train_per_family':1,'n_eval_per_family':1,'train_seeds':(131,), 'eval_seeds':(911,)}
        a=run_suite(**kwargs)
        b=run_suite(**kwargs)
        self.assertEqual(json.dumps(a,sort_keys=True),json.dumps(b,sort_keys=True))
        self.assertEqual(a['policies']['bitwork_context']['summary']['final_correct'],4)


if __name__ == '__main__': unittest.main()

class GenesisMemoryTests(unittest.TestCase):
    def test_witnessed_prior_roundtrip_and_tamper(self):
        from nomad.genesis_store import save_prior,load_prior
        from nomad.genesis import train_prior
        tasks=make_tasks(131,('square_plus','sum_times_y'),n_per_family=1)
        prior,training=train_prior(tasks)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'prior.json'
            sha=save_prior(p,prior)
            restored=load_prior(p)
            self.assertEqual(prior.snapshot(),restored.snapshot())
            self.assertEqual(len(sha),64)
            raw=json.loads(p.read_text())
            raw['prior']['witnessed']+=1
            p.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):load_prior(p)

class GenesisAbstentionTests(unittest.TestCase):
    def test_outside_typed_grammar_abstains(self):
        # Cubic plus a separate square needs more than seven AST nodes.
        pts=[(x,y) for x in (-5,-3,0,2,4) for y in (-4,1,3)]
        def examples(rows):
            return tuple(IOExample(x,y,x*x*x+y*y) for x,y in rows)
        task=SynthesisTask('out-of-grammar','def solve(x, y):\n    return x+y\n',
                           examples(pts[:12]),examples(pts[12:]),examples(pts[12:]))
        ev,receipt=evaluate_task(task,max_nodes=7)
        self.assertFalse(ev.synthesized)
        self.assertFalse(ev.witness_supported)
        self.assertFalse(ev.final_correct)
        self.assertIsNone(receipt)
