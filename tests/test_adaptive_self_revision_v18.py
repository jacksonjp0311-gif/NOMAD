"""Candidate preparation only; no native or whole-engine improvement claim."""
import json
from pathlib import Path
import tempfile
import unittest

from nomad.recursion import RankingExample as E, SyntheticTask as T, prepare_ranking_experiment
from nomad.mission_runtime import digest


class AdaptiveSelfRevisionTests(unittest.TestCase):
    def development(self):
        return [T('dev-'+str(i),(E(3,0,0,False),E(3,2,1,True))) for i in range(3)]

    def test_development_nomination_freezes_candidate_and_independent_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'experiment'
            report=prepare_ranking_experiment(output,self.development(),heldout_sha256='a'*64)
            self.assertEqual(report['status'],'PREPARED_NOT_RUN')
            self.assertTrue(report['development_improved'])
            self.assertNotEqual(report['nomination'],'cold')
            self.assertEqual(report['independent_acceptance']['status'],'HOLD')
            self.assertEqual(report['self_improvement_advantage'],'NOT_ESTABLISHED')
            self.assertFalse(report['heldout_read'])
            self.assertFalse(report['authoritative_source_replaced'])
            for name,sha in report['files_sha256'].items(): self.assertEqual(digest((output/name).read_bytes()),sha)
            self.assertEqual(json.loads((output/'protocol.json').read_bytes()),report)

    def test_equal_development_result_is_not_eligible_for_test_claim(self):
        tasks=[T('dev-'+str(i),(E(5,4,0,True),E(1,0,1,False))) for i in range(2)]
        with tempfile.TemporaryDirectory() as temporary:
            report=prepare_ranking_experiment(Path(temporary)/'experiment',tasks,heldout_sha256='b'*64)
            self.assertEqual(report['nomination'],'cold')
            self.assertFalse(report['candidate_eligible_for_independent_test'])

    def test_missing_independent_corpus_is_development_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            report=prepare_ranking_experiment(Path(temporary)/'experiment',self.development())
            self.assertEqual(report['status'],'DEVELOPMENT_NOMINATION_ONLY')
            self.assertIsNone(report['heldout_sha256'])
            self.assertFalse(report['candidate_eligible_for_independent_test'])
            self.assertEqual(report['independent_acceptance']['independent_corpus_status'],'MISSING_INDEPENDENT_HELDOUT_CORPUS')

    def test_protocol_cannot_overwrite_prior_candidate_or_accept_unbounded_tasks(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'experiment'
            prepare_ranking_experiment(output,self.development(),heldout_sha256='c'*64)
            original=(output/'protocol.json').read_bytes()
            with self.assertRaises(FileExistsError):
                prepare_ranking_experiment(output,self.development(),heldout_sha256='d'*64)
            self.assertEqual((output/'protocol.json').read_bytes(),original)
            with self.assertRaises(ValueError):
                prepare_ranking_experiment(Path(temporary)/'bad',[self.development()[0]]*2,heldout_sha256='e'*64)


if __name__=='__main__': unittest.main()
