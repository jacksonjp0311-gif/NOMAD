"""Preserve pinned public originals and admit exact development projections.

Downloaded code is parsed only. This tool never imports, compiles or executes
upstream source, and it creates no private or unseen evaluation contracts.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad import frontier


def sha(raw):return hashlib.sha256(raw).hexdigest()
def blob(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def write_new(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:handle.write(raw)
def write_json(path,value):write_new(path,json.dumps(value,sort_keys=True,indent=2,allow_nan=False).encode()+b'\n')


def exact_projection(text,symbols):
    tree=ast.parse(text);selected=[]
    for symbol in symbols:
        matches=[node for node in tree.body if
            isinstance(node,ast.FunctionDef) and node.name==symbol or
            isinstance(node,ast.Assign) and len(node.targets)==1 and
            isinstance(node.targets[0],ast.Name) and node.targets[0].id==symbol]
        if len(matches)!=1:raise ValueError('projection symbol absent or ambiguous: '+symbol)
        node=matches[0]
        if isinstance(node,ast.Assign):ast.literal_eval(node.value)
        elif node.decorator_list:raise ValueError('decorated function projection unsupported')
        selected.append(node)
    projected='\n\n'.join(ast.get_source_segment(text,node) for node in selected)+'\n'
    if [ast.dump(n,include_attributes=False) for n in ast.parse(projected).body]!=[
        ast.dump(n,include_attributes=False) for n in selected]:raise ValueError('projection changed an AST node')
    return projected,[{'symbol':symbol,'line_start':node.lineno,'line_end':node.end_lineno}
                       for symbol,node in zip(symbols,selected)]


def admission(path,public):
    try:
        analysis=frontier.inspect_function_repository(path,public,max_candidates=64,max_files_changed=1)
        return {'status':'PARSE_ONLY_SUPPORTED','candidate_inventory_count':len(analysis['proposals']),
                'candidate_inventory_sha256':analysis['candidate_inventory_sha256']}
    except (ValueError,SyntaxError) as error:
        return {'status':'UNSUPPORTED','reason':str(error)}


def prepare(downloads,destination):
    if destination.exists():raise FileExistsError('preserve existing provenance; choose a new destination')
    if not isinstance(downloads,list) or not 1<=len(downloads)<=12:raise ValueError('bounded provenance list required')
    # Validate all bytes before creating the bundle. Git blob identity binds the
    # original bytes, including CRLF and trailing newlines, to upstream Git.
    for item in downloads:
        if not re.fullmatch(r'[a-z0-9-]{1,60}',item['id']):raise ValueError('unsafe provenance identifier')
        if not re.fullmatch(r'[0-9a-f]{40}',item['revision']):raise ValueError('exact upstream revision required')
        for kind in ('source','license'):
            raw=item[kind+'_content'].encode('utf-8')
            if len(raw)>100000 or blob(raw)!=item[kind+'_git_blob']:raise ValueError('upstream '+kind+' bytes differ from Git blob')
    if len({item['id'] for item in downloads})!=len(downloads):raise ValueError('duplicate provenance identifier')
    reports=[]
    for item in downloads:
        base=destination/item['id'];original=base/'original'
        source=item['source_content'].encode();license_raw=item['license_content'].encode()
        write_new(original/'subject.py',source);write_new(original/'LICENSE',license_raw)
        write_json(base/'UPSTREAM_ISSUE.json',item['issue'])
        public={'goal_text':item['goal'],'public':item['public'],
                'scope':'Openly authored development examples; not independent held-out verification.'}
        write_json(base/'PUBLIC_DEVELOPMENT.json',public)
        report={'schema':'nomad.adaptive-upstream-provenance.v18','id':item['id'],
            'repository':'https://github.com/'+item['repository'],'revision':item['revision'],
            'source_url':'https://github.com/'+item['repository']+'/blob/'+item['revision']+'/'+item['source_path'],
            'upstream_source_path':item['source_path'],'source_git_blob':item['source_git_blob'],
            'source_sha256':sha(source),'license_path':item['license_path'],'license_git_blob':item['license_git_blob'],
            'license_sha256':sha(license_raw),'license_retained':True,'issue_url':item['issue']['url'],
            'issue_sha256':sha(canonical(item['issue'])),'issue_reporter':item['issue']['author'],
            'issue_created_at':item['issue']['created_at'],'public_spec_sha256':sha(canonical(public)),
            'original_module_admission':admission(original,item['public']),
            'scope':item['scope'],'upstream_repository_snapshot_complete':False,
            'downloaded_source_host_execution':False,'native_execution':'NOT_RUN','repair_success':'NOT_ESTABLISHED',
            'independent_defect_reproduction':'NOT_RUN','full_repository_repair':'NOT_ESTABLISHED',
            'private_contracts_created':False,'evaluation_eligible':False,
            'exposure':'Upstream issue, public examples and original source inspected during development.',
            'preparation_script_sha256':sha(Path(__file__).read_bytes())}
        if item['projection_symbols'] is not None:
            text,ranges=exact_projection(source.decode(),item['projection_symbols'])
            write_new(base/'projection'/'subject.py',text.encode());write_new(base/'projection'/'LICENSE',license_raw)
            report.update(projection_sha256=sha(text.encode()),projection_nodes=ranges,
                selected_function_and_literal_AST_unchanged=True,
                projection_admission=admission(base/'projection',item['public']),
                transformation='Exact selected top-level functions and literal assignments; omitted module context is outside this developmental subproblem.')
        else:report['projection_admission']={'status':'NOT_PREPARED','reason':'Do not rewrite dependencies to manufacture admission.'}
        report['receipt_sha256']=sha(canonical(report));write_json(base/'PROVENANCE.json',report);reports.append(report)
    manifest={'schema':'nomad.adaptive-public-development-corpus.v18','status':'EXPOSED_DEVELOPMENT_ONLY_NOT_EVALUATION_CORPUS',
        'entries':reports,'independent_evaluation_tasks_registered':0,'native_repairs_executed':0,
        'private_contracts_created':False,'excluded_evaluation_repositories':sorted(item['repository'].lower() for item in downloads),
        'additional_metadata_exposure_repositories':['unidata/metpy','python-attrs/attrs','python-humanize/humanize'],
        'limits':['Three repository owners are recorded, not a formal authorship or shared-ancestry audit.',
            'An authentic upstream issue report is not independent reproduction.',
            'Exact projected helper repair would not establish full upstream repository repair.',
            'Independent curator must supply disjoint unseen repositories, private contract commitments and native qualification.']}
    manifest['receipt_sha256']=sha(canonical(manifest));write_json(destination/'CORPUS.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args();report=prepare(json.loads(args.input.read_bytes()),args.destination)
    print(json.dumps({'entries':len(report['entries']),'projection_statuses':{
        r['id']:r['projection_admission']['status'] for r in report['entries']},'native_repairs':0},sort_keys=True))


if __name__=='__main__':main()
