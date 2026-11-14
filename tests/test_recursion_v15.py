import copy
import zipfile
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from nomad.native_bitwork import action_for_family, load_native, shadow_study
from nomad.recursion import (EvidenceScopedPrior, RankingExample, SyntheticTask,
    synthesize_ranking_source, compile_ranking_source, assess_candidate)

ROOT=Path(__file__).resolve().parents[1]
STUDY=json.loads((ROOT/'results/FRONTIER_STUDY_V014.json').read_text())

class RecursionV15Tests(unittest.TestCase):
    def test_runtime_is_original_bgr_engine(self):
        cls=load_native()
        self.assertEqual(cls.__module__,'bgr140.engine')
        model=cls()
        value=model.predict(0)
        self.assertGreaterEqual(value,0)
        self.assertLessEqual(value,1)
        model.observe(0,1)
        self.assertEqual(model.snapshot()['version'],'1.4.0')

    def test_binary_action_is_semantic(self):
        self.assertEqual(action_for_family('<=→>='),0)
        self.assertEqual(action_for_family('and→or'),1)
        with self.assertRaises(ValueError): action_for_family('not-a-family')

    def test_real_public_outcome_replay(self):
        study=shadow_study(STUDY['training']+STUDY['cold'])
        self.assertEqual(study['events'],sum(len(r['trace']) for r in STUDY['training']+STUDY['cold']))
        self.assertEqual(study['model'],'bgr140.GovernedBitworkV14')

    def test_scope_requires_three_independent_witnesses(self):
        row=STUDY['training'][0]
        p=EvidenceScopedPrior(3)
        r=copy.deepcopy(row['witness'])
        c=SimpleNamespace(family=row['selected']['family'])
        self.assertTrue(p.admit(bits=row['bitwork_signature'],family=row['selected']['family'],
            task_id='external-1',expected_source_sha256=row['selected']['candidate_sha256'],
            project=row['project'],receipt=r,independently_observed=True))
        # A second task ID cannot re-label an old source and an old receipt.
        self.assertFalse(p.admit(bits=row['bitwork_signature'],family=row['selected']['family'],
            task_id='external-2',expected_source_sha256=row['selected']['candidate_sha256'],
            project=row['project'],receipt=r,independently_observed=True))
        self.assertEqual(p.score(row['bitwork_signature'],c),0)
        # Synthetic independent receipt fixtures exercise the gate mechanics;
        # they are NOT external research evidence or security signatures.
        for i in (2,3):
            rr=copy.deepcopy(r)
            rr['source_sha256']=hashlib.sha256(f'separate-fixture-{i}'.encode()).hexdigest()
            content={k:v for k,v in rr.items() if k!='receipt_sha256'}
            rr['receipt_sha256']=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            self.assertTrue(p.admit(bits=row['bitwork_signature'],family=row['selected']['family'],
                task_id=f'external-{i}',expected_source_sha256=rr['source_sha256'],
                project=row['project'],receipt=rr,independently_observed=True))
        self.assertEqual(p.score(row['bitwork_signature'],c),3)

    def test_invalid_provenance_refused(self):
        row=STUDY['training'][0];p=EvidenceScopedPrior()
        args=dict(bits=row['bitwork_signature'],family=row['selected']['family'],task_id='X',
                  expected_source_sha256='forged-sha',project=row['project'],
                  receipt=row['witness'],independently_observed=True)
        self.assertFalse(p.admit(**args))
        args['expected_source_sha256']=row['selected']['candidate_sha256']
        args['independently_observed']=False
        self.assertFalse(p.admit(**args))
        tampered=copy.deepcopy(row['witness']);tampered['supported']=False
        args['independently_observed']=True;args['receipt']=tampered
        self.assertFalse(p.admit(**args))

    def test_negative_catalogue_contrasts_promote_contest(self):
        row=next(x for x in STUDY['transferred'] if x['id']=='catalogue-names')
        self.assertFalse(row['witness']['supported'])
        p=EvidenceScopedPrior()
        self.assertFalse(p.admit(bits=row['bitwork_signature'],family=row['selected']['family'],
            task_id=row['id'],expected_source_sha256=row['selected']['candidate_sha256'],
            project=row['project'],receipt=row['witness'],independently_observed=True))
        self.assertIn(p.key(row['bitwork_signature'],row['selected']['family']),p.contested)

    def test_prior_tampering_detected(self):
        p=EvidenceScopedPrior();rec=p.snapshot(); self.assertEqual(EvidenceScopedPrior.load(rec).min_support,3)
        rec['min_support']=2
        with self.assertRaises(ValueError):EvidenceScopedPrior.load(rec)

    def test_synthesized_code_executes_without_imports(self):
        fn=compile_ranking_source(synthesize_ranking_source('prior_first'))
        self.assertLess(fn(0,10,20),fn(9,1,1))
        self.assertNotIn('import',synthesize_ranking_source('prior_first'))

    def test_patched_ast_cannot_execute_arbitrary_source(self):
        with self.assertRaises(ValueError):compile_ranking_source('import os\ndef ranking_key(a,b,c): return os.system("whoami")')
        with self.assertRaises(ValueError):synthesize_ranking_source('run_shell')
        with self.assertRaises(ValueError):compile_ranking_source('def ranking_key(semantic, prior, line):\n  return (0,0,0)\n')

    def test_hold_without_external_transfer_even_when_toy_improves(self):
        def tasks(n,kind):
            return [SyntheticTask(str(i),tuple(RankingExample(4 if j<2 else 2,0 if j<2 else 5,j,j==2)
                                        for j in range(3))) for i in range(n)]
        res=assess_candidate(base_source=synthesize_ranking_source('cold'),
                             candidate_source=synthesize_ranking_source('prior_first'),
                             dev=tasks(5,'x'),heldout=tasks(8,'x'),external_transfer_confirmed=False)
        self.assertTrue(res['improved_in_bounded_lab'])
        self.assertEqual(res['production_promotion'],'HOLD')

    def test_native_runtime_baseline_zip_preserved(self):
        # Exact v0.16 archive contains the v0.15 predecessor and its v0.14.
        # Do not needlessly duplicate 65MiB in every new release.
        previous=ROOT/'baseline/NOMAD-v0.16.0.zip'
        self.assertTrue(previous.exists())
        with zipfile.ZipFile(previous) as z:
            v15=z.read('NOMAD-v0.16.0/baseline/NOMAD-v0.15.0.zip')
        self.assertEqual(hashlib.sha256(v15).hexdigest(),
            '088203e8af0b0c9886417c20a7eec2e75176b05b8313a527356def3b96a76544')
        import io
        with zipfile.ZipFile(io.BytesIO(v15)) as z:
            v14=z.read('NOMAD-v0.15.0/baseline/NOMAD-v0.14.0.zip')
            self.assertEqual(hashlib.sha256(v14).hexdigest(),
                '22c218597f5fa1cfc4003fc7694daac420ac42d0603feaeb8130ade6ef2619ea')
        self.assertTrue((ROOT/'vendor/BGR-v1.4.0-runtime.zip').exists())

if __name__=='__main__':unittest.main()
