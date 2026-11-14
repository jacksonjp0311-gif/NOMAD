"""NOMAD v0.15 RECURSION: candidate-only self-revision and witnessed scope.

This is a *bounded research harness*. It synthesizes a pure ranking function
from whitelisted AST structures, evaluates it on disjoint tasks, and produces
an immutable proposal receipt. It NEVER writes the running engine, WITNESS,
the benchmark oracle, or protected source. Production self-modification is not
permitted by this module.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
from typing import Callable, Iterable

from .frontier import Prior, verify_witness


def stable_hash(data: object) -> str:
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class EvidenceScopedPrior(Prior):
    """An existing v0.14 prior is ineligible until independent witnessed support.

    Support counts distinct source tasks, never attempts or repeated contracts.
    Conflicting independent evidence contests that specific key. This is an
    *eligibility* rule, not an authenticated witness or a proof of causality.
    """
    def __init__(self, min_support: int = 3):
        super().__init__()
        if not isinstance(min_support,int) or min_support<2:
            raise ValueError('minimum support must be >=2')
        self.min_support = min_support
        self.positive: dict[str,set[str]] = {}
        self.source_witnesses: dict[str,set[str]] = {}
        self.receipt_witnesses: dict[str,set[str]] = {}
        self.contested: set[str] = set()
        self.events: list[dict] = []

    def admit(self, *, bits:int, family:str, task_id:str, expected_source_sha256:str,
              project:str, receipt:dict, independently_observed:bool) -> bool:
        if not independently_observed:
            return False
        if not task_id or not family or type(bits)!=int or bits<0:
            return False
        if not verify_witness(receipt) or receipt.get('source_sha256')!=expected_source_sha256:
            return False
        if receipt.get('project')!=project or not isinstance(expected_source_sha256,str):
            return False
        if len(expected_source_sha256)!=64 or any(c not in '0123456789abcdef' for c in expected_source_sha256):
            return False
        key=self.key(bits,family)
        accepted=receipt.get('supported') is True
        rejected=receipt.get('supported') is False
        if not accepted and not rejected:
            return False
        if accepted and receipt.get('upstream_suite_passed') is not True:
            return False
        if accepted and receipt.get('additional_contract',{}).get('supported') is False:
            return False
        if rejected and receipt.get('upstream_suite_passed') is True:
            # Critical: a seemingly passing patch contradicted by other evidence.
            self.contested.add(key)
        if accepted and key not in self.contested:
            # All three must be independent: task ID, patched source bytes and
            # WITNESS receipt. Replaying one receipt under new task IDs must
            # NEVER manufacture the evidence threshold.
            if (task_id in self.positive.get(key,set()) or
                expected_source_sha256 in self.source_witnesses.get(key,set()) or
                receipt['receipt_sha256'] in self.receipt_witnesses.get(key,set())):
                return False
            self.positive.setdefault(key,set()).add(task_id)
            self.source_witnesses.setdefault(key,set()).add(expected_source_sha256)
            self.receipt_witnesses.setdefault(key,set()).add(receipt['receipt_sha256'])
        self.events.append({'key':key,'task_id':task_id,'accepted':accepted,
                            'witness_sha256':receipt['receipt_sha256']})
        return accepted

    def score(self,bits:int,c) -> int:
        key=self.key(bits,c.family)
        if key in self.contested:
            return 0
        support=min(len(self.positive.get(key,set())),
                    len(self.source_witnesses.get(key,set())),
                    len(self.receipt_witnesses.get(key,set())))
        return support if support>=self.min_support else 0

    def snapshot(self)->dict:
        data={'schema':'nomad.recursion.evidence-prior.v1',
              'min_support':self.min_support,
              'positive':{k:sorted(v) for k,v in sorted(self.positive.items())},
              'sources':{k:sorted(v) for k,v in sorted(self.source_witnesses.items())},
              'receipts':{k:sorted(v) for k,v in sorted(self.receipt_witnesses.items())},
              'contested':sorted(self.contested), 'events':self.events}
        return {**data,'sha256':stable_hash(data)}

    @classmethod
    def load(cls,record:dict)->'EvidenceScopedPrior':
        core={k:v for k,v in record.items() if k!='sha256'}
        if core.get('schema')!='nomad.recursion.evidence-prior.v1' or stable_hash(core)!=record.get('sha256'):
            raise ValueError('invalid or modified memory')
        obj=cls(core['min_support'])
        obj.positive={k:set(v) for k,v in core['positive'].items()}
        obj.source_witnesses={k:set(v) for k,v in core['sources'].items()}
        obj.receipt_witnesses={k:set(v) for k,v in core['receipts'].items()}
        obj.contested=set(core['contested'])
        obj.events=list(core['events'])
        return obj


@dataclass(frozen=True)
class RankingExample:
    """A synthetic, evaluator-labelled microtask; not real repo success."""
    semantic:int
    prior:int
    line:int
    is_correct:bool


@dataclass(frozen=True)
class SyntheticTask:
    id:str
    candidates:tuple[RankingExample,...]


_ALLOWED_ORDERS = {
    'cold': ('semantic','line','prior'),
    'prior_first': ('prior','semantic','line'),
    'semantic_then_prior': ('semantic','prior','line'),
    'line_first': ('line','semantic','prior'),
}


def synthesize_ranking_source(name: str) -> str:
    """Emit real Python source from an explicitly bounded AST vocabulary."""
    if name not in _ALLOWED_ORDERS:
        raise ValueError('unapproved synthesis production')
    parts=[]
    for field in _ALLOWED_ORDERS[name]:
        atom=ast.Name(id=field,ctx=ast.Load())
        parts.append(atom if field=='line' else ast.UnaryOp(op=ast.USub(), operand=atom))
    node=ast.Module(body=[ast.FunctionDef(name='ranking_key',
        args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=x) for x in ('semantic','prior','line')],
                           kwonlyargs=[],kw_defaults=[],defaults=[]),
        body=[ast.Return(value=ast.Tuple(elts=parts,ctx=ast.Load()))],decorator_list=[])],
        type_ignores=[])
    ast.fix_missing_locations(node)
    return ast.unparse(node)+'\n'


def compile_ranking_source(source:str) -> Callable:
    """Validate exact generated AST shape before executing this tiny pure function."""
    tree=ast.parse(source)
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):
        raise ValueError('unapproved module structure')
    fn=tree.body[0]
    if fn.name!='ranking_key' or len(fn.body)!=1 or not isinstance(fn.body[0],ast.Return):
        raise ValueError('unapproved function structure')
    if [a.arg for a in fn.args.args]!=['semantic','prior','line'] or fn.decorator_list:
        raise ValueError('unapproved arguments or decorators')
    ret=fn.body[0].value
    if not isinstance(ret,ast.Tuple) or len(ret.elts)!=3:
        raise ValueError('unapproved return shape')
    names=[]
    for expr in ret.elts:
        if isinstance(expr,ast.Name): names.append((expr.id,False))
        elif isinstance(expr,ast.UnaryOp) and isinstance(expr.op,ast.USub) and isinstance(expr.operand,ast.Name):
            names.append((expr.operand.id,True))
        else: raise ValueError('unapproved instruction')
    if set(x for x,_ in names)!={'semantic','prior','line'}:
        raise ValueError('invalid score inputs')
    if any(is_negative!=(name!='line') for name,is_negative in names):
        raise ValueError('unapproved numeric ordering')
    canonical_sources={synthesize_ranking_source(k) for k in _ALLOWED_ORDERS}
    if source not in canonical_sources:
        raise ValueError('source is not an enumerated pure revision')
    scope={'__builtins__':{}}
    exec(compile(tree,'<nomad-bounded-revision>','exec'),scope)
    return scope['ranking_key']


def evaluate_ranking(tasks:Iterable[SyntheticTask], f:Callable)->dict:
    total=0;solved=0;attempts=0
    for task in tasks:
        ranked=sorted(task.candidates,key=lambda e:f(e.semantic,e.prior,e.line))
        try:position=next(i for i,x in enumerate(ranked,1) if x.is_correct)
        except StopIteration:continue
        attempts+=position;solved+=1;total+=1
    return {'tasks':total,'solved':solved,'total_attempts':attempts,
            'mean_attempts':round(attempts/total,4) if total else None}


def assess_candidate(*, base_source:str, candidate_source:str,
                     dev:Iterable[SyntheticTask], heldout:Iterable[SyntheticTask],
                     external_transfer_confirmed:bool=False)->dict:
    incumbent=compile_ranking_source(base_source)
    proposed=compile_ranking_source(candidate_source)
    dev=list(dev);heldout=list(heldout)
    base_dev=evaluate_ranking(dev,incumbent);cand_dev=evaluate_ranking(dev,proposed)
    base_hold=evaluate_ranking(heldout,incumbent);cand_hold=evaluate_ranking(heldout,proposed)
    improves=(cand_dev['solved']==base_dev['solved'] and
              cand_hold['solved']==base_hold['solved'] and
              cand_dev['total_attempts']<base_dev['total_attempts'] and
              cand_hold['total_attempts']<base_hold['total_attempts'])
    return {'schema':'nomad.recursion.candidate.v1',
            'incumbent_sha256':hashlib.sha256(base_source.encode()).hexdigest(),
            'candidate_sha256':hashlib.sha256(candidate_source.encode()).hexdigest(),
            'dev':{'incumbent':base_dev,'candidate':cand_dev},
            'heldout':{'incumbent':base_hold,'candidate':cand_hold},
            'improved_in_bounded_lab':improves,
            'external_transfer_confirmed':external_transfer_confirmed,
            'production_promotion':'HOLD' if not (improves and external_transfer_confirmed) else 'ELIGIBLE_FOR_EXTERNAL_REVIEW',
            'self_modification_executed':False,
            'authority':'candidate proposal only; no automatic source replacement'}


# The self-revision gate reuses the platform mission's isolated candidate and
# receipts. It has deliberately no operation that writes authoritative source.
SELF_REGRESSION_COMMAND = ['python', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-q']
_PROTECTED_SELF_FILES = {
    'nomad/__init__.py', 'nomad/frontier.py', 'nomad/platform_cli.py',
    'nomad/platform.py', 'nomad/protect_cli.py', 'nomad/mnemonic.py',
    'nomad/recursion.py', 'nomad/witness.py', 'nomad/mission_witness.py',
    'nomad/mission_runtime.py', 'nomad/platform_mission.py', 'nomad/effects.py',
    'nomad/isolation.py', 'nomad/supervised.py', 'nomad/windows_job.py',
    'nomad/archive_guard.py', 'nomad/safe_eval.py', 'nomad/ledger.py',
}


def _revision_identity(root: Path, manifest: dict) -> dict:
    from .mission_runtime import canonical, digest
    entries = [[name, checksum, (root/name).stat().st_size]
               for name, checksum in sorted(manifest.items())]
    return {'snapshot_sha256': digest(canonical(entries)), 'source_files': len(entries),
            'source_bytes': sum(row[2] for row in entries)}


def _check_regression_receipt(receipt: dict, identity: dict, image: str) -> None:
    """Validate observed execution bindings, never a learner's PASS assertion."""
    import re
    if (not isinstance(receipt, dict) or receipt.get('schema') != 'nomad.isolated-test.v1'
            or any(receipt.get(key) != value for key, value in identity.items())
            or receipt.get('command') != SELF_REGRESSION_COMMAND
            or receipt.get('image_digest') != image.split('@sha256:')[-1]
            or receipt.get('returncode') != 0 or type(receipt.get('returncode')) is not int
            or receipt.get('timed_out') is not False or receipt.get('tests_passed') is not True
            or receipt.get('container_cleanup_confirmed') is not True
            or receipt.get('output_truncated') is not False
            or not isinstance(receipt.get('output_sha256'), str)
            or len(receipt['output_sha256']) != 64
            or any(c not in '0123456789abcdef' for c in receipt['output_sha256'])
            or not isinstance(receipt.get('container_name'), str)
            or re.fullmatch(r'nomad-[a-f0-9]{24}', receipt['container_name']) is None
            or receipt.get('preflight', {}).get('ready') is not True):
        raise ValueError('independent isolated regression receipt is missing, stale or not passing')


