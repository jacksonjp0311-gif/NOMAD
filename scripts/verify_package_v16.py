"""NOMAD v0.16 read-only verifier: checks original package bytes first.

It never rebuilds a manifest, alters source, or rewrites frozen study results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
MANIFEST=Path('results/RELEASE_MANIFEST_V016.json')
PARENT_SHA='088203e8af0b0c9886417c20a7eec2e75176b05b8313a527356def3b96a76544'
BGR_SHA='93177c5cc628ac0c6426d8c612c0d769b86ed53cbd7b2a3f872d2706c601a8c2'
V14_SHA='22c218597f5fa1cfc4003fc7694daac420ac42d0603feaeb8130ade6ef2619ea'


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def tracked_files():
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT).as_posix()
        if (rel==MANIFEST.as_posix() or rel.startswith('runs/') or
            rel.startswith('results/CI_') or
            any(x in ('__pycache__','.pytest_cache','.git','.mypy_cache') for x in p.parts) or
            p.suffix in ('.pyc','.pyo')):
            continue
        yield rel,p


def verify()->dict:
    record=json.loads((ROOT/MANIFEST).read_text())
    if record.get('schema')!='nomad.v0.16.manifest.v1':
        raise ValueError('unexpected manifest schema')
    expected=record['sha256_by_path']
    actual={rel:sha(p) for rel,p in tracked_files()}
    if set(actual)!=set(expected):
        raise ValueError('file inventory mismatch; extra '+repr(sorted(set(actual)-set(expected))[:5])+
                         '; missing '+repr(sorted(set(expected)-set(actual))[:5]))
    diffs=[rel for rel in expected if expected[rel]!=actual[rel]]
    if diffs:raise ValueError('file changed since sealing: '+str(diffs[:5]))
    parent=ROOT/'baseline/NOMAD-v0.15.0.zip'
    bgr=ROOT/'vendor/BGR-v1.4.0-runtime.zip'
    if sha(parent)!=PARENT_SHA or sha(bgr)!=BGR_SHA:
        raise ValueError('parent or native BGR bytes do not match verified predecessor')
    with zipfile.ZipFile(parent) as z:
        nested='NOMAD-v0.15.0/baseline/NOMAD-v0.14.0.zip'
        if hashlib.sha256(z.read(nested)).hexdigest()!=V14_SHA:
            raise ValueError('nested predecessor no longer matches v0.15 release')
    freeze=json.loads((ROOT/'experiments/FREEZE_V016.json').read_text())
    for rel,exp in freeze['sha256_by_path'].items():
        if sha(ROOT/rel)!=exp:raise ValueError('registered source modified: '+rel)
    from scripts.audit_mission_v16 import audit
    audited=audit(ROOT/'results/v016')
    old=json.loads((ROOT/'results/AUDIT_V016.json').read_text())
    if old!=audited:raise ValueError('frozen independent audit differs from re-evaluation')
    study=json.loads((ROOT/'results/STUDY_V016.json').read_text())
    if (study['cases']!=6 or study['completed_after_restart']!=6 or
        study['structurally_identical_replays']!=6 or
        study['same_committed_source']!=6 or
        study['logical_action_uniqueness']!=6):
        raise ValueError('registered mission-continuity study failed')
    return {'schema':'nomad.v0.16.verification.v1','status':'passed',
            'tracked_files':len(actual),'frozen_sources':len(freeze['sha256_by_path']),
            'parent_v15_sha256':PARENT_SHA,'original_BGR_runtime_sha256':BGR_SHA,
            'nested_v14_archive_verified':True,'independent_study_audit':audited,
            'authority':'engineering continuity only; scientific and production gates HOLD'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tests',action='store_true')
    parser.add_argument('--audit',action='store_true',help='Also show independently reconstructed audit (always checked)')
    parser.add_argument('--smoke',action='store_true',help='Run new disposable trusted mission')
    a=parser.parse_args()
    result=verify()
    if a.tests:
        p=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-q'],cwd=ROOT,check=False)
        if p.returncode:raise SystemExit('regressions failed')
        result['regressions']='passed'
    if a.smoke:
        import tempfile
        from nomad.codeworld import make_codeworld_tasks
        from nomad.mission_runtime import initialize,run
        with tempfile.TemporaryDirectory(prefix='nomad-v16-verify-') as td:
            task=next(x for x in make_codeworld_tasks(9117,per_family=1) if '-bin-' in x.task_id)
            rt=Path(td)/'task'
            initialize(rt,task)
            check=run(rt,trusted_fixture=True)
            if check['status']!='completed':raise ValueError('smoke mission failed')
        result['real_unittest_witness_smoke']='passed'
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
