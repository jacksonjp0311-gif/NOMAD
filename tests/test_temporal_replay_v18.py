import copy
import unittest
from scripts.verify_temporal_replay_v18 import deterministic


class TemporalReplayTests(unittest.TestCase):
    def row(self):
        return {'split':'evaluation','family':'stationary','seed':18186101,'mode':'persistent',
            'status':'COMPLETED','config':{},'input_sha256':'a'*64,'trace':[{'p':.5}],
            'metrics':{'loss':.7},'decisions':[{'mechanism':'native'}],'switches':1,
            'detector_metrics':{'false_alarms':1},'final_state_sha256':'b'*64,'source_stable':True,
            'telemetry':{'active_forecasts':1,'active_cpu_seconds':.5},
            'checkpoints':[{'observed_prefix':256,'deterministic_state_sha256':'c'*64,'method':'direct',
                            'state_sha256':'d'*64,'state_bytes':512,'cpu_seconds':.2}]}

    def test_measured_clocks_and_raw_storage_hashes_are_not_predictions(self):
        a=self.row(); b=copy.deepcopy(a)
        b['telemetry']['active_cpu_seconds']=1.2
        b['checkpoints'][0].update(state_sha256='e'*64,state_bytes=520,cpu_seconds=.7)
        self.assertEqual(deterministic(a),deterministic(b))

    def test_forecast_operation_and_state_changes_cannot_be_ignored(self):
        a=self.row()
        for field in ('forecast','operation','state'):
            b=copy.deepcopy(a)
            if field=='forecast': b['trace'][0]['p']=.6
            elif field=='operation': b['telemetry']['active_forecasts']=2
            else: b['checkpoints'][0]['deterministic_state_sha256']='f'*64
            self.assertNotEqual(deterministic(a),deterministic(b))
