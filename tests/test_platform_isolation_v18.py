"""Native Windows supervision and portable intake contracts.

Docker mocks here are contract tests, never native containment evidence.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from nomad.archive_guard import extract_checked
from nomad.isolation import (IsolationUnavailable, SandboxPolicy, UnsafeWorkspace,
                             cleanup_isolated, docker_arguments, docker_preflight, run_isolated,
                             snapshot_source)
from nomad.supervised import ProcessResult, minimal_env, run_supervised

IMAGE = 'example.org/nomad/python@sha256:' + 'a' * 64


def result(data, code=0):
    output = json.dumps(data).encode()
    return ProcessResult(code, output, sha256(output).hexdigest(), False, False,
                         len(output), 1, 'windows-job-empty-confirmed')


def process_alive(pid):
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x00100000, False, pid)
    if not handle:
        return False
    try:
        return api.WaitForSingleObject(handle, 0) == 258
    finally:
        api.CloseHandle(handle)


@unittest.skipUnless(os.name == 'nt', 'native Windows Job Object tests')
class NativeWindowsSupervisionTests(unittest.TestCase):
    def test_parent_exit_cleans_live_descendant(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = ('import subprocess,sys,pathlib; '
                      'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]); '
                      'pathlib.Path(sys.argv[1]).write_text(str(p.pid))')
            observed = run_supervised([sys.executable, '-c', script, str(root / 'pid')],
                                      cwd=root, timeout_s=5)
            self.assertEqual(observed.returncode, 0)
            self.assertEqual(observed.cleanup, 'windows-job-empty-confirmed')
            self.assertTrue(observed.metrics['available'])
            self.assertEqual(observed.metrics['active_processes_at_cleanup'], 0)
            self.assertGreater(observed.metrics['peak_job_commit_bytes'], 0)
            self.assertFalse(process_alive(int((root / 'pid').read_text())))

    def test_timeout_cleans_target_and_descendant(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = ('import subprocess,sys,pathlib,time,os; '
                      'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]); '
                      'pathlib.Path(sys.argv[1]).write_text(str(os.getpid())+","+str(p.pid)); '
                      'time.sleep(30)')
            observed = run_supervised([sys.executable, '-c', script, str(root / 'pids')],
                                      cwd=root, timeout_s=1)
            self.assertTrue(observed.timed_out)
            self.assertEqual(observed.cleanup, 'windows-job-empty-confirmed')
            self.assertTrue(all(not process_alive(int(pid)) for pid in (root / 'pids').read_text().split(',')))

    def test_assignment_failure_does_not_start_target(self):
        from nomad.windows_job import JobUnavailable
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            marker = root / 'must-not-exist'
            with patch('nomad.windows_job.WindowsJob.assign', side_effect=JobUnavailable('injected assignment refusal')):
                with self.assertRaises(JobUnavailable):
                    run_supervised([sys.executable, '-c', 'import pathlib,sys;pathlib.Path(sys.argv[1]).touch()',
                                    str(marker)], cwd=root, timeout_s=5)
            self.assertFalse(marker.exists())

    def test_supervisor_hard_death_closes_job_and_kills_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pid_file = root / 'target.pid'
            script = '''import os,pathlib,sys,threading,time
from nomad.supervised import run_supervised
target=pathlib.Path(sys.argv[1])
def die():
    deadline=time.monotonic()+5
    while not target.exists() and time.monotonic()<deadline: time.sleep(0.02)
    os._exit(71)
threading.Thread(target=die,daemon=True).start()
run_supervised([sys.executable,'-c','import os,pathlib,sys,time;pathlib.Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(30)',str(target)],cwd=target.parent,timeout_s=20)
'''
            repo_root = Path(__file__).resolve().parents[1]
            observed = subprocess.run([sys.executable, '-c', script, str(pid_file)],
                                      cwd=repo_root, env=minimal_env({'PYTHONPATH': str(repo_root)}),
                                      capture_output=True, timeout=10)
            self.assertEqual(observed.returncode, 71, observed.stderr)
            self.assertTrue(pid_file.exists())
            pid = int(pid_file.read_text())
            deadline = time.monotonic() + 3
            while process_alive(pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(process_alive(pid))

    def test_native_junction_to_host_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'source'
            source.mkdir()
            (source / 'safe.py').write_text('x=1')
            outside = root / 'protected'
            outside.mkdir()
            (outside / 'sentinel').write_text('protected-host-bytes')
            junction = source / 'link'
            created = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(junction), str(outside)],
                                     capture_output=True, timeout=5)
            self.assertEqual(created.returncode, 0, created.stderr)
            try:
                with self.assertRaises(UnsafeWorkspace):
                    snapshot_source(source, root / 'snapshot', SandboxPolicy(IMAGE))
                self.assertFalse((root / 'snapshot').exists())
                self.assertEqual((outside / 'sentinel').read_text(), 'protected-host-bytes')
            finally:
                os.rmdir(junction)  # Remove only this link, never its target.


class PortableIntakeTests(unittest.TestCase):
    def test_uppercase_credentials_and_env_variants_are_rejected(self):
        for name in ('.ENV', '.env.production', 'SECRET.PEM', 'ID_RSA'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / 'source'
                source.mkdir()
                (source / name).write_text('credential')
                with self.assertRaises(UnsafeWorkspace):
                    snapshot_source(source, root / 'copy', SandboxPolicy(IMAGE))

    def test_zip_windows_aliases_and_case_collisions_are_rejected(self):
        for names in (['CON.txt'], ['a.py.'], ['a.py '], ['a.py', 'A.py'], ['a:b'],
                      ['x/LPT1'], ['x/COM\u00b9'], ['dir/a.py', 'DIR/b.py']):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                archive = root / 'bad.zip'
                with zipfile.ZipFile(archive, 'w') as handle:
                    for name in names:
                        handle.writestr(name, 'x=1')
                with self.assertRaises(UnsafeWorkspace):
                    extract_checked(archive, root / 'out')
                self.assertFalse((root / 'out').exists())

    def test_docker_policy_binds_entrypoint_digest_and_mount(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy = SandboxPolicy(IMAGE)
            args = docker_arguments(engine='docker', snapshot=root, image=IMAGE,
                                    name='nomad-' + 'a' * 24, command=['python', '-m', 'unittest'], policy=policy)
            self.assertEqual(args[args.index('--entrypoint') + 1], 'python')
            self.assertIn('--no-healthcheck', args)
            self.assertIn('--cgroupns=private', args)
            with self.assertRaises(ValueError):
                docker_arguments(engine='docker', snapshot=root, image=IMAGE.replace('a'*64, 'b'*64),
                                 name='nomad-' + 'a' * 24, command=['python'], policy=policy)
            comma = root / 'comma,path'
            comma.mkdir()
            with self.assertRaises(ValueError):
                docker_arguments(engine='docker', snapshot=comma, image=IMAGE,
                                 name='nomad-' + 'a' * 24, command=['python'], policy=policy)


class DockerPreflightContractTests(unittest.TestCase):
    def test_cleanup_removes_only_inspected_owned_container_id(self):
        name = 'nomad-' + 'a' * 24
        container_id = 'b' * 64
        with patch('nomad.isolation.sandbox_available', return_value=True), \
             patch('nomad.isolation.run_supervised', side_effect=[
                 result([{'Id': container_id, 'Config': {'Labels': {
                     'nomad.managed': 'v0.18', 'nomad.execution': name}}}]),
                 result({}), result('No such object: ' + name, code=1)]) as mocked:
            self.assertTrue(cleanup_isolated(name))
        self.assertEqual(mocked.call_args_list[1].args[0][-1], container_id)

    def test_cleanup_refuses_foreign_container_name_collision(self):
        with patch('nomad.isolation.sandbox_available', return_value=True), \
             patch('nomad.isolation.run_supervised', return_value=result([
                 {'Config': {'Labels': {'owner': 'someone-else'}}}])) as mocked:
            self.assertFalse(cleanup_isolated('nomad-' + 'a' * 24))
        self.assertEqual(mocked.call_count, 1)
        self.assertNotIn('rm', mocked.call_args.args[0])

    def test_daemon_preflight_is_not_containment_qualification(self):
        with patch('nomad.isolation.sandbox_available', return_value=True), \
             patch('nomad.isolation.run_supervised', side_effect=[
                 result({'OSType': 'linux', 'SecurityOptions': ['name=seccomp,profile=builtin'], 'ServerVersion': 'contract'}),
                 result([{'Os': 'linux', 'RepoDigests': [IMAGE], 'Config': {}}])]) as mocked:
            report = docker_preflight(SandboxPolicy(IMAGE))
        self.assertTrue(report['ready'])
        self.assertFalse(report['native_containment_qualified'])
        self.assertIn('--config', mocked.call_args_list[0].args[0])
        self.assertIn('--host', mocked.call_args_list[0].args[0])

    def test_incorrect_daemon_or_digest_or_volume_is_denied(self):
        cases = [({'OSType': 'windows'}, None),
                 ({'OSType': 'linux', 'SecurityOptions': []}, None),
                 ({'OSType': 'linux', 'SecurityOptions': ['name=seccomp']},
                  [{'Os': 'linux', 'RepoDigests': [], 'Config': {}}]),
                 ({'OSType': 'linux', 'SecurityOptions': ['name=seccomp']},
                  [{'Os': 'linux', 'RepoDigests': [IMAGE], 'Config': {'Volumes': {'/leak': {}}}}])]
        for daemon, image in cases:
            with self.subTest(daemon=daemon, image=image):
                replies = [result(daemon)] + ([] if image is None else [result(image)])
                with patch('nomad.isolation.sandbox_available', return_value=True), \
                     patch('nomad.isolation.run_supervised', side_effect=replies):
                    self.assertFalse(docker_preflight(SandboxPolicy(IMAGE))['ready'])

    def test_failed_preflight_never_dispatches_source(self):
        with tempfile.TemporaryDirectory() as td, \
             patch('nomad.isolation.sandbox_available', return_value=True), \
             patch('nomad.isolation.docker_preflight', return_value={'ready': False, 'reasons': ['no daemon']}), \
             patch('nomad.isolation.run_supervised') as dispatch:
            with self.assertRaises(IsolationUnavailable):
                run_isolated(Path(td), command=['python'], policy=SandboxPolicy(IMAGE))
            dispatch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
