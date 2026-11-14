"""Read-only NOMAD v0.15 release verifier. Does not regenerate manifests."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
MANIFEST=Path('results/RELEASE_MANIFEST_V015.json')


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
        if (rel==MANIFEST.as_posix() or rel.startswith('runs/') or rel.startswith('results/CI_') or
            any(part in ('__pycache__','.pytest_cache','.git','.mypy_cache') for part in p.parts) or
            p.suffix in ('.pyc','.pyo')):
            continue
        yield rel,p


def verify():
    record=json.loads((ROOT/MANIFEST).read_text(encoding='utf-8'))
    if record.get('schema')!='nomad.v0.15.manifest.v1':
        raise ValueError('unknown release manifest')
    expected=record['sha256_by_path']
    actual={name:sha(path) for name,path in tracked_files()}
    if set(expected)!=set(actual):
        omitted=sorted(set(actual)-set(expected));missing=sorted(set(expected)-set(actual))
        raise ValueError(f'file inventory changed; untracked={omitted[:10]} missing={missing[:10]}')
    mismatch=[k for k in expected if expected[k]!=actual[k]]
    if mismatch:raise ValueError('modified packaged content: '+repr(mismatch[:10]))
    if sha(ROOT/'baseline/NOMAD-v0.14.0.zip')!=record['predecessor_sha256']:
        raise ValueError('predecessor altered')
    if sha(ROOT/'vendor/BGR-v1.4.0-runtime.zip')!=record['bgr_runtime_sha256']:
        raise ValueError('original native Bitwork runtime altered')
    fps=json.loads((ROOT/'experiments/FINGERPRINT_V015.json').read_text())
    for rel, expected_sha in fps['sha256_by_path'].items():
        if sha(ROOT/rel)!=expected_sha:raise ValueError('research source fingerprint changed: '+rel)
    r={'schema':'nomad.v0.15.verifier.v1','status':'passed','files':len(actual),
       'research_sources':len(fps['sha256_by_path']),
       'predecessor_hash_verified':True,'bgr_runtime_hash_verified':True,
       'source_fingerprint_status':'verified post-development snapshot; not preregistration'}
    return r


def main():
    pa=argparse.ArgumentParser()
    pa.add_argument('--tests',action='store_true')
    pa.add_argument('--replay',action='store_true')
    args=pa.parse_args()
    verified=verify()
    if args.tests:
        c=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-q'],cwd=ROOT,check=False)
        if c.returncode:raise SystemExit('regression tests failed')
        verified['regression_tests']='passed'
    if args.replay:
        from scripts.run_recursion_v15 import run_all
        orig=json.loads((ROOT/'results/STUDY_V015.json').read_text())
        new=run_all()
        if new!=orig:raise SystemExit('research replay disagreed with sealed study')
        verified['research_replay']='passed (same known traces and synthetic seeds)'
    print(json.dumps(verified,indent=2))

if __name__=='__main__':main()