def review_isolated_revision(mission_root: Path, authoritative_source: Path, *,
                             allowed_paths: Iterable[str], baseline_regression: dict,
                             candidate_regression: dict) -> dict:
    """Assess a completed isolated revision without installing it.

    authoritative_source is the exact source-only baseline supplied to the
    mission. Full Git metadata/credentials are never copied into a worker.
    Caller-owned native receipts need a trusted external storage anchor; their
    checksums are not signatures. Public examples alone cannot pass this gate.
    """
    from . import platform_mission
    from .mission_runtime import canonical, digest, exclusive_owner
    from .isolation import SandboxPolicy
    mission_root = Path(mission_root).resolve(strict=True)
    authoritative_source = Path(authoritative_source).resolve(strict=True)
    if (mission_root == authoritative_source or mission_root in authoritative_source.parents
            or authoritative_source in mission_root.parents):
        raise ValueError('self-revision evidence and authoritative source must be disjoint')
    allowed = set(allowed_paths)
    if not allowed or len(allowed) > 2 or any(
            not isinstance(name, str) or '\\' in name or ':' in name
            or not name.startswith('nomad/') or not name.endswith('.py')
            or '..' in Path(name).parts or name.casefold() in _PROTECTED_SELF_FILES
            for name in allowed):
        raise ValueError('self-revision scope must name at most two non-verifier NOMAD modules')
    with exclusive_owner(mission_root):
        goal = platform_mission.resolved_goal(mission_root)
        summary = platform_mission.inspect(mission_root)
        if (summary.get('status') != 'completed' or summary.get('witness_observations', 0) < 1
                or summary.get('final_observations', 0) < 1):
            raise ValueError('independently completed mission required before self-revision review')
        policy = SandboxPolicy(**goal['policy']); policy.validate()
        original = platform_mission._manifest(authoritative_source)
        baseline = platform_mission._manifest(mission_root/'baseline')
        candidate = platform_mission._manifest(mission_root/'workspace')
        if original != baseline or baseline != goal['baseline']:
            raise ValueError('authoritative source differs from the pinned original; refuse replacement')
        if set(candidate) != set(baseline):
            raise ValueError('self-revision cannot add/remove source, tests or evidence files')
        changed = sorted(name for name in baseline if baseline[name] != candidate[name])
        if not changed or not set(changed) <= allowed:
            raise ValueError('candidate changed protected or undeclared source')
        base_id = _revision_identity(mission_root/'baseline', baseline)
        candidate_id = _revision_identity(mission_root/'workspace', candidate)
        _check_regression_receipt(baseline_regression, base_id, policy.image)
        _check_regression_receipt(candidate_regression, candidate_id, policy.image)
        if baseline_regression['container_name'] == candidate_regression['container_name']:
            raise ValueError('baseline and candidate require separate observed executions')
        report = {'schema': 'nomad.recursion.isolated-revision.v18',
                  'mission_id': goal['mission_id'], 'journal_head': summary['journal_head'],
                  'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'mission_runtime_sha256': goal.get('runtime_sha256', {}),
                  'baseline': base_id, 'candidate': candidate_id, 'changed_paths': changed,
                  'baseline_regression_sha256': digest(canonical(baseline_regression)),
                  'candidate_regression_sha256': digest(canonical(candidate_regression)),
                  'source_unchanged': platform_mission._manifest(authoritative_source) == original,
                  'rollback': 'original baseline preserved; candidate is disposable; no authoritative write',
                  'status': 'ELIGIBLE_FOR_INDEPENDENT_REVIEW', 'authoritative_source_replaced': False,
                  'production_promotion': 'HOLD', 'self_improvement_advantage': 'NOT_ESTABLISHED',
                  'authority': 'proposal audit only; no automatic integration or verifier modification'}
        if report['source_unchanged'] is not True:
            raise ValueError('source changed during independent self-revision review')
        return {**report, 'receipt_sha256': digest(canonical(report))}
