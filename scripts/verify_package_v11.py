"""NOMAD v0.11 read-only release verification.

Checks preexisting package manifest BEFORE running any test or audit. This is
hash consistency, not a cryptographic release signature or an OS sandbox.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def current_files():
    files={}
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT).as_posix()
        if rel=='results/RELEASE_MANIFEST.json' or rel.startswith('.git/') or '/__pycache__/' in '/'+rel or rel.endswith(('.pyc','.pyo')):continue
        if rel.startswith('runs/') or rel.startswith('dist/') or rel.startswith('build/'): continue
        files[rel]=sha(p)
    return dict(sorted(files.items()))


def verify():
    errors=[]
    manifest=json.loads((ROOT/'results/RELEASE_MANIFEST.json').read_text())
    expected=manifest['files']; actual=current_files()
    for key in sorted(set(expected)|set(actual)):
        if expected.get(key)!=actual.get(key): errors.append('manifest byte mismatch '+key)

    freeze=json.loads((ROOT/'experiments/FREEZE_V011_RELEASE.json').read_text())
    for key,hexdigest in freeze['source_sha256'].items():
        if key=='nomad/__init__.py':
            # Exactly one post-freeze metadata change is permitted. No learning,
            # search or audit code changed after the final source freeze.
            with zipfile.ZipFile(ROOT/'baseline/NOMAD-v0.10.0.zip') as z:
                predecessor=z.read('NOMAD-v0.10.0/nomad/__init__.py')
            revised=predecessor.replace(b'__version__ = "0.10.0"',b'__version__ = "0.11.0"')
            if sha(ROOT/key)!=hashlib.sha256(revised).hexdigest():
                errors.append('post-freeze version metadata differs beyond specified string')
            if hashlib.sha256(predecessor).hexdigest()!=hexdigest:
                errors.append('initial freeze of predecessor metadata differs')
            continue
        if actual.get(key)!=hexdigest:errors.append('frozen learner/auditor source changed '+key)

    predecessor=sha(ROOT/'baseline/NOMAD-v0.10.0.zip')
    if predecessor!=freeze['parent_archive_sha256'] or predecessor!=manifest['parent_sha256']:
        errors.append('predecessor archive changed')

    if sha(ROOT/'results/study-v011-release.json')!=manifest['frozen_study_sha256']:
        errors.append('recorded study changed')
    from scripts.assemble_audit_v11 import assemble
    latest=assemble()
    recorded=json.loads((ROOT/'results/AUDIT_V011_RELEASE.json').read_text())
    if latest!=recorded or latest['status']!='passed':errors.append('batched independent audit changed or incomplete')
    if sha(ROOT/'results/AUDIT_V011_RELEASE.json')!=manifest['audit_sha256']:
        errors.append('audit report changed')
    from scripts.gates_v11_release import report
    decision=report(); saved=json.loads((ROOT/'results/GATES_V011.json').read_text())
    if saved!=decision or decision['status']!='passed':errors.append('research gates not reproducible')

    failed=json.loads((ROOT/'results/AUDIT_V011.json').read_text())
    if failed['status']!='failed' or len(failed.get('issues',[]))==0:
        errors.append('negative audit precheck not preserved')

    return {'schema':'nomad.v011.release-verification.v1',
        'status':'passed' if not errors else 'failed',
        'version':'0.11.0','manifest_files_checked':len(expected),
        'study_sha256':manifest['frozen_study_sha256'],
        'parent_archive_sha256':predecessor,
        'frozen_source_entries_checked':len(freeze['source_sha256']),
        'independent_contract_replays':latest['contract_replays'],
        'batch_scoped_audits_bound_to_study':len(latest['batches']),
        'failed_precheck_retained':True,'issues':errors}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--tests',action='store_true')
    p.add_argument('--rerun-audit',action='store_true')
    args=p.parse_args()
    r=verify();print(json.dumps(r,indent=2))
    if r['status']!='passed':return 1
    if args.tests:
        p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=ROOT)
        if p.returncode:return p.returncode
    if args.rerun_audit:
        # Re-run the three independent, seed-scoped audits without overwriting
        # or modifying ANY canonical evidence or release manifest.
        from scripts.audit_v11_corrected import audit
        canonical=json.loads((ROOT/'results/AUDIT_V011_RELEASE.json').read_text())
        for row in canonical['batches']:
            seed=row['seed']; src=ROOT/f'results/audit_batches/seed-{seed}.json'
            result=audit(json.loads(src.read_text()))
            if result['status']!='passed':return 2
            print(f'Independently replayed seed {seed}: {result["distinct_contract_replays"]} contracts')
    return 0

if __name__=='__main__':raise SystemExit(main())
