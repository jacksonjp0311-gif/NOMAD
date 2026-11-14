"""Native Docker recovery qualification for the bounded arithmetic adapter.

Requires a matching current native-isolation PASS receipt before creating any
mission. This script never substitutes mocked receipts or host repository tests.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad.effects import EffectLedger
from nomad.isolation import SandboxPolicy, _docker_prefix, docker_preflight, sandbox_available
from nomad.mission_runtime import InjectedInterruption, Journal, MissionHold
from nomad.platform_mission import (CHECKPOINTS, MEMORY_ID, initialize, inspect,
                                    recover, resolved_goal, run)
from nomad.supervised import minimal_env, run_supervised
from scripts.qualify_isolation_v18 import CONTROLLED_CASES, canonical_digest, qualification_host_identity

SCHEMA = 'nomad.platform-recovery-qualification.v18'
POLICY = {'timeout_s': 10.0, 'memory_mib': 128, 'cpus': 0.5, 'pids_limit': 16,
          'max_files': 3000, 'max_total_bytes': 30_000_000}


def required_cases() -> list[str]:
    return ['reference_and_terminal_replay', *CHECKPOINTS, 'owner_hard_death_with_live_container',
            *('tampered-' + name for name in ('sealed.json', 'planning_memory.json',
                                             'events.jsonl', 'baseline/arithmetic.py'))]


def source_identity() -> dict[str, str]:
    paths = sorted((ROOT / 'nomad').glob('*.py')) + [Path(__file__).resolve(),
        ROOT / 'scripts' / 'qualify_isolation_v18.py']
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def _seal(report: dict) -> dict:
    report['source_sha256_after'] = source_identity()
    report['source_stable'] = report['source_sha256_before'] == report['source_sha256_after']
    if not report['source_stable']:
        if report['status'] != 'FAIL':
            report['status'] = report['isolated_mission_recovery'] = 'HOLD'
        report['reason'] = (report.get('reason') or '') + '; source changed during qualification'
    report['receipt_sha256'] = canonical_digest(report)
    return report


def _validate_isolation_receipt(path: Path, policy: SandboxPolicy, host: dict) -> str:
    if path.stat().st_size > 2_000_000:
        raise ValueError('native-isolation receipt exceeds budget')
    raw = path.read_bytes()
    record = json.loads(raw)
    if not isinstance(record, dict):
        raise ValueError('native-isolation receipt must be an object')
    body = {key: value for key, value in record.items() if key != 'receipt_sha256'}
    if (record.get('schema') != 'nomad.native-isolation-qualification.v18'
            or record.get('backend') != 'docker'
            or record.get('status') != 'PASS' or record.get('native_containment_gate') != 'PASS'
            or record.get('receipt_sha256') != canonical_digest(body)
            or record.get('image') != policy.image or record.get('policy') != asdict(policy)
            or record.get('policy_sha256') != canonical_digest(asdict(policy))
            or record.get('host_identity_sha256') != canonical_digest(host)
            or record.get('source_stable') is not True
            or record.get('source_sha256_before') != record.get('source_sha256_after')):
        raise ValueError('native-isolation PASS receipt does not match current image, policy or host')
    cases = record.get('cases', [])
    expected = set(CONTROLLED_CASES) | {'supervisor_hard_death_cleanup'}
    if (not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases)
            or len(cases) != len(expected) or {case.get('case') for case in cases} != expected
            or any(case.get('status') != 'PASS' for case in cases)
            or record.get('protected_host_sentinel_unchanged') is not True):
        raise ValueError('native-isolation receipt lacks complete actual passing cases')
    death = next(case for case in cases if case['case'] == 'supervisor_hard_death_cleanup')
    if (death.get('observed_live_container_before_owner_death') is not True
            or death.get('cleanup_confirmed_after_owner_death') is not True):
        raise ValueError('native-isolation owner-death evidence contradicts its passing label')
    sources = record['source_sha256_after']
    required = {'nomad/isolation.py', 'nomad/supervised.py', 'nomad/windows_job.py',
                'scripts/qualify_isolation_v18.py'}
    if not isinstance(sources, dict) or not required <= set(sources):
        raise ValueError('native-isolation receipt source binding incomplete')
    for name, sha in sources.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or ':' in name or '\\' in name:
            raise ValueError('unsafe qualification source path')
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != sha:
            raise ValueError('native-isolation receipt is stale for current source')
    return hashlib.sha256(raw).hexdigest()


def _fixture(base: Path, policy: SandboxPolicy, *, negative_final=False):
    source = base / 'source'
    source.mkdir(parents=True)
    (source / 'arithmetic.py').write_bytes(b'def solve(x, y):\n    return x+y\n')
    (source / 'public_api.py').write_bytes(b'from arithmetic import solve\n')
    (source / 'tests').mkdir()
    # A short controlled delay makes actual running-container observation
    # possible. It stays inside the qualified per-experiment wall budget.
    (source / 'tests' / 'test_public.py').write_bytes(
        b'import time,unittest\nfrom public_api import solve\ntime.sleep(3)\n'
        b'class PublicTests(unittest.TestCase):\n'
        b'    def test_subtract(self): self.assertEqual(solve(4,2),2)\n')
    public = [{'x': 4, 'y': 2, 'expected': 2}, {'x': 7, 'y': 3, 'expected': 4}]
    challenge = [{'x': 8, 'y': 3, 'expected': 5}, {'x': 2, 'y': 5, 'expected': -3}]
    final = [{'x': -5, 'y': 3, 'expected': -8 if not negative_final else 999}]
    root = base / 'mission'
    initialize(root, source, goal_text='Controlled native recovery subtraction fixture',
               public=public, challenge=challenge, final=final, policy=policy)
    return root, source


def _rows(root: Path) -> list[dict]:
    goal = json.loads((root / 'goal.json').read_bytes())
    return Journal(root / 'events.jsonl', goal['mission_id']).read()


def _control(root: Path, reference: dict | None = None) -> dict:
    summary = inspect(root)
    rows = _rows(root)
    decisions = [row['kind'] for row in rows if row['kind'] not in
                 ('PROBE_DISPATCHED', 'PROBE_RECOVERED', 'EXECUTION_DISPATCHED', 'EXECUTION_RECOVERED')]
    memory = Journal(root / 'mnemonic' / 'events.jsonl', MEMORY_ID).read()
    admissions = sum(row['kind'] == 'OBSERVATION_ADMITTED' for row in memory)
    effects = EffectLedger(root / 'effects', create=False).snapshot()
    before = (root / 'events.jsonl').read_bytes()
    replay = run(root)
    replay_unchanged = before == (root / 'events.jsonl').read_bytes()
    from nomad.platform_mission import _manifest
    original_unchanged = _manifest(root.parent / 'source') == resolved_goal(root)['baseline']
    result = {'status': summary['status'], 'committed_sha256': summary['committed_sha256'],
              'baseline_probes_recorded': summary['baseline_probes_recorded'],
              'public_executions_recorded': summary['public_executions_recorded'],
              'witness_observations': summary['witness_observations'],
              'final_observations': summary['final_observations'], 'dispatches': summary['dispatches'],
              'learning_admissions': admissions, 'external_effects_replay_safe': effects['replay_safe'],
              'terminal_replay_unchanged': replay_unchanged and replay['status'] == 'completed',
              'original_source_unchanged': original_unchanged,
              'decision_sequence': decisions, 'journal_head': summary['journal_head']}
    result['matches_reference'] = reference is None or all(result[key] == reference[key] for key in
        ('committed_sha256', 'baseline_probes_recorded', 'public_executions_recorded',
         'witness_observations', 'final_observations', 'learning_admissions', 'decision_sequence'))
    result['passed'] = (summary['status'] == 'completed' and admissions == 1 and effects['replay_safe']
                        and result['terminal_replay_unchanged'] and result['matches_reference'] and original_unchanged
                        and summary['baseline_probes_recorded'] == summary['public_executions_recorded'] == 1)
    return result


def _hard_death_once(root: Path, base: Path) -> dict:
    scratch = root.parent / 'supervisor-scratch'
    scratch.mkdir(exist_ok=False)
    code = ('from pathlib import Path; import sys,tempfile; tempfile.tempdir=sys.argv[2]; '
            'from nomad.platform_mission import run; '
            'run(Path(sys.argv[1]))')
    owner = subprocess.Popen([sys.executable, '-B', '-c', code, str(root), str(scratch)], cwd=ROOT,
        env=minimal_env({'PYTHONPATH': str(ROOT)}), stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    observed = False
    container_name = None
    try:
        deadline = time.monotonic() + 20
        while owner.poll() is None and time.monotonic() < deadline:
            try:
                last = _rows(root)[-1]
            except MissionHold:
                time.sleep(0.05)
                continue
            if last['kind'] in ('PROBE_DISPATCHED', 'EXECUTION_DISPATCHED'):
                container_name = last['data']['container_name']
                observation = run_supervised([*_docker_prefix('docker', base), 'container', 'inspect',
                    '--format', '{{.State.Running}}', container_name], cwd=base,
                    env=minimal_env(), timeout_s=2, max_output_bytes=2048)
                if observation.returncode == 0 and observation.output.strip() == b'true':
                    observed = True
                    break
            time.sleep(0.05)
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.wait(timeout=5)
    if not observed:
        # A known recorded dispatch still needs disposal, even when the probe
        # did not witness a running container. Never count that case as PASS.
        recover(root)
        raise MissionHold('owner death probe did not observe a live isolated container')
    try:
        run(root)
    except MissionHold:
        held_before_cleanup = True
    else:
        raise MissionHold('unknown worker outcome was replayed without cleanup')
    recovery = recover(root)
    return {'observed_running_container': observed, 'container_name': container_name,
            'held_before_cleanup': held_before_cleanup, 'recovery_status': recovery['status'],
            'owner_exit_code': owner.returncode}


def _hard_death(root: Path, base: Path) -> dict:
    # The owner is stopped by the inner finally. An exception while inspecting
    # Docker must still reconcile its durable dispatch before this probe exits.
    try:
        return _hard_death_once(root, base)
    except BaseException as original_error:
        try:
            recover(root)
        except BaseException as cleanup_error:
            raise MissionHold('owner-death probe failed and recorded container cleanup is unconfirmed: '
                              + str(cleanup_error)) from original_error
        raise


def qualify(image: str | None = None, isolation_receipt: Path | None = None,
            evidence_root: Path | None = None) -> dict:
    host = qualification_host_identity()
    report = {'schema': SCHEMA, 'status': 'HOLD', 'isolated_mission_recovery': 'HOLD',
        'backend': 'docker', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'image': image, 'docker_binary_present': sandbox_available(),
        'host_identity': host, 'host_identity_sha256': canonical_digest(host),
        'source_sha256_before': source_identity(), 'cases': [], 'planned_cases': required_cases(), 'reason': None,
        'scope': 'controlled arithmetic fixture recovery only; not real external repair or general autonomy',
        'receipt_authority': 'operator-owned observation; checksum is not a signature',
        'unimplemented_scope': ['power-loss durability', 'service-restart durability',
                                'remote irreversible-effect exactly-once behavior'],
        'cloud_model_calls': 0, 'repository_host_execution': False}
    if image is None or isolation_receipt is None:
        report['reason'] = 'reviewed image and matching current native-isolation PASS receipt required; no mission initialized'
        return _seal(report)
    try:
        policy = SandboxPolicy(image=image, **POLICY)
        policy.validate()
        report['policy'] = asdict(policy)
        report['policy_sha256'] = canonical_digest(report['policy'])
        report['isolation_receipt_sha256'] = _validate_isolation_receipt(Path(isolation_receipt), policy, host)
        report['preflight'] = docker_preflight(policy)
        if not report['preflight']['ready']:
            raise MissionHold('Docker preflight unavailable; no mission initialized')
        if evidence_root is None:
            raise MissionHold('persistent evidence_root required before any native mission')
        evidence_root = Path(evidence_root).resolve()
        if evidence_root.exists():
            raise MissionHold('evidence directory exists; refusing to overwrite history')
    except (OSError, ValueError, TypeError, KeyError, MissionHold) as error:
        report['reason'] = str(error)
        return _seal(report)
    evidence_root.mkdir(parents=True, exist_ok=False)
    report['evidence_root'] = str(evidence_root)
    with nullcontext(evidence_root) as base:
        sentinel = base / 'protected-host-sentinel'
        sentinel.write_bytes(b'host-only controlled recovery sentinel')
        try:
            reference_root, source = _fixture(base / 'reference', policy)
            source_before = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in source.rglob('*') if p.is_file()}
            run(reference_root)
            reference = _control(reference_root)
            report['cases'].append({'case': 'reference_and_terminal_replay', 'status': 'PASS' if reference['passed'] else 'FAIL', 'result': reference})
            if not reference['passed']:
                raise MissionHold('reference mission failed qualification')
            for checkpoint in CHECKPOINTS:
                if checkpoint.startswith('after_rollback'):
                    continue
                root, _ = _fixture(base / checkpoint, policy)
                try:
                    run(root, interrupt_at=checkpoint)
                except InjectedInterruption:
                    pass
                else:
                    raise MissionHold('requested interruption boundary was not reached: ' + checkpoint)
                if checkpoint in ('after_dispatch', 'after_probe_dispatch'):
                    recover(root)
                run(root)
                control = _control(root, reference)
                report['cases'].append({'case': checkpoint, 'status': 'PASS' if control['passed'] else 'FAIL', 'result': control})
            root, _ = _fixture(base / 'owner-hard-death', policy)
            death = _hard_death(root, base)
            run(root)
            control = _control(root, reference)
            report['cases'].append({'case': 'owner_hard_death_with_live_container',
                'status': 'PASS' if control['passed'] else 'FAIL', 'death': death, 'result': control})
            for checkpoint in ('after_rollback_write', 'after_rollback_record'):
                root, _ = _fixture(base / checkpoint, policy, negative_final=True)
                try:
                    run(root, interrupt_at=checkpoint)
                except InjectedInterruption:
                    pass
                else:
                    raise MissionHold('requested rollback interruption boundary was not reached: ' + checkpoint)
                result = run(root)
                goal = resolved_goal(root)
                restored = hashlib.sha256((root / 'workspace' / goal['target']).read_bytes()).hexdigest() == goal['baseline'][goal['target']]
                passed = result['status'] == 'rejected' and restored and not (root / 'mnemonic').exists()
                report['cases'].append({'case': checkpoint, 'status': 'PASS' if passed else 'FAIL',
                                      'restored_original': restored, 'result': result})
            for number, name in enumerate(('sealed.json', 'planning_memory.json', 'events.jsonl', 'baseline/arithmetic.py')):
                root, _ = _fixture(base / ('tamper-' + str(number)), policy)
                path = root / name
                path.chmod(0o600)
                path.write_bytes(path.read_bytes() + b'corruption')
                try:
                    run(root)
                except MissionHold:
                    refused = True
                else:
                    refused = False
                dispatched = b'DISPATCHED' in (root / 'events.jsonl').read_bytes()
                report['cases'].append({'case': 'tampered-' + name,
                    'status': 'PASS' if refused and not dispatched else 'FAIL', 'dispatched': dispatched})
            source_after = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in source.rglob('*') if p.is_file()}
            report['original_source_unchanged'] = source_before == source_after
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
            report['cases'].append({'case': 'qualification_execution', 'status': 'HOLD', 'reason': str(error)})
        try:
            report['protected_host_sentinel_unchanged'] = sentinel.read_bytes() == b'host-only controlled recovery sentinel'
        except OSError:
            report['protected_host_sentinel_unchanged'] = False
        report['evidence_files_sha256'] = {
            path.relative_to(base).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(base.rglob('*')) if path.is_file()}
    expected_cases = len(required_cases())
    statuses = [case['status'] for case in report['cases']]
    protected = report['protected_host_sentinel_unchanged'] and report.get('original_source_unchanged', False)
    report['status'] = ('FAIL' if 'FAIL' in statuses or not report['protected_host_sentinel_unchanged'] else
        'PASS' if len(statuses) == expected_cases and all(s == 'PASS' for s in statuses) and protected else 'HOLD')
    report['isolated_mission_recovery'] = report['status']
    return _seal(report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image')
    parser.add_argument('--isolation-receipt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path,
                        help='new persistent directory for native journals and snapshots')
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('output exists; preserve evidence and select a new path')
    evidence_root = args.evidence_root or args.output.with_name(args.output.stem + '.evidence')
    report = qualify(args.image, args.isolation_receipt, evidence_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, sort_keys=True, indent=2)
        handle.write('\n')
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report['isolated_mission_recovery'] == 'PASS' else 3


if __name__ == '__main__':
    raise SystemExit(main())
