"""Release candidate tests: evidence-first durable NOMAD missions (trusted fixtures)."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

from nomad.codeworld import CodeWorldExample, CodeWorldTask, make_codeworld_tasks
from nomad.mission_runtime import (InjectedInterruption, MissionHold,
    exclusive_owner, initialize, inspect, run)


ROOT = Path(__file__).resolve().parents[1]


def fixture(family: str = 'bin', seed: int = 9117) -> CodeWorldTask:
    tasks = make_codeworld_tasks(seed, per_family=1)
    return next(t for t in tasks if f'-{family}-' in t.task_id)


class MissionRuntimeV16Tests(unittest.TestCase):
    def test_end_to_end_real_unittest_and_independent_witness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'mission'
            goal=initialize(root,fixture('bin'))
            actual=run(root,trusted_fixture=True)
            self.assertEqual(actual['status'],'completed')
            self.assertEqual(actual['attempts'],1)
            self.assertEqual(actual['witness_observations'],1)
            self.assertEqual(actual['final_observations'],1)
            self.assertEqual(actual['committed_sha256'],inspect(root)['committed_sha256'])
            self.assertEqual(inspect(root)['journal_head'],actual['journal_head'])
            self.assertNotEqual(goal['original_sha256'],actual['committed_sha256'])
            self.assertNotIn('challenge', (root/'goal.json').read_text())
            self.assertNotIn('final', (root/'goal.json').read_text())

    def test_restart_seven_interruption_boundaries(self):
        checkpoints = ('after_plan','after_patch_write','after_patch_record',
                       'after_public','after_witness','after_final','after_completed')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)/'base'
            initialize(base,fixture('bin'))
            uninterrupted=run(base,trusted_fixture=True)
            baseline_journal=(base/'events.jsonl').read_bytes()
            for label in checkpoints:
                with self.subTest(checkpoint=label):
                    root=Path(tmp)/label
                    initialize(root,fixture('bin'))
                    with self.assertRaises(InjectedInterruption):
                        run(root,trusted_fixture=True,interrupt_at=label)
                    self.assertEqual(run(root,trusted_fixture=True)['status'],'completed')
                    self.assertEqual((root/'events.jsonl').read_bytes(),baseline_journal)
                    self.assertEqual(inspect(root)['committed_sha256'],uninterrupted['committed_sha256'])
                    self.assertEqual(inspect(root)['attempts'],1)

    def test_rollback_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'base'
            initialize(base,fixture('const'))
            expected=run(base,trusted_fixture=True)
            self.assertEqual(expected['status'],'completed')
            self.assertGreater(expected['attempts'],1)
            expected_records=[json.loads(row) for row in (base/'events.jsonl').read_text().splitlines()]
            for stop in ('after_rollback_write','after_rollback_record'):
                with self.subTest(stop=stop):
                    root=Path(tmp)/stop
                    initialize(root,fixture('const'))
                    with self.assertRaises(InjectedInterruption):
                        run(root,trusted_fixture=True,interrupt_at=stop)
                    result=run(root,trusted_fixture=True)
                    self.assertEqual(result['status'],'completed')
                    observed_records=[json.loads(row) for row in (root/'events.jsonl').read_text().splitlines()]
                    self.assertEqual([r['kind'] for r in observed_records],
                                     [r['kind'] for r in expected_records])
                    # unittest failure tracebacks embed the temporary root path;
                    # raw output hashes legitimately differ across workspaces.
                    for got, ref in zip(observed_records, expected_records):
                        self.assertEqual(got['data'].get('attempt'), ref['data'].get('attempt'))
                        self.assertEqual(got['data'].get('passed'), ref['data'].get('passed'))
                        self.assertEqual(got['data'].get('candidate_sha256'),
                                         ref['data'].get('candidate_sha256'))

    def test_actual_separate_process_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture('bin'))
            env={**os.environ,'PYTHONPATH':str(ROOT)}
            call=[sys.executable,'-B','-m','nomad.mission_cli','run','--root',str(root),'--trusted-fixture']
            crashed=subprocess.run(call+['--interrupt-at','after_patch_write'],
                                   cwd=ROOT,env=env,capture_output=True,text=True,timeout=12)
            self.assertEqual(crashed.returncode,75,crashed.stderr)
            continued=subprocess.run(call,cwd=ROOT,env=env,
                                     capture_output=True,text=True,timeout=15)
            self.assertEqual(continued.returncode,0,continued.stderr)
            self.assertEqual(json.loads(continued.stdout)['status'],'completed')
            self.assertEqual(len([r for r in (root/'events.jsonl').read_text().splitlines()
                                  if json.loads(r)['kind']=='PATCH_APPLIED']),1)

    def test_public_overfit_rejected_by_independent_witness(self):
        public=tuple(CodeWorldExample({'x':x,'y':1},x-1) for x in (3,5,8))
        challenge=tuple(CodeWorldExample({'x':x,'y':2},x*2) for x in (4,6,9))
        final=tuple(CodeWorldExample({'x':x,'y':3},x*3) for x in (4,6,9))
        task=CodeWorldTask('overfit-trap','def solve(x, y):\n    return x + y\n',
                           public,challenge,final,'evaluator-only-label')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            goal=initialize(root,task)
            result=run(root,trusted_fixture=True)
            self.assertEqual(result['status'],'exhausted')
            self.assertIsNone(result['committed_sha256'])
            self.assertEqual((root/'workspace'/'solution.py').read_text(),task.source)
            events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
            self.assertTrue(any(e['kind']=='PUBLIC_RESULT' and e['data']['passed'] for e in events))
            self.assertTrue(any(e['kind']=='WITNESS_RESULT' and not e['data']['supported'] for e in events))

    def test_final_holdout_can_reject_witness_positive(self):
        target=lambda x,y:x-y
        public=tuple(CodeWorldExample({'x':x,'y':2},target(x,2)) for x in (5,7,9))
        challenge=tuple(CodeWorldExample({'x':x,'y':3},target(x,3)) for x in (4,6,8))
        final=tuple(CodeWorldExample({'x':x,'y':4},x*4) for x in (5,6,7))
        task=CodeWorldTask('final-disagreement','def solve(x, y):\n    return x + y\n',
                           public,challenge,final,'not-reader-visible')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,task)
            result=run(root,trusted_fixture=True)
            self.assertEqual(result['status'],'exhausted')
            self.assertEqual((root/'workspace'/'solution.py').read_text(),task.source)
            rows=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
            self.assertTrue(any(x['kind']=='WITNESS_RESULT' and x['data']['supported'] for x in rows))
            self.assertTrue(any(x['kind']=='FINAL_RESULT' and not x['data']['supported'] for x in rows))

    def test_altered_journal_holds_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            p=root/'events.jsonl'
            content=p.read_text().replace('MISSION_CREATED','MISSION_OVERWRITTEN')
            p.write_text(content)
            with self.assertRaises(MissionHold):run(root,trusted_fixture=True)

    def test_truncated_journal_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            p=root/'events.jsonl'
            p.write_bytes(p.read_bytes()[:-1])
            with self.assertRaises(MissionHold):inspect(root)

    def test_source_drift_holds_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            p=root/'workspace'/'solution.py'
            p.write_text('def solve(x,y):\n    return 999\n')
            with self.assertRaises(MissionHold):run(root,trusted_fixture=True)
            self.assertIn('999',p.read_text())

    def test_public_test_tamper_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            p=root/'workspace'/'tests'/'test_public.py'
            p.write_text('import unittest\n')
            with self.assertRaises(MissionHold):run(root,trusted_fixture=True)

    def test_private_evidence_tamper_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            p=root/'sealed'/'withheld.json'
            p.write_text(p.read_text().replace('9117','9118'))
            with self.assertRaises(MissionHold):run(root,trusted_fixture=True)

    def test_untrusted_execution_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            with self.assertRaises(PermissionError):run(root)

    @unittest.skipUnless(os.name=='posix','POSIX exclusive owner test; Windows native acceptance is separate')
    def test_second_process_cannot_take_live_mission_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            code='from nomad.mission_runtime import exclusive_owner;from pathlib import Path;\nwith exclusive_owner(Path(%r)): pass' % str(root)
            with exclusive_owner(root):
                p=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,
                    env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True,timeout=10)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('already owned',p.stderr)

    def test_post_completion_source_change_invalidates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            run(root,trusted_fixture=True)
            (root/'workspace'/'solution.py').write_text('def solve(x,y): return 999')
            with self.assertRaises(MissionHold):inspect(root)
            with self.assertRaises(MissionHold):run(root,trusted_fixture=True)

    def test_terminal_replay_does_no_extra_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'mission'
            initialize(root,fixture())
            run(root,trusted_fixture=True)
            before=(root/'events.jsonl').read_bytes()
            summary=run(root,trusted_fixture=True)
            self.assertEqual(before,(root/'events.jsonl').read_bytes())
            self.assertIn('reused',summary['note'])


if __name__=='__main__':unittest.main()
