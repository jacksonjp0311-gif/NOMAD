"""Parse-only, auditable projection of a pinned public development function.

Never imports, compiles or executes the downloaded module. This projection is
exposed development material, not a complete repository task or unseen corpus.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tokenize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nomad import frontier

SOURCE_SHA256 = '5c64fba293085474be90d99736519ebb8fc63db0288482190ce8d296bccd19b3'
SOURCE_GIT_BLOB = '1e94e62aabcff3aaf26df34e506c5dc402c69202'
LICENSE_SHA256 = 'f676cbf8e504df7f12c9628ab17dddf686671d785f2a9f403098f29fadde4a96'
REVISION = '053cab15c3e3469aefc31bba8d452fd340563cf0'
FIX_COMMIT = 'ce2ec51d71dd1aa1abe19cb989a394ebd07a1919'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def exact_function_projection(text, qualified_name):
    node = ast.parse(text)
    for name in qualified_name.split('.'):
        matches = [child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == name]
        if len(matches) != 1: raise ValueError('function path is absent or ambiguous')
        node = matches[0]
    if node.decorator_list: raise ValueError('decorated projection is outside this preparation scope')
    lines = text.splitlines(keepends=True)
    # Plain dedent changes whitespace *inside* multiline strings/docstrings.
    # Remove enclosing code indentation while preserving every literal byte.
    protected = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.STRING:
            protected.update(range(token.start[0]+1, token.end[0]+1))
    body = ''.join(line if number in protected or not line.strip() else line[node.col_offset:]
                   for number,line in enumerate(lines[node.lineno-1:node.end_lineno], node.lineno))
    # Retain the original future-annotation context as well as the function text.
    future = [child for child in ast.parse(text).body if isinstance(child, ast.ImportFrom) and child.module == '__future__']
    header = ''.join(''.join(lines[child.lineno-1:child.end_lineno]) for child in future)
    projection = header+'\n'+body
    parsed = next(child for child in ast.parse(projection).body if isinstance(child, ast.FunctionDef))
    if ast.dump(parsed, include_attributes=False) != ast.dump(node, include_attributes=False):
        raise ValueError('projection changed the function AST')
    return projection, node.lineno, node.end_lineno


def prepare(root):
    original = root/'original'/'algorithms'/'math'/'rabin_miller.py'
    raw = original.read_bytes(); license_raw = (root/'original'/'LICENSE').read_bytes()
    if sha(raw) != SOURCE_SHA256 or sha(license_raw) != LICENSE_SHA256:
        raise ValueError('downloaded original bytes differ from primary-source commitment')
    blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if blob != SOURCE_GIT_BLOB: raise ValueError('downloaded source does not match Git blob identity')
    projected, start, end = exact_function_projection(raw.decode('utf-8'), 'is_prime._pow2_factor')
    destination = root/'projection'
    if destination.exists() or (root/'PROVENANCE.json').exists(): raise FileExistsError('preserve existing development provenance')
    destination.mkdir()
    (destination/'pow2_factor.py').write_bytes(projected.encode('utf-8'))
    shutil.copyfile(root/'original'/'LICENSE', destination/'LICENSE')
    # These are openly authored development examples. No private partition is
    # created, and their outputs are not evidence that the source was executed.
    public = [{'module':'pow2_factor','function':'_pow2_factor','args':[18014398509481986],
               'expected':[1,9007199254740993]},
              {'module':'pow2_factor','function':'_pow2_factor','args':[40],'expected':[3,5]}]
    analysis = frontier.inspect_function_repository(destination, public, max_candidates=64, max_files_changed=1)
    public_document = {'goal_text':'Preserve exact integer factor decomposition for positive integers.', 'public':public}
    (root/'PUBLIC_DEVELOPMENT.json').write_text(json.dumps(public_document,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    report = {'schema':'nomad.frontier-development-projection.v18', 'repository':'https://github.com/keon/algorithms',
        'issue':'https://github.com/keon/algorithms/issues/2733', 'revision':REVISION,
        'associated_fix_commit':FIX_COMMIT, 'fix_parent_matches_revision':True,
        'source_url':'https://github.com/keon/algorithms/blob/'+REVISION+'/algorithms/math/rabin_miller.py',
        'source_sha256':SOURCE_SHA256,'source_git_blob':SOURCE_GIT_BLOB,'license_sha256':LICENSE_SHA256,
        'license':'MIT, copyright (c) 2017 Keon; retained with original and projection',
        'qualified_function':'is_prime._pow2_factor','source_line_start':start,'source_line_end':end,
        'projection_sha256':sha(projected.encode()),'function_AST_unchanged':True,
        'transformation':'dedent exact nested function text and retain original future-annotation import; expose as top-level function',
        'omitted_context':'outer primality function and external random import are outside the projection',
        'admission':'PARSE_ONLY_SUPPORTED', 'candidate_inventory_sha256':analysis['candidate_inventory_sha256'],
        'candidate_inventory_count':len(analysis['proposals']), 'downloaded_source_host_execution':False,
        'native_execution':'NOT_RUN','repair_success':'NOT_ESTABLISHED','full_repository_repair':'NOT_ESTABLISHED',
        'evaluation_eligible':False,'private_contracts_created':False,
        'known_answer_exposure':'upstream issue and associated patch were inspected for provenance; never supplied as a repair candidate',
        'preparation_source_sha256':sha(Path(__file__).read_bytes())}
    (root/'PROVENANCE.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args(); report=prepare(args.root)
    print(json.dumps({key:report[key] for key in ('admission','candidate_inventory_count','native_execution','projection_sha256')}))


if __name__=='__main__': main()
