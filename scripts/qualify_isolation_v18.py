"""Bounded native Docker probes. Missing prerequisites produce a durable HOLD.

Run only with an independently reviewed, pre-pulled digest-pinned Linux Python
image. These controlled fixtures are the only repository code executed here.
No image is fetched, Docker installed, or host security setting changed.
"""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nomad.isolation import (IsolationUnavailable, SandboxPolicy, _docker_prefix,
                             cleanup_isolated, docker_preflight, run_isolated,
                             sandbox_available)
from nomad.supervised import minimal_env, run_supervised

CONTROLLED_CASES = ('nonroot', 'protected_host', 'environment', 'readonly', 'network',
                   'namespaces', 'resource_config', 'pid_exhaustion', 'cpu_budget',
                   'memory_exhaustion', 'output_budget', 'timeout')


def canonical_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode('utf-8')).hexdigest()


def qualification_source_identity() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    names = ('nomad/isolation.py', 'nomad/supervised.py', 'nomad/windows_job.py',
             'scripts/qualify_isolation_v18.py')
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def qualification_host_identity() -> dict[str, str]:
    return {'system': platform.system(), 'release': platform.release(),
            'version': platform.version(), 'machine': platform.machine(),
            'hostname_sha256': hashlib.sha256(platform.node().encode('utf-8')).hexdigest()}


def _seal_report(report: dict) -> dict:
    report['source_sha256_after'] = qualification_source_identity()
    report['source_stable'] = report['source_sha256_before'] == report['source_sha256_after']
    report['policy_sha256'] = canonical_digest(report['policy']) if 'policy' in report else None
    if not report['source_stable'] and report['status'] == 'PASS':
        report['status'] = report['native_containment_gate'] = 'HOLD'
        report['reason'] = 'Qualification source changed during execution'
    report['receipt_sha256'] = canonical_digest(report)
    return report


PROBE = r'''import json,os,pathlib,socket,subprocess,sys,time
case=sys.argv[1]
if case=='nonroot':
    assert os.getuid()!=0 and os.getgid()!=0
elif case=='protected_host':
    for path in json.loads(sys.argv[2]):
        try:
            pathlib.Path(path).read_bytes()
        except OSError:
            continue
        raise AssertionError('host sentinel became readable')
    assert not pathlib.Path('/var/run/docker.sock').exists()
elif case=='environment':
    assert 'NOMAD_QUALIFICATION_SENTINEL' not in os.environ
elif case=='readonly':
    try:
        pathlib.Path('/work/unauthorized-write').write_text('bad')
    except OSError:
        pass
    else:
        raise AssertionError('source mount writable')
    try:
        pathlib.Path('/unauthorized-root-write').write_text('bad')
    except OSError:
        pass
    else:
        raise AssertionError('root filesystem writable')
elif case=='network':
    assert {p.name for p in pathlib.Path('/sys/class/net').iterdir()}=={'lo'}
    with socket.socket() as connection:
        connection.settimeout(1)
        assert connection.connect_ex(('1.1.1.1',53))!=0
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as dns:
        dns.settimeout(1)
        try:
            dns.connect(('1.1.1.1',53))
            dns.send(b'\x00'*12)
        except OSError:
            pass
        else:
            raise AssertionError('outbound DNS datagram was accepted')
    try:
        ipv6=socket.socket(socket.AF_INET6)
    except OSError:
        ipv6=None
    if ipv6 is not None:
        with ipv6:
            ipv6.settimeout(1)
            assert ipv6.connect_ex(('2606:4700:4700::1111',53,0,0))!=0
    routes=pathlib.Path('/proc/net/route').read_text().splitlines()[1:]
    assert all(line.split()[1]!='00000000' for line in routes)
elif case=='namespaces':
    # The controlled entrypoint is PID 1 in its private process namespace.
    assert os.getpid()==1
    assert pathlib.Path('/proc/1/comm').read_text().strip().startswith('python')
    assert not pathlib.Path('/var/run/docker.sock').exists()
    try:
        handle=open('/proc/sysrq-trigger','wb')
    except OSError:
        pass
    else:
        handle.close()
        raise AssertionError('kernel control file writable')
elif case=='resource_config':
    root=pathlib.Path('/sys/fs/cgroup')
    assert int((root/'memory.max').read_text())==128*1024*1024
    assert int((root/'pids.max').read_text())==16
    quota,period=(root/'cpu.max').read_text().split()
    assert quota!='max' and int(quota)/int(period)<=0.5
elif case=='pid_exhaustion':
    children=[]
    denied=False
    try:
        for _ in range(24):
            try:
                children.append(subprocess.Popen([sys.executable,'-c','import time;time.sleep(15)']))
            except OSError:
                denied=True
                break
        assert denied and len(children)<16
    finally:
        for child in children: child.kill()
        for child in children: child.wait()
elif case=='cpu_budget':
    wall=time.monotonic(); cpu=time.process_time()
    while time.monotonic()-wall<3:
        sum(range(10000))
    assert (time.process_time()-cpu)/(time.monotonic()-wall)<0.75
elif case=='memory_exhaustion':
    def oom_kills():
        return int(dict(line.split() for line in pathlib.Path('/sys/fs/cgroup/memory.events').read_text().splitlines())['oom_kill'])
    before=oom_kills()
    child=subprocess.run([sys.executable,'-c','blocks=[bytearray(1024*1024) for _ in range(256)]'],check=False)
    assert child.returncode==-9 and oom_kills()>before
elif case=='output_budget':
    print('x'*500000)
elif case=='timeout':
    time.sleep(60)
else:
    raise AssertionError('unknown controlled probe')
print('controlled probe completed: '+case)
'''


