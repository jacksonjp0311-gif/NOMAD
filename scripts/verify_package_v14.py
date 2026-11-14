"""NOMAD v0.14 non-mutating package verifier.

Checks the EXISTING release manifest before execution and does not regenerate
frozen evidence. SHA256 is file integrity, not a remote authenticated signature.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'results/RELEASE_MANIFEST_V014.json'

def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1<<20),b''):h.update(block)
 return h.hexdigest()

def file_map()->dict[str,str]:
 d={}
 for p in ROOT.rglob('*'):
  if not p.is_file():continue
  name=p.relative_to(ROOT).as_posix()
  if name==MANIFEST.relative_to(ROOT).as_posix() or name.startswith(('.git/','runs/','dist/','build/')) or any(seg in ('__pycache__','.pytest_cache') for seg in p.relative_to(ROOT).parts) or name.endswith(('.pyc','.pyo')):continue
  d[name]=sha(p)
 return dict(sorted(d.items()))

def verify()->dict:
 issues=[]
 if not MANIFEST.exists():return {'status':'failed','issues':['missing immutable release manifest']}
 mf=json.loads(MANIFEST.read_text())
 expected=mf['files']; actual=file_map()
 for path in sorted(set(expected)|set(actual)):
  if expected.get(path)!=actual.get(path):issues.append('missing, new or mismatched file: '+path)
 predecessor=ROOT/'baseline/NOMAD-v0.13.0.zip'
 if not predecessor.is_file() or sha(predecessor)!=mf['predecessor_sha256']:
  issues.append('predecessor archive hash mismatch')
 else:
  with zipfile.ZipFile(predecessor) as archive:
   if archive.testzip() is not None:issues.append('predecessor CRC failed')
 source_checks=0
 for package in ('affine','catalogue','confection'):
  man=ROOT/'external_sources'/(package+'.manifest.json')
  try: data=json.loads(man.read_text())
  except (OSError,json.JSONDecodeError):issues.append('missing upstream manifest: '+package);continue
  for rel,h in data['files'].items():
   p=ROOT/'external_sources'/package/rel
   source_checks+=1
   if not p.is_file() or sha(p)!=h:issues.append('upstream snapshot changed: '+package+'/'+rel)
 for key,path in (('study','results/FRONTIER_STUDY_V014.json'),('audit','results/AUDIT_V014.json'),('development','results/FRONTIER_DEV_PRECONTRACT.json')):
  if actual.get(path)!=mf[key+'_sha256']:
   issues.append('research evidence does not match release seal: '+key)
 if actual.get('docs/EXPERIMENT_V014.md')!=mf['experiment_sha256']:
  issues.append('experiment description does not match release seal')
 try:
  study=json.loads((ROOT/'results/FRONTIER_STUDY_V014.json').read_text())
  audit=json.loads((ROOT/'results/AUDIT_V014.json').read_text())
  c=study['cold_summary'];l=study['transferred_summary']
  if (c['witnessed_repairs'],l['witnessed_repairs'],c['exact_restorations'],l['exact_restorations'])!=(2,1,2,1):
   issues.append('study no longer matches negative-release scientific contract')
  if study['external_issue_gate'][:4]!='HOLD' or audit['external_issue_research_gate']!='HOLD':
   issues.append('research hold was silently promoted')
  if audit['status']!='passed' or audit['contract_rejections_observed']<1:issues.append('independent counterexample audit missing')
 except (OSError,KeyError,TypeError,ValueError):issues.append('study/audit structure invalid')
 return {'schema':'nomad.frontier.release-verification.v1',
         'status':'passed' if not issues else 'failed','version':'0.14.0',
         'tracked_file_hashes':len(expected),'upstream_source_hashes':source_checks,
         'predecessor_sha256':mf['predecessor_sha256'],
         'research_promotion':'HOLD — learned prior did not beat cold search',
         'native_rust':'not tested in this environment',
         'issues':issues}

def main()->int:
 p=argparse.ArgumentParser()
 p.add_argument('--tests',action='store_true')
 p.add_argument('--audit',action='store_true')
 args=p.parse_args()
 r=verify();print(json.dumps(r,indent=2))
 if r['status']!='passed':return 1
 if args.tests:
  s=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=ROOT)
  if s.returncode:return s.returncode
 if args.audit:
  s=subprocess.run([sys.executable,'scripts/audit_frontier_v14.py'],cwd=ROOT)
  if s.returncode:return s.returncode
 return 0
if __name__=='__main__':raise SystemExit(main())
