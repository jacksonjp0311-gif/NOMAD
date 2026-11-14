"""NOMAD v0.17 threat-model tests. Docker contract tests are not kernel isolation tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from nomad.supervised import minimal_env, run_supervised
from nomad.isolation import (SandboxPolicy, UnsafeWorkspace, IsolationUnavailable,
                             snapshot_source, docker_arguments, run_isolated)
from nomad.archive_guard import extract_checked
from nomad.effects import EffectLedger
from nomad.mission_runtime import MissionHold

IMAGE = 'example.org/nomad/python@sha256:'+'a'*64


def repo(root: Path) -> Path:
    p=root/'upstream-source'
    p.mkdir()
    (p/'solution.py').write_text('def solve(x):\n    return x + 1\n')
    (p/'tests').mkdir()
    (p/'tests'/'test_smoke.py').write_text('import unittest\n')
    return p


class IsolationContractTests(unittest.TestCase):
    def test_unknown_code_has_no_local_execution_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            with patch('nomad.isolation.sandbox_available',return_value=False):
                with patch('nomad.isolation.run_supervised') as forbidden:
                    with self.assertRaises(IsolationUnavailable):
                        run_isolated(source, command=['python','-B','-m','unittest'],
                                     policy=SandboxPolicy(image=IMAGE))
                    forbidden.assert_not_called()

    def test_snapshot_only_regular_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            p=SandboxPolicy(image=IMAGE)
            out=snapshot_source(source,Path(td)/'copy',p)
            self.assertEqual(out.files,2)
            self.assertEqual((out.root/'solution.py').read_bytes(),
                             (source/'solution.py').read_bytes())
            self.assertEqual(len(out.digest),64)
            self.assertTrue(out.bytes>0)

    def test_symlink_escape_is_refused(self):
        if not hasattr(os,'symlink'):
            self.skipTest('symlink unavailable')
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            secret=Path(td)/'private.txt'
            secret.write_text('NOT_FOR_SANDBOX')
            (source/'leak.py').symlink_to(secret)
            with self.assertRaises(UnsafeWorkspace):
                snapshot_source(source,Path(td)/'copy',SandboxPolicy(image=IMAGE))
            self.assertFalse((Path(td)/'copy').exists())

    def test_credential_and_git_material_are_denied(self):
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            (source/'.env').write_text('SECRET=x')
            with self.assertRaises(UnsafeWorkspace):
                snapshot_source(source,Path(td)/'copy',SandboxPolicy(image=IMAGE))
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            (source/'.git').mkdir()
            (source/'.git'/'config').write_text('url=secret')
            with self.assertRaises(UnsafeWorkspace):
                snapshot_source(source,Path(td)/'copy',SandboxPolicy(image=IMAGE))

    def test_hardlink_and_size_budget(self):
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            os.link(source/'solution.py',source/'link.py')
            with self.assertRaises(UnsafeWorkspace):
                snapshot_source(source,Path(td)/'copy',SandboxPolicy(image=IMAGE))
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            (source/'large').write_bytes(b'x'*3000)
            with self.assertRaises(UnsafeWorkspace):
                snapshot_source(source,Path(td)/'copy',SandboxPolicy(image=IMAGE,max_total_bytes=1024))

    def test_docker_invocation_denies_host_surface(self):
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            policy=SandboxPolicy(image=IMAGE)
            snap=snapshot_source(source,Path(td)/'snapshot',policy)
            command=docker_arguments(engine='docker',snapshot=snap.root,
                 image=IMAGE,name='nomad-'+'a'*24,policy=policy,
                 command=['python','-B','-m','unittest','discover','-s','tests'])
            args=' '.join(command)
            for need in ['--network=none','--read-only','--cap-drop=ALL',
                         '--user=65534:65534','no-new-privileges','--pids-limit',
                         '--memory','--cpus','--pull=never','readonly']:
                self.assertIn(need,args)
            for forbidden in ['--privileged','/var/run/docker.sock','--network=host',str(source)]:
                self.assertNotIn(forbidden,args)
            self.assertEqual(command[-1],'tests')
            with self.assertRaises(ValueError):
                docker_arguments(engine='docker',snapshot=snap.root,image=IMAGE,
                                 name='nomad-'+'a'*24,policy=policy,command=['bash','-c','oops'])
            with self.assertRaises(ValueError):
                SandboxPolicy(image='python:latest').validate()

    def test_mock_container_orchestration_does_not_grant_witness_authority(self):
        from nomad.supervised import ProcessResult
        import hashlib
        def result(code:int, output:bytes=b'', cleanup='posix-process-group-exited'):
            return ProcessResult(code, output, hashlib.sha256(output).hexdigest(),
                                 False,False,len(output),12,cleanup)
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            with patch('nomad.isolation.sandbox_available',return_value=True), \
                 patch('nomad.isolation.run_supervised',side_effect=[
                     result(0),result(1,b'Error: No such object: container')]) as call:
                receipt=run_isolated(source,command=['python','-B','-m','unittest'],
                                     policy=SandboxPolicy(image=IMAGE))
            self.assertTrue(receipt['tests_passed'])
            self.assertEqual(receipt['authority'],'test execution only; independent WITNESS still required')
            self.assertEqual(call.call_count,2)
            self.assertIn('--network=none',call.call_args_list[0].args[0])

    def test_uncertain_container_cleanup_holds_even_on_exit_zero(self):
        from nomad.supervised import ProcessResult
        import hashlib
        def result(code:int, output:bytes=b''):
            return ProcessResult(code, output, hashlib.sha256(output).hexdigest(),
                                 False,False,len(output),5,'posix-process-group-exited')
        with tempfile.TemporaryDirectory() as td:
            source=repo(Path(td))
            with patch('nomad.isolation.sandbox_available',return_value=True), \
                 patch('nomad.isolation.run_supervised',side_effect=[
                      result(0),result(1,b'Cannot connect to Docker daemon')]):
                with self.assertRaises(IsolationUnavailable):
                    run_isolated(source,command=['python','-B','-m','unittest'],
                                 policy=SandboxPolicy(image=IMAGE))

    def test_output_is_bounded_and_secrets_are_not_inherited(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ,{'NOMAD_FAKE_API_SECRET':'do-not-inherit'}):
                p=run_supervised([sys.executable,'-c',
                    'import os;print(os.getenv("NOMAD_FAKE_API_SECRET", "absent"));print("A"*50000)'],
                    cwd=Path(td),timeout_s=5,env=minimal_env(),max_output_bytes=600)
            self.assertFalse(p.timed_out)
            self.assertEqual(p.returncode,0)
            self.assertIn(b'absent',p.output)
            self.assertNotIn(b'do-not-inherit',p.output)
            self.assertLessEqual(len(p.output),600)
            self.assertTrue(p.truncated)

    def test_timeout_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            p=run_supervised([sys.executable,'-c','import time;time.sleep(9)'],
                             cwd=Path(td),timeout_s=0.15,max_output_bytes=100)
            self.assertTrue(p.timed_out)
            self.assertEqual(p.returncode,124)
            self.assertLess(p.elapsed_ms,3000)

    @unittest.skipUnless(os.name=='posix' and Path('/proc').is_dir(),
                         'POSIX process-group test')
    def test_orphaned_descendant_is_cleaned(self):
        with tempfile.TemporaryDirectory() as td:
            pid=Path(td)/'child.pid'
            text='''import subprocess,sys,pathlib
p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(25)"])
pathlib.Path(sys.argv[1]).write_text(str(p.pid))
'''
            result=run_supervised([sys.executable,'-c',text,str(pid)],cwd=Path(td),
                                  timeout_s=5,max_output_bytes=200)
            self.assertEqual(result.returncode,0)
            childpid=int(pid.read_text())
            for _ in range(20):
                statpath=Path('/proc')/str(childpid)/'stat'
                if not statpath.exists() or statpath.read_text().split()[2]=='Z':
                    break
                time.sleep(0.1)
            else:
                self.fail('descendant remained running after supervisor exited')

    def test_archive_traversal_and_symlink_denied(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            z=base/'escape.zip'
            with zipfile.ZipFile(z,'w') as f:
                f.writestr('../escape.txt','bad')
            with self.assertRaises(UnsafeWorkspace):extract_checked(z,base/'extract')
            self.assertFalse((base/'escape.txt').exists())
            z2=base/'link.zip'
            with zipfile.ZipFile(z2,'w') as f:
                info=zipfile.ZipInfo('symlink')
                info.create_system=3
                info.external_attr=(0o120777<<16)
                f.writestr(info,'/etc/passwd')
            with self.assertRaises(UnsafeWorkspace):extract_checked(z2,base/'extract2')

    def test_archive_valid_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            z=base/'valid.zip'
            with zipfile.ZipFile(z,'w') as f:
                f.writestr('code/a.py','x=1\n')
            result=extract_checked(z,base/'dest')
            self.assertEqual(result['files'],1)
            self.assertEqual((base/'dest'/'code'/'a.py').read_text(),'x=1\n')
            with self.assertRaises(UnsafeWorkspace):extract_checked(z,base/'dest')


class EffectRecoveryTests(unittest.TestCase):
    @staticmethod
    def h(v='payload'):
        import hashlib
        return hashlib.sha256(v.encode()).hexdigest()

    def test_restart_holds_indeterminate_external_effect(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=EffectLedger(Path(td))
            with ledger.ownership() as owner:
                token=ledger.prepare(owner,'remote:change:1','non_idempotent_external',self.h())
                self.assertTrue(token.startswith('1:'))
                ledger.dispatch(owner,'remote:change:1')
                with self.assertRaises(MissionHold):ledger.dispatch(owner,'remote:change:1')
            with ledger.ownership() as owner:
                self.assertEqual(owner.epoch,2)
                self.assertEqual(ledger.snapshot()['hold_uncertain'],['remote:change:1'])
                with self.assertRaises(MissionHold):
                    ledger.prepare(owner,'new-job','idempotent_write',self.h('new'))
                with self.assertRaises(MissionHold):
                    ledger.reconcile(owner,'remote:change:1',was_applied=True,
                                     evidence_sha256=self.h('readback'))
                ledger.reconcile(owner,'remote:change:1',was_applied=True,
                     evidence_sha256=self.h('readback'),
                     independent_check=lambda eid,applied,proof: eid=='remote:change:1' and applied and proof==self.h('readback'))
                self.assertTrue(ledger.snapshot()['replay_safe'])
                with self.assertRaises(MissionHold):
                    ledger.prepare(owner,'remote:change:1','idempotent_write',self.h())
                ledger.prepare(owner,'new-job','idempotent_write',self.h('new'))

    def test_mission_denies_resume_with_uncertain_external_effect(self):
        from nomad.codeworld import make_codeworld_tasks
        from nomad.mission_runtime import initialize, run, inspect
        with tempfile.TemporaryDirectory() as td:
            task=next(x for x in make_codeworld_tasks(9117,per_family=1) if '-bin-' in x.task_id)
            root=Path(td)/'mission'
            initialize(root,task)
            ledger=EffectLedger(root/'effects',create=False)
            with ledger.ownership() as owner:
                ledger.prepare(owner,'payment-1','non_idempotent_external',self.h('pay'))
                ledger.dispatch(owner,'payment-1')
            with self.assertRaises(MissionHold):run(root,trusted_fixture=True)
            with self.assertRaises(MissionHold):inspect(root)
            self.assertEqual((root/'workspace'/'solution.py').read_text(),task.source)

    def test_real_hard_crash_fences_unknown_remote_effect(self):
        with tempfile.TemporaryDirectory() as td:
            script = """from nomad.effects import EffectLedger
