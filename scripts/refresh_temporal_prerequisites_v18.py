"""Temporal read-only prerequisites, differential archive search and corpus gaps.

Writes new observations only. Does not provision infrastructure, execute a source
repository, inspect private contracts or reinterpret old qualification results.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.qualify_windows_v18 import environment
from scripts.search_lineage_frontier_v18 import KNOWN, MAX_ARCHIVE, inspect_members

PRIOR='results/ARCHIVE_DIFFERENTIAL_ADAPTIVE_V018.json'
ANCHOR='results/ARCHIVE_SEARCH_FINAL_FRONTIER_V018.json'
CATALOG='experiments/development/adaptive_sources/CORPUS.json'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def seal(report):return {**report,'receipt_sha256':sha(canonical(report))}
def read(relative):
    path=ROOT/relative
    if path.stat().st_size>4_000_000:raise ValueError('prerequisite receipt byte budget exceeded')
    return json.loads(path.read_bytes())
def write_new(path,report):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(report,handle,sort_keys=True,indent=2,allow_nan=False);handle.write('\n')


def inventory():
    return seal({'schema':'nomad.temporal-infrastructure-refresh.v18',
        'created_utc':datetime.now(timezone.utc).isoformat(),'environment':environment(),
        'source_sha256':{name:sha((ROOT/name).read_bytes()) for name in
            ('scripts/refresh_temporal_prerequisites_v18.py','scripts/qualify_windows_v18.py')},
        'configuration_changed':False,'software_installed':False,'repository_code_executed':False,
        'native_containment_gate':'HOLD','strict_peak_counter_gate':'HOLD',
        'native_probe_cases_executed':0,'function_recovery_cases_executed':0,
        'scope':'read-only availability inventory, not a containment qualification',
        'reason':'Actual native13 containment PASS and same-source/image/policy native21 function recovery remain required.'})


def select_recent(metadata,cutoff):return max(metadata.st_mtime,metadata.st_ctime)>=cutoff


def archive_differential():
    previous=read(PRIOR);anchor=read(ANCHOR)
    cutoff=datetime.fromisoformat(previous['created_utc']).timestamp()
    roots=[Path(p) for p in previous['scope_roots']]
    old_objects={row['object'] for row in anchor['git_archive_objects']}
    old_objects.update(row['object'] for row in previous['new_git_archive_objects'])
    report={'schema':'nomad.temporal-archive-differential.v18',
        'created_utc':datetime.now(timezone.utc).isoformat(),'cutoff_utc':previous['created_utc'],
        'prior_receipts_sha256':{name:sha((ROOT/name).read_bytes()) for name in (PRIOR,ANCHOR)},
        'scope_roots':[str(p) for p in roots],'limits':{'paths':2000,'archive_bytes':MAX_ARCHIVE,'members':20000},
        'history_modified':False,'archives_extracted':False,'originals_regenerated':False,'gate_D':'HOLD',
        'inspected':[],'errors':[],'omissions':[],'new_git_archive_objects':[],
        'older_timestamp_paths_not_rehashed':0,
        'selection':'ZIP modification or Windows creation time at or after prior adaptive search; new reachable Git archive blobs only.',
        'scope_limit':'Known local roots only; copies preserving both old timestamps, cloud stores and recycle bins are outside this differential guarantee.'}
    existing=[p for p in roots if p.is_dir()]
    report['omissions'].extend({'root':str(p),'reason':'directory absent'} for p in roots if p not in existing)
    paths=[]
    if existing:
        listing=subprocess.run(['rg','--files','--hidden','--no-ignore','-g','*.zip',
            '-g','!**/.git/**','-g','!**/node_modules/**','-g','!**/.venv/**',*map(str,existing)],
            capture_output=True,text=True,timeout=60)
        report['enumeration_exit_code']=listing.returncode
        report['enumeration_stderr_sha256']=sha(listing.stderr.encode()) if listing.stderr else None
        paths=sorted({Path(p) for p in listing.stdout.splitlines()},key=str)
    report['zip_paths_found']=len(paths)
    if len(paths)>2000:report['omissions'].append({'reason':'path budget','count':len(paths)-2000})
    for path in paths[:2000]:
        try:
            metadata=path.lstat()
            if not select_recent(metadata,cutoff):
                report['older_timestamp_paths_not_rehashed']+=1;continue
            if not stat.S_ISREG(metadata.st_mode) or getattr(metadata,'st_reparse_tag',0):
                report['omissions'].append({'path':str(path),'reason':'nonregular or reparse archive'});continue
            if metadata.st_size>MAX_ARCHIVE:
                report['omissions'].append({'path':str(path),'reason':'archive byte budget'});continue
            raw=path.read_bytes();checksum=sha(raw)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:nested=inspect_members(archive)
            report['inspected'].append({'path':str(path),'bytes':len(raw),'sha256':checksum,
                'known_identity':KNOWN.get(checksum),'nested_candidates':nested,
                'mtime_ns':metadata.st_mtime_ns,'ctime_ns':metadata.st_ctime_ns})
        except (OSError,ValueError,zipfile.BadZipFile,RuntimeError) as error:
            report['errors'].append({'path':str(path),'reason':type(error).__name__})
    history=subprocess.run(['git','rev-list','--objects','--all'],cwd=ROOT,capture_output=True,text=True,timeout=30,check=True)
    for line in history.stdout.splitlines():
        oid,_,name=line.partition(' ')
        if oid in old_objects or not name.lower().endswith('.zip'):continue
        size=int(subprocess.run(['git','cat-file','-s',oid],cwd=ROOT,capture_output=True,text=True,timeout=10,check=True).stdout)
        if size>MAX_ARCHIVE:report['omissions'].append({'git_object':oid,'reason':'archive byte budget'});continue
        raw=subprocess.run(['git','cat-file','blob',oid],cwd=ROOT,capture_output=True,timeout=10,check=True).stdout
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:nested=inspect_members(archive)
        report['new_git_archive_objects'].append({'object':oid,'path':name,'bytes':len(raw),'sha256':sha(raw),
            'known_identity':KNOWN.get(sha(raw)),'nested_candidates':nested})
    found=set()
    def collect(rows):
        for row in rows:
            if row.get('known_identity') not in (None,'v17_compact'):found.add(row['known_identity'])
            collect(row.get('nested_candidates',row.get('nested',[])))
    collect(report['inspected']);collect(report['new_git_archive_objects'])
    report['original_v14_v15_v16_found']=sorted(found)
    report['conclusion']='candidate original requires independent lineage validation' if found else 'No missing original predecessor recovered in this differential scope.'
    return seal(report)


def corpus_gap():
    catalog=read(CATALOG)
    return seal({'schema':'nomad.temporal-authentic-corpus-gap.v18',
        'created_utc':datetime.now(timezone.utc).isoformat(),'status':'HOLD',
        'catalog_sha256':sha((ROOT/CATALOG).read_bytes()),'existing_development_bundles':len(catalog['entries']),
        'exact_projection_parse_only_supported':sum(row.get('projection_admission',{}).get('status')=='PARSE_ONLY_SUPPORTED' for row in catalog['entries']),
        'qualified_training_repositories':0,'minimum_training_repositories':2,
        'unseen_evaluation_repositories':0,'minimum_evaluation_repositories':8,
        'unseen_evaluation_tasks':0,'minimum_evaluation_tasks':24,
        'original_protocol_preserved':True,'downloaded_repository_code_executed':False,
        'private_contracts_opened':False,'private_contracts_fabricated':False,'repository_repair_successes':0,
        'missing':['reviewed live Linux Docker boundary and thirteen actual containment PASS cases',
            'same-source/image/policy twenty-one-case native function recovery PASS',
            'independent curator and withheld disjoint source/issue/test provenance',
            'complete native aggregate controller-plus-worker CPU/wall/memory limits and cost receipts',
            'full repository adapter if tasks exceed admitted bounded JSON-function subset'],
        'external_research':{'source':'https://www.swebench.com/SWE-bench/guides/evaluation/',
            'inspected':'public harness overview only; no task dataset or private contract loaded',
            'finding':'SWE-bench tests real repository patches in Docker; its full repository harness is not this admitted JSON-function adapter.',
            'public_documentation_example_exposure':['sympy/sympy issue20590'],
            'adopted_benchmark_tasks':0},
        'curator_sequence':['freeze independent upstream repository/commit/issue/license identities',
            'exclude every development-exposed repository and exact task',
            'commit public contract, independent challenge/final contracts and failure reproduction provenance separately',
            'verify reproduction and repair in qualified containers without importing source on host',
            'freeze disjoint training/evaluation splits and numerical aggregate budgets before learner access'],
        'conclusion':'Authentic public leads do not complete an independently curated isolated repair experiment.'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('environment-output','archive-output','corpus-output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();paths=[args.environment_output,args.archive_output,args.corpus_output]
    if len({p.resolve() for p in paths})!=3 or any(p.exists() for p in paths):parser.error('use distinct new receipt paths')
    for path,producer in zip(paths,(inventory,archive_differential,corpus_gap)):write_new(path,producer())
    print(json.dumps({'native_containment':'HOLD','corpus':'HOLD','new_receipts':[str(p) for p in paths]}))


if __name__=='__main__':main()
