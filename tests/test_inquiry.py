from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nomad.inquiry import (
    PROBE_COSTS, ProbeLikelihoods, _initial_prior, _roles, _candidate_costs,
    _entropy, _update, choose_probe, fit_inquiry, make_inquiry_tasks,
    repo_snapshot, run_inquiry, run_probe,
)
from nomad.repo_world import materialize
from nomad.simulation_v9 import run_suite


class InquiryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training = make_inquiry_tasks(17, per_kind=2)
        cls.world, cls.likelihoods = fit_inquiry(cls.training)
        cls.evaluation = make_inquiry_tasks(20017, per_kind=1)

    def test_no_task_kind_leaks_through_id(self):
        self.assertEqual(len({f.repo.task_id for f in self.evaluation}), 4)
        for f in self.evaluation:
            self.assertTrue(f.repo.task_id.startswith('inq-'))
            for hidden in ('core_binary', 'middle_constant', 'entry_syntax', 'config_constant'):
                self.assertNotIn(hidden, f.repo.task_id)

    def test_only_supplied_api_roles(self):
        for task in self.evaluation:
            values = set(_roles(task.repo).values())
            self.assertTrue({'entry','core','config','middle'} <= values)
            self.assertIn('other',values)
            self.assertTrue(all(p.role in PROBE_COSTS for p in task.contracts))

    def test_probe_causal_signatures_are_executable(self):
        expected_fail_roles = (
            {'core','middle','entry'},
            {'middle','entry'},
            {'entry'},
            {'config','middle','entry'},
        )
        for task, expected in zip(self.evaluation, expected_fail_roles):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                materialize(task.repo,root)
                actual = {p.role for p in task.contracts if not run_probe(root,task.repo,p).passed}
                self.assertEqual(actual,expected)

    def test_probe_receipt_integrity_and_staleness(self):
        fixture = self.evaluation[0]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); materialize(fixture.repo,root)
            digest=repo_snapshot(root,fixture.repo)
            receipt=run_probe(root,fixture.repo,fixture.contracts[0])
            self.assertTrue(receipt.verify(digest))
            self.assertFalse(replace(receipt,passed=not receipt.passed).verify(digest))
            self.assertFalse(replace(receipt,probe_id='foreign').verify(digest))
            self.assertFalse(receipt.verify('0'*64))
            path=root/next(iter(fixture.repo.files))
            path.write_text(path.read_text()+'\n# changed epoch\n')
            self.assertFalse(receipt.verify(repo_snapshot(root,fixture.repo)))

    def test_probe_does_not_edit_source(self):
        task=self.evaluation[0]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);materialize(task.repo,root)
            before=repo_snapshot(root,task.repo)
            for p in task.contracts:
                run_probe(root,task.repo,p)
            self.assertEqual(before,repo_snapshot(root,task.repo))

    def test_likelihoods_are_witness_trained(self):
        self.assertEqual(self.likelihoods.fit_cases,len(self.training))
        for c in self.likelihoods.snapshot()['rows']:
            self.assertGreater(c['pass_probability'],0)
            self.assertLess(c['pass_probability'],1)

    def test_prior_distribution_normalizes(self):
        fixture=self.evaluation[0]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);materialize(fixture.repo,root)
            from nomad.repo_world import candidate_files
            files=candidate_files(fixture.repo)
            prior=_initial_prior(root,fixture.repo,self.world,files)
            self.assertAlmostEqual(sum(prior.values()),1)
            self.assertTrue(all(p>0 for p in prior.values()))
            self.assertGreater(_entropy(prior),0)

    def test_bayesian_update_moves_core_posterior_after_core_probe_failure(self):
        fixture=self.evaluation[0]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);materialize(fixture.repo,root)
            from nomad.repo_world import candidate_files
            files=candidate_files(fixture.repo)
            prior=_initial_prior(root,fixture.repo,self.world,files)
            posterior=_update(prior,_roles(fixture.repo),self.likelihoods,'core',False)
            core=next(f for f,role in _roles(fixture.repo).items() if role=='core')
            self.assertGreater(posterior[core],prior[core])

    def test_budget_zero_disables_probes(self):
        r=run_inquiry(self.evaluation[0],self.world,self.likelihoods,max_probe_cost=0)
        self.assertEqual(r.probes,0)
        self.assertEqual(r.probe_cost,0)
        self.assertTrue(r.final_correct)

    def test_repeated_queries_are_prevented_and_budget_enforced(self):
        for fixture in self.evaluation:
            for policy in ('active','all','random'):
                r=run_inquiry(fixture,self.world,self.likelihoods,policy=policy)
                self.assertLessEqual(r.probes,3)
                self.assertLessEqual(r.probe_cost,0.9+1e-9)
                self.assertEqual(len({p.probe_id for p in r.probe_receipts}),r.probes)
                self.assertTrue(r.final_correct)
                self.assertTrue(r.witness_supported)

    def test_evaluator_labels_do_not_affect_diagnostic_policy(self):
        task=self.evaluation[0]
        corrupted=replace(task.repo,true_bug_file='not-real.py',true_family='not-real')
        r1=run_inquiry(task,self.world,self.likelihoods)
        r2=run_inquiry(replace(task,repo=corrupted),self.world,self.likelihoods)
        self.assertEqual(r1.candidate_attempts,r2.candidate_attempts)
        self.assertEqual(r1.predicted_file,r2.predicted_file)
        self.assertEqual([p.passed for p in r1.probe_receipts],[p.passed for p in r2.probe_receipts])
        self.assertEqual([p.probe_id for p in r1.probe_receipts],[p.probe_id for p in r2.probe_receipts])

    def test_challenge_data_do_not_guide_probe_selection(self):
        task=self.evaluation[0]
        r1=run_inquiry(task,self.world,self.likelihoods)
        # Poisoned hidden challenge and final labels may block admission, but
        # must not change the chosen diagnostic queries or proposed file order.
        ex=task.repo.challenge[0]
        challenge=(replace(ex, expected=123456789),)+task.repo.challenge[1:]
        corrupt=replace(task.repo,challenge=challenge)
        r2=run_inquiry(replace(task,repo=corrupt),self.world,self.likelihoods)
        self.assertEqual(r1.predicted_file,r2.predicted_file)
        self.assertEqual([p.probe_id for p in r1.probe_receipts],[p.probe_id for p in r2.probe_receipts])
        self.assertFalse(r2.witness_supported)

    def test_active_information_gain_greater_than_zero(self):
        task=self.evaluation[0]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);materialize(task.repo,root)
            from nomad.repo_world import candidate_files
            files=candidate_files(task.repo)
            prior=_initial_prior(root,task.repo,self.world,files)
            decision=choose_probe(prior,_candidate_costs(task.repo,files),_roles(task.repo),
                                  self.likelihoods,task.menu(),frozenset(),0.9)
            self.assertIsNotNone(decision)
            self.assertGreater(decision.information_gain_bits,0)
            self.assertGreater(decision.net_expected_savings,0)

    def test_real_repository_unittest_and_witness(self):
        fixture=self.evaluation[0]
        r=run_inquiry(fixture,self.world,self.likelihoods,verify_repo_tests=True)
        self.assertTrue(r.solved)
        self.assertTrue(r.witness_supported)
        self.assertTrue(r.final_correct)

    def test_development_study_smoke(self):
        study=run_suite((17,),per_kind=1,integration=False)
        self.assertEqual(study['policies']['active']['final_correct'],4)
        self.assertEqual(study['policies']['world']['final_correct'],4)
        self.assertEqual(study['policies']['active']['probe_budget_violations'],0)


if __name__ == '__main__':
    unittest.main()
