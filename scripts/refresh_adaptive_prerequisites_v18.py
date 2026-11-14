"""Read-only environment refresh and timestamp-scoped archive differential."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.qualify_windows_v18 import environment
from scripts.search_lineage_frontier_v18 import KNOWN, MAX_ARCHIVE, inspect_members


def sha(raw): return hashlib.sha256(raw).hexdigest()
def seal(report):
    report['receipt_sha256']=sha(json.dumps(report,sort_keys=True,separators=(',',':')).encode())
    return report
def write_new(path,report):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(report,handle,sort_keys=True,indent=2);handle.write('\n')


def refresh():
    report={'schema':'nomad.adaptive-infrastructure-refresh.v18',
        'created_utc':datetime.now(timezone.utc).isoformat(),'environment':environment(),
        'configuration_changed':False,'software_installed':False,'repository_code_executed':False,
        'native_containment_gate':'HOLD','strict_peak_counter_gate':'HOLD',
        'native_probe_cases_executed':0,'function_recovery_cases_executed':0,
        'source_sha256':{'scripts/refresh_adaptive_prerequisites_v18.py':sha(Path(__file__).read_bytes()),
            'scripts/qualify_windows_v18.py':sha((ROOT/'scripts/qualify_windows_v18.py').read_bytes())},
        'scope':'read-only inventory only; existing Windows trusted supervision is not hostile-code containment',
        'reason':'A reviewed digest image, live approved Docker boundary and actual native evidence remain prerequisites.'}
    return seal(report)


def differential(previous_path):
    previous_raw=previous_path.read_bytes(); previous=json.loads(previous_raw)
    cutoff=datetime.fromisoformat(previous['created_utc']).timestamp()
    roots=[Path(p) for p in previous['scope_roots']]
    report={'schema':'nomad.adaptive-archive-differential.v18',
        'created_utc':datetime.now(timezone.utc).isoformat(),'previous_receipt':str(previous_path),
        'previous_receipt_sha256':sha(previous_raw),'cutoff_utc':previous['created_utc'],
        'scope_roots':[str(p) for p in roots],'history_modified':False,'archives_extracted':False,
        'originals_regenerated':False,'gate_D':'HOLD','inspected':[],'errors':[],'omissions':[],
        'limits':{'paths':2000,'archive_bytes':MAX_ARCHIVE,'members':20000},
        'selection':'Only ZIPs with mtime or Windows creation time at/after previous search; older-timestamp files are not rehashed.',
        'limits_note':'Not exhaustive cloud/recycle-bin/whole-machine search; copied files preserving both old timestamps can be missed.'}
    listing=subprocess.run(['rg','--files','--hidden','--no-ignore','-g','*.zip',
        '-g','!**/.git/**','-g','!**/node_modules/**','-g','!**/.venv/**',
        *map(str,[p for p in roots if p.is_dir()])],capture_output=True,text=True,timeout=60)
    report['enumeration_exit_code']=listing.returncode
    report['enumeration_stderr_sha256']=sha(listing.stderr.encode()) if listing.stderr else None
    paths=sorted({Path(p) for p in listing.stdout.splitlines()},key=str)
    report['zip_paths_found']=len(paths);report['older_timestamp_paths_not_rehashed']=0
    if len(paths)>2000:report['omissions'].append({'reason':'path limit','count':len(paths)-2000})
    for path in paths[:2000]:
        try:
            metadata=path.stat()
            if max(metadata.st_mtime,metadata.st_ctime)<cutoff:
                report['older_timestamp_paths_not_rehashed']+=1;continue
            if metadata.st_size>MAX_ARCHIVE:
                report['omissions'].append({'path':str(path),'reason':'size limit'});continue
            raw=path.read_bytes(); checksum=sha(raw)
            with zipfile.ZipFile(path) as archive:nested=inspect_members(archive)
            report['inspected'].append({'path':str(path),'bytes':len(raw),'sha256':checksum,
                'known_identity':KNOWN.get(checksum),'nested_candidates':nested,
                'mtime_ns':metadata.st_mtime_ns,'ctime_ns':metadata.st_ctime_ns})
        except (OSError,ValueError,zipfile.BadZipFile,RuntimeError) as error:
            report['errors'].append({'path':str(path),'reason':type(error).__name__})
    old_objects={row['object'] for row in previous['git_archive_objects']}
    history=subprocess.run(['git','rev-list','--objects','--all'],cwd=ROOT,capture_output=True,text=True,timeout=30,check=True)
    report['new_git_archive_objects']=[]
    for line in history.stdout.splitlines():
        oid,_,name=line.partition(' ')
        if oid in old_objects or not name.lower().endswith('.zip'):continue
        size=int(subprocess.run(['git','cat-file','-s',oid],cwd=ROOT,capture_output=True,text=True,timeout=10,check=True).stdout)
        if size>MAX_ARCHIVE:report['omissions'].append({'git_object':oid,'reason':'size limit'});continue
        raw=subprocess.run(['git','cat-file','blob',oid],cwd=ROOT,capture_output=True,timeout=10,check=True).stdout
        report['new_git_archive_objects'].append({'object':oid,'path':name,'bytes':len(raw),
            'sha256':sha(raw),'known_identity':KNOWN.get(sha(raw))})
    found=set()
    def collect(rows):
        for row in rows:
            if row.get('known_identity') not in (None,'v17_compact'):found.add(row['known_identity'])
            collect(row.get('nested_candidates',row.get('nested',[])))
    collect(report['inspected']);collect(report['new_git_archive_objects'])
    report['original_v14_v15_v16_found']=sorted(found)
    report['conclusion']='new candidate original requires independent lineage verification' if found else 'No missing authentic predecessor recovered in this differential scope.'
    return seal(report)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment-output',type=Path,required=True)
    parser.add_argument('--archive-output',type=Path,required=True)
    parser.add_argument('--previous',type=Path,default=ROOT/'results/ARCHIVE_SEARCH_FINAL_FRONTIER_V018.json')
    args=parser.parse_args()
    if args.environment_output.exists() or args.archive_output.exists():parser.error('preserve existing receipts; choose new paths')
    env=refresh();write_new(args.environment_output,env)
    archives=differential(args.previous);write_new(args.archive_output,archives)
    print(json.dumps({'native_containment':'HOLD','new_zip_paths_inspected':len(archives['inspected']),
        'older_timestamp_paths_not_rehashed':archives['older_timestamp_paths_not_rehashed'],
        'originals_found':archives['original_v14_v15_v16_found']},sort_keys=True))


if __name__=='__main__':main()
