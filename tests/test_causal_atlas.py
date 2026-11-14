from __future__ import annotations
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from nomad.causal_atlas import (
    AtlasLearner, Contract, SymbolGraph, make_atlas_tasks, observe_intervention,
    repair_atlas_task, run_contract, source_digest, score_predictions,
    train_impact_model, write_world,
)
from nomad.genesis import synthesize
from nomad.simulation_v11 import run_study

PATCH='def solve(x, y):\n    return x*y+y\n'


class AtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task=make_atlas_tasks(111,per_family=1)[0]

    def test_actual_effects_are_measured_not_declared(self):
        t=self.task
        observations=observe_intervention(t,PATCH)
        self.assertTrue(all(x.verify() for x in observations))
        # Primary and bridge, direct dependent and conditional branch affected.
        self.assertEqual([r.changed for r in observations],
                         [True,True,True,False,False,False,False,True,True])

    def test_import_is_not_equivalent_to_effect(self):
        t=self.task
        graph=SymbolGraph(t.files)
        shadow=t.contracts[3]
        self.assertTrue(graph.imported_reachable(shadow.module,t.changed_file[:-3]))
        self.assertFalse(graph.reachable(shadow.key,t.changed_file[:-3]+'.solve')[0])
        masked=t.contracts[4]
        self.assertTrue(graph.reachable(masked.key,t.changed_file[:-3]+'.solve')[0])
        self.assertIn('zero_mask',graph.features(masked,t.changed_file))
        cancel=t.contracts[5]
        self.assertIn('self_cancel',graph.features(cancel,t.changed_file))

    def test_dynamically_resolved_symbol_abstains(self):
        t=self.task; graph=SymbolGraph(t.files)
        self.assertEqual(graph.features(t.contracts[-1],t.changed_file),('uncertain',))
        mdl=train_impact_model(make_atlas_tasks(119,per_family=1))
        self.assertEqual(mdl.predict(('uncertain',))[0],'abstain')

    def test_learned_effect_model_and_name_independence(self):
        training=make_atlas_tasks(201,per_family=1)
        tests=make_atlas_tasks(207,per_family=1)
        model=train_impact_model(training)
        self.assertGreater(model.total,0)
        for t in tests:
            g=SymbolGraph(t.files)
            records=observe_intervention(t,PATCH)
            for c,r in zip(t.contracts,records):
                p,prob,n=model.predict(g.features(c,t.changed_file))
                if p=='abstain':
                    self.assertEqual(g.features(c,t.changed_file),('uncertain',))
                else:self.assertEqual(p=='impact',r.changed)

    def test_receipt_digest_does_not_grant_authenticity(self):
        t=self.task
        r=observe_intervention(t,PATCH)[0]
        m=AtlasLearner(); f=SymbolGraph(t.files).features(t.contracts[0],t.changed_file)
        m.observe(f,r)
        with self.assertRaises(ValueError):
            m.observe(f,dataclasses.replace(r,after=(999.0,)))
        with self.assertRaises(ValueError):
            m.observe(f,dataclasses.replace(r,epoch=888))

    def test_public_synthesis_ignores_hidden_splits(self):
        t=self.task
        from nomad.genesis import SynthesisTask, IOExample
        st=SynthesisTask(t.task_id,t.files[t.changed_file],t.public,t.challenge,t.final)
        altered=dataclasses.replace(st,
            challenge=tuple(IOExample(e.x,e.y,22222) for e in st.challenge),
            final=tuple(IOExample(e.x,e.y,-22222) for e in st.final))
        a=synthesize(st)
        b=synthesize(altered)
        self.assertEqual((a.candidate,a.candidates_evaluated,a.source_context),
                         (b.candidate,b.candidates_evaluated,b.source_context))

    def test_graph_guided_real_file_edit(self):
        t=self.task
        result=repair_atlas_task(t,priority='graph',actual_tests=True)
        self.assertTrue(result['solved'])
        self.assertTrue(result['final_correct'])
        self.assertTrue(result['public_unittest'])
        self.assertTrue(result['witness_supported'])
        self.assertEqual(result['files_visited'],1)
        self.assertTrue(result['chosen_file_is_actual_source'])

    def test_graph_priority_does_not_change_available_programs(self):
        t=self.task
        flat=repair_atlas_task(t,priority='flat')
        graph=repair_atlas_task(t,priority='graph')
        self.assertEqual((flat['final_correct'],graph['final_correct']),(True,True))
        self.assertLessEqual(graph['files_visited'],flat['files_visited'])

    def test_research_study_is_deterministic(self):
        args=dict(train_seeds=(201,),eval_seeds=(207,),per_family=1,
                  integration_cases=0,include_repairs=False)
        a=run_study(**args); b=run_study(**args)
        self.assertEqual(json.dumps(a,sort_keys=True),json.dumps(b,sort_keys=True))
        self.assertEqual(a['impact_metrics']['learned_atlas']['fn'],0)
        self.assertEqual(a['impact_metrics']['learned_atlas']['fp'],0)
        self.assertGreater(a['impact_metrics']['learned_atlas']['f1'],a['impact_metrics']['direct_call_graph']['f1'])

    def test_clean_world_does_not_execute_outside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):write_world(Path(tmp),{'../escape.py':'raise RuntimeError()'})
            with self.assertRaises(ValueError):write_world(Path(tmp),{'/tmp/escape.py':'raise RuntimeError()'})

    def test_degenerate_metric_not_claimed_as_success(self):
        score=score_predictions([False,False],[False,None])
        self.assertEqual(score['abstained'],1)
        self.assertEqual(score['f1'],0.0)


if __name__=='__main__':unittest.main()
