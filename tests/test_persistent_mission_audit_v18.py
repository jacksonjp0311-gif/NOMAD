"""Independent integration review: numerical state and bounded validation memo.

Only authored fixture worker doubles run. These tests do not qualify Docker.
"""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad import platform_mission as mission
from nomad.persistent import (PersistentController, digest as state_digest,
    predictor_restore, predictor_snapshot)
from nomad.adaptive import make_predictor, probability
from nomad.mission_runtime import MissionHold, canonical
from tests.test_adaptive_mission_v18 import rehash
from tests.test_persistent_mission_v18 import initialize, controlled_execution


def changed_cache(predictor_document):
    result=copy.deepcopy(predictor_document)
    fields=result['payload']['state']['fields']['base']['fields']['discovered']['fields']
    constant=next(value for key,value in fields['pool']['v'] if key==2**32-1)
    fields['_rank_cache']={'t':'list','v':[constant]}
    fields['_exact_scores']={'t':'dict','v':[[{'t':'tuple','v':[2**32-1,1]},1000.]]}
    result['sha256']=state_digest(result['payload'])
    return result


class NumericalCacheAudit(unittest.TestCase):
    def test_prediction_affecting_caches_are_retained_in_semantic_comparison(self):
        controller=PersistentController();controller.peek_probabilities('native')
        original=controller.snapshot();altered=copy.deepcopy(original)
        altered['payload']['states']['native']=changed_cache(altered['payload']['states']['native'])
        altered['sha256']=state_digest(altered['payload'])
        self.assertEqual(original['payload']['history'],altered['payload']['history'])
        self.assertEqual(original['payload']['source_sha256'],altered['payload']['source_sha256'])
        self.assertNotEqual(mission._persistent_semantics(original),mission._persistent_semantics(altered))

    def test_frozen_codec_cache_integrity_boundary_is_not_misrepresented(self):
        original=predictor_snapshot(make_predictor('native'),'native')
        altered=changed_cache(original)
        clean=predictor_restore(original,'native');changed=predictor_restore(altered,'native')
        # A local checksum can be rewritten. This fixture demonstrates why the
        # mission must compare caches with independently replayed public state.
        self.assertNotEqual(probability(clean,0),probability(changed,0))
        self.assertEqual(original['payload']['runtime'],altered['payload']['runtime'])
        self.assertEqual(original['payload']['prefix_sha256'],altered['payload']['prefix_sha256'])

    def test_rehashed_public_update_cache_poisoning_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='nomad-cache-audit-') as temporary:
            root,goal=initialize(Path(temporary),late=True)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                self.assertEqual(mission.run(root)['status'],'completed')
            mission.inspect(root)  # Populate validation memo before tampering.
            path=root/'events.jsonl';rows=mission.Journal(path,goal['mission_id']).read()
            update=next(r['data'] for r in rows if r['kind']=='F_P_UPDATED' and 'native' in r['data']['state']['payload']['states'])
            state=update['state'];old_history=copy.deepcopy(state['payload']['history'])
            state['payload']['states']['native']=changed_cache(state['payload']['states']['native'])
            state['sha256']=state_digest(state['payload'])
            self.assertEqual(state['payload']['history'],old_history)
            rehash(rows);path.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))
            with self.assertRaises(MissionHold) as caught:
                mission.inspect(root)
            errors=(caught.exception,caught.exception.__cause__)
            self.assertTrue(any(isinstance(error,MissionHold) and
                'post-observation learned state changed' in str(error) for error in errors))


class ValidationMemoAudit(unittest.TestCase):
    def setUp(self): mission._PERSISTENT_VALIDATED.clear()
    def tearDown(self): mission._PERSISTENT_VALIDATED.clear()

    def context(self, replay):
        stack=ExitStack()
        stack.enter_context(patch.object(mission,'_runtime_identity',return_value={'platform':'current'}))
        stack.enter_context(patch.object(mission,'_persistent_source_identity',return_value={'bridge':'current'}))
        stack.enter_context(patch.object(mission,'_persistent_runtime_identity',return_value={'verified_vendor':'current'}))
        call=stack.enter_context(patch.object(mission,'_replay_persistent_trace',side_effect=replay))
        return stack,call

    def test_full_content_flags_and_defensive_copies_are_bound(self):
        stack,call=self.context(lambda *args,**kwargs:{'validated':[1]})
        with stack:
            rows=[{'sha256':'unchanged-recorded-hash','data':1}];goal={'source':'one'}
            first=mission._validate_persistent_trace(goal,rows);first['validated'].append(99)
            second=mission._validate_persistent_trace(goal,rows);self.assertEqual(second,{'validated':[1]})
            second['validated'].append(88)
            self.assertEqual(mission._validate_persistent_trace(goal,rows),{'validated':[1]})
            self.assertEqual(call.call_count,1)
            mission._validate_persistent_trace(goal,rows,complete=True)
            mission._validate_persistent_trace(goal,rows,selected='different')
            rows[0]['data']=2;mission._validate_persistent_trace(goal,rows)
            goal['source']='two';mission._validate_persistent_trace(goal,rows)
            self.assertEqual(call.call_count,5)

    def test_runtime_and_native_bridge_rechecked_before_hit(self):
        stack,call=self.context(lambda *args,**kwargs:{'validated':True})
        with stack:
            mission._validate_persistent_trace({},[])
            with patch.object(mission,'_persistent_source_identity',return_value={'bridge':'changed'}):
                mission._validate_persistent_trace({},[])
            self.assertEqual(call.call_count,2)
            with patch.object(mission,'_persistent_runtime_identity',side_effect=ValueError('fixture vendor bytes changed')):
                with self.assertRaisesRegex(ValueError,'vendor bytes changed'):
                    mission._validate_persistent_trace({},[])
            self.assertEqual(call.call_count,2)

    def test_memo_storage_and_input_bounds(self):
        stack,call=self.context(lambda *args,**kwargs:{'padding':'x'*1_600_000})
        with stack:
            for number in range(6):mission._validate_persistent_trace({'goal':number},[])
            self.assertLessEqual(len(mission._PERSISTENT_VALIDATED),4)
            self.assertLessEqual(sum(map(len,mission._PERSISTENT_VALIDATED.values())),8_000_000)
            self.assertTrue(all(type(value) is bytes for value in mission._PERSISTENT_VALIDATED.values()))
            with self.assertRaises(MissionHold):mission._validate_persistent_trace({},[{}]*2049)
            with patch.object(mission,'PERSISTENT_JOURNAL_BYTES',10):
                with self.assertRaises(MissionHold):mission._validate_persistent_trace({},[])
        mission._PERSISTENT_VALIDATED.clear()
        stack,call=self.context(lambda *args,**kwargs:{'oversize':'x'*2_000_000})
        with stack:
            mission._validate_persistent_trace({},[])
            self.assertEqual(mission._PERSISTENT_VALIDATED,{})


if __name__=='__main__':unittest.main()
