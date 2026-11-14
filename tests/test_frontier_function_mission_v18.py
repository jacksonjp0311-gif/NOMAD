"""Controller contracts using explicitly authored fixture execution doubles.

No Docker or hostile-code containment result is inferred from this test suite.
Only the literal fixture programs in this file run in the double's namespace.
"""
import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nomad import frontier, platform_mission as mission
from nomad.isolation import SandboxPolicy, IsolationUnavailable
from nomad.mission_runtime import InjectedInterruption, MissionHold, canonical, digest

POLICY=SandboxPolicy('python@sha256:'+'a'*64)


def case(module, function, args, expected):
    return {'module':module,'function':function,'args':args,'expected':expected}


def fixture(base, *, two=False):
    source=base/'source'; source.mkdir()
    (source/'lower.py').write_text('def bounded(value, limit):\n    if value < limit:\n        return limit\n    return value\n',encoding='utf-8')
    files=['lower']
    if two:
        (source/'upper.py').write_text('def bounded(value, limit):\n    if value > limit:\n        return limit\n    return value\n',encoding='utf-8')
        files.append('upper')
    public=[]; challenge=[]; final=[]
    for module in files:
        desired=min if module=='lower' else max
        public += [case(module,'bounded',[2,5],desired(2,5)),case(module,'bounded',[9,5],desired(9,5))]
        challenge += [case(module,'bounded',[-3,1],desired(-3,1))]
        final += [case(module,'bounded',[18,7],desired(18,7))]
    return source,public,challenge,final


