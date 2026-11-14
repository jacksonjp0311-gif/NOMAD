"""Prospective extension refuses unqualified work; never runs repository code."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from scripts import experiment_repository_adaptive_v18 as extension
from scripts import experiment_frontier_v18 as original


class RepositoryAdaptiveTests(unittest.TestCase):
    def test_original_four_arms_remain_exact(self):
        protocol=extension.protocol()
        self.assertEqual(protocol['original_A_to_D_protocol'],original.protocol())
        self.assertEqual(protocol['additional_arm']['label'],'E')
        self.assertFalse(protocol['whole_mission_cost']['qualified'])

    def test_current_design_refuses_execution_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); design=extension.freeze_design(base/'design.json')
            extension.validate_design(design)
            result=extension.refusal(design,base/'run.json')
            self.assertEqual(result['execution'],'NOT_RUN');self.assertEqual(result['trials'],[])
            self.assertFalse(result['private_contracts_opened'])
            with self.assertRaises(FileExistsError):extension.freeze_design(base/'design.json')
            with self.assertRaises(FileExistsError):extension.refusal(design,base/'run.json')

    def test_host_counter_cannot_become_linux_worker_or_total_cpu(self):
        events=[{'kind':'F_DISPATCHED','data':{'container_name':'first'}},
                {'kind':'F_OBSERVED','data':{'execution':{'container_name':'first',
                    'supervisor_metrics':{'available':True,'cpu_user_s':.2,'cpu_kernel_s':.1}}}}]
        result=extension.cost_coverage(events,controller_cpu_seconds=.1,wall_seconds=1)
        self.assertTrue(result['host_cli_cpu_coverage_complete'])
        self.assertIsNone(result['total_mission_cpu_seconds'])
        self.assertIsNone(result['docker_worker_cpu_seconds'])
        events.append({'kind':'F_DISPATCHED','data':{'container_name':'interrupted'}})
        self.assertFalse(extension.cost_coverage(events,controller_cpu_seconds=.1,wall_seconds=1)['host_cli_cpu_coverage_complete'])

    def test_foreign_counter_and_source_mutation_refused(self):
        events=[{'kind':'F_DISPATCHED','data':{'container_name':'first'}},
                {'kind':'F_OBSERVED','data':{'execution':{'container_name':'foreign',
                    'supervisor_metrics':{'available':True,'cpu_user_s':.2,'cpu_kernel_s':.1}}}}]
        self.assertFalse(extension.cost_coverage(events,controller_cpu_seconds=.1,wall_seconds=1)['host_cli_cpu_coverage_complete'])
        with tempfile.TemporaryDirectory() as temporary:
            design=extension.freeze_design(Path(temporary)/'design.json')
            changed=deepcopy(design);changed['payload']['source_sha256']['nomad/adaptive.py']='0'*64
            changed['sha256']=extension.shared.digest(changed['payload'])
            with self.assertRaises(ValueError):extension.validate_design(changed)

    def test_development_repositories_cannot_be_unseen_evaluation(self):
        for repository in extension.exposed_repositories():
            with self.subTest(repository=repository),self.assertRaisesRegex(ValueError,'newly exposed'):
                extension.audit({'tasks':[{'split':'evaluation','repository':'https://github.com/'+repository}]},Path('.'))


if __name__=='__main__':unittest.main()
