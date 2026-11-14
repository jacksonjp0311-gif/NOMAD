"""Repeatable native host qualification with exact PASS/HOLD/FAIL separation.

Writes new reports only. Runs reviewed NOMAD tests and generated native fixtures
on host. Unfamiliar repository execution belongs to isolation only.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import time
import unittest
import hashlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nomad.platform import doctor, runtime_smoke


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('nomad', 'tests', 'scripts') for p in sorted((ROOT / folder).glob('*.py'))}


class TimedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timings = []

    def startTest(self, test):
        self.started_test = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        self.timings.append({'test': str(test), 'wall_s': time.perf_counter() - self.started_test})
        super().stopTest(test)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('refusing to overwrite qualification evidence')
    started = time.perf_counter()
    cpu = time.process_time()
    before = source_hashes()
    buffer = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(stream=buffer, verbosity=2, resultclass=TimedResult).run(suite)
    test_wall = time.perf_counter() - started
    test_cpu = time.process_time() - cpu
    record = {
        'schema': 'nomad.platform.study.v1', 'version': '0.18.0',
        'observed_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256_by_path': before,
        'source_unchanged_during_tests': before == source_hashes(),
        'tests': {'run': result.testsRun, 'failures': len(result.failures),
                  'errors': len(result.errors), 'skipped': len(result.skipped),
                  'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
                  'skip_reasons': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
                  'status': 'PASS' if result.wasSuccessful() else 'FAIL',
                  'wall_s': test_wall, 'controller_cpu_s': test_cpu,
                  'slowest_tests': sorted(result.timings, key=lambda row: row['wall_s'], reverse=True)[:10]},
        'doctor': doctor(), 'native_runtimes': runtime_smoke(),
        'native_containment': 'HOLD',
        'cpu_scope': 'controller process only; excludes child process CPU',
        'api_calls': 0, 'api_cost_usd': 0,
        'electricity_cost_usd': None, 'energy_joules': None,
        'cost_note': 'No cloud model used. Hardware power and local electricity cost were not measured.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write('\n')
    with args.output.with_suffix('.log').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(buffer.getvalue())
    print(json.dumps(record['tests'], indent=2))
    return 0 if result.wasSuccessful() and record['source_unchanged_during_tests'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
