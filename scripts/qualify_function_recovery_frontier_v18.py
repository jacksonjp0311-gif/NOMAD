"""Real Docker recovery qualification for the bounded JSON function adapter.

No fixture runs until a current native-isolation PASS binds this exact host,
image and policy. Execution is never replaced with a host runner or a double.
Results preserve finite fixture evidence; they are not a general autonomy gate.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nomad import platform_mission as mission
from nomad.effects import EffectLedger
from nomad.frontier import FUNCTION_ADAPTER
from nomad.isolation import SandboxPolicy, _docker_prefix, docker_preflight, sandbox_available
from nomad.mission_runtime import InjectedInterruption, Journal, MissionHold, canonical, digest
from nomad.supervised import minimal_env, run_supervised
from scripts.qualify_isolation_v18 import canonical_digest, qualification_host_identity
from scripts.qualify_recovery_v18 import POLICY, _validate_isolation_receipt

SCHEMA = 'nomad.function-recovery-qualification.frontier.v18'
CHECKPOINTS = ('after_plan', 'after_patch_write', 'after_patch_record', 'after_dispatch',
               'after_public', 'after_proposal', 'after_witness', 'after_final',
               'after_commit', 'before_memory', 'after_memory', 'after_learning')
TAMPER_PATHS = ('sealed.json', 'planning_memory.json', 'planning_ranker.json',
                'events.jsonl', 'baseline/lower.py')
CONTROL_CASES = ('reference_and_terminal_replay', *CHECKPOINTS,
                 'owner_hard_death_with_live_container', 'two_file_partial_patch_recovery')
EXPECTED_CONTROL_CASES = CONTROL_CASES


def required_cases() -> list[str]:
    return [*CONTROL_CASES, 'final_rejection_restores_source',
            *('tampered-'+name for name in TAMPER_PATHS)]


def source_identity() -> dict[str, str]:
    paths = sorted((ROOT/'nomad').glob('*.py')) + [Path(__file__).resolve(),
        ROOT/'scripts'/'qualify_isolation_v18.py', ROOT/'scripts'/'qualify_recovery_v18.py']
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def _seal(report: dict) -> dict:
    report['source_sha256_after'] = source_identity()
    report['source_stable'] = report['source_sha256_before'] == report['source_sha256_after']
    if not report['source_stable']:
        if report['status'] != 'FAIL': report['status'] = 'HOLD'
        report['reason'] = (report.get('reason') or '')+'; source changed during qualification'
    report['isolated_mission_recovery'] = report['status']
    report['receipt_sha256'] = canonical_digest(report)
    return report


def _fixture(base: Path, policy: SandboxPolicy, *, two=False, negative_final=False):
    source = base/'source'; source.mkdir(parents=True)
    (source/'lower.py').write_bytes(b'def bounded(value, limit):\n'
        b'    if value < limit:\n        return limit\n    return value\n')
    modules = ['lower']
    if two:
        (source/'upper.py').write_bytes(b'def bounded(value, limit):\n'
            b'    if value > limit:\n        return limit\n    return value\n')
        modules.append('upper')
    tests = source/'tests'; tests.mkdir()
    # Controlled trusted suite delay gives the live-container owner-death probe
    # an observation window while staying below the qualified ten-second limit.
    (tests/'test_public.py').write_bytes(b'import time, unittest\nfrom lower import bounded\n'
        b'time.sleep(3)\nclass PublicTests(unittest.TestCase):\n'
        b'    def test_lower(self): self.assertEqual(bounded(2,5),2)\n')
    public=[]; challenge=[]; final=[]
    def case(module, args, expected):
        return {'module':module, 'function':'bounded', 'args':args, 'expected':expected}
    for module in modules:
        wanted = min if module=='lower' else max
        public += [case(module, [2,5], wanted(2,5)), case(module, [9,5], wanted(9,5))]
        challenge.append(case(module, [-3,1], wanted(-3,1)))
        final.append(case(module, [18,7], 999999 if negative_final else wanted(18,7)))
    root=base/'mission'
    mission.initialize_functions(root, source, goal_text='Controlled native bounded-function recovery fixture',
        public=public, challenge=challenge, final=final, policy=policy, max_candidates=128,
        max_executions=150, public_command=list(mission.COMMAND))
    return root


def _rows(root):
    goal=json.loads((root/'goal.json').read_bytes())
    return Journal(root/'events.jsonl',goal['mission_id']).read()


def _control(root, reference=None):
    summary=mission.inspect(root); goal=mission.resolved_goal(root); rows=_rows(root)
    memory=Journal(root/'mnemonic'/'events.jsonl',mission.FUNCTION_MEMORY_ID).read()
    admissions=sum(row['kind']=='OBSERVATION_ADMITTED' for row in memory)
    effects=EffectLedger(root/'effects',create=False).snapshot()
    before=(root/'events.jsonl').read_bytes(); replay=mission.run(root)
    observations=[]
    for row in rows:
        if row['kind']!='F_OBSERVED': continue
        data=row['data']; result=data['result']
        if data['operation'].startswith('suite:'):
            # Unittest output includes wall time. Preserve its raw receipt in
            # evidence, but compare the verified semantic result across runs.
            result={'supported':result['supported'],
                'returncode':data['execution']['returncode'],'timed_out':data['execution']['timed_out']}
        observations.append({'operation':data['operation'],'result':result})
    workspace=mission._manifest(root/'workspace')
    original_unchanged=mission._manifest(root.parent/'source')==goal['baseline']
    decision_sequence=[r['kind'] for r in rows if r['kind'] not in ('F_DISPATCHED','F_RECOVERED')]
    result={'status':summary['status'], 'committed_candidate_sha256':goal['candidate']['id'],
        'changed_files':len(goal['candidate']['files']), 'committed_source_sha256':canonical_digest(workspace),
        'baseline_source_sha256':canonical_digest(goal['baseline']),
        'observation_results_sha256':canonical_digest(observations),
        'decision_sequence':decision_sequence, 'journal_head':summary['journal_head'],
        'dispatches':summary['dispatches'], 'public_executions_recorded':summary['public_executions_recorded'],
        'baseline_probes_recorded':summary['baseline_probes_recorded'],
        'witness_observations':summary['witness_observations'], 'final_observations':summary['final_observations'],
        'learning_admissions':admissions, 'external_effects_replay_safe':effects['replay_safe'],
        'terminal_replay_unchanged':before==(root/'events.jsonl').read_bytes() and replay['status']=='completed',
        'original_source_unchanged':original_unchanged}
    result['matches_reference']=reference is None or all(result[key]==reference[key] for key in (
        'committed_candidate_sha256','committed_source_sha256','baseline_source_sha256',
        'observation_results_sha256','decision_sequence','public_executions_recorded',
        'baseline_probes_recorded','witness_observations','final_observations','learning_admissions'))
    result['passed']=(summary['status']=='completed' and admissions==1 and effects['replay_safe']
        and result['terminal_replay_unchanged'] and result['matches_reference'] and original_unchanged
        and summary['witness_observations']==summary['final_observations']==1)
    return result


def _hard_death_once(root, base):
    scratch=root.parent/'supervisor-scratch'; scratch.mkdir(exist_ok=False)
    code=('from pathlib import Path; import sys,tempfile; tempfile.tempdir=sys.argv[2]; '
          'from nomad.platform_mission import run; run(Path(sys.argv[1]))')
    owner=subprocess.Popen([sys.executable,'-B','-c',code,str(root),str(scratch)],cwd=ROOT,
        env=minimal_env({'PYTHONPATH':str(ROOT)}),stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    observed=False; container=None
    try:
        deadline=time.monotonic()+120
        while owner.poll() is None and time.monotonic()<deadline:
            try: last=_rows(root)[-1]
            except MissionHold:
                time.sleep(0.05); continue
            if last['kind']=='F_DISPATCHED':
                container=last['data']['container_name']
                state=run_supervised([*_docker_prefix('docker',base),'container','inspect',
                    '--format','{{.State.Running}}',container],cwd=base,env=minimal_env(),
                    timeout_s=2,max_output_bytes=2048)
                if state.returncode==0 and state.output.strip()==b'true':
                    observed=True; break
            time.sleep(0.05)
    finally:
        if owner.poll() is None: owner.kill()
        owner.wait(timeout=5)
    if not observed:
        mission.recover(root)
        raise MissionHold('owner-death probe did not observe a live function container')
    try: mission.run(root)
    except MissionHold: held=True
    else: raise MissionHold('unknown function outcome replayed before cleanup')
    recovery=mission.recover(root)
    last=_rows(root)[-1]
    cleaned=(last['kind']=='F_RECOVERED' and last['data']['container_name']==container
             and last['data']['disposal_confirmed'] is True)
    if not cleaned: raise MissionHold('function owner-death disposal is unconfirmed')
    return {'observed_live_container_before_owner_death':True,
        'cleanup_confirmed_after_owner_death':True, 'held_before_cleanup':held,
        'container_name':container,'recovery_status':recovery['status'],'owner_exit_code':owner.returncode}


def _hard_death(root, base):
    try: return _hard_death_once(root,base)
    except BaseException as error:
        try: mission.recover(root)
        except BaseException as cleanup_error:
            raise MissionHold('function owner-death cleanup unconfirmed: '+str(cleanup_error)) from error
        raise


def qualify(image=None, isolation_receipt=None, evidence_root=None):
    host=qualification_host_identity()
    report={'schema':SCHEMA,'status':'HOLD','isolated_mission_recovery':'HOLD','backend':'docker',
        'adapter_scopes':[FUNCTION_ADAPTER],'created_utc':datetime.now(timezone.utc).isoformat(),
        'image':image,'docker_binary_present':sandbox_available(),
        'host_identity':host,'host_identity_sha256':canonical_digest(host),
        'source_sha256_before':source_identity(),'planned_cases':required_cases(),'cases':[],
        'reason':None,'cloud_model_calls':0,'repository_host_execution':False,
        'receipt_authority':'operator-owned observation; checksum is not a signature',
        'scope':'controlled one/two-file JSON function fixtures; interrupted/resumed equivalence and real worker disposal',
        'unimplemented_scope':['power-loss durability','service-restart durability',
            'remote irreversible-effect exactly-once behavior','aggregate mission compute budget']}
    if image is None or isolation_receipt is None:
        report['reason']='reviewed image and current native-isolation PASS required; no function mission initialized'
        return _seal(report)
    try:
        policy=SandboxPolicy(image=image,**POLICY); policy.validate()
        report['policy']=asdict(policy); report['policy_sha256']=canonical_digest(report['policy'])
        report['isolation_receipt_sha256']=_validate_isolation_receipt(Path(isolation_receipt),policy,host)
        report['preflight']=docker_preflight(policy)
        if not report['preflight']['ready']: raise MissionHold('current Docker preflight HOLD; no function mission initialized')
        if evidence_root is None: raise MissionHold('new persistent evidence_root required before native missions')
        evidence_root=Path(evidence_root).resolve()
        if evidence_root.exists(): raise MissionHold('evidence directory exists; refusing to overwrite history')
    except (OSError,ValueError,TypeError,KeyError,MissionHold) as error:
        report['reason']=str(error); return _seal(report)
    evidence_root.mkdir(parents=True,exist_ok=False); base=evidence_root
    report['evidence_root']=str(base); roots=[]
    sentinel=base/'protected-host-sentinel'; sentinel.write_bytes(b'host-only controlled function recovery sentinel')
    def fixture(name,**kwargs):
        root=_fixture(base/name,policy,**kwargs); roots.append(root); return root
    def control_case(name,root,reference=None,**details):
        control=_control(root,reference)
        report['cases'].append({'case':name,'status':'PASS' if control['passed'] else 'FAIL',
                                'result':control,**details})
        if not control['passed']: raise MissionHold('function reference equivalence failed: '+name)
        return control
    try:
        root=fixture('reference'); mission.run(root)
        reference=control_case('reference_and_terminal_replay',root)
        for checkpoint in CHECKPOINTS:
            root=fixture(checkpoint)
            try: mission.run(root,interrupt_at=checkpoint)
            except InjectedInterruption: pass
            else: raise MissionHold('function interruption not reached: '+checkpoint)
            if checkpoint=='after_dispatch': mission.recover(root)
            mission.run(root); control_case(checkpoint,root,reference)
        root=fixture('owner-hard-death'); death=_hard_death(root,base)
        mission.run(root); control_case('owner_hard_death_with_live_container',root,reference,death=death)
        two_reference_root=fixture('two-file-reference',two=True); mission.run(two_reference_root)
        two_reference=_control(two_reference_root)
        if not two_reference['passed'] or two_reference['changed_files']!=2:
            raise MissionHold('two-file reference did not establish a composed repair')
        root=fixture('two-file-partial',two=True)
        try: mission.run(root,interrupt_at='after_multifile_patch_write')
        except InjectedInterruption: pass
        else: raise MissionHold('actual multi-file partial patch interruption not reached')
        pending=_rows(root)[-1]; current=mission._manifest(root/'workspace')
        if pending['kind']!='F_PATCH': raise MissionHold('partial multi-file intent missing')
        before=pending['data']['before']; after=pending['data']['after']
        changed=[name for name in before if before[name]!=after[name]]
        partial=(len(changed)==2 and any(current[name]==before[name] for name in changed)
                 and any(current[name]==after[name] for name in changed))
        if not partial: raise MissionHold('interruption did not leave a true mixed two-file snapshot')
        mission.run(root); control_case('two_file_partial_patch_recovery',root,two_reference,
            actual_mixed_two_file_snapshot_observed=True,reference_control=two_reference)
        root=fixture('negative-final',negative_final=True); result=mission.run(root)
        restored=mission._manifest(root/'workspace')==mission.resolved_goal(root)['baseline']
        passed=result['status']=='rejected' and restored and not (root/'mnemonic').exists()
        report['cases'].append({'case':'final_rejection_restores_source','status':'PASS' if passed else 'FAIL',
            'restored_original':restored,'no_learning_admitted':not (root/'mnemonic').exists(),'result':result})
        for number,name in enumerate(TAMPER_PATHS):
            root=fixture('tamper-'+str(number)); path=root/name
            path.chmod(0o600); path.write_bytes(path.read_bytes()+b'corruption')
            try: mission.run(root)
            except MissionHold: refused=True
            else: refused=False
            dispatched=b'F_DISPATCHED' in (root/'events.jsonl').read_bytes()
            report['cases'].append({'case':'tampered-'+name,'status':'PASS' if refused and not dispatched else 'FAIL',
                                  'refused':refused,'dispatched':dispatched})
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,subprocess.TimeoutExpired) as error:
        report['cases'].append({'case':'qualification_execution','status':'HOLD','reason':str(error)})
    finally:
        for root in roots:
            try:
                if _rows(root)[-1]['kind']=='F_DISPATCHED': mission.recover(root)
            except (OSError,ValueError,KeyError,TypeError,MissionHold) as error:
                # Deliberately damaged journals are never dispatched. For other
                # roots preserve unconfirmed cleanup explicitly as HOLD.
                if root.parent.name.startswith('tamper-'): continue
                report['cases'].append({'case':'pending_cleanup','status':'HOLD','reason':str(error)})
    try: report['protected_host_sentinel_unchanged']=sentinel.read_bytes()==b'host-only controlled function recovery sentinel'
    except OSError: report['protected_host_sentinel_unchanged']=False
    try:
        report['original_source_unchanged']=all(mission._manifest(root.parent/'source')==
            json.loads((root/'goal.json').read_bytes())['baseline'] for root in roots)
    except (OSError,ValueError,KeyError,TypeError,MissionHold):
        report['original_source_unchanged']=False
    report['evidence_files_sha256']={}
    try:
        for path in sorted(base.rglob('*')):
            if path.is_file(): report['evidence_files_sha256'][path.relative_to(base).as_posix()]=digest(path.read_bytes())
        report['evidence_inventory_complete']=True
    except (OSError,ValueError):
        report['evidence_inventory_complete']=False
        report['cases'].append({'case':'evidence_inventory','status':'HOLD',
                                'reason':'retained evidence could not be read completely'})
    cases=report['cases']; exact=len(cases)==len(required_cases()) and {r['case'] for r in cases}==set(required_cases())
    failed=any(r['status']=='FAIL' for r in cases) or not report['protected_host_sentinel_unchanged'] or not report['original_source_unchanged']
    report['status']='FAIL' if failed else 'PASS' if exact and all(r['status']=='PASS' for r in cases) else 'HOLD'
    return _seal(report)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image'); parser.add_argument('--isolation-receipt',type=Path)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--evidence-root',type=Path)
    args=parser.parse_args(argv)
    if args.output.exists(): parser.error('output exists; select a new path to preserve evidence')
    evidence_root=args.evidence_root or args.output.with_name(args.output.stem+'.evidence')
    result=qualify(args.image,args.isolation_receipt,evidence_root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(result,handle,indent=2,sort_keys=True); handle.write('\n')
    print(json.dumps({'status':result['status'],'cases_executed':len(result['cases']),
                      'reason':result['reason'],'receipt_sha256':result['receipt_sha256']},sort_keys=True))
    return 0 if result['status']=='PASS' else 3


if __name__=='__main__': raise SystemExit(main())
