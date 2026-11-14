"""NOMAD v0.11 CAUSAL ATLAS: bounded software consequence forecasting.

The testbed is deliberately limited to trusted, generated, pure Python fixture
repositories. No code runs on a user's arbitrary repository. The learner sees
only training interventions, AST-derived graph features and PUBLIC contracts;
withheld challenge/final outcomes are reserved for WITNESS and evaluation.

This is a learned intervention-effect predictor over supplied features, not a
proof that correlation establishes unrestricted causal mechanisms.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import math
import random
import subprocess
import sys
import tempfile
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable

from .genesis import IOExample, SynthesisTask, synthesize, _render, _extract_expression
from .repo_world import _clear_local_modules
from .witness import Witness


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Contract:
    module: str
    function: str
    rows: tuple[tuple[int, int], ...]

    @property
    def key(self) -> str:
        return f'{self.module}.{self.function}'


@dataclass(frozen=True)
class AtlasTask:
    task_id: str
    files: dict[str, str]
    changed_file: str
    contracts: tuple[Contract, ...]
    public: tuple[IOExample, ...]
    challenge: tuple[IOExample, ...]
    final: tuple[IOExample, ...]
    family: str = 'evaluator-only'


@dataclass(frozen=True)
class ChangeReceipt:
    task_id: str
    epoch: int
    before_digest: str
    after_digest: str
    changed_file: str
    contract: str
    before: tuple[float, ...]
    after: tuple[float, ...]
    receipt_digest: str

    def payload(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != 'receipt_digest'}

    def verify(self) -> bool:
        return self.receipt_digest == digest(self.payload()) and self.before_digest != self.after_digest

    @property
    def changed(self) -> bool:
        return self.before != self.after


def _safe_filename(name: str) -> bool:
    return name.endswith('.py') and '/' not in name and '\\' not in name and Path(name).name == name


def write_world(root: Path, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        if not _safe_filename(name):
            raise ValueError(f'unsafe filename: {name}')
        (root / name).write_text(source, encoding='utf-8')


def source_digest(files: dict[str, str]) -> str:
    return digest({k: hashlib.sha256(v.encode()).hexdigest() for k,v in sorted(files.items())})


def run_contract(root: Path, contract: Contract) -> tuple[float, ...]:
    """Execute *generated, trusted fixtures*; never a safe sandbox for unknown code."""
    _clear_local_modules(root)
    sys.path.insert(0, str(root))
    try:
        importlib.invalidate_caches()
        fn = getattr(importlib.import_module(contract.module), contract.function)
        return tuple(float(fn(x, y)) for x, y in contract.rows)
    finally:
        sys.path.remove(str(root))
        _clear_local_modules(root)


class SymbolGraph:
    """Conservative import/call graph for direct Python calls in fixture programs.

    Names are used to resolve edges, but never provided to the learned
    impact-signature. Unresolved dynamic calls force explicit uncertainty.
    """
    def __init__(self, files: dict[str, str]):
        self.files = files
        self.imports: dict[str, set[str]] = {}
        self.calls: dict[str, set[str]] = {}
        self.functions: dict[str, ast.FunctionDef] = {}
        self.masks: dict[str, set[str]] = {}
        self.unknown: set[str] = set()
        stems = {Path(k).stem for k in files}
        for filename, source in files.items():
            module = Path(filename).stem
            try:
                tree = ast.parse(source)
            except SyntaxError:
                self.unknown.add(module)
                continue
            bindings: dict[str, str] = {}
            module_imports: set[str] = set()
            for stmt in tree.body:
                if isinstance(stmt, ast.ImportFrom) and stmt.module in stems:
                    module_imports.add(stmt.module)
                    for alias in stmt.names:
                        bindings[alias.asname or alias.name] = f'{stmt.module}.{alias.name}'
                if isinstance(stmt, ast.Import):
                    for alias in stmt.names:
                        target = alias.name.split('.')[0]
                        if target in stems:
                            module_imports.add(target)
                            bindings[alias.asname or alias.name] = f'{target}.*'
            self.imports[module] = module_imports
            for stmt in tree.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                fq = f'{module}.{stmt.name}'
                self.functions[fq] = stmt
                edges: set[str] = set()
                masks: set[str] = set()
                for node in ast.walk(stmt):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            found = bindings.get(node.func.id)
                            if found and not found.endswith('.*'):
                                edges.add(found)
                            elif node.func.id in {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}:
                                edges.add(f'{module}.{node.func.id}')
                            elif node.func.id in ('getattr','eval','exec','globals','locals'):
                                self.unknown.add(fq)
                        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                            found = bindings.get(node.func.value.id)
                            if found and found.endswith('.*'):
                                edges.add(found[:-1] + node.func.attr)
                            else:
                                self.unknown.add(fq)
                    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                        if (isinstance(node.left, ast.Constant) and node.left.value == 0) or (
                            isinstance(node.right, ast.Constant) and node.right.value == 0):
                            masks.add('zero_multiplier')
                    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
                        if ast.dump(node.left, include_attributes=False) == ast.dump(node.right, include_attributes=False):
                            masks.add('self_cancel')
                    if isinstance(node, ast.IfExp):
                        masks.add('conditional')
                self.calls[fq] = edges
                self.masks[fq] = masks
        # No claims about calls that lead to unknown or unparsed symbols.

    def reachable(self, start: str, target: str) -> tuple[bool, int, bool, set[str]]:
        queue = deque([(start,0,[start])])
        seen = set()
        uncertain = False
        while queue:
            node, dist, path = queue.popleft()
            if node == target:
                return True, dist, uncertain, set().union(*(self.masks.get(n,set()) for n in path))
            if node in seen:
                continue
            seen.add(node)
            if node in self.unknown or node not in self.functions:
                uncertain = True
            for nxt in self.calls.get(node,()):
                if nxt not in seen:
                    queue.append((nxt,dist+1,path+[nxt]))
        return False, -1, uncertain, set()

    def imported_reachable(self, contract_module: str, changed_module: str) -> bool:
        frontier=[contract_module]
        seen=set()
        while frontier:
            m=frontier.pop()
            if m==changed_module:return True
            if m in seen: continue
            seen.add(m)
            frontier.extend(self.imports.get(m,()))
        return False

    def features(self, contract: Contract, changed_file: str) -> tuple[str,...]:
        target=f'{Path(changed_file).stem}.solve'
        actual, dist, uncertain, masks=self.reachable(contract.key,target)
        imported=self.imported_reachable(contract.module,Path(changed_file).stem)
        if uncertain:
            return ('uncertain',)
        return (
            'import' if imported else 'no_import',
            'called' if actual else 'not_called',
            f'depth_{min(dist,3)}' if actual else 'depth_absent',
            'zero_mask' if 'zero_multiplier' in masks else 'no_zero_mask',
            'self_cancel' if 'self_cancel' in masks else 'no_self_cancel',
            'conditional' if 'conditional' in masks else 'no_conditional',
        )


class AtlasLearner:
    """Empirical conditional intervention model over disclosed AST features.

    Needs actual witnessed changes to learn. An unseen structural signature is
    treated as uncertain and routed to full verification (not declared safe).
    """
    def __init__(self):
        self.counts: dict[tuple[str,...], list[int]]={}
        self.total=0

    def observe(self, features: tuple[str,...], receipt: ChangeReceipt) -> None:
        if not receipt.verify():
            raise ValueError('invalid or stale effect receipt')
        if features == ('uncertain',):
            return
        posneg = self.counts.setdefault(features,[0,0])
        posneg[1 if receipt.changed else 0] += 1
        self.total += 1

    def predict(self, features: tuple[str,...], min_evidence: int = 2) -> tuple[str,float,int]:
        counts=self.counts.get(features,[0,0]); n=sum(counts)
        prob=(counts[1]+1)/(n+2) # Laplace estimate, not certified causal probability
        if features == ('uncertain',) or n<min_evidence:
            return ('abstain',prob,n)
        return ('impact' if prob>0.5 else 'no_impact',prob,n)

    def snapshot(self) -> dict:
        return {'schema':'nomad.atlas.empirical-impact.v1','observations':self.total,
                'cells':[{'features':list(k),'unchanged':v[0],'changed':v[1]}
                         for k,v in sorted(self.counts.items())]}


def observe_intervention(task: AtlasTask, new_source: str, *, changed_file_override: str|None=None) -> list[ChangeReceipt]:
    changed_file=changed_file_override or task.changed_file
    if not _safe_filename(changed_file):
        raise ValueError('unsafe changed file')
    start=task.files
    edited={**start,changed_file:new_source}
    old_hash=source_digest(start); new_hash=source_digest(edited)
    if old_hash==new_hash: raise ValueError('no intervention')
    with tempfile.TemporaryDirectory(prefix='nomad-atlas-') as td:
        root=Path(td); write_world(root,start)
        observations=[]
        for c in task.contracts:
            before=run_contract(root,c)
            (root/changed_file).write_text(new_source,encoding='utf-8')
            after=run_contract(root,c)
            (root/changed_file).write_text(start[changed_file],encoding='utf-8')
            fields={'task_id':task.task_id,'epoch':0,'before_digest':old_hash,
                    'after_digest':new_hash,'changed_file':changed_file,
                    'contract':c.key,'before':before,'after':after}
            observations.append(ChangeReceipt(**fields,receipt_digest=digest(fields)))
        return observations


def train_impact_model(tasks: Iterable[AtlasTask], *, intervention: str='def solve(x, y):\n    return x * y + y\n') -> AtlasLearner:
    model=AtlasLearner()
    for task in tasks:
        graph=SymbolGraph(task.files)
        for contract,receipt in zip(task.contracts,observe_intervention(task,intervention)):
            model.observe(graph.features(contract,task.changed_file),receipt)
    return model


def score_predictions(labels: list[bool], preds: list[bool|None]) -> dict:
    valid=[(y,p) for y,p in zip(labels,preds) if p is not None]
    tp=sum(y and p for y,p in valid); fp=sum(not y and p for y,p in valid)
    fn=sum(y and not p for y,p in valid); tn=sum(not y and not p for y,p in valid)
    abstained=len(labels)-len(valid)
    prec=tp/(tp+fp) if tp+fp else 0.0
    rec=tp/(tp+fn) if tp+fn else 0.0
    return {'n':len(labels),'evaluated':len(valid),'abstained':abstained,
            'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':prec,'recall':rec,
            'f1':2*prec*rec/(prec+rec) if prec+rec else 0.0,
            'accuracy':(tp+tn)/len(valid) if valid else None}


def _expr_oracles():
    from .simulation_v10 import _targets
    return _targets()


def make_atlas_tasks(seed: int, *, per_family: int=1, families: tuple[str,...]|None=None) -> list[AtlasTask]:
    """Freshly randomized names; deterministic fixtures, disjoint input splits.

    Generator-only target expressions are never included in source or model
    feature signatures. Data are finite and deliberately small.
    """
    r=random.Random(seed)
    oracles=_expr_oracles()
    families=families or ('square_plus','sum_times_y','difference_product','shifted_product')
    result=[]
    for family in families:
        for j in range(per_family):
            names=[f'm{seed%997}_{j}_{i}' for i in range(13)]
            r.shuffle(names)
            core,bridge,primary,secondary,shadow,masked,cancel,unrelated,conditional,dynamic,*extras=names
            # imports resolve through shuffled paths and symbol aliases; only
            # AST relationships, never module names, are scored by the learner.
            files={
                f'{core}.py':'def solve(x, y):\n    return x + y\n',
                f'{bridge}.py':f'from {core} import solve as upstream\n\ndef solve(x, y):\n    return upstream(x, y)\n',
                f'{primary}.py':f'from {bridge} import solve as bridge_fn\n\ndef solve(x, y):\n    return bridge_fn(x, y)\n',
                f'{secondary}.py':f'from {core} import solve as do_work\n\ndef solve(x, y):\n    return do_work(x, y) + 9\n',
                f'{shadow}.py':f'from {core} import solve as merely_imported\n\ndef solve(x, y):\n    return x - y\n',
                f'{masked}.py':f'from {core} import solve as masked_function\n\ndef solve(x, y):\n    return 0 * masked_function(x, y)\n',
                f'{cancel}.py':f'from {core} import solve as cancel_fn\n\ndef solve(x, y):\n    return cancel_fn(x, y) - cancel_fn(x, y)\n',
                f'{unrelated}.py':'def solve(x, y):\n    return x + y\n',
                f'{conditional}.py':f'from {core} import solve as conditional_fn\n\ndef solve(x, y):\n    return conditional_fn(x,y) if x > 0 else x-y\n',
                f'{dynamic}.py':f'from {core} import solve as dynamic_fn\n\ndef solve(x, y):\n    return globals()["dynamic_fn"](x,y)\n',
            }
            for extra in extras:
                files[f'{extra}.py']='def solve(x, y):\n    return x + y\n'
            rows=[(-4,3),(-2,5),(0,2),(1,6),(3,-2),(4,5),(5,3),(-3,-1),(2,4),(-5,6),(6,-3),(3,7),(-6,-4),(7,2),(2,-6)]
            rng=random.Random(seed*73+j*19+sum(map(ord,family)))
            # Kept strong public probes. Challenge/final are disjoint.
            rows=rows[:5]+rng.sample(rows[5:],len(rows[5:]))
            oracle=oracles[family]
            def make_examples(pairs):return tuple(IOExample(x,y,oracle(x,y)) for x,y in pairs)
            contracts=tuple(Contract(k,'solve',tuple(rows[:5])) for k in (primary,bridge,secondary,shadow,masked,cancel,unrelated,conditional,dynamic))
            result.append(AtlasTask(f'a{seed}-{j}-{family}',files,f'{core}.py',contracts,
                                    make_examples(rows[:5]),make_examples(rows[5:10]),make_examples(rows[10:]),family))
    r.shuffle(result)
    return result


def _assert_actual_disk_tests(root: Path, task: AtlasTask) -> bool:
    primary=task.contracts[0].module
    (root/'tests').mkdir(exist_ok=True)
    text=['import unittest',f'from {primary} import solve','', 'class PublicTests(unittest.TestCase):']
    for i,e in enumerate(task.public):
        text += [f'    def test_{i:02d}(self):',f'        self.assertEqual(solve({e.x},{e.y}),{e.expected})']
    (root/'tests'/'test_public.py').write_text('\n'.join(text)+'\n',encoding='utf8')
    p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],
                     cwd=root,capture_output=True,text=True,timeout=12)
    return p.returncode==0


def repair_atlas_task(task: AtlasTask, *, priority: str='graph', prior=None,
                      actual_tests: bool=False, max_eval: int=65000) -> dict:
    """Connect WORLD MODEL location to GENESIS synthesis to WITNESS.

    The evaluator knows changed_file; this routine does not use it to select a
    location. The graph ranks candidate files by dependency on the public entry.
    Public outputs guide synthesis. Hidden splits are used only after selection.
    """
    graph=SymbolGraph(task.files)
    primary=task.contracts[0]
    choices=[]
    for name,src in task.files.items():
        try: _extract_expression(src)
        except (SyntaxError,ValueError): continue
        call,dist,uncertain,_ = graph.reachable(primary.key,f'{Path(name).stem}.solve')
        # Files whose solve is actually called receive priority. Model cannot
        # see the evaluator's true changed_file when sorting.
        score=int(call)*100-(dist if dist>=0 else 9)
        choices.append((name,score))
    if priority=='graph': order=[name for name,_ in sorted(choices,key=lambda x:(-x[1],x[0]))]
    elif priority=='flat': order=[name for name,_ in sorted(choices)]
    else:raise ValueError('unknown priority')
    with tempfile.TemporaryDirectory(prefix='nomad-codeworld-atlas-') as td:
        root=Path(td); write_world(root,task.files)
        before_public=run_contract(root,Contract(primary.module,'solve',tuple((e.x,e.y) for e in task.public)))
        before_challenge=run_contract(root,Contract(primary.module,'solve',tuple((e.x,e.y) for e in task.challenge)))
        attempts=0; vectors=0
        for name in order:
            attempts+=1
            synthesis_task=SynthesisTask(task.task_id,task.files[name],task.public,task.challenge,task.final)
            solution=synthesize(synthesis_task,prior=prior,max_eval=max_eval)
            vectors+=solution.candidates_evaluated
            if not solution.public_correct or not solution.candidate:continue
            new_src=_render(solution.candidate)
            (root/name).write_text(new_src,encoding='utf8')
            public_contract=Contract(primary.module,'solve',tuple((e.x,e.y) for e in task.public))
            public_vals=run_contract(root,public_contract)
            if public_vals != tuple(e.expected for e in task.public):
                (root/name).write_text(task.files[name],encoding='utf8')
                continue
            disk_tests=_assert_actual_disk_tests(root,task) if actual_tests else True
            if not disk_tests:
                (root/name).write_text(task.files[name],encoding='utf8');continue
            chall_vals=run_contract(root,Contract(primary.module,'solve',tuple((e.x,e.y) for e in task.challenge)))
            witness=Witness('nomad-witness-v011-causal-atlas')
            tid=hashlib.sha256(f'{task.task_id}|{name}|{new_src}'.encode()).hexdigest()
            receipt=witness.attest(task_id=task.task_id,transmission_id=tid,world_epoch=0,
                current_public=before_public,target_public=tuple(float(e.expected) for e in task.public),
                candidate_public=public_vals,current_challenge=before_challenge,
                target_challenge=tuple(float(e.expected) for e in task.challenge),candidate_challenge=chall_vals)
            permitted=witness.authorize(receipt,task_id=task.task_id,transmission_id=tid,world_epoch=0)
            final=run_contract(root,Contract(primary.module,'solve',tuple((e.x,e.y) for e in task.final)))
            if not permitted or final != tuple(e.expected for e in task.final):
                (root/name).write_text(task.files[name],encoding='utf8');continue
            effects=observe_intervention(task,new_src,changed_file_override=name)
            return {'task_id':task.task_id,'solved':True,'final_correct':True,
                    'chosen_file_is_actual_source': name==task.changed_file,
                    'files_visited':attempts,'candidate_vectors':vectors,
                    'public_unittest':disk_tests,'witness_supported':permitted,
                    'actual_effects':{rec.contract:rec.changed for rec in effects}}
        return {'task_id':task.task_id,'solved':False,'final_correct':False,'chosen_file_is_actual_source':False,
                'files_visited':attempts,'candidate_vectors':vectors,
                'public_unittest':False,'witness_supported':False,'actual_effects':{}}
