# Public runners, v0.18.0

On 2026-11-19, repository visibility changed to public with explicit user
authorization. Anonymous repository and data access were verified. GitHub
Actions was already enabled; no billing settings or paid runner configuration
changed.

The existing `continuous-awake` and `continuous-sleep` workflows on `main` both
completed and pushed their data commits:

- [Awake run 44473852058](https://github.com/jacksonjp0311-gif/NOMAD/actions/runs/44473852058):
  data commit `fe663eb41829172fdd44cec83e020b5828dd83ac`.
- [Sleep run 44473905429](https://github.com/jacksonjp0311-gif/NOMAD/actions/runs/44473905429):
  data commit `18780cc35b3dc57fc925ecc99d5af4ba02454f7c`.

Their existing schedules remain active: awake at minute 0, sleep at minute 30
of each hour. They currently execute `nomad.cycle`, the minimal observation
cycle. These runs demonstrate hosted execution and persistence, not independently
verified repairs or learning. No development changes were merged into `main`.

## Development CI corrections

The first unblocked [development CI run](https://github.com/jacksonjp0311-gif/NOMAD/actions/runs/44473859945)
passed source integrity, then Ubuntu/Python 3.11 reported 485 tests: 468 passed,
2 failures, 2 errors and 13 skips. Matrix fail-fast cancelled other work.

- Trusted process recovery tests requested Windows Job Object limits on POSIX.
  They now request those limits only on Windows. Both recovery assertions still
  execute on POSIX, using the existing process-group supervisor. No containment
  boundary or production budget was weakened.
- Both Rust failures took approximately seven seconds, matching the existing
  native timeout. CI now initializes and reports its installed Rust compiler
  before testing, outside the per-candidate execution budget. Rust assertions
  include the native error reason. The seven-second runtime limit is unchanged.
- Matrix fail-fast is disabled so all operating-system/Python combinations can
  report their own results.

Focused Windows verification: 18 passed, 0 failed, 0 skipped:

```powershell
python -B -m unittest tests.test_persistent_process_v18 tests.test_transcend_v13 tests.test_temporal_packaging_v18 -v
```

The complete matrix remains Ubuntu and Windows, Python 3.11 and 3.12. Final
remote conclusions and logs are available under
[development CI](https://github.com/jacksonjp0311-gif/NOMAD/actions/workflows/ci.yml?query=branch%3Av0.18-platform).
Public visibility does not change qualification: Gates A/B/C/D remain HOLD.
The previous operations seal and all frozen scientific results remain intact.
This internal snapshot uses `RELEASE_MANIFEST_RUNNERS_V018.json`; version remains
0.18.0. No scientific benchmark replay is required for these test/CI changes.
