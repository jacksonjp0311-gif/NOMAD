import copy
import unittest
from scripts.verify_adaptive_replay_v18 import deterministic_trial


class AdaptiveReplayTests(unittest.TestCase):
    def fixture(self):
        return {'split':'evaluation','family':'authored-fixture','seed':1,'mode':'adaptive','status':'COMPLETED',
            'input_sha256':'a'*64,'trace':[{'p':.3,'action':0,'outcome':1,'mechanism':'frequency'}],
            'metrics':{'mean_logloss':1.2},'decisions':[{'mechanism':'frequency'}],'final_state_sha256':'b'*64,
            'telemetry':{'decision_wall_seconds':1.,'native_builds':0},'cost':{'total_cpu_seconds':1.}}

    def test_cost_changes_are_excluded_but_count_changes_are_not(self):
        a=self.fixture();b=copy.deepcopy(a);b['cost']['total_cpu_seconds']=2.;b['telemetry']['decision_wall_seconds']=2.
        self.assertEqual(deterministic_trial(a),deterministic_trial(b))
        b['telemetry']['native_builds']=1
        self.assertNotEqual(deterministic_trial(a),deterministic_trial(b))

    def test_prediction_choice_and_metric_changes_are_retained(self):
        a=self.fixture()
        for field in ('trace','metrics','decisions'):
            b=copy.deepcopy(a);b[field]=[]
            self.assertNotEqual(deterministic_trial(a),deterministic_trial(b))


if __name__=='__main__':unittest.main()
