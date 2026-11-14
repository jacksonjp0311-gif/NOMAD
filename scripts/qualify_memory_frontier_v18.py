"""Controlled native Windows accounting diagnosis, never a strict-peak proof.

Reserve virtual addresses, attempt one commit, and compare kernel counters and
the region's state. Only this checked-in trusted fixture executes on the host.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nomad.supervised import run_supervised
from scripts.qualify_isolation_v18 import canonical_digest, qualification_host_identity

CHILD = r'''import ctypes,json,sys
from ctypes import wintypes
sys.path.insert(0,sys.argv[2])
from nomad.windows_job import _ExtendedLimits
class MemoryUsage(ctypes.Structure):
    _fields_=[('JobMemory',ctypes.c_uint64),('PeakJobMemoryUsed',ctypes.c_uint64)]
class ProcessCounters(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ('peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private','private_ws')]+[('shared_commit',ctypes.c_uint64)]
class Region(ctypes.Structure):
    _fields_=[('BaseAddress',ctypes.c_void_p),('AllocationBase',ctypes.c_void_p),('AllocationProtect',wintypes.DWORD),('PartitionId',wintypes.WORD),('RegionSize',ctypes.c_size_t),('State',wintypes.DWORD),('Protect',wintypes.DWORD),('Type',wintypes.DWORD)]
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.QueryInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p]
kernel.QueryInformationJobObject.restype=wintypes.BOOL
kernel.GetCurrentProcess.restype=wintypes.HANDLE
kernel.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,wintypes.DWORD,wintypes.DWORD]
kernel.VirtualAlloc.restype=ctypes.c_void_p
kernel.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,wintypes.DWORD]
kernel.VirtualFree.restype=wintypes.BOOL
kernel.VirtualQuery.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t]
kernel.VirtualQuery.restype=ctypes.c_size_t
psapi=ctypes.WinDLL('psapi',use_last_error=True)
psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
def snapshot():
    extended=_ExtendedLimits(); usage=MemoryUsage(); process=ProcessCounters(); process.cb=ctypes.sizeof(process)
    if not kernel.QueryInformationJobObject(None,9,ctypes.byref(extended),ctypes.sizeof(extended),None): raise ctypes.WinError(ctypes.get_last_error())
    # Class28 is present in Microsoft's hcsshim source; unsupported platforms
    # report that fact instead of fabricating an alternative counter.
    usage_ok=bool(kernel.QueryInformationJobObject(None,28,ctypes.byref(usage),ctypes.sizeof(usage),None))
    usage_error=0 if usage_ok else ctypes.get_last_error()
    process_ok=bool(psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(process),ctypes.sizeof(process)))
    process_error=0 if process_ok else ctypes.get_last_error()
    return {'job_limit_bytes':extended.JobMemoryLimit,'extended_peak_job_bytes':extended.PeakJobMemoryUsed,'extended_peak_process_bytes':extended.PeakProcessMemoryUsed,
        'memory_usage_class28':{'available':usage_ok,'winerror':usage_error,'current_job_bytes':usage.JobMemory if usage_ok else None,'peak_job_bytes':usage.PeakJobMemoryUsed if usage_ok else None},
        'process_ex2':{'available':process_ok,'winerror':process_error,'private_commit_bytes':process.private if process_ok else None,'peak_private_commit_bytes':process.peak_pagefile if process_ok else None,'shared_commit_bytes':process.shared_commit if process_ok else None,'working_set_bytes':process.ws if process_ok else None}}
def region(address):
    value=Region()
    if not kernel.VirtualQuery(address,ctypes.byref(value),ctypes.sizeof(value)): raise ctypes.WinError(ctypes.get_last_error())
    return {'state':value.State,'region_bytes':value.RegionSize,'protect':value.Protect}
size=int(sys.argv[1])*1024*1024
before=snapshot()
address=kernel.VirtualAlloc(None,size,0x2000,0x04)
if not address: raise ctypes.WinError(ctypes.get_last_error())
try:
    reserved=region(address)
    after_reserve=snapshot()
    committed=kernel.VirtualAlloc(address,size,0x1000,0x04)
    error=0 if committed else ctypes.get_last_error()
    after_commit=snapshot()
    observed_region=region(address)
finally:
    if not kernel.VirtualFree(address,0,0x8000): raise ctypes.WinError(ctypes.get_last_error())
after_release=snapshot()
print(json.dumps({'requested_bytes':size,'commit_succeeded':bool(committed),'commit_winerror':error,'before':before,'after_reserve':after_reserve,'after_commit':after_commit,'after_release':after_release,'reserved_region':reserved,'after_commit_region':observed_region},sort_keys=True))
'''


def source_identity() -> dict:
    names = ('nomad/windows_job.py', 'nomad/supervised.py',
             'scripts/qualify_memory_frontier_v18.py')
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def probe(request_mib: int) -> dict:
    if type(request_mib) is not int or request_mib not in (32, 128, 256):
        raise ValueError('controlled requests are exactly 32,128,256 MiB')
    with tempfile.TemporaryDirectory(prefix='nomad-memory-frontier-') as directory:
        observed = run_supervised([sys.executable, '-I', '-S', '-c', CHILD, str(request_mib), str(ROOT)],
            cwd=Path(directory), timeout_s=8, max_output_bytes=16384,
            windows_memory_mib=96, windows_max_processes=6)
    transport = asdict(observed)
    transport['output'] = observed.output.decode('utf-8', errors='replace')
    result = {'request_mib': request_mib, 'transport': transport, 'status': 'HOLD'}
    if (observed.returncode != 0 or observed.timed_out or observed.truncated
            or observed.cleanup != 'windows-job-empty-confirmed'):
        result['reason'] = 'controlled native fixture or cleanup failed'
        return result
    value = json.loads(observed.output)
    result['observation'] = value
    expected_success = request_mib == 32
    correct = (value['commit_succeeded'] is expected_success
        and value['reserved_region']['state'] == 0x2000
        and value['after_commit_region']['state'] == (0x1000 if expected_success else 0x2000)
        and value['before']['job_limit_bytes'] == 96 * 1024 * 1024
        and (expected_success or value['commit_winerror'] in (8, 1455)))
    result['status'] = 'PASS' if correct else 'FAIL'
    result['scope'] = 'commit result and queried region state only; counters are observations, not acceptance criteria'
    return result


def qualify() -> dict:
    report = {'schema': 'nomad.memory-frontier-qualification.v18',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'host_identity': qualification_host_identity(),
              'source_sha256_before': source_identity(), 'cases': [],
              'strict_peak_counter_gate': 'HOLD', 'native_containment_gate': 'HOLD',
              'scope': 'trusted controlled reservation/commit experiments; no sampling-based strict maximum',
              'cloud_model_calls': 0}
    if os.name != 'nt':
        report['status'] = 'HOLD'
        report['reason'] = 'native Windows required'
    else:
        for repetition in range(2):
            for request in (32, 128, 256):
                case = probe(request)
                case['repetition'] = repetition
                report['cases'].append(case)
        report['status'] = ('FAIL' if any(case['status'] == 'FAIL' for case in report['cases']) else
                            'PASS' if all(case['status'] == 'PASS' for case in report['cases']) else 'HOLD')
    report['source_sha256_after'] = source_identity()
    report['source_stable'] = report['source_sha256_before'] == report['source_sha256_after']
    if not report['source_stable'] and report['status'] == 'PASS':
        report['status'] = 'HOLD'
    report['receipt_sha256'] = canonical_digest(report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('output exists; preserve the prior receipt')
    report = qualify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({key: report[key] for key in ('status', 'strict_peak_counter_gate',
          'native_containment_gate', 'source_stable')}, sort_keys=True))
    return 0 if report['status'] == 'PASS' else 3


if __name__ == '__main__':
    raise SystemExit(main())
