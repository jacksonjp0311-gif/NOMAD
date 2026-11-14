"""Additional controlled Windows qualification; no unfamiliar host execution."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from nomad.isolation import SandboxPolicy
from nomad.supervised import minimal_env, run_supervised
from nomad.windows_job import WindowsJob
from tests.test_platform_isolation_v18 import process_alive

OBSERVATIONS = []
IMAGE = 'example.invalid/reviewed@sha256:' + 'a' * 64


def record(case, observed, **extra):
    payload = asdict(observed)
    payload['output'] = observed.output.decode('utf-8', errors='replace')
    OBSERVATIONS.append({'case': case, 'observation': payload, **extra})


@unittest.skipUnless(os.name == 'nt', 'native Windows qualification')
class NativeResourceQualification(unittest.TestCase):
    def test_job_memory_allocation_is_refused_at_declared_budget(self):
        script = '''import ctypes,json
from ctypes import wintypes
class Counters(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ('peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
psapi=ctypes.WinDLL('psapi',use_last_error=True)
kernel.GetCurrentProcess.restype=wintypes.HANDLE
kernel.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,wintypes.DWORD,wintypes.DWORD]
kernel.VirtualAlloc.restype=ctypes.c_void_p
kernel.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,wintypes.DWORD]
kernel.VirtualFree.restype=wintypes.BOOL
psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
process=kernel.GetCurrentProcess()
before=Counters();before.cb=ctypes.sizeof(before)
after=Counters();after.cb=ctypes.sizeof(after)
blocks=[];error=None;denied=False
try:
    for _ in range(20):
        assert psapi.GetProcessMemoryInfo(process,ctypes.byref(before),ctypes.sizeof(before))
        address=kernel.VirtualAlloc(None,8*1024*1024,0x3000,0x04)
        if not address:
            error=ctypes.get_last_error()
            assert psapi.GetProcessMemoryInfo(process,ctypes.byref(after),ctypes.sizeof(after))
            denied=True
            break
        blocks.append(address)
finally:
    for address in blocks: assert kernel.VirtualFree(address,0,0x8000)
print(json.dumps({'allocation_denied':denied,'allocated_mib':len(blocks)*8,'winerror':error,'private_usage_before_failed_commit':before.private,'private_usage_after_failed_commit':after.private}))
'''
        with tempfile.TemporaryDirectory() as td:
            observed = run_supervised([sys.executable, '-I', '-S', '-c', script],
                                      cwd=Path(td), timeout_s=10, max_output_bytes=4096,
                                      windows_memory_mib=96, windows_max_processes=6)
        record('native_memory_limit', observed, declared_memory_mib=96)
        self.assertEqual(observed.returncode, 0, observed.output)
        output = json.loads(observed.output)
        self.assertTrue(output['allocation_denied'])
        self.assertLess(output['allocated_mib'], 96)
        self.assertIn(output['winerror'], (8, 1455))
        self.assertEqual(output['private_usage_after_failed_commit'], output['private_usage_before_failed_commit'])
        self.assertEqual(observed.metrics['configured_job_memory_bytes'], 96 * 1024 * 1024)
        # The native peak counter can include behavior not explained by current
        # commit measurements. Keep its raw value; never reinterpret it as a
        # proven maximum of successfully committed bytes.
        self.assertEqual(observed.cleanup, 'windows-job-empty-confirmed')

    def test_job_process_creation_is_refused_at_declared_budget(self):
        script = '''import json,subprocess,sys
children=[]
denied=False
error=None
try:
    for _ in range(12):
        try: children.append(subprocess.Popen([sys.executable,'-I','-S','-c','import time;time.sleep(20)']))
        except OSError as exc:
            denied=True;error=exc.winerror;break
finally:
    for child in children:
        if child.poll() is None: child.kill()
    for child in children: child.wait(timeout=3)
print(json.dumps({'creation_denied':denied,'children_started':len(children),'winerror':error}))
'''
        with tempfile.TemporaryDirectory() as td:
            observed = run_supervised([sys.executable, '-I', '-S', '-c', script],
                                      cwd=Path(td), timeout_s=10, max_output_bytes=4096,
                                      windows_memory_mib=256, windows_max_processes=6)
        record('native_process_limit', observed, declared_process_limit=6)
        self.assertEqual(observed.returncode, 0, observed.output)
        output = json.loads(observed.output)
        self.assertTrue(output['creation_denied'])
        self.assertEqual(output['children_started'], 4)  # Launcher + target consume two slots.
        self.assertEqual(observed.metrics['configured_active_process_limit'], 6)
        self.assertEqual(observed.cleanup, 'windows-job-empty-confirmed')

    def test_explicit_process_breakaway_is_denied(self):
        script = '''import json,subprocess,sys,pathlib
denied=False
error=None
try:
    child=subprocess.Popen([sys.executable,'-I','-S','-c','import pathlib,sys;pathlib.Path(sys.argv[1]).touch()',sys.argv[1]],creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB)
except OSError as exc:
    denied=True;error=exc.winerror
else:
    child.wait(timeout=3)
print(json.dumps({'breakaway_denied':denied,'winerror':error}))
'''
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / 'escaped-process-marker'
            observed = run_supervised([sys.executable, '-I', '-S', '-c', script, str(marker)],
                                      cwd=Path(td), timeout_s=8, max_output_bytes=4096)
            escaped = marker.exists()
        record('native_breakaway_denied', observed, escaped_marker_created=escaped)
        self.assertEqual(observed.returncode, 0, observed.output)
        self.assertEqual(json.loads(observed.output), {'breakaway_denied': True, 'winerror': 5})
        self.assertFalse(escaped)
        self.assertEqual(observed.cleanup, 'windows-job-empty-confirmed')

    def test_owner_death_before_assignment_cannot_release_target(self):
        code = '''import os,pathlib,sys
from nomad.windows_job import WindowsJob
from nomad.supervised import run_supervised
def die_before_assignment(self,process):
    pathlib.Path(sys.argv[1]).write_text(str(process.pid))
    os._exit(73)
WindowsJob.assign=die_before_assignment
run_supervised([sys.executable,'-c','import pathlib,sys;pathlib.Path(sys.argv[1]).touch()',sys.argv[2]],cwd=pathlib.Path(sys.argv[1]).parent,timeout_s=10)
'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            launcher = root / 'launcher.pid'
            marker = root / 'target.marker'
            repo = Path(__file__).resolve().parents[1]
            observed = subprocess.run([sys.executable, '-c', code, str(launcher), str(marker)],
                                      cwd=repo, env=minimal_env({'PYTHONPATH': str(repo)}),
                                      capture_output=True, timeout=10)
            self.assertEqual(observed.returncode, 73, observed.stderr)
            pid = int(launcher.read_text())
            deadline = time.monotonic() + 3
            while process_alive(pid) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(process_alive(pid))
            self.assertFalse(marker.exists())
            OBSERVATIONS.append({'case': 'owner_death_before_assignment', 'returncode': observed.returncode,
                                 'launcher_exited': True, 'target_started': False})

    def test_repeated_abrupt_owner_death_leaves_no_targets(self):
        code = '''import ctypes,json,os,pathlib,sys,threading,time
from nomad.supervised import run_supervised
from nomad.windows_job import WindowsJob,_ProcessIds
target=pathlib.Path(sys.argv[1])
jobs=[]
original_assign=WindowsJob.assign
def observe_job(self,process):
    original_assign(self,process)
    jobs.append(self)
WindowsJob.assign=observe_job
def die():
    deadline=time.monotonic()+5
    while not target.exists() and time.monotonic()<deadline: time.sleep(0.01)
    ids=_ProcessIds()
    assert jobs and jobs[0].api.QueryInformationJobObject(jobs[0].handle,3,ctypes.byref(ids),ctypes.sizeof(ids),None)
    pathlib.Path(str(target)+'.job').write_text(json.dumps(list(ids.Ids[:ids.Count])))
    os._exit(74)
threading.Thread(target=die,daemon=True).start()
run_supervised([sys.executable,'-c','import os,pathlib,sys,time;pathlib.Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(20)',str(target)],cwd=target.parent,timeout_s=15)
'''
        repo = Path(__file__).resolve().parents[1]
        for iteration in range(3):
            with self.subTest(iteration=iteration), tempfile.TemporaryDirectory() as td:
                target = Path(td) / 'target.pid'
                observed = subprocess.run([sys.executable, '-c', code, str(target)], cwd=repo,
                                          env=minimal_env({'PYTHONPATH': str(repo)}),
                                          capture_output=True, timeout=10)
                self.assertEqual(observed.returncode, 74, observed.stderr)
                pids = json.loads(Path(str(target) + '.job').read_text())
                self.assertIn(int(target.read_text()), pids)
                deadline = time.monotonic() + 3
                while any(process_alive(pid) for pid in pids) and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(any(process_alive(pid) for pid in pids))
                OBSERVATIONS.append({'case': 'repeated_owner_death', 'iteration': iteration,
                                     'returncode': observed.returncode, 'target_exited': True,
                                     'observed_job_members': len(pids), 'all_observed_members_exited': True})


class BudgetValidationQualification(unittest.TestCase):
    def test_docker_hold_receipt_binds_current_host_source_without_claiming_pass(self):
        from scripts.qualify_isolation_v18 import canonical_digest, qualify, qualification_host_identity
        report = qualify(None)
        body = {key: value for key, value in report.items() if key != 'receipt_sha256'}
        self.assertEqual(report['receipt_sha256'], canonical_digest(body))
        self.assertEqual(report['host_identity_sha256'], canonical_digest(qualification_host_identity()))
        self.assertEqual(report['source_sha256_before'], report['source_sha256_after'])
        self.assertEqual(report['native_containment_gate'], 'HOLD')
        self.assertEqual(report['cases'], [])

    def test_invalid_job_budgets_are_denied_before_native_api(self):
        for kwargs in ({'memory_mib': 0}, {'memory_mib': True}, {'memory_mib': 96.5},
                       {'memory_mib': 4097}, {'max_processes': 1}, {'max_processes': True},
                       {'max_processes': 257}, {'max_processes': 6.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                WindowsJob(**kwargs)

    def test_invalid_sandbox_count_types_are_denied(self):
        for kwargs in ({'memory_mib': 128.5}, {'pids_limit': True}, {'max_files': 1.5},
                       {'max_total_bytes': 1024.5}, {'timeout_s': True}, {'cpus': True},
                       {'timeout_s': '10'}, {'cpus': float('nan')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                SandboxPolicy(image=IMAGE, **kwargs).validate()

    def test_invalid_supervision_limits_are_denied(self):
        with tempfile.TemporaryDirectory() as td:
            for kwargs in ({'timeout_s': True}, {'timeout_s': '1'},
                           {'timeout_s': 1, 'max_output_bytes': True},
                           {'timeout_s': 1, 'max_output_bytes': 1024.5}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    run_supervised([sys.executable, '-c', 'pass'], cwd=Path(td), **kwargs)


if __name__ == '__main__':
    unittest.main()
