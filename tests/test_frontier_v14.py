"""FRONTIER external-source harness tests (trusted offline fixtures only)."""
from __future__ import annotations
import dataclasses, json
from pathlib import Path
import tempfile
import unittest

from nomad.frontier import (Candidate, Prior, bgr_failure_signature, candidates, clone_frozen,
                            digest, order_candidates, public_test_clues, run_external_contract,
                            run_tests, TestResult, verify_witness, witness_and_record)

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'external_sources'


class FrontierTests(unittest.TestCase):
    def test_candidate_edits_are_single_site_and_source_bound(self):
        src='def f(x):\n    return x <= 3 and x != 4\n'
        edits=candidates(src,'sample.py','test_f')
        self.assertTrue(edits)
        self.assertIn('return x >= 3 and x != 4',[c.render(src).splitlines()[-1].strip() for c in edits])
        with self.assertRaises(ValueError):edits[0].render('wrong code')

    def test_membership_repairs_cover_not_in(self):
        src='def f(d,k):\n    return k in d\n'
        ex=candidates(src,'sample.py','test_f')
        self.assertIn('return k not in d',[c.render(src).splitlines()[-1].strip() for c in ex])
        back=candidates('def f(d,k):\n    return k not in d\n','sample.py','test_f')
        self.assertIn('return k in d',[c.render('def f(d,k):\n    return k not in d\n').splitlines()[-1].strip() for c in back])

    def test_public_clues_include_implicit_contains(self):
        words=public_test_clues(SOURCES/'catalogue'/'catalogue'/'tests','registry_call or registry_get_set')
        self.assertIn('contains',words)

    def test_frozen_external_hashes_and_copy(self):
        with tempfile.TemporaryDirectory() as td:
            for project in ('affine','catalogue','confection'):
                clone=clone_frozen(SOURCES,project,Path(td)/project)
                self.assertTrue((clone/project/'__init__.py').is_file())
                src=(SOURCES/project/project/'__init__.py').read_bytes()
                self.assertEqual(digest(src),digest((clone/project/'__init__.py').read_bytes()))

    def test_frozen_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            import shutil
            cp=Path(td)/'snap'
            shutil.copytree(SOURCES,cp)
            f=cp/'catalogue'/'catalogue'/'__init__.py'
            f.write_text(f.read_text()+'\n# tampered\n')
            with self.assertRaises(ValueError):clone_frozen(cp,'catalogue',Path(td)/'out')

    def test_prior_is_context_scoped_and_rejects_bad_schema(self):
        p=Prior()
        c=Candidate('x',1,'f','!=','==',0,2,1)
        p.observe(37,c,True)
        self.assertEqual(p.score(37,c),1)
        self.assertEqual(p.score(38,c),0)
        self.assertEqual(Prior.load(p.snapshot()).score(37,c),1)
        with self.assertRaises(ValueError):Prior.load({'schema':'other','counts':{}})
        with self.assertRaises(ValueError):Prior.load({'schema':'nomad.frontier.prior.v1','counts':{'0:foo':-4}})

    def test_bgr_signature_stable_and_no_project_identifier(self):
        r=TestResult(False,1,1.0,digest('AssertionError'), 'AssertionError: value mismatch')
        self.assertEqual(bgr_failure_signature(r),bgr_failure_signature(dataclasses.replace(r,elapsed_s=42)))
        self.assertGreater(bgr_failure_signature(r),0)

    def test_nonallowlisted_project_refused(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):run_tests(Path(td),'anything_else')

    def test_witness_checksum_rejects_tamper(self):
        row={'schema':'nomad.frontier.witness.v1','supported':True,'source_sha256':'x'}
        row['receipt_sha256']=digest(json.dumps(row,sort_keys=True,separators=(',',':')))
        self.assertTrue(verify_witness(row))
        row['supported']=False
        self.assertFalse(verify_witness(row))

    def test_catalogue_api_contract_detects_false_test_pass(self):
        with tempfile.TemporaryDirectory() as td:
            repo=clone_frozen(SOURCES,'catalogue',Path(td)/'repo')
            self.assertTrue(run_external_contract(repo,'catalogue')['supported'])
            src=repo/'catalogue'/'__init__.py'
            old=src.read_text()
            # Changes a conjunction in get_all; upstream suite can miss the effect.
            bad=old.replace('len(self.namespace) == len(keys) - 1 and all(',
                            'len(self.namespace) != len(keys) - 1 or all(',1)
            src.write_text(bad)
            self.assertFalse(run_external_contract(repo,'catalogue')['supported'])

if __name__=='__main__':unittest.main()
