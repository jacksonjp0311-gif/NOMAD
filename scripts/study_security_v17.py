"""Development-only recorder for LOCAL v0.17 security contracts.

Not a kernel/container acceptance certificate. Never overwrite a prior receipt.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=ROOT/'results/SECURITY_V017.json')
    a=p.parse_args()
    if a.output.exists():
        raise SystemExit('original security results exist; refuse overwrite')
    suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_security_v17')
    count=suite.countTestCases()
    completed=subprocess.run([sys.executable,'-B','-m','unittest','tests.test_security_v17','-q'],
                 cwd=ROOT,capture_output=True,timeout=45,check=False)
    if completed.returncode:
        sys.stderr.write((completed.stdout+completed.stderr).decode(errors='replace'))
        raise SystemExit('local adversarial regression tests failed')
    record={
        'schema':'nomad.security.local-study.v1', 'version':'0.17.0',
        'framework':'unittest', 'registered_test_count':count,
        'tests_passed':count, 'tests_failed':0,
        'run_output_sha256':hashlib.sha256(completed.stdout+completed.stderr).hexdigest(),
        'host_os':platform.system(), 'python_major_minor':'.'.join(map(str,sys.version_info[:2])),
        'docker_binary_present':shutil.which('docker') is not None,
        'adversarial_kernel_container_execution':'NOT_TESTED',
        'native_windows_acceptance':'NOT_TESTED',
        'untrusted_host_fallback':'DENY',
        'external_effect_unknown_outcome':'HOLD',
        'external_effect_real_remote_service':'NOT_TESTED',
        'witness_cryptographic_attestation':'NOT_IMPLEMENTED',
        'native_BGR_real_coding_advantage':'NOT_ESTABLISHED',
        'limitations':'Tests include POSIX process-group cleanup, mocked Docker command/cleanup, and real hard-crash ledger recovery. Not an OS container escape test.'
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps(record,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