from pathlib import Path
import hashlib,os,sys
log=EffectLedger(Path(sys.argv[1]))
with log.ownership() as owner:
    log.prepare(owner,'remote:receipt:one','non_idempotent_external',hashlib.sha256(b'payload').hexdigest())
    log.dispatch(owner,'remote:receipt:one')
    os._exit(71)
"""
            root=Path(__file__).resolve().parents[1]
            from nomad.supervised import minimal_env
            p=subprocess.run([sys.executable,'-c',script,td],cwd=root,
                              env=minimal_env({'PYTHONPATH':str(root)}),
                              capture_output=True,timeout=8)
            self.assertEqual(p.returncode,71)
            ledger=EffectLedger(Path(td),create=False)
            with ledger.ownership() as owner:
                self.assertEqual(owner.epoch,2)
                self.assertEqual(ledger.snapshot()['hold_uncertain'],['remote:receipt:one'])
                with self.assertRaises(MissionHold):
                    ledger.dispatch(owner,'remote:receipt:one')

    def test_missing_effect_ledger_fails_closed(self):
        from nomad.codeworld import make_codeworld_tasks
        from nomad.mission_runtime import initialize, run
        with tempfile.TemporaryDirectory() as td:
            task=next(x for x in make_codeworld_tasks(9117,per_family=1) if '-bin-' in x.task_id)
            root=Path(td)/'mission'
            initialize(root,task)
            (root/'effects'/'effects.jsonl').unlink()
            with self.assertRaises(MissionHold):run(root,trusted_fixture=True)

    def test_prepared_effect_can_be_canceled_but_never_reused(self):
        with tempfile.TemporaryDirectory() as td:
            l=EffectLedger(Path(td))
            with l.ownership() as o:
                l.prepare(o,'noop','non_idempotent_external',self.h())
                l.reconcile(o,'noop',was_applied=False,evidence_sha256=self.h('absent'),
                            independent_check=lambda *_: True)
                self.assertTrue(l.snapshot()['replay_safe'])
                with self.assertRaises(MissionHold):l.dispatch(o,'noop')

    def test_tampered_ledger_rejected_and_stale_owner_cannot_act(self):
        with tempfile.TemporaryDirectory() as td:
            l=EffectLedger(Path(td))
            with l.ownership() as o:
                l.prepare(o,'w1','read_only',self.h())
                stale=o
            with self.assertRaises(MissionHold):l.dispatch(stale,'w1')
            with l.ownership() as o:
                self.assertEqual(o.epoch,2)
            p=Path(td)/'effects.jsonl'
            p.write_bytes(p.read_bytes().replace(b'PREPARED',b'ALTERED!'))
            with self.assertRaises(MissionHold):l.snapshot()

if __name__=='__main__':unittest.main()
