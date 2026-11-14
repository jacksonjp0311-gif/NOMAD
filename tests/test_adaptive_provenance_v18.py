"""Parse-only provenance checks and independent-rejection reporting regression."""
import ast
from dataclasses import asdict
import json
from pathlib import Path
import unittest

from nomad.witness import Witness
from scripts import prepare_adaptive_provenance_v18 as preparation
from scripts import experiment_frontier_v18 as experiment

ROOT=Path(__file__).resolve().parents[1]


class AdaptiveProvenanceTests(unittest.TestCase):
    def test_pinned_original_bytes_and_exact_projection_nodes(self):
        directory=ROOT/'experiments/development/adaptive_sources'
        catalog=json.loads((directory/'CORPUS.json').read_bytes())
        for entry in catalog['entries']:
            with self.subTest(entry=entry['id']):
                base=directory/entry['id'];source=(base/'original/subject.py').read_bytes()
                license_raw=(base/'original/LICENSE').read_bytes()
                self.assertEqual(preparation.sha(source),entry['source_sha256'])
                self.assertEqual(preparation.blob(source),entry['source_git_blob'])
                self.assertEqual(preparation.sha(license_raw),entry['license_sha256'])
                self.assertEqual(preparation.blob(license_raw),entry['license_git_blob'])
                self.assertFalse(entry['evaluation_eligible']);self.assertFalse(entry['downloaded_source_host_execution'])
                if 'projection_nodes' in entry:
                    projected,_=preparation.exact_projection(source.decode(),[row['symbol'] for row in entry['projection_nodes']])
                    self.assertEqual(projected.encode(),(base/'projection/subject.py').read_bytes())
                    self.assertEqual(preparation.sha(projected.encode()),entry['projection_sha256'])

    def test_projection_refuses_executable_global_initialization(self):
        with self.assertRaises(ValueError):preparation.exact_projection('X=open("secret")\ndef f(x): return x\n',['X','f'])

    def test_challenge_rejection_is_counted_without_nonexistent_supported_field(self):
        witness=Witness('independent-regression').attest(task_id='task',transmission_id='candidate',world_epoch=0,
            current_public=(0.,),target_public=(1.,),candidate_public=(1.,),
            current_challenge=(0.,),target_challenge=(1.,),candidate_challenge=(0.,))
        payload=asdict(witness);self.assertNotIn('supported',payload)
        self.assertFalse(witness.supported)
        self.assertTrue(experiment.independent_rejection([{'kind':'F_WITNESS','data':{'receipt':payload}}]))

    def test_supported_witness_is_not_rejection_and_final_rejection_is(self):
        witness=Witness('independent-regression').attest(task_id='task',transmission_id='candidate',world_epoch=0,
            current_public=(0.,),target_public=(1.,),candidate_public=(1.,),
            current_challenge=(0.,),target_challenge=(1.,),candidate_challenge=(1.,))
        rows=[{'kind':'F_WITNESS','data':{'receipt':asdict(witness)}}]
        self.assertFalse(experiment.independent_rejection(rows))
        self.assertTrue(experiment.independent_rejection(rows+[{'kind':'F_FINAL','data':{'supported':False}}]))


if __name__=='__main__':unittest.main()
