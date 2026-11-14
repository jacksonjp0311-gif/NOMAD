"""Audit an isolated NOMAD revision; never install or execute it on the host."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nomad.isolation import SandboxPolicy, docker_preflight, sandbox_available
from nomad.platform_mission import resolved_goal
from nomad.recursion import review_isolated_revision
from scripts.qualify_isolation_v18 import canonical_digest, qualification_host_identity
from scripts.qualify_recovery_v18 import _validate_isolation_receipt


def read_receipt(path: Path) -> dict:
    if path.stat().st_size > 2_000_000:
        raise ValueError('receipt exceeds bounded input size')
    record = json.loads(path.read_bytes())
    if not isinstance(record, dict): raise ValueError('receipt must be an object')
    return record


def review(args) -> dict:
    report = {'schema': 'nomad.self-revision-qualification.v18', 'version': '0.18.0',
              'status': 'HOLD', 'execution': 'NOT_RUN', 'candidate_reviewed': False,
              'authoritative_source_replaced': False, 'production_promotion': 'HOLD',
              'self_improvement_advantage': 'NOT_ESTABLISHED',
              'reviewer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'docker_available': sandbox_available(), 'host_identity': qualification_host_identity(),
              'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted((ROOT/'nomad').glob('*.py'))}}
    try:
        if not report['docker_available']:
            raise ValueError('Docker unavailable; no host self-modification substitute')
        if not all((args.mission_root, args.authoritative_source, args.baseline_regression,
                    args.candidate_regression, args.native_qualification, args.allowed)):
            raise ValueError('completed candidate mission, independent baseline/candidate regression receipts and native qualification required')
        goal = resolved_goal(args.mission_root)
        policy = SandboxPolicy(**goal['policy']); policy.validate()
        report['qualification_sha256'] = _validate_isolation_receipt(
            args.native_qualification, policy, report['host_identity'])
        report['policy'] = asdict(policy)
        preflight = docker_preflight(policy)
        report['preflight'] = preflight
        if not preflight['ready']:
            raise ValueError('current Docker/image preflight unavailable')
        audit = review_isolated_revision(args.mission_root, args.authoritative_source,
            allowed_paths=args.allowed, baseline_regression=read_receipt(args.baseline_regression),
            candidate_regression=read_receipt(args.candidate_regression))
        report.update(status=audit['status'], execution='REVIEWED_EXISTING_NATIVE_EVIDENCE',
                      candidate_reviewed=True, audit=audit)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        report['reason'] = str(error)
    report['receipt_sha256'] = canonical_digest(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('mission-root', 'authoritative-source', 'baseline-regression',
                 'candidate-regression', 'native-qualification'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--allowed', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists(): parser.error('refusing to overwrite a self-revision receipt')
    result = review(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as out:
        json.dump(result, out, sort_keys=True, indent=2); out.write('\n')
    print(json.dumps({key: result.get(key) for key in
                     ('status','execution','candidate_reviewed','reason')}))
    return 0 if result['candidate_reviewed'] else 3


if __name__ == '__main__': raise SystemExit(main())
