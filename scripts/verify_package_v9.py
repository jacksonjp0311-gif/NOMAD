"""Verify NOMAD INQUIRY pre-existing package evidence BEFORE executing code.

Intentionally never regenerates or overwrites the shipped manifest, study,
receipts, or gate report. Do not call this on untrusted extracted code: it can
optionally execute tests with --tests/--audit, so use sandbox isolation.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v9 import assemble_runs, FROZEN_EVAL_SEEDS


def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def scan()->dict[str,str]:
    found={}
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT).as_posix()
        if rel=='results/RELEASE_MANIFEST.json' or rel.startswith('.git/') or '__pycache__' in rel or rel.endswith('.pyc'):
            continue
        found[rel]=digest(p)
    return dict(sorted(found.items()))


def verify()->dict[str,object]:
    errors=[]
    manifest=json.loads((ROOT/'results/RELEASE_MANIFEST.json').read_text())
    expected=manifest['files']; actual=scan()
    for path in sorted(set(actual)|set(expected)):
        if expected.get(path)!=actual.get(path):errors.append(f'manifest mismatch: {path}')
    plan=json.loads((ROOT/'experiments/PLAN_V009.json').read_text())
    amendment=json.loads((ROOT/'experiments/HARNESS_AMENDMENT_V009.json').read_text())
    for path,original_sha in plan['source_sha256'].items():
        want=(amendment['posthoc_runner_sha256'] if path=='nomad/simulation_v9.py' else original_sha)
        if actual.get(path)!=want:errors.append(f'frozen source changed: {path}')
    if digest(ROOT/'baseline/NOMAD-v0.8.0.zip')!=plan['predecessor_archive_sha256']:
        errors.append('v0.8 archive changed')
    for seed,sha in amendment['seed_receipts_sha256'].items():
        path=ROOT/f'results/study-v009/seed-{seed}.json'
        if digest(path)!=sha:errors.append(f'seed {seed} changed')
    runs=[json.loads((ROOT/f'results/study-v009/seed-{s}.json').read_text()) for s in FROZEN_EVAL_SEEDS]
    rebuilt=assemble_runs(runs,FROZEN_EVAL_SEEDS)
    original=json.loads((ROOT/'results/simulation-v009.json').read_text())
    if rebuilt!=original:errors.append('assembled frozen simulation mismatches original data')
    gate=json.loads((ROOT/'results/GATES.json').read_text())
    if gate['status']!='passed' or not all(v for k,v in gate.items() if k.startswith('gate_')):
        errors.append('release gate is not passed')
    if digest(ROOT/'results/simulation-v009.json')!=gate['simulation_sha256']:
        errors.append('simulation hash mismatch')
    if digest(ROOT/'results/AUDIT_V009.json')!=gate['probe_audit_sha256']:
        errors.append('audit hash mismatch')
    return {'status':'passed' if not errors else 'failed','version':'0.9.0',
            'manifest_files':len(expected),'preexisting_source_seal_checked':True,
            'frozen_seed_batches':list(FROZEN_EVAL_SEEDS),
            'original_study_reassembled':rebuilt==original,'errors':errors}


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--tests',action='store_true',help='after integrity checks, run all historical and new tests')
    p.add_argument('--audit',action='store_true',help='after integrity checks, replay public probe receipts')
    args=p.parse_args()
    report=verify()
    print(json.dumps(report,indent=2))
    if report['status']!='passed':return 2
    if args.tests:
        p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=ROOT)
        if p.returncode:return p.returncode
    if args.audit:
        from scripts.audit_v9 import audit
        fresh=audit()
        archived=json.loads((ROOT/'results/AUDIT_V009.json').read_text())
        if fresh!=archived:
            print('probe audit differs from shipped audit',file=sys.stderr)
            return 3
        print(f"Replayed {fresh['probe_receipts_replayed']} stored probe receipts")
    return 0
if __name__=='__main__':raise SystemExit(main())
