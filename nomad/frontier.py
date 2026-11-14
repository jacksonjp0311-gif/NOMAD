"""NOMAD FRONTIER v0.14 — offline external-source repair harness.

Scope: trusted, frozen third-party Python distribution sources only.
Defects in the study are evaluator-injected, NOT upstream GitHub issues.
A real process runs upstream tests. Search may inspect the source and *public*
test identifier but receives no seed mutation description, original source,
hidden result, or correct patch. Final verification runs outside search.
No container isolation; never run this on untrusted source repositories.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize
from typing import Iterable

SWAPS = {
    '==': ('!=',), '!=': ('==',), '>': ('>=','<'), '<': ('<=','>'),
    '>=': ('>','<','<='), '<=': ('<','>','>='),
    '+': ('-',), '-': ('+',), '*': ('+',),
    'and': ('or',), 'or': ('and',),
}
SCHEMA = 'nomad.frontier.v0.14'


def digest(data: bytes | str) -> str:
    if isinstance(data, str): data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Candidate:
    file: str
    line: int
    owner: str
    before: str
    after: str
    start: int
    end: int
    semantic_score: int

    @property
    def family(self):
        return self.before + '→' + self.after

    def render(self, original: str) -> str:
        if original[self.start:self.end] != self.before:
            raise ValueError('stale candidate source')
        return original[:self.start] + self.after + original[self.end:]


def _owner_spans(text: str) -> list[tuple[int,int,str]]:
    tree = ast.parse(text)
    spans = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((n.lineno,n.end_lineno or n.lineno,n.name))
    return spans


def _words(s: str) -> set[str]:
    return set(re.findall(r'[a-z0-9]+',s.lower())) - {'test','tests','py','case','registry','and','or','not'}


def public_test_clues(test_root: Path, selector: str) -> set[str]:
    """Read only selector-matched public tests; never inspect other test bodies."""
    terms=[t.strip() for t in re.split(r'\s+(?:or|and)\s+',selector) if t.strip()]
    result=set()
    for file in sorted(test_root.glob('test_*.py')):
        try: tree=ast.parse(file.read_text(encoding='utf-8'))
        except (ValueError,SyntaxError,UnicodeError):continue
        for fn in ast.walk(tree):
            if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) or not fn.name.startswith('test_'):continue
            if not any(term in fn.name for term in terms):continue
            for n in ast.walk(fn):
                if isinstance(n,ast.Attribute):result.update(_words(n.attr))
                if isinstance(n,ast.Compare) and any(isinstance(op,(ast.In,ast.NotIn)) for op in n.ops):
                    result.add('contains')
                if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Mult):result.add('mul')
    return result


def candidates(text: str, relpath: str, public_selector: str, extra_words: Iterable[str] = ()) -> list[Candidate]:
    """Enumerate bounded single-token syntax changes without a target patch oracle."""
    spans = _owner_spans(text)
    test_words = _words(public_selector) | set(extra_words)
    lines=text.splitlines(keepends=True)
    offsets=[0]
    for line in lines:offsets.append(offsets[-1]+len(line))
    out=[]
    toks=list(tokenize.generate_tokens(io.StringIO(text).readline))
    for j,t in enumerate(toks):
        if t.string not in SWAPS and t.string != 'in':continue
        if t.type in (tokenize.STRING, tokenize.COMMENT):continue
        row, col=t.start
        if row<1 or row>len(lines):continue
        start=offsets[row-1]+col
        end=start+len(t.string)
        original_token=t.string
        alts=SWAPS.get(t.string,())
        if t.string=='in':
            prev=toks[j-1] if j else None
            if prev and prev.string=='not' and prev.end[0]==row:
                start=offsets[row-1]+prev.start[1]
                original_token=text[start:end]
                alts=('in',)
            else:
                alts=('not in',)
        if text[start:end]!=original_token:continue
        owners=[(b-a,n) for a,b,n in spans if a<=row<=b]
        owner=min(owners)[1] if owners else '<module>'
        score=len(_words(owner)&test_words)
        # keep multiple alternatives, and sort source positions deterministically
        for alt in alts:
            out.append(Candidate(relpath,row,owner,original_token,alt,start,end,score))
    return out


def bgr_failure_signature(report: 'TestResult') -> int:
    """A compact binary observation, not a direct native BGR execution."""
    s=report.output.lower()
    signals=('assertionerror','typeerror','valueerror','keyerror','indexerror',
             'attributeerror','syntaxerror','failed','error','collected',
             'timeout','passed','notimplementederror','zero','expected','traceback')
    bits=sum(1<<i for i,k in enumerate(signals) if k in s)
    return bits | (int(not report.passed)<<15)


@dataclass(frozen=True)
class TestResult:
    passed: bool
    returncode: int
    elapsed_s: float
    output_sha256: str
    output: str
    timed_out: bool = False

    def sanitized(self)->dict:
        return dict(passed=self.passed,returncode=self.returncode,
                    elapsed_s=round(self.elapsed_s,4), output_sha256=self.output_sha256,
                    timed_out=self.timed_out, output_excerpt=self.output[-450:])


def run_tests(root: Path, project: str, *, selector: str = '', timeout_s: float = 20.0) -> TestResult:
    """Executes only explicitly trusted local fixtures; never shell=True."""
    root=root.resolve(strict=True)
    if project not in ('affine','catalogue','confection'):
        raise ValueError('outside frozen allowlisted source corpus')
    test_dir=root/project/'tests'
    if not test_dir.is_dir():raise ValueError('missing upstream tests')
    args=[sys.executable,'-B','-m','pytest','-q','--disable-warnings','--maxfail=1',str(test_dir)]
    if selector:args.extend(['-k',selector])
    env={**os.environ,'PYTHONPATH':str(root),
         'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONDONTWRITEBYTECODE':'1'}
    tic=time.perf_counter()
    try:
        out=subprocess.run(args,cwd=root,env=env,text=True,capture_output=True,
                           timeout=timeout_s,check=False)
        message=out.stdout+'\n'+out.stderr
        return TestResult(out.returncode==0,out.returncode,time.perf_counter()-tic,digest(message),message)
    except subprocess.TimeoutExpired as exc:
        s='TIMEOUT: '+str(exc)
        return TestResult(False,124,time.perf_counter()-tic,digest(s),s,True)


class Prior:
    """Small context-conditioned search preference, stored separately from execution evidence.

    No language, project name, source filename or mutation oracle in the key.
    Similar behavior to NOMAD's contextual operator ordering, but not a native
    BGR inference runtime. Witnessed successes may update this prior.
    """
    def __init__(self):self.counts:dict[str,int]={}
    def key(self,bits:int, family:str)->str:return f'{bits}:{family}'
    def observe(self, bits:int, candidate:Candidate, verified:bool)->None:
        if verified:
            k=self.key(bits,candidate.family)
            self.counts[k]=self.counts.get(k,0)+1
    def score(self,bits:int,c:Candidate)->int:
        return self.counts.get(self.key(bits,c.family),0)
    def snapshot(self)->dict:return {'schema':'nomad.frontier.prior.v1','counts':dict(sorted(self.counts.items()))}
    @classmethod
    def load(cls,data:dict)->'Prior':
        if data.get('schema')!='nomad.frontier.prior.v1':raise ValueError('incompatible memory schema')
        obj=cls()
        for k,v in data['counts'].items():
            if not isinstance(k,str) or type(v)!=int or v<0:raise ValueError('invalid prior')
            obj.counts[k]=v
        return obj


def order_candidates(items:list[Candidate], bits:int, prior:Prior|None)->list[Candidate]:
    # Ranking relies only on public test identifier + witnessed transfer counts.
    return sorted(items,key=lambda c:(-c.semantic_score,-(prior.score(bits,c) if prior else 0),
                                       c.line,c.start,c.before,c.after))


@dataclass(frozen=True)
class RepairResult:
    task_id: str
    policy: str
    repaired: bool
    candidate_attempts: int
    candidate_budget: int
    selected: dict | None
    initial_public: dict
    final_public: dict | None
    # withheld full-suite WITNESS check is filled by independent evaluator
    witness: dict | None
    search_cpu_proxy: str
    abstention: str | None
    trace: list[dict]


def repair(*, workspace: Path, project: str, test_selector: str,
           prior:Prior|None, budget:int=36, timeout_s:float=20.,
           task_id:str='task') -> tuple[RepairResult,int,Candidate|None]:
    """Repair a *disposable* workspace. Returns source signature and proposal.

    Callers must run WITNESS themselves. Search never receives full-suite output.
    """
    source_path=(workspace/project/'__init__.py').resolve()
    if workspace.resolve() not in source_path.parents:raise ValueError('path escapes workspace')
    old=source_path.read_text(encoding='utf-8')
    initial=run_tests(workspace,project,selector=test_selector,timeout_s=timeout_s)
    bits=bgr_failure_signature(initial)
    if initial.passed:
        return RepairResult(task_id,'learned' if prior else 'cold',False,0,budget,None,
                            initial.sanitized(),None,None,'public pytest subprocess calls','public tests already passed',[]),bits,None
    clues=public_test_clues(workspace/project/'tests',test_selector)
    cs=order_candidates(candidates(old,f'{project}/__init__.py',test_selector,clues),bits,prior)
    trace=[]
    for i,c in enumerate(cs[:budget],start=1):
        src=c.render(old)
        try:ast.parse(src)
        except SyntaxError:continue
        try:
            source_path.write_text(src,encoding='utf-8')
            report=run_tests(workspace,project,selector=test_selector,timeout_s=timeout_s)
        finally:
            source_path.write_text(old,encoding='utf-8')
        trace.append({'index':i,'source_line':c.line,'owner':c.owner,'edit_family':c.family,
                      'public_pass':report.passed,'result_hash':report.output_sha256})
        if report.passed:
            # EVALUATOR receives proposal only; full upstream suite is not run during search.
            return RepairResult(task_id,'learned' if prior else 'cold',True,len(trace),budget,
                                {'path':c.file,'line':c.line,'owner':c.owner,'family':c.family,
                                 'source_before_sha256':digest(old),'candidate_sha256':digest(src)},
                                initial.sanitized(),report.sanitized(),None,
                                'public pytest subprocess calls',None,trace),bits,c
    return RepairResult(task_id,'learned' if prior else 'cold',False,len(trace),budget,None,
                        initial.sanitized(),None,None,'public pytest subprocess calls',
                        'bounded search exhausted',trace),bits,None


def run_external_contract(root:Path,project:str,timeout_s:float=12.0)->dict:
    """Independent API invariant, not supplied to the policy during search.

    The Catalogue contract independently requires get_all() to return exactly
    the immediate namespace children, not descendants or foreign entries.
    This targets API semantics rather than restoring the evaluator's source bytes.
    Other packages have no supplemental independent contract in v0.14.
    """
    if project!='catalogue':return {'status':'not_available','supported':None}
    program="import catalogue\ncatalogue.REGISTRY.clear()\na=catalogue.create('frontier','leaf')\nb=catalogue.create('frontier','other')\ncatalogue._set(('frontier','leaf','apple'), 1)\ncatalogue._set(('frontier','leaf','pear'), 2)\ncatalogue._set(('frontier','other','pear'), 3)\ncatalogue._set(('frontier','leaf','apple','child'), 4)\nassert a.get_all()=={'apple':1,'pear':2}, a.get_all()\nassert b.get_all()=={'pear':3}, b.get_all()\nprint('catalogue_namespace_contract_ok')\n"
    env={**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
    try:
        r=subprocess.run([sys.executable,'-B','-c',program],cwd=root,env=env,
                         capture_output=True,text=True,timeout=timeout_s,check=False)
        return {'status':'passed' if r.returncode==0 else 'failed',
                'supported':r.returncode==0,'receipt_sha256':digest(r.stdout+r.stderr),
                'contract_sha256':digest(program)}
    except subprocess.TimeoutExpired:
        return {'status':'timeout','supported':False,'contract_sha256':digest(program)}


def witness_and_record(workspace:Path,project:str,candidate:Candidate|None,old_source:str,*,timeout_s=30.)->dict:
    """Independent full upstream suite; no search shortcut or readback of holdout."""
    if candidate is None:return {'supported':False,'reason':'no candidate'}
    p=workspace/project/'__init__.py'
    new=candidate.render(old_source)
    try:
        p.write_text(new,encoding='utf-8')
        actual=run_tests(workspace,project,timeout_s=timeout_s)
        contract=run_external_contract(workspace,project,timeout_s=timeout_s)
    finally:
        p.write_text(old_source,encoding='utf-8')
    result={'schema':'nomad.frontier.witness.v1','supported':actual.passed and contract.get('supported') is not False,
            'upstream_suite_passed':actual.passed,
            'additional_contract':contract,
            'source_sha256':digest(new),'project':project,
            'observed_test_exit_code':actual.returncode,
            'test_output_sha256':actual.output_sha256,
            'verified_at_scope':'full upstream distributed test suite',
            'elapsed_s':round(actual.elapsed_s,4)}
    result['receipt_sha256']=digest(json.dumps(result,sort_keys=True,separators=(',',':')))
    return result


def verify_witness(record:dict)->bool:
    if record.get('schema')!='nomad.frontier.witness.v1':return False
    content={k:v for k,v in record.items() if k!='receipt_sha256'}
    return record.get('receipt_sha256')==digest(json.dumps(content,sort_keys=True,separators=(',',':')))


def clone_frozen(frozen:Path, project:str, dest:Path)->Path:
    """Create an isolated writable copy for a known-good, hash-verified source."""
    record=json.loads((frozen/(project+'.manifest.json')).read_text())
    src=frozen/project
    for rel,sha in record['files'].items():
        p=src/rel
        if not p.is_file() or digest(p.read_bytes())!=sha:raise ValueError('upstream source altered: '+rel)
    shutil.copytree(src,dest,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','.coverage'))
    return dest


# The v0.18 adapter below is parse-only on the host. The legacy v0.14 host
# executors above remain explicitly trusted-fixture APIs and are never called.
FUNCTION_ADAPTER = 'python-functions-v1'
FUNCTION_BUILTINS = frozenset(('abs', 'all', 'any', 'bool', 'dict', 'enumerate',
    'float', 'int', 'len', 'list', 'max', 'min', 'range', 'reversed', 'round',
    'set', 'sorted', 'str', 'sum', 'tuple', 'zip', 'isinstance'))
FUNCTION_ERRORS = frozenset(('ValueError', 'TypeError', 'KeyError', 'IndexError',
    'ZeroDivisionError', 'RuntimeError', 'AssertionError', 'OverflowError'))
FUNCTION_METHODS = frozenset(('append', 'extend', 'insert', 'pop', 'remove', 'clear',
    'copy', 'count', 'index', 'reverse', 'sort', 'get', 'items', 'keys', 'values',
    'setdefault', 'update', 'add', 'discard', 'union', 'intersection', 'difference',
    'lower', 'upper', 'casefold', 'strip', 'lstrip', 'rstrip', 'split', 'rsplit',
    'splitlines', 'join', 'replace', 'startswith', 'endswith', 'find', 'rfind',
    'partition', 'rpartition', 'isdigit', 'isalpha', 'isalnum', 'isspace', 'zfill'))
FUNCTION_SCHEMA = 'nomad.frontier.function-contract.v1'


def validate_function_cases(rows: list[dict]) -> list[dict]:
    """A finite JSON API contract; expected values never enter a worker command."""
    if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
        raise ValueError('function contract requires 1..32 cases per partition')
    normalized = []
    for row in rows:
        if (not isinstance(row, dict) or set(row) - {'module', 'function', 'args', 'kwargs', 'expected', 'raises'}
                or not {'module', 'function', 'args'} <= set(row)
                or ('expected' in row) == ('raises' in row)):
            raise ValueError('invalid typed function case')
        if (not isinstance(row['module'], str) or not all(p.isidentifier() and '__' not in p for p in row['module'].split('.'))
                or not isinstance(row['function'], str) or not row['function'].isidentifier() or '__' in row['function']
                or not isinstance(row['args'], list) or not isinstance(row.get('kwargs', {}), dict)
                or any(not isinstance(k, str) or not k.isidentifier() or '__' in k for k in row.get('kwargs', {}))):
            raise ValueError('invalid callable or JSON argument shape')
        if 'raises' in row and row['raises'] not in FUNCTION_ERRORS:
            raise ValueError('unregistered exception contract')
        encoded = json.dumps(row, allow_nan=False, separators=(',', ':'))
        if len(encoded.encode()) > 4096:
            raise ValueError('function case exceeds JSON size budget')
        def bounded(value, depth=0):
            if depth > 8: raise ValueError('function JSON nesting exceeds budget')
            if isinstance(value, dict):
                if any(not isinstance(k, str) for k in value): raise ValueError('JSON keys must be strings')
                for v in value.values(): bounded(v, depth+1)
            elif isinstance(value, list):
                for v in value: bounded(v, depth+1)
            elif value is not None and type(value) not in (str, int, float, bool):
                raise ValueError('non JSON contract value')
        bounded(row)
        normalized.append({**row, 'kwargs': row.get('kwargs', {})})
    identities = [json.dumps({k: r[k] for k in ('module', 'function', 'args', 'kwargs')}, sort_keys=True) for r in normalized]
    if len(set(identities)) != len(identities): raise ValueError('duplicate function inputs')
    return normalized


def function_inputs(rows: list[dict]) -> list[dict]:
    return [{k: row[k] for k in ('module', 'function', 'args', 'kwargs')} for row in rows]


def _module_name(filename: str) -> str:
    parts = filename[:-3].split('/')
    if parts[-1] == '__init__': parts.pop()
    return '.'.join(parts)


def _function_import(node: ast.ImportFrom, module: str, package_init: bool) -> str:
    if not node.level: return node.module or ''
    package = module.split('.') if package_init else module.split('.')[:-1]
    if node.level > len(package): raise ValueError('relative import escapes admitted package')
    return '.'.join(package[:len(package)-node.level+1] + ([node.module] if node.module else []))


def admit_function_sources(files: dict[str, str]) -> dict:
    """Reject channels that could impersonate the trusted return-value observer.

    This is a restricted grammar admission rule, not a Python sandbox. Execution
    still requires qualified Docker. Classes, callbacks, dynamic imports,
    reflection, external libraries and arbitrary module initialization HOLD.
    """
    import builtins
    forbidden_builtins = set(dir(builtins)) - FUNCTION_BUILTINS - FUNCTION_ERRORS
    modules = {_module_name(name): name for name in files}
    if len(modules) != len(files) or '' in modules or not 1 <= len(files) <= 32:
        raise ValueError('function adapter requires 1..32 uniquely named modules')
    if any(m.split('.')[0] in sys.stdlib_module_names or not all(p.isidentifier() for p in m.split('.')) for m in modules):
        raise ValueError('repository module shadows standard library or has invalid name')
    trees = {}
    symbols = {}
    for name, source in files.items():
        if len(source.encode()) > 32768: raise ValueError('module exceeds parser budget')
        tree = ast.parse(source)
        if sum(1 for _ in ast.walk(tree)) > 512: raise ValueError('module AST exceeds budget')
        trees[name] = tree
        symbols[name] = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        if len(symbols[name]) != len(set(symbols[name])): raise ValueError('duplicate function definition')
    graph = {name: set() for name in files}
    for name, tree in trees.items():
        imported = set()
        module_aliases = {}
        import_bindings = set()
        def bind_import(bound):
            if bound in import_bindings or '__' in bound or bound in forbidden_builtins:
                raise ValueError('duplicate or reserved import binding')
            import_bindings.add(bound)
        module = _module_name(name)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == '__future__' and not node.level:
                if [a.name for a in node.names] != ['annotations']: raise ValueError('unsupported future import')
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in modules: raise ValueError('external import outside function contract')
                        bound = alias.asname or alias.name
                        if '.' in bound: raise ValueError('dotted imports require explicit alias')
                        bind_import(bound)
                        module_aliases[bound] = modules[alias.name]
                        graph[name].add(modules[alias.name])
                else:
                    dependency = _function_import(node, module, name.endswith('/__init__.py'))
                    if dependency not in modules: raise ValueError('external or unresolved local import')
                    dependency_file = modules[dependency]
                    for alias in node.names:
                        if alias.name not in symbols[dependency_file]: raise ValueError('only ordinary local functions may be imported')
                        bind_import(alias.asname or alias.name)
                        imported.add(alias.asname or alias.name)
                    graph[name].add(dependency_file)
            elif isinstance(node, ast.FunctionDef):
                if '__' in node.name: raise ValueError('reflection-shaped function export refused')
                if len(node.args.args)+len(node.args.posonlyargs)+len(node.args.kwonlyargs)>8:
                    raise ValueError('function parameter budget exceeded')
                if node.decorator_list or node.args.vararg or node.args.kwarg:
                    raise ValueError('decorators and variadic functions outside adapter')
                for default in [*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)]:
                    ast.literal_eval(default)
                if any(isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Lambda)) for statement in node.body for n in ast.walk(statement)):
                    raise ValueError('nested definitions and callbacks outside adapter')
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                ast.literal_eval(node.value)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(not isinstance(t, ast.Name) for t in targets): raise ValueError('module assignment must bind literal constants')
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                pass
            else: raise ValueError('executable module initialization outside adapter')
        callable_names = set(symbols[name]) | imported | FUNCTION_BUILTINS | FUNCTION_ERRORS
        prohibited = (ast.ClassDef, ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom,
            ast.Lambda, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.AsyncFor,
            ast.NamedExpr, ast.Delete, ast.Match)
        for node in ast.walk(tree):
            if isinstance(node, prohibited): raise ValueError('unsupported function grammar: ' + type(node).__name__)
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in tree.body:
                raise ValueError('function-local import outside adapter')
            if isinstance(node, ast.Name) and ('__' in node.id or node.id in forbidden_builtins):
                raise ValueError('reflection or nonapproved builtin value refused')
            if isinstance(node, ast.arg) and '__' in node.arg: raise ValueError('reflection parameter refused')
            annotation=(node.annotation if isinstance(node,(ast.arg,ast.AnnAssign)) else
                        node.returns if isinstance(node,ast.FunctionDef) else None)
            if annotation is not None and any(isinstance(n,ast.Call) for n in ast.walk(annotation)):
                raise ValueError('executable annotation outside adapter')
            if ((isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in module_aliases)
                    or isinstance(node, ast.arg) and node.arg in module_aliases
                    or isinstance(node, (ast.FunctionDef, ast.ExceptHandler)) and node.name in module_aliases):
                raise ValueError('local module alias rebinding or shadowing refused')
            if isinstance(node, ast.Attribute):
                if '__' in node.attr: raise ValueError('reflection attribute refused')
                local_export = isinstance(node.value, ast.Name) and node.value.id in module_aliases and node.attr in symbols[module_aliases[node.value.id]]
                if not local_export and node.attr not in FUNCTION_METHODS: raise ValueError('unregistered attribute access')
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id not in callable_names: raise ValueError('dynamic or unregistered call')
                elif not isinstance(node.func, ast.Attribute): raise ValueError('indirect callable refused')
                if any(k.arg is None for k in node.keywords) or any(isinstance(a, ast.Starred) for a in node.args):
                    raise ValueError('dynamic argument expansion outside adapter')
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(n, ast.Attribute) for t in targets for n in ast.walk(t)):
                    raise ValueError('module/object attribute mutation refused')
    return {'modules': modules, 'symbols': symbols, 'graph': {k: sorted(v) for k, v in graph.items()}}


def inspect_function_structure(root: Path, public: list[dict]) -> dict:
    """Admit source and contracts without generating or executing candidates."""
    from .isolation import _input_paths, SandboxPolicy
    public = validate_function_cases(public)
    files = {}
    admitted_paths=_input_paths(Path(root),policy=SandboxPolicy('inspection@sha256:'+'0'*64))
    for path,relative,metadata in admitted_paths:
        if path.suffix.casefold() in ('.so','.pyd','.dll','.dylib','.pyc','.pyo','.egg','.zip'):
            raise ValueError('binary/bytecode import artifact outside source observer contract')
        if path.suffix!='.py': continue
        rel = relative.as_posix()
        if any(p in ('tests', 'test') for p in path.relative_to(root).parts) or path.name.startswith('test_'): continue
        if len(files) >= 32 or path.stat().st_size > 32768: raise ValueError('function source parser budget exceeded')
        files[rel] = path.read_text(encoding='utf-8')
    structure = admit_function_sources(files)
    for row in public:
        name = structure['modules'].get(row['module'])
        if not name or row['function'] not in structure['symbols'][name]: raise ValueError('contract callable is not an admitted definition')
    return {**structure, 'files': files}


def inspect_function_repository(root: Path, public: list[dict], *, max_candidates=64,
        max_files_changed=2, genesis_max_eval=4096, generation_files=None, ast_check_budget=None) -> dict:
    from .python_operators import generate_python_candidates
    from .genesis import IOExample, SynthesisTask, synthesize
    if (type(max_candidates) is not int or not 0 <= max_candidates <= 128
            or max_files_changed not in (1, 2) or type(genesis_max_eval) is not int
            or not 0 <= genesis_max_eval <= 4096):
        raise ValueError('function proposal budgets invalid')
    if ast_check_budget is not None and (type(ast_check_budget) is not int or not 0<=ast_check_budget<=4096):
        raise ValueError('AST candidate check budget invalid')
    public = validate_function_cases(public)
    inspected = inspect_function_structure(root, public)
    files = inspected['files']
    structure = {k:v for k,v in inspected.items() if k!='files'}
    selected_files = list(files) if generation_files is None else list(generation_files)
    if (len(set(selected_files)) != len(selected_files) or any(name not in files for name in selected_files)):
        raise ValueError('generation localization must reference admitted source files')
    single = []
    synthesis_runs = []
    # Reuse GENESIS's typed finite expression language for eligible public
    # two-integer APIs. Parameter alpha-renaming is AST-based, never text eval.
    for module, function in sorted({(r['module'],r['function']) for r in public}):
        cases=[r for r in public if (r['module'],r['function'])==(module,function)]
        name=structure['modules'][module]
        if not max_candidates or not genesis_max_eval or name not in selected_files: continue
        tree=ast.parse(files[name]); fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==function)
        if (len(fn.args.args)!=2 or fn.args.posonlyargs or fn.args.kwonlyargs or fn.args.defaults
                or any(r['kwargs'] or len(r['args'])!=2 or any(type(v) is not int or abs(v)>10000 for v in r['args'])
                       or type(r.get('expected')) is not int or abs(r['expected'])>1000000 for r in cases)):
            continue
        run=synthesize(SynthesisTask('function-public', 'def solve(x, y):\n    return 0\n',
            tuple(IOExample(r['args'][0],r['args'][1],r['expected']) for r in cases),(),()),max_eval=genesis_max_eval,max_nodes=7)
        synthesis_runs.append({'module':module,'function':function,**asdict(run)})
        if run.candidate is None: continue
        class Rename(ast.NodeTransformer):
            def visit_Name(self,node):
                return ast.copy_location(ast.Name(id={'x':fn.args.args[0].arg,'y':fn.args.args[1].arg}.get(node.id,node.id),ctx=node.ctx),node)
        expression=Rename().visit(ast.parse(run.candidate,mode='eval').body)
        fn.body=[ast.Return(value=expression)]
        ast.fix_missing_locations(tree); replacement=ast.unparse(tree)+'\n'
        admit_function_sources({**files,name:replacement})
        patch={name:replacement}
        single.append({'id':digest(json.dumps(patch,sort_keys=True)),'files':patch,'family':'binary_operator',
                       'origin':'GENESIS','description':'public-only typed expression synthesis with parameter binding'})
    generated = 0
    for name in selected_files if max_candidates else ():
        source = files[name]
        groups = generate_python_candidates(source)
        # Round-robin families prevents identifier combinatorics crowding out
        # comparison/control-flow edits. All filters are source/public only.
        flattened = [rows[i] for i in range(max([len(v) for v in groups.values()] or [0])) for rows in groups.values() if i < len(rows)]
        accepted = 0
        for candidate in flattened:
            if ast_check_budget is not None and generated>=ast_check_budget: break
            generated += 1
            try:
                updated = admit_function_sources({**files, name: candidate.source})
                if updated['symbols'] != structure['symbols'] or updated['graph'] != structure['graph']: continue
            except (ValueError, SyntaxError, RecursionError): continue
            patch = {name: candidate.source}
            single.append({'id': digest(json.dumps(patch, sort_keys=True)), 'files': patch,
                           'family': candidate.operator_family, 'description': candidate.description})
            accepted += 1
            if accepted >= min(32, max(8, max_candidates // max(1,len(files)*2))): break
        if ast_check_budget is not None and generated>=ast_check_budget: break
    single = list({item['id']: item for item in reversed(single)}.values())[::-1]
    proposals = list(single)
    if max_files_changed == 2:
        for i, first in enumerate(single):
            for second in single[i+1:]:
                if set(first['files']) & set(second['files']): continue
                patch = {**first['files'], **second['files']}
                proposals.append({'id': digest(json.dumps(patch, sort_keys=True)), 'files': patch,
                    'family': first['family'] if first['family'] == second['family'] else 'binary_operator',
                    'description': 'bounded composition: ' + first['description'] + '; ' + second['description']})
                if len(proposals) >= max_candidates: break
            if len(proposals) >= max_candidates: break
    proposals = proposals[:max_candidates]
    return {**structure, 'files': files, 'proposals': proposals, 'generated_candidates_checked': generated,
            'genesis':synthesis_runs,
            'candidate_inventory_sha256': digest(json.dumps(proposals, sort_keys=True))}


FUNCTION_OBSERVER = '''import importlib,json,sys
requests=json.loads(sys.argv[1])
sys.path.insert(0,"/work")
observed=[]
for request in requests:
    try:
        module=importlib.import_module(request["module"])
        function=getattr(module,request["function"])
        value=function(*request["args"],**request["kwargs"])
        observed.append({"value":value})
    except Exception as error:
        observed.append({"raises":type(error).__name__})
print(json.dumps({"schema":"nomad.frontier.observation.v1","observed":observed},sort_keys=True,separators=(",",":"),allow_nan=False))
'''


def function_command(rows: list[dict]) -> list[str]:
    payload=json.dumps(function_inputs(rows), sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(payload.encode())>12000: raise ValueError('function invocation payload exceeds portable command budget')
    return ['python', '-I', '-B', '-c', FUNCTION_OBSERVER,
            payload]


def compare_function_output(execution: dict, rows: list[dict]) -> dict:
    output = execution.get('output_utf8')
    if not isinstance(output, str) or digest(output) != execution.get('output_sha256') or execution.get('output_truncated'):
        raise ValueError('complete integrity-bound observer output required')
    if not execution.get('tests_passed'):
        return {'matches': [False] * len(rows), 'observed_sha256': digest(output), 'supported': False}
    try: observed = json.loads(output)
    except ValueError as error: raise ValueError('observer did not return one JSON document') from error
    if (not isinstance(observed, dict) or set(observed) != {'schema', 'observed'}
            or observed['schema'] != 'nomad.frontier.observation.v1'
            or not isinstance(observed['observed'], list) or len(observed['observed']) != len(rows)):
        raise ValueError('observer protocol mismatch')
    expected = [{'value': r['expected']} if 'expected' in r else {'raises': r['raises']} for r in rows]
    # Canonical JSON equality preserves booleans versus numbers and dict order.
    matches = [json.dumps(v, sort_keys=True, allow_nan=False) == json.dumps(w, sort_keys=True, allow_nan=False)
               for v, w in zip(observed['observed'], expected)]
    return {'matches': matches, 'observed_sha256': digest(output), 'supported': all(matches)}