def _crash_cleanup_probe(source: Path, policy: SandboxPolicy, base: Path) -> dict:
    name = 'nomad-' + uuid.uuid4().hex[:24]
    repo_root = Path(__file__).resolve().parents[1]
    child_code = '''import pathlib,sys,tempfile
from nomad.isolation import SandboxPolicy,run_isolated
tempfile.tempdir=sys.argv[4]
run_isolated(pathlib.Path(sys.argv[1]),command=['python','probe.py','timeout'],policy=SandboxPolicy(image=sys.argv[2],timeout_s=30,memory_mib=128,cpus=.5,pids_limit=16),container_name=sys.argv[3])
'''
    child = subprocess.Popen([sys.executable, '-c', child_code, str(source), policy.image,
                              name, str(base)], cwd=repo_root,
                             env=minimal_env({'PYTHONPATH': str(repo_root)}),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    observed_running = False
    try:
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and child.poll() is None:
                check = run_supervised([*_docker_prefix('docker', base), 'container', 'inspect',
                                        '--format', '{{.State.Running}}', name],
                                       cwd=base, timeout_s=3, max_output_bytes=4096)
                if check.returncode == 0 and check.output.strip() == b'true':
                    observed_running = True
                    break
                time.sleep(0.1)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
    finally:
        # A metadata/owner-wait exception must not strand the daemon-owned
        # container after its supervisor dies. This cleans only our UUID name
        # and requires the isolation layer's ownership-label validation.
        cleanup = cleanup_isolated(name)
    return {'case': 'supervisor_hard_death_cleanup',
            'status': 'PASS' if observed_running and cleanup else 'HOLD',
            'observed_live_container_before_owner_death': observed_running,
            'cleanup_confirmed_after_owner_death': cleanup,
            'container_name': name}


def qualify(image: str | None) -> dict:
    report = {'schema': 'nomad.native-isolation-qualification.v18',
              'backend': 'docker',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'HOLD', 'native_containment_gate': 'HOLD',
              'scope': 'controlled Linux Docker probes on this host; not a general escape-proof claim',
              'docker_binary_present': sandbox_available(), 'image': image,
              'cases': [], 'planned_cases': list(CONTROLLED_CASES) + ['supervisor_hard_death_cleanup'],
              'reason': None, 'cloud_model_calls': 0,
              'source_sha256_before': qualification_source_identity(),
              'host_identity': qualification_host_identity(),
              'receipt_authority': 'operator-owned observation; checksum is not a signature'}
    report['host_identity_sha256'] = canonical_digest(report['host_identity'])
    if image is None:
        report['reason_codes'] = ['REVIEWED_IMAGE_UNCONFIGURED']
        if not report['docker_binary_present']:
            report['reason_codes'].insert(0, 'DOCKER_BINARY_UNAVAILABLE')
        report['reason'] = '; '.join(report['reason_codes']) + '; no source execution'
        return _seal_report(report)
    policy = SandboxPolicy(image=image, timeout_s=10, memory_mib=128, cpus=0.5, pids_limit=16)
    policy.validate()
    report['policy'] = asdict(policy)
    report['preflight'] = docker_preflight(policy)
    if not report['preflight']['ready']:
        report['reason'] = '; '.join(report['preflight']['reasons'])
        return _seal_report(report)
    with tempfile.TemporaryDirectory(prefix='nomad-native-qualification-') as td:
        base = Path(td)
        source = base / 'controlled-source'
        source.mkdir()
        (source / 'probe.py').write_text(PROBE, encoding='utf-8', newline='\n')
        sentinel = base / 'protected-host-sentinel'
        sentinel.write_text('NOMAD synthetic host-only sentinel', encoding='utf-8')
        sentinel_paths = [str(sentinel)]
        if os.name == 'nt':
            drive = sentinel.drive[0].lower()
            suffix = sentinel.as_posix()[3:]
            sentinel_paths.extend(prefix + '/' + drive + '/' + suffix
                                  for prefix in ('/host_mnt', '/mnt', '/run/desktop/mnt/host'))
        original_env = os.environ.get('NOMAD_QUALIFICATION_SENTINEL')
        os.environ['NOMAD_QUALIFICATION_SENTINEL'] = 'synthetic-not-a-real-secret'
        try:
            for case in CONTROLLED_CASES:
                started = time.monotonic()
                command = ['python', 'probe.py', case]
                if case == 'protected_host':
                    command.append(json.dumps(sentinel_paths))
                try:
                    receipt = run_isolated(source, command=command, policy=policy)
                    passed = receipt['tests_passed']
                    if case == 'timeout':
                        passed = receipt['timed_out'] and receipt['returncode'] == 124
                    elif case == 'output_budget':
                        passed = passed and receipt['output_truncated']
                    report['cases'].append({'case': case, 'status': 'PASS' if passed else 'FAIL',
                                            'elapsed_s': time.monotonic()-started, 'receipt': receipt})
                except (OSError, IsolationUnavailable, ValueError) as error:
                    report['cases'].append({'case': case, 'status': 'HOLD', 'reason': str(error)})
                    break
            try:
                report['cases'].append(_crash_cleanup_probe(source, policy, base))
            except (OSError, IsolationUnavailable, subprocess.TimeoutExpired) as error:
                report['cases'].append({'case': 'supervisor_hard_death_cleanup', 'status': 'HOLD', 'reason': str(error)})
        finally:
            if original_env is None:
                os.environ.pop('NOMAD_QUALIFICATION_SENTINEL', None)
            else:
                os.environ['NOMAD_QUALIFICATION_SENTINEL'] = original_env
        try:
            report['protected_host_sentinel_unchanged'] = sentinel.read_text() == 'NOMAD synthetic host-only sentinel'
        except OSError:
            # Loss of the protected sentinel is an observed boundary failure,
            # not a reason to omit the qualification receipt.
            report['protected_host_sentinel_unchanged'] = False
    statuses = [case['status'] for case in report['cases']]
    report['status'] = ('FAIL' if 'FAIL' in statuses or not report['protected_host_sentinel_unchanged'] else 'PASS'
                        if len(statuses) == 13 and all(x == 'PASS' for x in statuses) else 'HOLD')
    report['native_containment_gate'] = report['status']
    return _seal_report(report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', help='Reviewed pre-pulled image with @sha256 digest')
    parser.add_argument('--output', type=Path, help='New receipt path; never overwrites existing evidence')
    args = parser.parse_args(argv)
    if args.output is not None and args.output.exists():
        parser.error('output already exists; preserve prior evidence and select a new receipt path')
    report = qualify(args.image)
    rendered = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(rendered)
    print(rendered)
    return 0 if report['status'] == 'PASS' else 3


if __name__ == '__main__':
    raise SystemExit(main())
