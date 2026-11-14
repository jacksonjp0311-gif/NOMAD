"""Independent semantic evidence checks using authored execution doubles only.

Rehashed temporary fixtures exercise scope checks beyond hash-chain integrity;
they do not claim signatures, authenticated storage, or native containment.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad import platform_mission as mission
from nomad.mission_runtime import Journal, MissionHold, canonical, digest
from tests.test_frontier_function_mission_v18 import POLICY, fixture, controlled_execution


def rechain(path, rows):
    previous = '0'*64
    for number, row in enumerate(rows, 1):
        row.update(seq=number, prev=previous)
        row['sha256'] = digest(canonical({k:v for k,v in row.items() if k!='sha256'}))
        previous = row['sha256']
    path.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))


class FunctionEvidenceBindingTests(unittest.TestCase):
    def initialize(self, base, *, complete=True):
        source, public, challenge, final = fixture(base)
        root = base/'mission'
        goal = mission.initialize_functions(root, source, goal_text='Bounded fixture evidence',
            public=public, challenge=challenge, final=final, policy=POLICY)
        if complete:
            with patch.object(mission, 'run_isolated', side_effect=controlled_execution):
                self.assertEqual(mission.run(root)['status'], 'completed')
        return root, goal

    def test_memory_source_task_action_and_runtime_must_match_origin(self):
        mutations = {
            'baseline': lambda r:r['baseline'].update({'lower.py':'1'*64}),
            'task': lambda r:r.update(task_identity='2'*64),
            'files': lambda r:r['files'].update({'lower.py':'def bounded(a,b): return a\n'}),
            'candidate': lambda r:r['candidate'].update(family='forged-family'),
            'capture_epoch': lambda r:r.update(capture_epoch=1),
            'runtime': lambda r:r.update(runtime='3'*64),
            'signature': lambda r:r['signatures'].update({'lower.py':['invented']}),
            'execution_goal': lambda r:r['execution_goal']['baseline'].update({'lower.py':'4'*64}),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root, _ = self.initialize(Path(temporary))
            path = root/'mnemonic'/'events.jsonl'
            original = Journal(path, mission.FUNCTION_MEMORY_ID).read()
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    rows = deepcopy(original); mutate(rows[1]['data']); rechain(path, rows)
                    with self.assertRaises(MissionHold): mission._function_memory(path.parent)

    def test_memory_public_execution_source_output_and_final_aggregate_are_bound(self):
        mutations = {
            'snapshot': lambda r:r['public_result']['execution'].update(snapshot_sha256='a'*64),
            'output': lambda r:r['public_result']['execution'].update(output_sha256='b'*64),
            'unsupported_final': lambda r:r['acceptance'].update(final_supported=False),
            'foreign_final_candidate': lambda r:r['acceptance'].update(candidate_sha256='c'*64),
            'foreign_witness': lambda r:r['acceptance'].update(witness_receipt_sha256='d'*64),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root, _ = self.initialize(Path(temporary))
            path = root/'mnemonic'/'events.jsonl'
            original = Journal(path, mission.FUNCTION_MEMORY_ID).read()
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    rows = deepcopy(original); record = rows[1]['data']; mutate(record)
                    acceptance = record['acceptance']
                    acceptance['sha256'] = digest(canonical({k:v for k,v in acceptance.items() if k!='sha256'}))
                    rechain(path, rows)
                    with self.assertRaises(MissionHold): mission._function_memory(path.parent)

    def test_duplicate_witness_final_and_diagnosis_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, goal = self.initialize(Path(temporary))
            path = root/'events.jsonl'; original = Journal(path, goal['mission_id']).read()
            for kind in ('F_WITNESS', 'F_FINAL', 'F_DIAGNOSIS'):
                with self.subTest(kind=kind):
                    rows = deepcopy(original); index = next(i for i,r in enumerate(rows) if r['kind']==kind)
                    rows.insert(index+1, deepcopy(rows[index])); rechain(path, rows)
                    with self.assertRaises(MissionHold): mission.inspect(root)

    def test_private_stages_require_public_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, goal = self.initialize(Path(temporary), complete=False)
            path = root/'events.jsonl'; original = Journal(path, goal['mission_id']).read()
            candidate = goal['analysis']['proposals'][0]['id']
            for stage in ('before', 'challenge', 'final', 'suite'):
                with self.subTest(stage=stage):
                    rechain(path, deepcopy(original))
                    Journal(path, goal['mission_id']).append('F_DISPATCHED', {
                        'operation':stage+':'+candidate, 'container_name':'nomad-'+'1'*24})
                    with self.assertRaises(MissionHold): mission.inspect(root)

    def test_completed_candidate_cannot_be_patched_after_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, goal = self.initialize(Path(temporary))
            path = root/'events.jsonl'; rows = Journal(path, goal['mission_id']).read()
            index = next(i for i,r in enumerate(rows) if r['kind']=='F_COMMITTED')
            inserted = deepcopy(next(r for r in rows if r['kind']=='F_PATCH'))
            inserted['data']['id'] = 'after-commit'
            rows.insert(index+1, inserted); rechain(path, rows)
            with self.assertRaisesRegex(MissionHold, 'committed.*immutable'): mission.inspect(root)

    def test_rehashed_mnemonic_effect_cannot_disagree_with_witness(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _ = self.initialize(Path(temporary))
            path = root/'mnemonic'/'events.jsonl'; rows = Journal(path, mission.FUNCTION_MEMORY_ID).read()
            record = rows[1]['data']; self.assertIsNotNone(record['mnemonic'])
            receipt = record['mnemonic']['receipt']
            receipt['before'] = receipt['after'][:]
            receipt['receipt_digest'] = mission.memory_digest({k:v for k,v in receipt.items() if k!='receipt_digest'})
            rechain(path, rows)
            with self.assertRaises(MissionHold): mission._function_memory(path.parent)

    def test_private_input_values_are_absent_from_learned_memory(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); source, public, challenge, final = fixture(base)
            challenge[0]['args'] = [-918273645, 1]; challenge[0]['expected'] = -918273645
            final[0]['args'] = [817263544, 7]; final[0]['expected'] = 7
            root = base/'mission'
            mission.initialize_functions(root, source, goal_text='Private input separation',
                public=public, challenge=challenge, final=final, policy=POLICY)
            with patch.object(mission, 'run_isolated', side_effect=controlled_execution):
                self.assertEqual(mission.run(root)['status'], 'completed')
            data = (root/'mnemonic'/'events.jsonl').read_text(encoding='utf-8')
            self.assertNotIn('918273645', data); self.assertNotIn('817263544', data)


if __name__ == '__main__':
    unittest.main()
