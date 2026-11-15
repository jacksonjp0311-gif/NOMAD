"""Pure-data diagnostic contracts; no learners or experiment harness imports."""
import copy
import unittest

from scripts.diagnose_temporal_v18 import episodes, episode_diagnostics, match_forecasts


def events(names):
    return [{'step':i,'action':i%2,'outcome':(i//2)%2,'p':.4,'mechanism':name}
            for i,name in enumerate(names)]


class TemporalDiagnosisContracts(unittest.TestCase):
    def test_selected_episodes_distinguish_retained_replay_from_cold_rebuild(self):
        trace=events(['frequency']*4+['native']*3+['frequency']*2+['native']*2)
        row={'family':'public_fixture','seed':1,'mode':'persistent','config':{'state_policy':'selectivewarm'},
             'trace':trace,'decisions':[], 'detector_metrics':{'alarm_prefixes':[]},
             'telemetry':{'catchup_observations':6}}
        warm=episode_diagnostics(row)
        self.assertEqual(warm['policy_implied_catchup_observations'],6)
        self.assertTrue(warm['catchup_count_agrees_with_trace_and_policy'])
        self.assertEqual(warm['first_native_episode']['forecasts'],3)
        cold=copy.deepcopy(row);cold['config']['state_policy']='cold';cold['telemetry']['catchup_observations']=13
        self.assertEqual(episode_diagnostics(cold)['policy_implied_catchup_observations'],13)
        full=copy.deepcopy(row);full['config']['state_policy']='fullwarm';full['telemetry']['catchup_observations']=0
        self.assertEqual(episode_diagnostics(full)['policy_implied_catchup_observations'],0)

    def test_native_prediction_difference_is_reported_instead_of_explained_away(self):
        row={'family':'public_fixture','seed':1,'mode':'persistent','trace':events(['native']*3)}
        control={'trace':events(['native']*3)}
        index={('public_fixture',1,'native'):control}
        result=match_forecasts([row],index)['persistent']
        self.assertEqual(result['status'],'EXACT_RECORDED_FORECAST_MATCH')
        row['trace'][1]['p']=.45
        result=match_forecasts([row],index)['persistent']
        self.assertEqual(result['status'],'DIFFERENCE_REQUIRES_REVIEW')
        self.assertEqual(result['counts']['native_mismatches'],1)
        self.assertEqual(result['first_mismatches_up_to32'][0]['step'],1)

    def test_unmatched_observations_refuse_comparison(self):
        row={'family':'public_fixture','seed':1,'mode':'persistent','trace':events(['native']*2)}
        control={'trace':events(['native']*2)};control['trace'][1]['outcome']^=1
        with self.assertRaises(ValueError): match_forecasts([row],{('public_fixture',1,'native'):control})

    def test_episode_boundaries_are_half_open(self):
        self.assertEqual(episodes(events(['frequency','native','native'])),[
            {'mechanism':'frequency','start':0,'end_exclusive':1,'forecasts':1},
            {'mechanism':'native','start':1,'end_exclusive':3,'forecasts':2}])


if __name__=='__main__': unittest.main()
