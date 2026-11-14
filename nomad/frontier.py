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
