"""Windows process-tree supervision for trusted commands, NOT a sandbox.

A trusted, isolated-Python launcher waits on a pipe until it belongs to a Job
Object. Only then may it start the requested command. This closes the ordinary
spawn-before-assignment race without undocumented thread APIs. The unnamed,
non-inheritable Job handle is owned by the supervisor; owner death kills its
members. WMI/service-created processes are outside this contract, so unfamiliar
code must still use the Docker boundary.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Mapping, Sequence


class JobUnavailable(OSError):
    """No requested command was authorized to start without a Job Object."""


class _BasicLimits(ctypes.Structure):
    _fields_ = [('ProcessTime', ctypes.c_int64), ('JobTime', ctypes.c_int64),
                ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD),
                ('SchedulingClass', wintypes.DWORD)]


class _IOCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ('ReadOperations', 'WriteOperations', 'OtherOperations',
                 'ReadBytes', 'WriteBytes', 'OtherBytes')]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', _BasicLimits), ('IoInfo', _IOCounters),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [('TotalUserTime', ctypes.c_int64), ('TotalKernelTime', ctypes.c_int64),
                ('ThisPeriodUserTime', ctypes.c_int64), ('ThisPeriodKernelTime', ctypes.c_int64),
                ('TotalPageFaultCount', wintypes.DWORD), ('TotalProcesses', wintypes.DWORD),
                ('ActiveProcesses', wintypes.DWORD), ('TotalTerminatedProcesses', wintypes.DWORD)]


class _ProcessIds(ctypes.Structure):
    _fields_ = [('Assigned', wintypes.DWORD), ('Count', wintypes.DWORD),
                ('Ids', ctypes.c_size_t * 256)]


class WindowsJob:
    def __init__(self, *, memory_mib: int = 1024, max_processes: int = 64):
        if os.name != 'nt':
            raise JobUnavailable('Windows Job Objects require Windows')
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        api = self.api
        api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        api.CreateJobObjectW.restype = wintypes.HANDLE
        api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        api.SetInformationJobObject.restype = wintypes.BOOL
        api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        api.AssignProcessToJobObject.restype = wintypes.BOOL
        api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        api.TerminateJobObject.restype = wintypes.BOOL
        api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                 wintypes.DWORD, ctypes.c_void_p]
        api.QueryInformationJobObject.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.WaitForSingleObject.restype = wintypes.DWORD
        self.handle = api.CreateJobObjectW(None, None)
        if not self.handle:
            raise JobUnavailable(ctypes.get_last_error(), 'CreateJobObjectW failed')
        limits = _ExtendedLimits()
        # KILL_ON_JOB_CLOSE | ACTIVE_PROCESS | JOB_MEMORY; no breakaway permission.
        limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x0008 | 0x0200
        limits.BasicLimitInformation.ActiveProcessLimit = max_processes
        limits.JobMemoryLimit = memory_mib * 1024 * 1024
        if not api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            self.close()
            raise JobUnavailable(error, 'SetInformationJobObject failed')

    def assign(self, process: subprocess.Popen) -> None:
        if not self.api.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            raise JobUnavailable(ctypes.get_last_error(), 'AssignProcessToJobObject failed; command denied')

    def terminate(self) -> str:
        # ActiveProcesses reaches zero slightly before termination handles are
        # signaled on Windows. Retain handles so cleanup verifies both facts.
        ids = _ProcessIds()
        handles = []
        listed = bool(self.api.QueryInformationJobObject(self.handle, 3, ctypes.byref(ids),
                                                         ctypes.sizeof(ids), None))
        if listed:
            for pid in ids.Ids[:ids.Count]:
                handle = self.api.OpenProcess(0x00100000, False, pid)
                if handle:
                    handles.append(handle)
                elif ctypes.get_last_error() != 87:  # An already exited process.
                    listed = False
        try:
            if not self.api.TerminateJobObject(self.handle, 124) or not listed:
                return 'windows-job-cleanup-unconfirmed'
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                accounting = _Accounting()
                if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting),
                                                          ctypes.sizeof(accounting), None):
                    return 'windows-job-cleanup-unconfirmed'
                if accounting.ActiveProcesses == 0 and all(
                        self.api.WaitForSingleObject(handle, 0) == 0 for handle in handles):
                    return 'windows-job-empty-confirmed'
                time.sleep(0.01)
            return 'windows-job-cleanup-unconfirmed'
        finally:
            for handle in handles:
                self.api.CloseHandle(handle)

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def metrics(self) -> dict:
        accounting = _Accounting()
        limits = _ExtendedLimits()
        if (not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting),
                                                   ctypes.sizeof(accounting), None)
                or not self.api.QueryInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                                          ctypes.sizeof(limits), None)):
            return {'available': False}
        return {'available': True, 'scope': 'Windows supervised process tree',
                'cpu_user_s': accounting.TotalUserTime / 10_000_000,
                'cpu_kernel_s': accounting.TotalKernelTime / 10_000_000,
                'peak_job_commit_bytes': limits.PeakJobMemoryUsed,
                'total_processes': accounting.TotalProcesses,
                'active_processes_at_cleanup': accounting.ActiveProcesses}


_LAUNCHER = '''import json,subprocess,sys
if sys.stdin.buffer.readline() != b"NOMAD_JOB_READY\\n":
    raise SystemExit(125)
command=json.loads(sys.argv[1])
try:
    result=subprocess.run(command,stdin=subprocess.DEVNULL,shell=False,check=False)
except OSError as error:
    print(str(error),file=sys.stderr)
    raise SystemExit(126)
raise SystemExit(result.returncode)
'''


def launch_in_job(argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> tuple[subprocess.Popen, WindowsJob]:
    job = WindowsJob()
    process = None
    try:
        # -I excludes the source directory/user site and -S disables site startup.
        process = subprocess.Popen([sys.executable, '-I', '-S', '-c', _LAUNCHER, json.dumps(list(argv))],
                                   cwd=str(cwd), env=dict(env), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        job.assign(process)
        assert process.stdin is not None
        process.stdin.write(b'NOMAD_JOB_READY\n')
        process.stdin.flush()
        process.stdin.close()
        return process, job
    except BaseException:
        if process is not None:
            process.kill()
            process.wait(timeout=3)
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
        job.close()
        raise
