"""TRANSCEND v0.13 — portable, bounded program synthesis and native receipts.

The learnable core is NOMAD's original GENESIS GrammarPrior conditioned on
Bitwork's binary failure signature. Neither the prior nor its ledger contains
language identity in the score key. Only typed, side-effect-free integer
expressions are emitted. This is a research laboratory, NOT a sandbox for
untrusted source or a general compiler/language-model interface.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Iterable

from .genesis import GrammarPrior, IOExample, SynthesisTask, _signature, synthesize
from .witness import Witness, WitnessReceipt

SCHEMA = 'nomad.transcend.memory.v1'
ZERO = '0' * 64
MAX_INTEGER = (1 << 53) - 1   # common exact integer range across Python/JS/Rust
OPS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*'}
LANGUAGES = ('python', 'javascript', 'rust')


def digest(obj: object) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _tree(expr: str) -> ast.expr:
    if len(expr) > 512 or '\x00' in expr:
        raise ValueError('expression too long or invalid')
    root = ast.parse(expr, mode='eval').body
    count = 0
    def validate(node: ast.AST, depth: int = 0):
        nonlocal count
        count += 1
        if count > 31 or depth > 12:
            raise ValueError('expression exceeds bounded grammar')
        if isinstance(node, ast.Name) and node.id in ('x', 'y'):
            return
        if isinstance(node, ast.Constant) and type(node.value) is int and -3 <= node.value <= 3:
            return
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            validate(node.left, depth + 1)
            validate(node.right, depth + 1)
            return
        raise ValueError('unsupported expression syntax')
    validate(root)
    return root


def _emit(node: ast.expr) -> str:
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Constant): return str(node.value)
    if isinstance(node, ast.BinOp): return f'({_emit(node.left)} {OPS[type(node.op)]} {_emit(node.right)})'
    raise ValueError('unreachable expression node')


def canonical(expr: str) -> str:
    return _emit(_tree(expr))


def _eval_node(node: ast.expr, x: int, y: int) -> int:
    if isinstance(node, ast.Name): return x if node.id == 'x' else y
    if isinstance(node, ast.Constant): return int(node.value)
    a, b = _eval_node(node.left, x, y), _eval_node(node.right, x, y)
    if isinstance(node.op, ast.Add): value = a+b
    elif isinstance(node.op, ast.Sub): value = a-b
    else: value = a*b
    if abs(value) > MAX_INTEGER:
        raise OverflowError('not portable to all supported numeric semantics')
    return value


def reference_values(expr: str, rows: Iterable[IOExample]) -> tuple[int, ...]:
    tree = _tree(expr)
    vals = []
    for r in rows:
        if any(type(v) is not int or abs(v) > MAX_INTEGER for v in (r.x, r.y)):
            raise OverflowError('unbounded input or non-integer')
        vals.append(_eval_node(tree, r.x, r.y))
    return tuple(vals)


def render(language: str, expr: str) -> str:
    if language not in LANGUAGES: raise ValueError('unsupported language')
    body = canonical(expr)
    if language == 'python':
        return f'def solve(x: int, y: int) -> int:\n    return {body}\n'
    if language == 'javascript':
        return f'function solve(x, y) {{ return {body}; }}\nmodule.exports = {{solve}};\n'
    return f'fn solve(x: i64, y: i64) -> i64 {{ {body} }}\n'


def _runner(language: str, source: str) -> str:
    if language == 'python':
        return source + ('\nimport sys\nfor line in sys.stdin:\n'
                         '    if line.strip():\n'
                         '        x, y = map(int, line.split())\n'
                         '        print(solve(x, y))\n')
    if language == 'javascript':
        return source + ('\nconst fs = require("node:fs");\n'
                         'const input = fs.readFileSync(0, "utf8");\n'
                         'for (const line of input.trim().split(/\\r?\\n/)) {\n'
                         '  if (!line.trim()) continue;\n'
                         '  const [x,y] = line.trim().split(/\\s+/).map(Number);\n'
                         '  const value = solve(x,y);\n'
                         '  if (!Number.isSafeInteger(value)) throw new Error("unsafe integer");\n'
                         '  process.stdout.write(String(value)+"\\n");\n}\n')
    return source + ('\nuse std::io::{self, Read};\n'
                     'fn main() {\n'
                     '  let mut input = String::new();\n'
                     '  io::stdin().read_to_string(&mut input).unwrap();\n'
                     '  for row in input.lines() {\n'
                     '    if row.trim().is_empty() { continue; }\n'
                     '    let mut parts = row.split_whitespace();\n'
                     '    let x: i64 = parts.next().unwrap().parse().unwrap();\n'
                     '    let y: i64 = parts.next().unwrap().parse().unwrap();\n'
                     '    println!("{}", solve(x, y));\n'
                     '  }\n}\n')


@dataclass(frozen=True)
class NativeResult:
    status: str
    values: tuple[int, ...]
    language: str
    source_sha256: str
    reason: str = ''


def native_available(language: str) -> bool:
    return language == 'python' or language == 'javascript' and shutil.which('node') is not None or language == 'rust' and shutil.which('rustc') is not None


def run_native(language: str, expr: str, rows: tuple[IOExample, ...], *, timeout: float = 7.0) -> NativeResult:
    """Run ONLY grammar-generated trusted code through installed native toolchain.

    This is not a security sandbox. The adapter refuses to execute any external
    source and emits the entire process body from a validated typed expression.
    """
    src = _runner(language, render(language, expr))
    src_hash = sha256(src.encode()).hexdigest()
    if not rows: return NativeResult('invalid', (), language, src_hash, 'empty rows')
    try:
        expected = reference_values(expr, rows)  # preflight numeric domain
    except (ValueError, OverflowError) as exc:
        return NativeResult('invalid', (), language, src_hash, str(exc))
    if not native_available(language):
        return NativeResult('unavailable', (), language, src_hash, 'native compiler/runtime missing')
    ext = {'python':'.py','javascript':'.js','rust':'.rs'}[language]
    input_text = ''.join(f'{e.x} {e.y}\n' for e in rows)
    try:
        with tempfile.TemporaryDirectory(prefix='nomad-transcend-') as raw:
            folder=Path(raw)
            program=folder/('solution'+ext)
            program.write_text(src,encoding='utf-8')
            if language == 'python':
                command=[sys.executable, '-I', '-S', '-B', str(program)]
            elif language == 'javascript':
                command=['node', str(program)]
            else:
                executable=folder/'nomad-rust-case'
                compile_run=subprocess.run(['rustc','--edition=2021','-O',str(program),'-o',str(executable)],
                                           cwd=folder,capture_output=True,text=True,timeout=timeout,check=False)
                if compile_run.returncode:
                    return NativeResult('failed',(),language,src_hash,'Rust compile error: '+compile_run.stderr[:1500])
                command=[str(executable)]
            ran=subprocess.run(command,input=input_text,cwd=folder,capture_output=True,
                               text=True,timeout=timeout,check=False)
            if ran.returncode:
                return NativeResult('failed',(),language,src_hash,'execution failed: '+ran.stderr[:1500])
            actual=tuple(int(line.strip()) for line in ran.stdout.splitlines())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return NativeResult('failed',(),language,src_hash,type(exc).__name__+': '+str(exc)[:250])
    if actual != expected:
        return NativeResult('mismatch',actual,language,src_hash,'native and independent IR semantics differ')
    if len(actual)!=len(rows):
        return NativeResult('mismatch',actual,language,src_hash,'wrong output count')
    return NativeResult('passed',actual,language,src_hash)


def witnessed(language: str, task: SynthesisTask, expr: str) -> tuple[WitnessReceipt | None, dict]:
    """Withhold challenge from synthesis, give WITNESS actual native observations."""
    prev='x+y'
    pub=run_native(language,expr,task.public)
    chal=run_native(language,expr,task.challenge)
    before_p=run_native(language,prev,task.public)
    before_c=run_native(language,prev,task.challenge)
    statuses=(pub.status,chal.status,before_p.status,before_c.status)
    info={'native_statuses':statuses,'language':language,'program_sha256':sha256(render(language,expr).encode()).hexdigest()}
    if statuses != ('passed',)*4:
        return None,info
    receipt=Witness(witness_id='nomad-witness-v013-transcend').attest(
        task_id=task.task_id,transmission_id=info['program_sha256'],world_epoch=0,
        current_public=tuple(map(float,before_p.values)),target_public=tuple(float(e.expected) for e in task.public),
        candidate_public=tuple(map(float,pub.values)),
        current_challenge=tuple(map(float,before_c.values)),target_challenge=tuple(float(e.expected) for e in task.challenge),
        candidate_challenge=tuple(map(float,chal.values)))
    return receipt,info


class TransferMemory:
    """Hash-linked witnessed root-operator preferences; old MNEMONIC untouched.

    The prior's key is (Bitwork failure signature, AST production), never
    language or filename. An evidence store checksum is NOT an authentication
    boundary; fresh target-language WITNESS remains mandatory.
    """
    def __init__(self):
        self.events: list[dict] = []
        self.head=ZERO
        self.frozen=False
        self._tasks:set[str]=set()

    def add(self, language: str, task: SynthesisTask, expression: str, receipt: WitnessReceipt) -> None:
        if self.frozen:raise ValueError('frozen memory')
        if language not in LANGUAGES:raise ValueError('invalid language')
        if task.task_id in self._tasks:raise ValueError('same task is not independent support')
        if not receipt.verify_checksum() or not receipt.supported or receipt.task_id!=task.task_id:
            raise ValueError('WITNESS support required')
        if receipt.transmission_id != sha256(render(language,expression).encode()).hexdigest():
            raise ValueError('receipt not for this source')
        tree=_tree(expression)
        if not isinstance(tree,ast.BinOp):raise ValueError('root has no learned grammar production')
        name=type(tree.op).__name__
        event={'task_id':task.task_id,'source_language':language,
               'context_bits':_signature(task),'root_operator':name,
               'program_sha256':receipt.transmission_id,'witness_receipt':asdict(receipt),
               'witness_sha256':receipt.receipt_hash}
        chain={'previous':self.head,'event':event}
        chain['sha256']=digest(chain)
        self.head=chain['sha256'];self.events.append(chain);self._tasks.add(task.task_id)

    def freeze(self):self.frozen=True

    def snapshot(self)->dict:
        return {'schema':SCHEMA,'events':self.events,'head':self.head,'frozen':self.frozen,
                'transfer_key':'bitwork_failure_bits + AST_root_operator; language_not_in_key',
                'predecessor':'NOMAD v0.12 MNEMONIC (separate evidence scope)'}

    def save(self,path: str|Path)->str:
        body=self.snapshot()
        doc={'payload':body,'payload_sha256':digest(body)}
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_name(path.name+'.tmp')
        tmp.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        os.replace(tmp,path)
        return doc['payload_sha256']

    @classmethod
    def load(cls,path: str|Path)->'TransferMemory':
        doc=json.loads(Path(path).read_text(encoding='utf-8'))
        body=doc['payload']
        if digest(body)!=doc['payload_sha256'] or body.get('schema')!=SCHEMA or body.get('frozen') is not True:
            raise ValueError('corrupt or unfrozen transfer memory')
        if body.get('transfer_key') != 'bitwork_failure_bits + AST_root_operator; language_not_in_key':
            raise ValueError('transfer signature changed')
        out=cls();prev=ZERO
        for chain in body['events']:
            if chain['previous']!=prev or digest({'previous':prev,'event':chain['event']})!=chain['sha256']:
                raise ValueError('broken evidence chain')
            ev=chain['event'];receipt=WitnessReceipt(**ev['witness_receipt'])
            if not receipt.verify_checksum() or not receipt.supported or receipt.task_id!=ev['task_id'] or receipt.receipt_hash!=ev['witness_sha256']:
                raise ValueError('invalid stored WITNESS receipt')
            if receipt.transmission_id!=ev['program_sha256'] or ev['source_language'] not in LANGUAGES or ev['root_operator'] not in ('Add','Sub','Mult'):
                raise ValueError('invalid training event')
            if not isinstance(ev['context_bits'],int) or ev['context_bits']<0 or ev['context_bits']>=1<<11:
                raise ValueError('invalid context bits')
            if ev['task_id'] in out._tasks:raise ValueError('duplicate evidence task')
            prev=chain['sha256'];out._tasks.add(ev['task_id']);out.events.append(chain)
        if prev!=body['head']:raise ValueError('wrong ledger head')
        out.head=prev;out.frozen=True
        return out

    def prior(self, *, contextual: bool) -> GrammarPrior:
        prior=GrammarPrior(contextual=contextual)
        for record in self.events:
            ev=record['event']
            for op in ('Add','Sub','Mult'):
                prior.operator.update(ev['context_bits'], op, ev['root_operator']==op)
            prior.witnessed+=1
        return prior

    def source_languages(self)->tuple[str,...]:
        return tuple(sorted({x['event']['source_language'] for x in self.events}))


def shifted_context(prior: GrammarPrior) -> GrammarPrior:
    shuffled=copy.deepcopy(prior)
    contexts=sorted({s for s,_ in shuffled.operator.context_counts})
    if len(contexts)>1:
        remap={c:contexts[(i+1)%len(contexts)] for i,c in enumerate(contexts)}
        shuffled.operator.context_counts={(remap[s],op):v for (s,op),v in shuffled.operator.context_counts.items()}
    return shuffled
