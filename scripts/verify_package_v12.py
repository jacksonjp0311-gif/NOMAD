"""NOMAD v0.12 read-only source, evidence and archive verification.

Must first check EXISTING manifest bytes without rewriting/recreating evidence.
A local SHA is not an authentication proof and this package is not an
arbitrary-code sandbox.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.mnemonic import EvidenceMemory
from scripts.gates_v12 import report as current_gates


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def package_files() -> dict[str,str]:
    out={}
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT).as_posix()
        if (rel in {'results/RELEASE_MANIFEST_V012.json'} or rel.startswith('.git/') or
            '/__pycache__/' in '/'+rel or rel.endswith(('.pyc','.pyo')) or
            rel.startswith(('runs/','dist/','build/'))): continue
        out[rel]=sha(p)
    return dict(sorted(out.items()))


def verify() -> dict:
    problems=[]
    manifest=json.loads((ROOT/'results/RELEASE_MANIFEST_V012.json').read_text())
    expected=manifest['files']; actual=package_files()
    for name in sorted(set(expected)|set(actual)):
        if expected.get(name)!=actual.get(name): problems.append('manifest mismatch '+name)
    freeze=json.loads((ROOT/'experiments/FREEZE_V012.json').read_text())
    for name,actual_hash in freeze['source_sha256'].items():
        if actual.get(name)!=actual_hash:problems.append('source was modified after release freeze '+name)
    if sha(ROOT/'experiments/PLAN_V012.json')!=freeze['plan_sha256']:
        problems.append('original pre-eval plan changed')
    parent=ROOT/'baseline/NOMAD-v0.11.0.zip'
    if sha(parent)!=freeze['predecessor_sha256'] or sha(parent)!=manifest['parent_sha256']:
        problems.append('v0.11 history archive changed')
    with zipfile.ZipFile(parent) as archive:
        if archive.testzip() is not None or 'NOMAD-v0.11.0/results/RELEASE_MANIFEST.json' not in archive.namelist():
            problems.append('parent ZIP integrity or manifest missing')
    if not (ROOT/'docs/ERRATA_V012.md').is_file():problems.append('registered plan erratum missing')
    study=json.loads((ROOT/'results/study-v012.json').read_text())
    if sha(ROOT/'results/study-v012.json')!=manifest['study_sha256']:
        problems.append('heldout study altered')
    if study['configuration']['heldout_seeds']!=freeze['release_heldout_seeds']:
        problems.append('heldout seeds differ from source freeze')
    memory=EvidenceMemory.load(ROOT/'results/MNEMONIC_MEMORY.json')
    memory_doc=json.loads((ROOT/'results/MNEMONIC_MEMORY.json').read_text())
    if study['saved_memory_sha256']!=memory_doc['payload_sha256'] or study['saved_memory_chain_head']!=memory.head:
        problems.append('training/evaluation memory differs')
    if not memory.frozen or len(memory.events)!=study['memory_event_count']:
        problems.append('memory not frozen or changed')
    recorded_gates=json.loads((ROOT/'results/GATES_V012.json').read_text())
    if recorded_gates!=current_gates() or recorded_gates['status']!='passed':
        problems.append('v0.12 study gates fail or disagree')
    if sha(ROOT/'results/GATES_V012.json')!=manifest['gates_sha256']:
        problems.append('gate report altered')
    audit=json.loads((ROOT/'results/AUDIT_V012.json').read_text())
    if sha(ROOT/'results/AUDIT_V012.json')!=manifest['audit_sha256'] or audit.get('status')!='passed' or audit.get('replayed_contracts')!=len(study['case_records']):
        problems.append('saved independent replay incomplete or altered')
    return {
        'schema':'nomad.mnemonic.release-integrity.v1',
        'status':'passed' if not problems else 'failed',
        'version':'0.12.0',
        'manifest_file_hashes_checked':len(expected),
        'source_freeze_hashes_checked':len(freeze['source_sha256']),
        'parent_zip_sha256':sha(parent),
        'memory_events':len(memory.events),
        'heldout_contracts':len(study['case_records']),
        'saved_independent_process_replays':audit['replayed_contracts'],
        'source_plan_erratum_retained':True,
        'issues':problems,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tests',action='store_true')
    parser.add_argument('--audit',action='store_true')
    parser.add_argument('--demo',action='store_true')
    opts=parser.parse_args()
    result=verify()
    print(json.dumps(result,indent=2))
    if result['status']!='passed':return 1
    if opts.tests:
        r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=ROOT)
        if r.returncode:return r.returncode
    if opts.demo:
        r=subprocess.run([sys.executable,'-m','nomad.mnemonic_cli','--demo'],cwd=ROOT)
        if r.returncode:return r.returncode
        r=subprocess.run([sys.executable,'-m','nomad.atlas_cli','--demo'],cwd=ROOT)
        if r.returncode:return r.returncode
    if opts.audit:
        from scripts.audit_v12 import audit
        current=audit(ROOT/'results/study-v012.json',ROOT/'results/MNEMONIC_MEMORY.json')
        saved=json.loads((ROOT/'results/AUDIT_V012.json').read_text())
        if current!=saved:return 2
        print('Independent process audit reproduced:',current['replayed_contracts'],'effects')
    return 0

if __name__=='__main__':raise SystemExit(main())
