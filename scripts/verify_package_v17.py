"""NOMAD v0.17 read-only verifier. NEVER reconstructs or overwrites evidence."""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
MANIFEST=Path('results/RELEASE_MANIFEST_V017.json')
FREEZE=Path('experiments/SOURCE_FREEZE_V017.json')
PARENT_SHA='9f206af8f285a97f77d97642f183ba9f120e9b4cf2f6de914ab6446d5dcfb3b6'
BGR_SHA='93177c5cc628ac0c6426d8c612c0d769b86ed53cbd7b2a3f872d2706c601a8c2'
V15_SHA='088203e8af0b0c9886417c20a7eec2e75176b05b8313a527356def3b96a76544'


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda:f.read(1<<20),b''):
            h.update(buf)
    return h.hexdigest()


def tracked_files():
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT).as_posix()
        if (rel==MANIFEST.as_posix() or rel.startswith('runs/') or
            rel.startswith('results/CI_') or
            any(x in ('__pycache__','.pytest_cache','.git','.mypy_cache') for x in p.parts)
            or p.suffix in ('.pyc','.pyo')):
            continue
        yield rel,p


def verify() -> dict:
    original=json.loads((ROOT/MANIFEST).read_bytes())
    if original.get('schema')!='nomad.v0.17.manifest.v1':
        raise ValueError('unexpected v0.17 release manifest')
    expected=original['sha256_by_path']
    actual={rel:sha(path) for rel,path in tracked_files()}
    if set(actual)!=set(expected):
        raise ValueError('release file inventory differs; extra='+repr(sorted(set(actual)-set(expected))[:10])+
                         ' missing='+repr(sorted(set(expected)-set(actual))[:10]))
    bad=[rel for rel,actual_sha in actual.items() if actual_sha!=expected[rel]]
    if bad:raise ValueError('release bytes changed: '+repr(bad[:10]))
    if sha(ROOT/'baseline/NOMAD-v0.16.0.zip')!=PARENT_SHA:
        raise ValueError('v0.16 predecessor changed')
    if sha(ROOT/'vendor/BGR-v1.4.0-runtime.zip')!=BGR_SHA:
        raise ValueError('original Bitwork runtime changed')
    with zipfile.ZipFile(ROOT/'baseline/NOMAD-v0.16.0.zip') as z:
        if hashlib.sha256(z.read('NOMAD-v0.16.0/baseline/NOMAD-v0.15.0.zip')).hexdigest()!=V15_SHA:
            raise ValueError('nested v0.15 predecessor changed')
    freeze=json.loads((ROOT/FREEZE).read_bytes())
    if freeze.get('schema')!='nomad.v0.17.source-freeze.v1':
        raise ValueError('missing v0.17 source freeze')
    for rel,v in freeze['sha256_by_path'].items():
        if sha(ROOT/rel)!=v:raise ValueError('frozen v0.17 source changed: '+rel)
    study=json.loads((ROOT/'results/SECURITY_V017.json').read_bytes())
    gates=json.loads((ROOT/'results/GATES_V017.json').read_bytes())
    if (study['registered_test_count'] < 19 or study['tests_passed'] != study['registered_test_count']
        or study['tests_failed']!=0 or
        gates['engineering_controls']!='PASS' or gates['adversarial_kernel_isolation']!='HOLD'
        or gates['windows_target_acceptance']!='HOLD'
        or gates['production_release']!='HOLD'):
        raise ValueError('security gate record inconsistent')
    return {'schema':'nomad.v0.17.verification.v1','status':'passed_engineering_controls_only',
            'tracked_files':len(actual),'frozen_sources':len(freeze['sha256_by_path']),
            'targeted_security_tests_recorded':study['tests_passed'],
            'parent_v16_sha256':PARENT_SHA,'original_bgr_sha256':BGR_SHA,
            'nested_v15_verified':True,'native_docker_kernel_isolation':'HOLD',
            'native_windows_acceptance':'HOLD','remote_effect_exactly_once':'HOLD',
            'external_transfer_and_bgr_coding_advantage':'HOLD',
            'production_promotion':'HOLD'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--tests',action='store_true',help='Run all inherited and new tests')
    p.add_argument('--security',action='store_true',help='Rerun security contract tests')
    p.add_argument('--smoke',action='store_true',help='Run one trusted fixture mission')
    args=p.parse_args()
    report=verify()
    if args.security:
        x=subprocess.run([sys.executable,'-B','-m','unittest','tests.test_security_v17','-q'],
                         cwd=ROOT,timeout=60,check=False)
        if x.returncode:raise SystemExit('security tests failed')
        report['security_contract_rerun']='passed'
    if args.tests:
        x=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-q'],
                         cwd=ROOT,timeout=480,check=False)
        if x.returncode:raise SystemExit('regressions failed')
        report['complete_regressions']='passed'
    if args.smoke:
        from nomad.codeworld import make_codeworld_tasks
        from nomad.mission_runtime import initialize,run
        with tempfile.TemporaryDirectory(prefix='nomad-v17-smoke-') as d:
            task=next(t for t in make_codeworld_tasks(9117,per_family=1) if '-bin-' in t.task_id)
            goal=Path(d)/'mission'
            initialize(goal,task)
            result=run(goal,trusted_fixture=True)
            if result['status']!='completed':raise ValueError('trusted fixture smoke failed')
        report['trusted_fixture_witness_smoke']='passed'
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