def controlled_execution(source, *, command, policy, container_name, include_output=False):
    """A fake Docker receipt; interprets only the authored comparison fixtures."""
    manifest=mission._manifest(source)
    entries=[[name,sha,(source/name).stat().st_size] for name,sha in manifest.items()]
    output=''
    if include_output:
        requests=json.loads(command[-1]); observed=[]
        for request in requests:
            tree=ast.parse((source/(request['module'].replace('.','/')+'.py')).read_text())
            fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==request['function'])
            values=dict(zip([a.arg for a in fn.args.args],request['args']))
            def expression(node):
                if isinstance(node,ast.Name): return values[node.id]
                if isinstance(node,ast.Constant): return node.value
                if isinstance(node,ast.UnaryOp): return -expression(node.operand)
                if isinstance(node,ast.BinOp):
                    a,b=expression(node.left),expression(node.right)
                    return {ast.Add:lambda:a+b,ast.Sub:lambda:a-b,ast.Mult:lambda:a*b,ast.FloorDiv:lambda:a//b}[type(node.op)]()
                if isinstance(node,ast.Compare):
                    a,b=expression(node.left),expression(node.comparators[0])
                    return {ast.Lt:lambda:a<b,ast.LtE:lambda:a<=b,ast.Gt:lambda:a>b,ast.GtE:lambda:a>=b,ast.Eq:lambda:a==b}[type(node.ops[0])]()
                raise ValueError('outside trusted test double')
            def statements(nodes):
                for node in nodes:
                    if isinstance(node,ast.Return): return True,expression(node.value)
                    if isinstance(node,ast.If):
                        found,value=statements(node.body if expression(node.test) else node.orelse)
                        if found:return found,value
                return False,None
            try: observed.append({'value':statements(fn.body)[1]})
            except Exception as error: observed.append({'raises':type(error).__name__})
        output=json.dumps({'schema':'nomad.frontier.observation.v1','observed':observed},sort_keys=True,separators=(',',':'))+'\n'
    receipt={'schema':'nomad.isolated-test.v1','container_name':container_name,'snapshot_sha256':digest(canonical(entries)),
        'source_files':len(entries),'source_bytes':sum(r[2] for r in entries),'image_digest':policy.image.split('@sha256:')[-1],
        'command':command,'returncode':0,'tests_passed':True,'timed_out':False,'container_cleanup_confirmed':True,
        'output_sha256':digest(output.encode()),'output_truncated':False}
    if include_output:receipt['output_utf8']=output
    return receipt


class FunctionMissionTests(unittest.TestCase):
    def initialize(self,base,**kwargs):
        source,public,challenge,final=fixture(base,two=kwargs.pop('two',False))
        root=base/'mission'
        goal=mission.initialize_functions(root,source,goal_text='Repair the declared bounded APIs',public=public,
            challenge=challenge,final=final,policy=POLICY,**kwargs)
        return root,source,goal

    def test_function_branches_and_complete_independent_contract_chain(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,source,goal=self.initialize(Path(temporary))
            before=mission._manifest(source)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution): result=mission.run(root)
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['witness_observations'],1)
            self.assertEqual(result['final_observations'],1)
            self.assertEqual(before,mission._manifest(source))
            with patch.object(mission,'run_isolated',side_effect=AssertionError('replayed execution')):
                self.assertEqual(mission.run(root)['status'],'completed')
            self.assertEqual(mission.inspect(root)['status'],'completed')

    def test_multifile_composition_repairs_both_public_apis(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,_,goal=self.initialize(Path(temporary),two=True,max_candidates=128,max_executions=150)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution): result=mission.run(root)
            self.assertEqual(result['status'],'completed')
            self.assertEqual(len(mission.resolved_goal(root)['candidate']['files']),2)

    def test_ambiguous_function_dispatch_requires_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,_,_=self.initialize(Path(temporary))
            with self.assertRaises(InjectedInterruption): mission.run(root,interrupt_at='after_dispatch')
            with self.assertRaises(MissionHold): mission.run(root)
            with patch('nomad.isolation.cleanup_isolated',return_value=True): mission.recover(root)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                self.assertEqual(mission.run(root)['status'],'completed')

    def test_final_rejection_does_not_feed_search_or_learning(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); source,public,challenge,final=fixture(base)
            final[0]['expected']=9999; root=base/'mission'
            mission.initialize_functions(root,source,goal_text='bounded task',public=public,challenge=challenge,final=final,policy=POLICY)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution): result=mission.run(root)
            self.assertEqual(result['status'],'rejected')
            self.assertEqual(mission._manifest(root/'workspace'),mission._manifest(source))
            self.assertFalse((root/'learning.json').exists())

    def test_observer_forbidden_channels_and_package_graph(self):
        bad=['import sys\ndef solve(x):\n    return x\n','def solve(x):\n    print(x)\n    return x\n',
             'def solve(x):\n    return x.__class__\n','def solve(x):\n    return eval(x)\n']
        for source in bad:
            with self.subTest(source=source),self.assertRaises(ValueError): frontier.admit_function_sources({'api.py':source})
        structure=frontier.admit_function_sources({'pkg/__init__.py':'',
            'pkg/api.py':'from .worker import bounded\ndef call(value):\n    return bounded(value)\n',
            'pkg/worker.py':'def bounded(value):\n    total = 0\n    for item in value:\n        total += item\n    return total\n'})
        self.assertEqual(structure['graph']['pkg/api.py'],['pkg/worker.py'])

    def test_genesis_synthesizes_novel_bound_parameter_expression(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); (root/'calc.py').write_text('def combine(left, right):\n    return left\n')
            rows=[case('calc','combine',[a,b],a+b*2) for a,b in [(1,2),(3,4),(-2,7),(8,-3)]]
            report=frontier.inspect_function_repository(root,rows)
            self.assertGreater(report['genesis'][0]['candidates_evaluated'],0)
            self.assertTrue(any(p.get('origin')=='GENESIS' for p in report['proposals']))

    def test_current_native_backend_absence_refuses_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,_,_=self.initialize(Path(temporary))
            with patch('nomad.isolation.sandbox_available',return_value=False),self.assertRaises(IsolationUnavailable): mission.run(root)
            self.assertEqual(mission.inspect(root)['status'],'hold_uncertain_execution')

    def test_public_probe_outcome_changes_actual_candidate_order(self):
        orders=[]
        with tempfile.TemporaryDirectory() as temporary:
            for number,force_pass in enumerate((False,True)):
                base=Path(temporary)/str(number);base.mkdir()
                root,_,goal=self.initialize(base,two=True,max_candidates=128)
                def execution(source,**kwargs):
                    receipt=controlled_execution(source,**kwargs)
                    requests=json.loads(kwargs['command'][-1])
                    if force_pass and len(requests)==1 and requests[0]['module']=='lower':
                        value=min(requests[0]['args'])
                        output=json.dumps({'schema':'nomad.frontier.observation.v1','observed':[{'value':value}]})
                        receipt.update(output_utf8=output,output_sha256=digest(output.encode()))
                    return receipt
                with patch.object(mission,'run_isolated',side_effect=execution),self.assertRaises(InjectedInterruption):
                    mission.run(root,interrupt_at='after_proposal')
                rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
                diagnosis=next(r['data'] for r in rows if r['kind']=='F_DIAGNOSIS')
                self.assertTrue(any(d['decision'] for d in diagnosis['decisions']))
                orders.append(diagnosis['order'])
        self.assertNotEqual(orders[0],orders[1])

    def test_function_resume_boundaries_do_not_repeat_observations(self):
        checkpoints=('after_plan','after_patch_write','after_patch_record','after_public',
            'after_proposal','after_witness','after_final','after_commit','before_memory','after_memory','after_learning')
        for boundary in checkpoints:
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as temporary:
                root,_,_=self.initialize(Path(temporary))
                with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                    with self.assertRaises(InjectedInterruption):mission.run(root,interrupt_at=boundary)
                    result=mission.run(root)
                self.assertEqual(result['status'],'completed')
                memory=mission.Journal(root/'mnemonic'/'events.jsonl',mission.FUNCTION_MEMORY_ID).read()
                self.assertEqual(sum(r['kind']=='OBSERVATION_ADMITTED' for r in memory),1)

    def test_foreign_output_receipt_and_lost_memory_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,_,_=self.initialize(Path(temporary))
            def foreign(*args,**kwargs):
                value=controlled_execution(*args,**kwargs);value['container_name']='nomad-'+'b'*24;return value
            with patch.object(mission,'run_isolated',side_effect=foreign),self.assertRaises(MissionHold):mission.run(root)
        with tempfile.TemporaryDirectory() as temporary:
            root,_,_=self.initialize(Path(temporary))
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):mission.run(root)
            (root/'mnemonic'/'events.jsonl').unlink()
            with self.assertRaises(MissionHold):mission.run(root)

    def test_distinct_task_memory_native_reuse_expiry_and_duplicate_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);memory=base/'memory'
            for index in range(3):
                task=base/str(index);task.mkdir();source,public,challenge,final=fixture(task)
                with (source/'lower.py').open('a') as handle:handle.write('\ndef marker():\n    return '+str(index+20)+'\n')
                root=task/'mission'
                mission.initialize_functions(root,source,goal_text='independent source task',public=public,challenge=challenge,
                    final=final,policy=POLICY,memory_root=memory,capture_epoch=index)
                with patch.object(mission,'run_isolated',side_effect=controlled_execution):mission.run(root)
            active=mission.read_function_memory_ranker(memory,now_epoch=2).summary(now_epoch=2)
            self.assertEqual(active['independent_tasks'],3)
            self.assertEqual(active['status'],'active')
            self.assertEqual(mission.read_function_memory_ranker(memory,now_epoch=7).summary(now_epoch=7)['eligible_observations'],0)
            source=base/'2'/'source';public,challenge,final=fixture_values()
            root=base/'duplicate'
            mission.initialize_functions(root,source,goal_text='renamed same source task',public=public,challenge=challenge,
                final=final,policy=POLICY,memory_root=memory,capture_epoch=3)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):mission.run(root)
            records=mission.Journal(memory/'events.jsonl',mission.FUNCTION_MEMORY_ID).read()
            self.assertEqual(len(records),4)

    def test_partial_two_file_patch_reconciles_without_partial_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root,_,goal=self.initialize(Path(temporary),two=True,max_candidates=128,max_executions=150)
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):
                with self.assertRaises(InjectedInterruption):mission.run(root,interrupt_at='after_multifile_patch_write')
            rows=mission.Journal(root/'events.jsonl',goal['mission_id']).read()
            self.assertEqual(rows[-1]['kind'],'F_PATCH')
            actual=mission._manifest(root/'workspace')
            self.assertNotEqual(actual,rows[-1]['data']['before'])
            self.assertNotEqual(actual,rows[-1]['data']['after'])
            with patch.object(mission,'run_isolated',side_effect=controlled_execution):self.assertEqual(mission.run(root)['status'],'completed')


def fixture_values():
    return ([case('lower','bounded',[2,5],2),case('lower','bounded',[9,5],5)],
            [case('lower','bounded',[-3,1],-3)],[case('lower','bounded',[18,7],7)])


if __name__=='__main__':unittest.main()
