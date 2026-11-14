"""Read-only v0.10 integrity verifier: never repairs/manufactures evidence.

Inspect a ZIP in a trusted sandbox before running its scripts. This checks
hash consistency relative to the bundled manifest; it is not a signature or
supply-chain authentication proof.
"""
from __future__ import annotations
import argparse,hashlib,json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))


def digest(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):
            h.update(b)
    return h.hexdigest()


def files():
    out={}
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        r=p.relative_to(ROOT).as_posix()
        if r=='results/RELEASE_MANIFEST.json' or r.startswith('.git/') or '__pycache__' in r or r.endswith('.pyc'):
            continue
        out[r]=digest(p)
    return dict(sorted(out.items()))


def verify():
    problems=[]
    manifest=json.loads((ROOT/'results/RELEASE_MANIFEST.json').read_text())
    expected=manifest['files']; actual=files()
    for key in sorted(set(expected)|set(actual)):
        if expected.get(key)!=actual.get(key):problems.append('manifest mismatch '+key)
    freeze=json.loads((ROOT/'experiments/FREEZE_V010.json').read_text())
    for key,sha in freeze['source_sha256'].items():
        if actual.get(key)!=sha:problems.append('frozen source changed '+key)
    plan=json.loads((ROOT/'experiments/PLAN_V010.json').read_text())
    if digest(ROOT/'baseline/NOMAD-v0.9.0.zip')!=manifest['parent_archive_sha256']:
        problems.append('predecessor altered')
    study=json.loads((ROOT/'results/study-v010.json').read_text())
    if study['experiment']['training_seeds']!=plan['training_seeds'] or study['experiment']['evaluation_seeds']!=plan['evaluation_seeds']:
        problems.append('seed plan/study mismatch')
    if study['experiment']['evaluation_cases']!=plan['heldout_cases']:
        problems.append('case plan/study mismatch')
    if digest(ROOT/'results/study-v010.json')!=manifest['frozen_study_sha256']:
        problems.append('frozen study altered')
    gates=json.loads((ROOT/'results/GATES_V010.json').read_text())
    from scripts.gates_v10 import report as calc_gates
    fresh_gates=calc_gates()
    if gates!=fresh_gates or gates['status']!='passed':
        problems.append('release gates not reproducible from study evidence')
    if digest(ROOT/'results/AUDIT_V010.json')!=manifest['independent_audit_sha256']:
        problems.append('audit altered')
    return {'status':'passed' if not problems else 'failed',
            'version':'0.10.0','checked_hashes':len(expected),
            'preexisting_manifest_checked':True,'frozen_source_checked':True,
            'parent_archive_preserved':True,'errors':problems}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tests',action='store_true')
    parser.add_argument('--audit',action='store_true')
    args=parser.parse_args()
    result=verify()
    print(json.dumps(result,indent=2))
    if result['status']!='passed':return 1
    if args.tests:
        r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=ROOT)
        if r.returncode:return r.returncode
    if args.audit:
        from scripts.audit_v10 import audit
        latest=audit(json.loads((ROOT/'results/study-v010.json').read_text()))
        recorded=json.loads((ROOT/'results/AUDIT_V010.json').read_text())
        if latest!=recorded:return 2
        print('Recomputed all frozen v0.10 candidate programs')
    return 0

if __name__=='__main__':raise SystemExit(main())
