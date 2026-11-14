"""Independent journal negatives using explicitly authored fixture workers only."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad import platform_mission as mission
from nomad.mission_runtime import MissionHold, canonical
from tests.test_adaptive_mission_v18 import initialize, rehash
from tests.test_frontier_function_mission_v18 import controlled_execution


class AdaptiveMissionReviewTests(unittest.TestCase):
    def test_private_observation_cannot_enter_rehashed_training_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,_=initialize(Path(temporary))
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):mission.run(root)
            path=root/'mnemonic/events.jsonl';rows=mission.Journal(path,mission.FUNCTION_MEMORY_ID).read()
            trace=rows[1]['data']['computation_evidence']['public_trace']
            item=next(r for r in trace if r['kind']=='F_DISPATCHED')
            item['data']['operation']='challenge:'+rows[1]['data']['candidate']['id']
            rehash(trace);rehash(rows);path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
            with self.assertRaises(MissionHold):mission.read_function_computation_controller(path.parent)

    def test_duplicate_control_cannot_enter_rehashed_training_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,_=initialize(Path(temporary))
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):mission.run(root)
            path=root/'mnemonic/events.jsonl';rows=mission.Journal(path,mission.FUNCTION_MEMORY_ID).read()
            trace=rows[1]['data']['computation_evidence']['public_trace']
            index=next(i for i,r in enumerate(trace) if r['kind']=='F_CONTROL')
            trace.insert(index,deepcopy(trace[index]))
            for number,row in enumerate(trace,1):row['seq']=number
            rehash(trace);rehash(rows);path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
            with self.assertRaises(MissionHold):mission.read_function_computation_controller(path.parent)

    def test_adaptive_observation_cannot_drop_computation_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,_=initialize(Path(temporary))
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):mission.run(root)
            path=root/'mnemonic/events.jsonl';rows=mission.Journal(path,mission.FUNCTION_MEMORY_ID).read()
            del rows[1]['data']['computation_evidence'];rehash(rows)
            path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
            with self.assertRaises(MissionHold):mission.read_function_computation_controller(path.parent)


if __name__=='__main__':unittest.main()
