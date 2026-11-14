"""Read-only v0.13 release integrity, registered study, and audit verification.

Never regenerates the manifest before checking it. A SHA chain demonstrates
byte consistency with a retained seal, not authenticated provenance against an
attacker with write access to the whole release.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.transcend import TransferMemory,digest
from nomad.simulation_v13 import release_gates,RELEASE_SEEDS,TRAIN_SEEDS

MANIFEST='results/RELEASE_MANIFEST_V013.json'


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def package_files() -> dict[str,str]:
    out={}
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT).as_posix()
        if (rel==MANIFEST or rel.startswith(('.git/','runs/','dist/','build/')) or
            '/__pycache__/' in '/'+rel or rel.endswith(('.pyc','.pyo'))):continue
        out[rel]=sha(p)
    return dict(sorted(out.items()))


def verify() -> dict:
    issues=[]
    manifest=json.loads((ROOT/MANIFEST).read_text(encoding='utf-8'))
    expected=manifest['files'];actual=package_files()
    for path in sorted(set(expected)|set(actual)):
        if expected.get(path)!=actual.get(path):issues.append('file does not match original release manifest: '+path)
    freeze=json.loads((ROOT/'experiments/FREEZE_V013.json').read_text(encoding='utf-8'))
    plan=json.loads((ROOT/'experiments/PLAN_V013.json').read_text(encoding='utf-8'))
    if sha(ROOT/'experiments/PLAN_V013.json')!=freeze['plan_sha256']:
        issues.append('registered experiment plan mutated')
    if sha(ROOT/'experiments/FREEZE_V013.json')!=manifest['freeze_sha256']:
        issues.append('source freeze mutated')
    for path,frozen in freeze['source_sha256'].items():
        if actual.get(path)!=frozen:issues.append('frozen research source mutated: '+path)
    parent=ROOT/'baseline/NOMAD-v0.12.0.zip'
    if sha(parent)!=freeze['predecessor_sha256'] or sha(parent)!=manifest['predecessor_sha256']:
        issues.append('byte-identical predecessor archive changed')
    with zipfile.ZipFile(parent) as zipped:
        if zipped.testzip() is not None:issues.append('predecessor ZIP CRC error')
        nested=('NOMAD-v0.12.0/baseline/NOMAD-v0.10.0.zip',
                'NOMAD-v0.12.0/baseline/NOMAD-v0.11.0.zip')
        if not all(s in zipped.namelist() for s in nested):issues.append('historical archive missing from predecessor')
    if (ROOT/'baseline/NOMAD-v0.10.0.zip').exists() or (ROOT/'baseline/NOMAD-v0.11.0.zip').exists():
        issues.append('historical duplicate ZIP unexpectedly reintroduced')
    study_file=ROOT/'results/v013-release/STUDY.json'
    audit_file=ROOT/'results/AUDIT_V013.json'
    gates_file=ROOT/'results/v013-release/GATES.json'
    for file_name,file_obj in [('study_sha256',study_file),('audit_sha256',audit_file),('gates_sha256',gates_file)]:
        if sha(file_obj)!=manifest[file_name]:issues.append('sealed evidence changed: '+file_name)
    study=json.loads(study_file.read_text(encoding='utf-8'))
    audit=json.loads(audit_file.read_text(encoding='utf-8'))
    gates=json.loads(gates_file.read_text(encoding='utf-8'))
    a=TransferMemory.load(ROOT/'results/v013-training/python-memory.json')
    b=TransferMemory.load(ROOT/'results/v013-training/javascript-memory.json')
    if len(a.events)!=24 or len(b.events)!=24 or study['directions'][0]['memory_head']!=a.head or study['directions'][1]['memory_head']!=b.head:
        issues.append('frozen training memory or study memory binding mismatch')
    if study.get('schema')!='nomad.transcend.study.v1' or study['evaluation_seeds']!={k:list(v) for k,v in RELEASE_SEEDS.items()}:
        issues.append('held-out study seeds or schema differ')
    if study['evaluation_seeds']!=freeze['holdout_seeds'] or study['evaluation_seeds']!=plan['heldout_seeds']:
        issues.append('registered held-out seeds altered')
    if study['train_seeds']!={k:list(v) for k,v in TRAIN_SEEDS.items()} or study['train_seeds']!=plan['source_seeds']:
        issues.append('source training seed mismatch')
    if release_gates(study,a,b)!=gates or gates['status']!='passed':
        issues.append('release research gates disagree or failed')
    if (audit['status']!='passed' or audit['study_sha256']!=sha(study_file)
        or audit['fresh_native_transfer_cases']!=48 or audit['matching_witness_receipts']!=48
        or audit['independent_scalar_candidates']!=192 or audit['errors']):
        issues.append('independent release audit does not support study')
    if audit['memory_heads']!={'python':a.head,'javascript':b.head}:
        issues.append('audit memory heads inconsistent')
    if study['rust'].get('status') not in ('not_native_verified','passed'):
        issues.append('Rust native state is not explicitly bounded')
    return {'schema':'nomad.transcend.release-verification.v1',
            'status':'passed' if not issues else 'failed','version':'0.13.0',
            'tracked_file_hashes':len(expected),'frozen_source_hashes':len(freeze['source_sha256']),
            'predecessor_sha256':sha(parent),'training_memory_events':len(a.events)+len(b.events),
            'release_tasks':gates['evaluated_tasks'],'independent_scalar_candidates':audit['independent_scalar_candidates'],
            'independent_native_cases':audit['fresh_native_transfer_cases'],
            'rust_native_release_status':study['rust']['status'],
            'issues':issues}


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--tests',action='store_true')
    p.add_argument('--audit',action='store_true')
    p.add_argument('--demo',action='store_true')
    args=p.parse_args()
    report=verify()
    print(json.dumps(report,indent=2))
    if report['status']!='passed':return 1
    if args.tests:
        r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=ROOT)
        if r.returncode:return r.returncode
    if args.demo:
        for lang in ('python','javascript'):
            r=subprocess.run([sys.executable,'-m','nomad.transcend_cli','--demo','--language',lang],cwd=ROOT)
            if r.returncode:return r.returncode
    if args.audit:
        from scripts.audit_v13 import audit
        current=audit(ROOT/'results/v013-release/STUDY.json',
                      ROOT/'results/v013-training/python-memory.json',
                      ROOT/'results/v013-training/javascript-memory.json')
        saved=json.loads((ROOT/'results/AUDIT_V013.json').read_text())
        if current!=saved:
            print('Fresh independent replay differs from frozen audit',file=sys.stderr)
            return 2
        print('Fresh independent replay passed:',current['fresh_native_transfer_cases'],'native targets')
    return 0
if __name__=='__main__':raise SystemExit(main())
